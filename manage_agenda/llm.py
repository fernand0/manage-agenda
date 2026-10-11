import configparser
import logging
import os
import shutil
import subprocess
import time
import types
from pathlib import Path

try:
    from google import genai
except Exception:
    genai = types.SimpleNamespace(
        configure=lambda *args, **kwargs: None,
        GenerativeModel=lambda *args, **kwargs: None,
        Client=lambda *args, **kwargs: None,
        list_models=lambda: [],
    )
try:
    import ollama
except Exception:
    ollama = types.SimpleNamespace(list=lambda: {"models": []})

try:
    from ollama import ChatResponse, chat
except Exception:
    ChatResponse = object

    def chat(*args, **kwargs):
        return None

try:
    from mistralai.client import Mistral
except Exception:
    class Mistral:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("mistralai is not installed")

from socialModules.configMod import CONFIGDIR, select_from_list


def get_image_ocr_prompt():
    """Returns the prompt template for extracting text from images."""
    prompt_file = Path(__file__).parent / "prompts" / "image_ocr_prompt.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()
    return (
        "Extract all the text contained in this image faithfully and completely. "
        "Return only the extracted text verbatim, without any explanations, summaries, "
        "translations, or added commentary. Be careful with spaces, when characters "
        "have enough space between them."
    )


# This shouln't go here?
def load_config(config_file):
    """Loads configuration from a file.

    Args:
        config_file (str): Path to the configuration file.

    Returns:
        configparser.ConfigParser: The configuration object.
    """
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)
    else:
        logging.error("Configuration file not found: %s", config_file)
        raise FileNotFoundError(f"Config file not found: {config_file}")
    return config


# --- API Abstraction ---
class LLMClient:
    """Abstracts interactions with LLMs (Ollama, Gemini, Mistral)."""

    def __init__(self, name_class=None):
        if hasattr(self, "config") and self.config:
            try:
                config_file = f"{CONFIGDIR}/.rss{name_class[:-6]}"
                config = load_config(config_file)
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Configuration file: {config_file} does not exist\n"
                    f"You need to create it and add the API key"
                ) from None
            except Exception as e:
                raise Exception(e) from e

            section = config.sections()[0]
            self.api_key = config.get(section, "api_key")
        self.model_name = None

    def generate_text(self, prompt):
        raise NotImplementedError("Subclasses must implement this method")

    def generate_text_from_image(self, image_path, prompt=None):
        raise NotImplementedError("Subclasses must implement this method")

    def get_name(self):
        raise NotImplementedError("Subclasses must implement this method")


class OllamaClient(LLMClient):
    @classmethod
    def is_server_running(cls):
        """Checks if the Ollama server is running and accessible."""
        try:
            ollama.list()
            return True
        except Exception:
            return False

    @classmethod
    def start_server(cls, timeout=10):
        """Starts the Ollama server if it is not already running.

        Args:
            timeout (int): Maximum seconds to wait for server to start.

        Returns:
            bool: True if server is running or successfully started, False otherwise.
        """
        if cls.is_server_running():
            return True

        if not shutil.which("ollama"):
            logging.error("Ollama executable not found in PATH.")
            return False

        logging.info("Ollama server is not running. Starting 'ollama serve'...")
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logging.error("Failed to start Ollama server: %s", e)
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(0.5)
            if cls.is_server_running():
                logging.info("Ollama server started successfully.")
                return True

        logging.error("Timed out waiting for Ollama server to start.")
        return False

    ensure_server = start_server

    def __init__(self, model_name="", multimodal=False):
        name_class = self.__class__.__name__
        self.config = False
        super().__init__(name_class)

        self.ensure_server()

        if isinstance(model_name, str) and model_name:
            self.model_name = model_name
        else:
            models = []
            try:
                models = self.list_models(multimodal=multimodal)
            except Exception as e:
                logging.error("Could not retrieve Ollama models: %s", e)

            if multimodal and not models:
                print("No multi-modal models found in Ollama.")
                print("Consider pulling a vision model (e.g. 'ollama pull llama3.2-vision' or 'ollama pull llava').")

            if isinstance(model_name, int):
                if models and len(models) > model_name:
                    item = models[model_name]
                    self.model_name = getattr(item, "model", None) or (
                        item.get("model") if isinstance(item, dict) else str(item)
                    )
                else:
                    self.model_name = ""
            elif models:
                title = "Available multi-modal models" if multimodal else "Available models"
                _, self.model_name = select_from_list(
                    models, identifier="model", title=title
                )
            else:
                self.model_name = ""

    def generate_text(self, prompt):
        def _chat():
            return chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"num_ctx": len(prompt)},
                keep_alive=0,
            )

        try:
            response: ChatResponse = _chat()
            # To unload a model from memory in Ollama, you must use the
            # keep_alive parameter with a value of 0 via the API.
            # curl http://localhost:11434/api/generate -d '{"model": "llama3.2", "keep_alive": 0}'
            return response.message.content if response else None
        except Exception as e:
            is_conn_error = (
                isinstance(e, ConnectionError)
                or "Failed to connect to Ollama" in str(e)
                or "connection refused" in str(e).lower()
            )
            if is_conn_error:
                logging.info("Ollama is not running. Attempting to start Ollama server...")
                if self.start_server():
                    try:
                        response: ChatResponse = _chat()
                        return response.message.content if response else None
                    except Exception as retry_err:
                        e = retry_err

            logging.error("Error generating text with Ollama: %s", e)
            if "model requires more system memory" in str(e) or "out of memory" in str(e).lower():
                logging.error("Ollama model %s requires more memory than available: %s", self.model_name, e)
                return "Memory"
            return None

    @classmethod
    def is_multimodal_model(cls, model_info):
        """Checks whether an Ollama model supports multimodal/vision input."""
        if isinstance(model_info, str):
            model_name = model_info
            details = None
        elif isinstance(model_info, dict):
            model_name = model_info.get("model") or model_info.get("name") or ""
            details = model_info.get("details", {})
        else:
            model_name = getattr(model_info, "model", None) or getattr(model_info, "name", None) or ""
            details = getattr(model_info, "details", None)

        name_lower = str(model_name).lower()

        if details:
            families = (
                details.get("families", [])
                if isinstance(details, dict)
                else getattr(details, "families", [])
            ) or []
            family = (
                details.get("family", "")
                if isinstance(details, dict)
                else getattr(details, "family", "")
            ) or ""
            all_families = [str(f).lower() for f in families] + [str(family).lower()]
            vision_families = {"clip", "mllama"}
            if any(f in vision_families for f in all_families):
                return True

        vision_indicators = (
            "vision",
            "llava",
            "minicpm-v",
            "moondream",
            "bakllava",
            "cogvlm",
            "pixtral",
            "qwen-vl",
            "qwen2-vl",
            "qwen2.5-vl",
            "-vl",
            "_vl",
        )
        return any(ind in name_lower for ind in vision_indicators)

    @classmethod
    def list_models(cls, multimodal=False):
        try:
            models = ollama.list()["models"]
        except Exception:
            if cls.start_server():
                models = ollama.list()["models"]
            else:
                raise
        if multimodal:
            models = [m for m in models if cls.is_multimodal_model(m)]
        return models

    def generate_text_from_image(self, image_path, prompt=None):
        prompt = prompt or get_image_ocr_prompt()
        image_path = str(image_path)

        def _chat():
            return chat(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_path],
                    }
                ],
                keep_alive=0,
            )

        try:
            response: ChatResponse = _chat()
            return response.message.content if response else None
        except Exception as e:
            is_conn_error = (
                isinstance(e, ConnectionError)
                or "Failed to connect to Ollama" in str(e)
                or "connection refused" in str(e).lower()
            )
            if is_conn_error:
                logging.info("Ollama is not running. Attempting to start Ollama server...")
                if self.start_server():
                    try:
                        response: ChatResponse = _chat()
                        return response.message.content if response else None
                    except Exception as retry_err:
                        e = retry_err

            logging.error("Error generating text from image with Ollama: %s", e)
            return None


class GeminiClient(LLMClient):
    @classmethod
    def is_multimodal_model(cls, model_info):
        """Checks whether a Gemini model supports multimodal input."""
        name = getattr(model_info, "name", "") if not isinstance(model_info, str) else model_info
        name_lower = str(name).lower()
        if any(x in name_lower for x in ("embedding", "aqa", "imagen")):
            return False
        return "gemini" in name_lower

    def __init__(self, model_name="", multimodal=False):
        name_class = self.__class__.__name__
        self.config = True

        super().__init__(name_class)

        self.client = genai.Client(api_key=self.api_key)
        if not model_name:
            models = self.list_models(multimodal=multimodal)
            title = "Available multi-modal models" if multimodal else None
            extra_args = {"title": title} if title else {}
            sel, name = select_from_list(
                models,
                identifier="name",
                selector="gemini",
                default="models/gemini-2.0-flash",
                **extra_args,
            )
            logging.debug("Selected model: %s", name)
            self.model_name = name.split("/")[1]
        else:
            self.model_name = model_name

    def generate_text(self, prompt):
        try:
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt
            )
            return response.text
        except Exception as e:
            logging.error("Error generating text with Gemini: %s", e)
            return None

    def generate_text_from_image(self, image_path, prompt=None):
        prompt = prompt or get_image_ocr_prompt()
        try:
            import mimetypes
            from google.genai import types

            mime_type, _ = mimetypes.guess_type(str(image_path))
            if not mime_type:
                mime_type = "image/jpeg"

            with open(image_path, "rb") as f:
                image_bytes = f.read()

            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[image_part, prompt],
            )
            return response.text
        except Exception as e:
            logging.error("Error generating text from image with Gemini: %s", e)
            return None

    def list_models(self, multimodal=False):
        models = list(self.client.models.list())
        if multimodal:
            models = [m for m in models if self.is_multimodal_model(m)]
        return models


class MistralClient(LLMClient):
    @classmethod
    def is_multimodal_model(cls, model_info):
        """Checks whether a Mistral model supports multimodal input."""
        model_id = (
            getattr(model_info, "id", "")
            if not isinstance(model_info, (str, dict))
            else (model_info.get("id", "") if isinstance(model_info, dict) else model_info)
        ).lower()
        caps = (
            getattr(model_info, "capabilities", None)
            if not isinstance(model_info, dict)
            else model_info.get("capabilities")
        )
        if caps:
            has_vision = (
                getattr(caps, "vision", False)
                if not isinstance(caps, dict)
                else caps.get("vision", False)
            )
            if has_vision:
                return True
        return "pixtral" in model_id or "vision" in model_id

    def __init__(self, model_name="", multimodal=False):
        name_class = self.__class__.__name__
        self.config = True

        super().__init__(name_class)

        self.client = Mistral(api_key=self.api_key)
        if not self.model_name:
            models = self.list_models(self, multimodal=multimodal).data
            default_model = "pixtral-12b-2409" if multimodal else "mistral-small-latest"
            title = "Available multi-modal models" if multimodal else None
            extra_args = {"title": title} if title else {}
            sel, name = select_from_list(
                models, identifier="id", default=default_model, **extra_args
            )
            self.model_name = name
        else:
            self.model_name = model_name

    def generate_text(self, prompt):
        try:
            response = self.client.chat.complete(
                model=self.model_name, messages=[{"content": prompt, "role": "user"}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error("Error generating text with Mistral: %s", e)
            return None

    def generate_text_from_image(self, image_path, prompt=None):
        prompt = prompt or get_image_ocr_prompt()
        try:
            import base64
            import mimetypes

            mime_type, _ = mimetypes.guess_type(str(image_path))
            if not mime_type:
                mime_type = "image/jpeg"

            with open(image_path, "rb") as f:
                b64_image = base64.b64encode(f.read()).decode("utf-8")

            response = self.client.chat.complete(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": f"data:{mime_type};base64,{b64_image}",
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error("Error generating text from image with Mistral: %s", e)
            return None

    @staticmethod
    def list_models(self, multimodal=False):
        res = self.client.models.list()
        if multimodal and hasattr(res, "data"):
            res.data = [m for m in res.data if MistralClient.is_multimodal_model(m)]
        return res


def select_llm(args, multimodal=False):
    """Selects and initializes the appropriate LLM client."""
    if args.interactive:
        llm_options = ["ollama", "gemini", "mistral"]
        title = "Select multi-modal model provider" if multimodal else "Select model provider"
        sel, ai = select_from_list(llm_options, title=title, default="ollama")
    else:
        ai = getattr(args, "ai", None) or "gemini"
    print(f"Selected AI: {ai}")

    if ai == "ollama":
        if args.interactive:
            model = None
            while not model:
                model = OllamaClient(multimodal=multimodal)
        else:
            default_model = "llama3.2-vision:latest" if multimodal else "granite4:latest"
            model = OllamaClient(default_model, multimodal=multimodal)
        return model
    elif ai == "gemini":
        if args.interactive:
            model = GeminiClient(multimodal=multimodal)
        else:
            model = GeminiClient("gemini-2.5-flash")
        return model
    elif ai == "mistral":
        if args.interactive:
            model = MistralClient(multimodal=multimodal)
        else:
            default_model = "pixtral-12b-2409" if multimodal else "mistral-small-latest"
            model = MistralClient(default_model, multimodal=multimodal)
        return model
    else:
        logging.error("Invalid LLM source: %s", ai)
        return None

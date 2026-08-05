import configparser
import logging
import os
import types

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
    chat = lambda *args, **kwargs: None

try:
    from mistralai.client import Mistral
except Exception:
    class Mistral:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("mistralai is not installed")

from socialModules.configMod import CONFIGDIR, select_from_list


def evaluate_models(args, prompt=None, eval_type=None):
    """
    Evaluates multiple Ollama models and prints their responses and timings.
    """
    from manage_agenda.config import config

    results = []
    models = OllamaClient.list_models()
    if not models:
        print("No models available")
    for model_info in models:
        model_name = model_info["model"]
        print(f"Evaluating model: {model_name}")
        client = OllamaClient(model_name=model_name)

        if eval_type == "email":
            from .utils import process_email_cli
            print(f"Cli (email): {process_email_cli(args, client)}")
        elif eval_type == "web":
            from .utils import process_web_cli
            print(f"Cli (web): {process_web_cli(args, client)}")
        elif eval_type == "txt":
            from .utils import process_txt_cli
            print(f"Cli (txt): {process_txt_cli(args, client, source_name=config.MSG_TXT_DIR)}")
        else:
            if prompt:
                import time
                print(f"Prompt: {prompt}")
                start_time = time.time()
                response = client.generate_text(prompt)
                end_time = time.time()

                duration = end_time - start_time
                results.append({"model": model_name, "response": response, "duration": duration})

    if results:
        print("\n--- Evaluation Results ---")
        for result in results:
            print(f"Model: {result['model']}")
            print(f"Time taken: {result['duration']:.2f} seconds")
            print(f"Response: {result['response']}")
            print("--------------------")


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
        logging.error(f"Configuration file not found: {config_file}")
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

    def get_name(self):
        raise NotImplementedError("Subclasses must implement this method")


class OllamaClient(LLMClient):
    def __init__(self, model_name=""):
        name_class = self.__class__.__name__
        self.config = False
        super().__init__(name_class)

        iss = isinstance(model_name,int)
        if not iss and not model_name:
            models = self.list_models()
            _, self.model_name = select_from_list(models, identifier="model", title="Available models")
        else:
            if isinstance(model_name,int):
                self.model_name = self.list_models()[0].model
            else:
                self.model_name = model_name

    def generate_text(self, prompt):
        try:
            response: ChatResponse = chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"num_ctx": len(prompt),
                },
                keep_alive = 0,
            )
            # To unload a model from memory in Ollama, you must use the
            # keep_alive parameter with a value of 0 via the API.
            # curl http://localhost:11434/api/generate -d '{"model": "llama3.2", "keep_alive": 0}'
            return response.message.content
        except Exception as e:
            logging.error(f"Error generating text with Ollama: {e}")
            if "model requires more system memory" in str(e) or "out of memory" in str(e).lower():
                logging.error(f"Ollama model {self.model_name} requires more memory than available: {e}")
                return "Memory"
            return None

    @staticmethod
    def list_models():
        return ollama.list()["models"]


class GeminiClient(LLMClient):
    # def __init__(self, model_name="gemini-1.5-flash-latest"):
    def __init__(self, model_name=""):
        name_class = self.__class__.__name__
        self.config = True

        super().__init__(name_class)

        self.client = genai.Client(api_key=self.api_key)
        if not model_name:
            # names = [el.name for el in genai.list_models()]
            models = self.list_models()
            sel, name = select_from_list(
                models,
                identifier="name",
                selector="gemini",
                default="models/gemini-2.0-flash",
            )
            print(name)
            self.model_name = name.split("/")[1]
        else:
            self.model_name = model_name

        #self.client = genai.GenerativeModel(self.model_name)

    def generate_text(self, prompt):
        try:
            #response = self.client.generate_content(prompt)
            response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                    )
            return response.text
        except Exception as e:
            logging.error(f"Error generating text with Gemini: {e}")
            return None

    #@staticmethod
    def list_models(self):
        #return list(genai.list_models())
        return list(self.client.models.list())


class MistralClient(LLMClient):
    def __init__(self, model_name=""):
        name_class = self.__class__.__name__
        self.config = True

        super().__init__(name_class)

        self.client = Mistral(api_key=self.api_key)
        if not self.model_name:
            # names = [el.id for el in self.list_models(self).data]
            models = self.list_models(self).data
            sel, name = select_from_list(models, identifier="id", default="mistral-small-latest")
            # sel = select_from_list(names, default="mistral-small-latest")
            self.model_name = name

    def generate_text(self, prompt):
        try:
            response = self.client.chat.complete(
                model=self.model_name, messages=[{"content": prompt, "role": "user"}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Error generating text with Mistral: {e}")
            return None

    @staticmethod
    def list_models(self):
        return self.client.models.list()


def select_llm(args):
    """Selects and initializes the appropriate LLM client."""
    if args.interactive:
        llm_options = ["ollama", "gemini", "mistral"]
        sel, ai = select_from_list(llm_options, title="Select model provider", default="gemini")
    else:
        ai = getattr(args, 'ai', None) or "gemini"
    print(f"Selected AI: {ai}")

    if ai == "ollama":
        if args.interactive:
            model = OllamaClient()
        else:
            model = OllamaClient('granite4:latest')
        return model
    elif ai == "gemini":
        if args.interactive:
            model = GeminiClient()
        else:
            model = GeminiClient("gemini-2.5-flash")
        return model
    elif ai == "mistral":
        model = MistralClient()
        return model
    else:
        logging.error(f"Invalid LLM source: {ai}")
        return None

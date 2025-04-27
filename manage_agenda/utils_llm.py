import configparser
import os
import google.generativeai as genai
import ollama
from ollama import chat, ChatResponse
from mistralai import Mistral
from socialModules.configMod import CONFIGDIR

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
        if self.config:
            try:
                config_file = f"{CONFIGDIR}/.rss{name_class[:-6]}"
                config = load_config(config_file)
            except FileNotFoundError as e:
                raise FileNotFoundError(
                    f"Configuration file: {config_file} does not exist\n"
                    f"You need to create it and add the API key"
                )
            except Exception as e:
                raise Exception(e)

            section = config.sections()[0]
            self.api_key = config.get(section, "api_key")
        self.model_name = None

    def generate_text(self, prompt):
        raise NotImplementedError("Subclasses must implement this method")


class OllamaClient(LLMClient):
    def __init__(self, model_name=""):
        name_class = self.__class__.__name__
        self.config = False

        super().__init__(name_class)
        if not model_name:
            # names = [el.model for el in self.list_models()]
            models = self.list_models()
            sel, name = select_from_list(models, identifier="model")
            # model_name = names[int(sel)]
            self.model_name = name
        else:
            self.model_name = model_name

        self.client = ollama.list()["models"][int(sel)]

    def generate_text(self, prompt):
        try:
            response: ChatResponse = chat(
                model=self.model_name, messages=[{"role": "user", "content": prompt}]
            )
            return response.message.content
        except Exception as e:
            logging.error(f"Error generating text with Ollama: {e}")
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

        genai.configure(api_key=self.api_key)
        if not model_name:
            # names = [el.name for el in genai.list_models()]
            models = genai.list_models()
            sel, name = select_from_list(
                models,
                identifier="name",
                selector="gemini",
                default="models/gemini-1.5-flash-latest",
            )
            self.model_name = name.split("/")[1]
        else:
            self.model_name = model_name

        self.client = genai.GenerativeModel(self.model_name)

    def generate_text(self, prompt):
        try:
            response = self.client.generate_content(prompt)
            return response.text
        except Exception as e:
            logging.error(f"Error generating text with Gemini: {e}")
            return None

    @staticmethod
    def list_models():
        return genai.list_models()


class MistralClient(LLMClient):
    def __init__(self, model_name=""):
        name_class = self.__class__.__name__
        self.config = True

        super().__init__(name_class)

        self.client = Mistral(api_key=self.api_key)
        if not self.model_name:
            # names = [el.id for el in self.list_models(self).data]
            models = self.list_models(self).data
            sel, name = select_from_list(
                models, identifier="id", default="mistral-small-latest"
            )
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




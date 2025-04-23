import click

import configparser
import datetime
import json
import logging
import os
import sys
import argparse  # Import argparse at the top

from collections import namedtuple

# AI modules
import google.generativeai as genai
import ollama
from ollama import chat, ChatResponse
from mistralai import Mistral
import googleapiclient

# Gmail an Gcalendar access modules
from socialModules import moduleImap, moduleRules  # Explicitly import modules
from socialModules.configMod import CONFIGDIR, DATADIR, checkFile, fileNamePath, logMsg

# --- Constants and Configuration ---
DEFAULT_DATA_DIR = os.path.expanduser("~/Documents/data/msgs/")

Args = namedtuple("args", ["interactive", "delete", "source"])

def setup_logging():
    """Configures logging to stdout."""
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )


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


def safe_get(data, keys, default=""):
    """Safely retrieves nested values from a dictionary."""
    try:
        for key in keys:
            data = data[key]
        return data
    except (KeyError, TypeError):
        return default


def select_from_list(options, identifier = "", selector="", default=""):
    """Selects an option form an iterable element, based on some identifier

    We can make an initial selection of elements that contain 'selector'
    We can select based on numbers or in substrings of the elements
    of the list.
    """

    if options and (isinstance(options[0], dict) or (hasattr(options[0], '__slots__'))):
        names = [safe_get(el, [identifier,]) if isinstance(el, dict) else getattr(el, identifier) for el in options]
    else:
        names = options
    sel = -1
    options_sel = names.copy()
    while sel<0:
        for i, elem in enumerate(options_sel):
            if selector in elem:
                print(f"{i}) {elem}")
        msg = "Selection "
        msg += f"({default}) " if default else ""
        sel = input(msg)
        if sel == "":
            if default:
                sel = names.index(default)
                # indices_coincidentes = list(i for i, elemento in enumerate(mi_lista) if busqueda in elemento)
        elif sel.isdigit() and int(sel) not in range(len(options_sel)):
            sel = -1
        elif not sel.isdigit():
            options_sel = [opt for opt in options_sel if sel in opt]
            print(f"Options: {options_sel}")
            if len(options_sel) == 1:
                sel = names.index(options_sel[0])
            else:
                sel = -1
        else:
            # Now we select the original number
            sel = names.index(options_sel[int(sel)])

    logging.info(f"Sel: {sel}")

    return sel, names[int(sel)]


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
            sel, name = select_from_list(models, identifier='model')
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
            #names = [el.name for el in genai.list_models()]
            models = genai.list_models()
            sel, name = select_from_list(
                models, identifier='name', selector="gemini", default="models/gemini-1.5-flash-latest"
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
                models, identifier='id', default="mistral-small-latest"
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


# --- Data Access ---
def select_message(message_src, max_messages=50):
    """Selects a message from a list.

    Args:
        message_src: An object with methods to get posts.
        max_messages (int): The maximum number of recent messages to display.

    Returns:
        The selected message or None if selection is invalid.
    """
    message_src.setPosts()
    recent_messages = message_src.getPosts()[-max_messages:]

    for i, msg in enumerate(recent_messages):
        from_msg = message_src.getPostFrom(msg)
        to_msg = message_src.getPostTo(msg)
        subject_msg = message_src.getPostTitle(msg)
        print(f"{i}) From: {from_msg}, Subject: {subject_msg}")

    msg_number = input("Which message? ")
    if msg_number.isnumeric() and 0 <= int(msg_number) < len(recent_messages):
        return recent_messages[int(msg_number)]
    else:
        logging.warning("Invalid message selection.")
        return None


def select_message_folder(message_src, folder="INBOX"):
    """Selects a message from a specific folder.

    Args:
        message_src: An object with methods to set channel and get posts.
        folder (str): The folder to select from.

    Returns:
        The selected message or None if selection is invalid.
    """
    message_src.setChannel(folder)
    logging.info(f"Selected folder: {message_src.getChannel()}")
    return select_message(message_src)


def select_calendar(calendar_api):
    """Selects a Google Calendar.

    Args:
        calendar_api: An object to interact with the Google Calendar API.

    Returns:
        The ID of the selected calendar or the calendar object.
    """
    calendar_api.setCalendarList()
    calendars = calendar_api.getCalendarList()
    eligible_calendars = [
        cal for cal in calendars if "reader" not in cal.get("accessRole", "")
    ]

    #names = [safe_get(cal, ["summary"]) for cal in eligible_calendars]
    selection, cal = select_from_list(eligible_calendars, 'summary')

    print(f"Cal: {cal}")
    return eligible_calendars[selection]['id']


# --- File I/O ---
def write_file(filename, content):
    """Writes content to a file.

    Args:
        filename (str): The name of the file.
        content (str): The content to write.
    """
    try:
        with open(f"{DEFAULT_DATA_DIR}{filename}", "w") as file:
            file.write(content)
        logging.info(f"File written: {filename}")
    except Exception as e:
        logging.error(f"Error writing file {filename}: {e}")


# --- Event Handling ---
def create_event_dict():
    """Creates a template dictionary for calendar events."""
    return {
        "summary": "",
        "location": "",
        "description": "",
        "start": {"dateTime": "", "timeZone": ""},
        "end": {"dateTime": "", "timeZone": ""},
        "recurrence": [],
        "attendees": [],
    }


def process_event_data(event, content):
    """Processes event data, adding the email content to the description.

    Args:
        event (dict): The event dictionary.
        content (str): The content of the email.
    """
    event["description"] = f"{safe_get(event, ['description'])}\n\nMessage:\n{content}"
    # if "attendees" in event and event["attendees"]:
    # if safe_get(event, ["attendees"]):  # in event and event["attendees"]:
    event["attendees"] = []  # Clear attendees
    return event


def adjust_event_times(event):
    """Adjusts event start/end times if one is missing."""
    start = safe_get(event, ["start", "dateTime"])
    end = safe_get(event, ["end", "dateTime"])

    if not start and end:
        event["start"] = {}
        event["start"]["dateTime"] = end
        event["start"]["timeZone"] = safe_get(
            event, ["end", "timeZone"], "Europe/Madrid"
        )
    elif not end and start:
        event["end"] = {}
        event["end"]["dateTime"] = start
        event["end"]["timeZone"] = safe_get(
            event, ["start", "timeZone"], "Europe/Madrid"
        )

    if not safe_get(event, ["start", "timeZone"]):
        event["start"]["timeZone"] = "Europe/Madrid"
    if not safe_get(event, ["end", "timeZone"]):
        event["end"]["timeZone"] = "Europe/Madrid"
    return event


# --- CLI Functions ---
def list_models_cli(args):
    """Lists available LLMs."""
    "Not used. Maybe interesting?"
    if args.source == "ollama":
        models = OllamaClient.list_models()
        for i, model in enumerate(models):
            print(f"{i}) {model['model']}")
    elif args.source == "gemini":
        models = GeminiClient.list_models()
        for i, model in enumerate(models):
            if "gemini" in model.name:
                print(f"{i}) {model.name}")
    else:
        print("Model listing not supported for this source.")


def extract_json(text):
    # Extract JSON (assuming response contains JSON within backticks)
    start_index = text.find("```")
    end_index = text.find("```", start_index + 1)
    vcal_json = text[
        start_index + 8 : end_index
    ].strip()  # Extract content between backticks

    return vcal_json


def process_email_cli(args, model):
    """Processes emails and creates calendar events."""

    rules = moduleRules.moduleRules()
    rules.checkRules()

    # Select API source (Gmail)
    api_src_type = "gmail"
    if args.interactive:
        api_src = rules.selectRuleInteractive(api_src_type)
    else:
        # The first configured gmail email in .rssBlogs
        source_name = rules.selectRule(api_src_type, "")[0]
        source_details = rules.more.get(source_name, {})
        logging.info(f"Source: {source_name} - {source_details}")
        api_src = rules.readConfigSrc("", source_name, source_details)

    # Process emails
    # folder = "INBOX/zAgenda" if "imap" in api_src.service.lower() else "zAgenda"
    folder = "zAgenda"
    api_src.setPostsType("posts")
    api_src.setLabels()
    label = api_src.getLabels(folder)
    if len(label) > 0:
        label_id = safe_get(label[0], ['id'])
        api_src.setChannel(folder)
        api_src.setPosts()

        for i, post in enumerate(api_src.getPosts()):
            post_id = api_src.getPostId(post)
            post_date = api_src.getPostDate(post)
            post_title = api_src.getPostTitle(post)

            print(f"{i}) Title: {post_title}")
            post_content = api_src.getPostContent(post)
            logging.debug(f"Text: {post_content}")
            post_date_time = datetime.datetime.fromtimestamp(int(post_date) / 1000)
            logging.debug(f"Date: {post_date_time}")

            time_difference = datetime.datetime.now() - post_date_time
            logging.debug(f"Date: {post_date_time} Diff: {time_difference.days}")

            if time_difference.days > 7:
                print(f"Too old ({time_difference.days} days), skipping.")
                continue

            # Get full email body
            if "gmail" in api_src.service.lower():
                # email_result = (
                #     api_src.getClient()
                #     .users()
                #     .messages()
                #     .get(userId="me", id=post_id)
                #     .execute()
                # )
                email_result = api_src.getMessage(post_id)
                full_email_content = api_src.getPostBody(email_result)

                if hasattr(full_email_content, "decode"):
                    full_email_content = full_email_content.decode("utf-8")
            # else:
            #     full_email_content = post_content

            email_text = f"{post_title}\nDate:{post_date_time}\n{full_email_content}"
            write_file(f"{post_id}.txt", email_text)  # Save email text

            # Generate event data
            event = create_event_dict()
            # date = api_src.getPostDate(post)
            prompt = (
                f"Rellenar los datos del diccionario {event}."
                "\nBuscamos datos relativos a una actividad. "
                "El inicio y el fin se pondrán en "
                " los campos event['start']['dateTime']  y "
                " event['end']['dateTime'] respectivamente,"
                f" y serán fechas "
                f"posteriores a {post_date_time}. El texto es:\n{email_text}"
                " No añadas comentarios al resultado, que"
                " se representará como un JSON."
            )
            print(f"Prompt:\n{prompt}")
            print(f"\nEnd Prompt:")

            # Get AI reply
            llm_response = model.generate_text(prompt)
            if not llm_response:
                print("Failed to get response from LLM, skipping.")
                continue  # Skip to the next email

            print(f"Reply:\n{llm_response}")

            vcal_json = extract_json(llm_response)
            write_file(f"{post_id}.vcal", vcal_json)  # Save vCal data

            # Select calendar
            api_dst_type = "gcalendar"
            if args.interactive:
                api_dst = rules.selectRuleInteractive(api_dst_type)
            else:
                # The first configured google calendar in .rssBlogs
                api_dst_name = rules.selectRule(api_dst_type, "")[0]
                api_dst_details = rules.more.get(api_dst_name, {})
                api_dst = rules.readConfigSrc("", api_dst_name, api_dst_details)

            try:
                event = json.loads(vcal_json)
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in vCal data: {vcal_json}")
                logging.error(f"Error: {e}")
                continue

            event = process_event_data(event, full_email_content)
            write_file(f"{post_id}.json", json.dumps(event))  # Save event JSON

            event = adjust_event_times(event)

            # start_time = event["start"].get("dateTime")
            start_time = safe_get(event, ["start", "dateTime"])
            # end_time = event["end"].get("dateTime")
            end_time = safe_get(event, ["end", "dateTime"])
            print(f"Start: {start_time}")
            print(f"End: {end_time}")
            print(f"Subject: {post_title}")

            selected_calendar = select_calendar(api_dst)
            if not selected_calendar:
                print("No calendar selected, skipping event creation.")
                continue

            try:
                # calendar_result = (
                #    api_dst.getClient()
                #    .events()
                #    .insert(calendarId=selected_calendar, body=event)
                #    .execute()
                # )
                # print(f"Calendar event created: {calendar_result.get('htmlLink')}")
                calendar_result = api_dst.publishPost(
                    post={"event": event, "idCal": selected_calendar}, api=api_dst
                )
                print(f"Calendar event created: {calendar_result}")
                # print(f"Calendar event created: {calendar_result.get('htmlLink')}")
            except googleapiclient.errors.HttpError as e:
                logging.error(f"Error creating calendar event: {e}")

            # Delete email (optional)
            if args.delete:
                input("Delete tag? (Press Enter to continue)")
                if "gmail" in api_src.service.lower():
                    try:
                        label = api_src.getLabels(api_src.getChannel())
                        logging.info(f"Msg: {post}")
                        res = api_src.modifyLabels(post_id, label_id, None)
                        label_id = api_src.getLabels(api_src.getChannel())[0]["id"]
                        print(f"Label deleted: {res}")
                        # api_src.getClient().users().messages().modify(
                        #     userId="me", id=post_id, body={"removeLabelIds": [label_id]}
                        # ).execute()
                        # logging.info(f"email {post_id} deleted.")
                    except googleapiclient.errors.httperror as e:
                        logging.error(f"Error deleting email: {e}")
                else:
                    flag = "\\Deleted"
                    api_src.getClient().store(post_id, "+FLAGS", flag)
                    logging.info(f"Email {post_id} marked for deletion.")
    else:
        print(f"There are no posts tagged with label {folder}")


def select_llm(args):
    """Selects and initializes the appropriate LLM client."""
    if args.interactive:
        selection = input("Local/mistral/gemini model )(l/m/g)? ")
        if selection == "l":
            args = Args(
                interactive=args.interactive, delete=args.delete, source="ollama"
            )
        elif selection == "m":
            args = Args(
                interactive=args.interactive, delete=args.delete, source="mistral"
            )
        else:
            args = Args(
                interactive=args.interactive, delete=args.delete, source="gemini"
            )
    else:
        args = Args(interactive=args.interactive, delete=args.delete, source="gemini")

    if args.source == "ollama":
        model = OllamaClient()
        return model
    elif args.source == "gemini":
        if args.interactive:
            model = GeminiClient()
        else:
            model = GeminiClient("gemini-1.5-flash-latest")
        return model
    elif args.source == "mistral":
        model = MistralClient()
        return model
    else:
        logging.error(f"Invalid LLM source: {args.source}")
        return None


@click.group()
@click.version_option()
def cli():
    "An app for adding entries to my calendar"


# @cli.command(name="command")
# @click.argument(
#     "example"
# )
@cli.command()
@click.option(
    "-i",
    "--interactive",
    default=False,
    help="Running in interactive mode",
)
@click.option(
    "-d",
    "--delete",
    default=True,
    help="Delete tag",
)
@click.option(
    "-s",
    "--source",
    default="gemini",
    help="Select LLM",
)
def add(interactive, delete, source):
    "Add entries to the calendar"
    setup_logging()

    args = Args(interactive=interactive, delete=delete, source=source)

    model = select_llm(args)

    print(f"Model: {model}")

    process_email_cli(args, model)

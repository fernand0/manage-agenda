import datetime
import json
import logging
import os
import sys
import googleapiclient
from socialModules import moduleImap, moduleRules
from socialModules.configMod import CONFIGDIR, DATADIR, checkFile, fileNamePath, logMsg
from collections import namedtuple

from manage_agenda.utils_llm import OllamaClient, GeminiClient, MistralClient

Args = namedtuple("args", ["interactive", "delete", "source"])

DEFAULT_DATA_DIR = os.path.expanduser("~/Documents/data/msgs/")


def setup_logging():
    """Configures logging to stdout."""
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )



def safe_get(data, keys, default=""):
    """Safely retrieves nested values from a dictionary."""
    try:
        for key in keys:
            data = data[key]
        return data
    except (KeyError, TypeError):
        return default


def select_from_list(options, identifier="", selector="", default=""):
    """Selects an option form an iterable element, based on some identifier

    We can make an initial selection of elements that contain 'selector'
    We can select based on numbers or in substrings of the elements
    of the list.
    """

    if options and (isinstance(options[0], dict) or (hasattr(options[0], "__slots__"))):
        names = [
            safe_get(
                el,
                [
                    identifier,
                ],
            )
            if isinstance(el, dict)
            else getattr(el, identifier)
            for el in options
        ]
    else:
        names = options
    sel = -1
    options_sel = names.copy()
    while isinstance(sel, str) or (sel < 0):
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
            # Now we select the original number
            sel = names.index(options_sel[int(sel)])

    logging.info(f"Sel: {sel}")

    return sel, names[int(sel)]


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

    # names = [safe_get(cal, ["summary"]) for cal in eligible_calendars]
    selection, cal = select_from_list(eligible_calendars, "summary")

    print(f"Cal: {cal}")
    return eligible_calendars[selection]["id"]


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
    # extract json (assuming response contains json within backticks)
    start_index = text.find("```")
    end_index = text.find("```", start_index + 1)
    vcal_json = text[
        start_index + 8 : end_index
    ].strip()  # extract content between backticks

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
        label_id = safe_get(label[0], ["id"])
        api_src.setChannel(folder)
        api_src.setPosts()

        if api_src.getPosts():
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

                email_text = (
                    f"{post_title}\nDate:{post_date_time}\n{full_email_content}"
                )
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

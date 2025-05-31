import datetime
import json
import googleapiclient
import logging
from socialModules import moduleImap, moduleRules
from socialModules.configMod import CONFIGDIR, DATADIR, checkFile, fileNamePath, logMsg, select_from_list, safe_get
from collections import namedtuple

from manage_agenda.utils_base import setup_logging, write_file#, select_from_list 
from manage_agenda.utils_llm import OllamaClient, GeminiClient, MistralClient

Args = namedtuple("args", ["interactive", "delete", "source"])

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

# def list_models_cli(args):
#     """Lists available LLMs."""
#     "Not used. Maybe interesting?"
#     if args.source == "ollama":
#         models = OllamaClient.list_models()
#         for i, model in enumerate(models):
#             print(f"{i}) {model['model']}")
#     elif args.source == "gemini":
#         models = GeminiClient.list_models()
#         for i, model in enumerate(models):
#             if "gemini" in model.name:
#                 print(f"{i}) {model.name}")
#     else:
#         print("Model listing not supported for this source.")


def extract_json(text):
    # extract json (assuming response contains json within backticks)
    if '```' in text:
        start_index = text.find("```")
        end_index = text.find("```", start_index + 1)
        vcal_json = text[
            start_index + 8 : end_index
        ].strip()  # extract content between backticks
    elif '<think>' in text:
        start_index = text.find("/think")
        vcal_json = text[
            start_index + 9 :].strip()

    return vcal_json

def select_account(args, api_src_type="gmail"):

    rules = moduleRules.moduleRules()
    rules.checkRules()

    # Select API source (Gmail)
    if args.interactive:
        api_src = rules.selectRuleInteractive(api_src_type)
    else:
        # The first configured gmail email in .rssBlogs
        source_name = rules.selectRule(api_src_type, "")[0]
        source_details = rules.more.get(source_name, {})
        logging.info(f"Source: {source_name} - {source_details}")
        api_src = rules.readConfigSrc("", source_name, source_details)
    return api_src


def list_events_folder(args, api_src, calendar=""):
    """Lists events in calendar."""
    if api_src.getClient():
        api_src.setPosts()
        if api_src.getPosts():
            for i, post in enumerate(api_src.getPosts()):
                print("1")
                post_id = api_src.getPostId(post)
                print("2")
                post_date = api_src.getPostDate(post)
                print("3")
                post_title = api_src.getPostTitle(post)
                print(f"{i}) {post_title}")
    else:
        print("Some problem with the account")

def list_emails_folder(args, api_src, folder="INBOX"):
    """Lists emails and in folder."""
    if api_src.getClient():
        # Process emails
        # folder = "INBOX/zAgenda" if "imap" in api_src.service.lower() else "zAgenda"
        # folder = "zAgenda"
        api_src.setPostsType("posts")
        api_src.setLabels()
        label = api_src.getLabels(folder)
        if len(label) > 0:
            label_id = safe_get(label[0], ["id"])
            api_src.setChannel(folder)
            api_src.setPosts()

            if api_src.getPosts():
                for i, post in enumerate(api_src.getPosts()):
                    if True: #i < 10:
                        post_id = api_src.getPostId(post)
                        post_date = api_src.getPostDate(post)
                        post_title = api_src.getPostTitle(post)
                        print(f"{i}) {post_title}")
    else:
        print("Some problem with the account")


def process_email_cli(args, model):
    """Processes emails and creates calendar events."""

    rules = moduleRules.moduleRules()
    rules.checkRules()

    # Select API source (Gmail)
    api_src_type = ["gmail", "imap"]
    if args.interactive:
        api_src = rules.selectRuleInteractive(api_src_type)
    else:
        # The first configured gmail email in .rssBlogs
        rules_all = rules.selectRule(api_src_type, "")
        source_name = rules_all[0]
        source_details = rules.more.get(source_name, {})
        api_src = rules.readConfigSrc("", source_name, source_details)

    # Process emails
    folder = "INBOX/zAgenda" if "imap" in api_src.service.lower() else "zAgenda"
    #folder = "zAgenda"
    api_src.setPostsType("posts")
    api_src.setLabels()
    label = api_src.getLabels(folder)
    print(f"Label: {label}")
    if len(label) > 0:
        api_src.setChannel(label[0])
        api_src.setPosts()

        if api_src.getPosts():
            for i, post in enumerate(api_src.getPosts()):
                post_id = api_src.getPostId(post)
                post_date = api_src.getPostDate(post)
                post_title = api_src.getPostTitle(post)

                print(f"{i}) Title: {post_title}")
                post_content = api_src.getPostContent(post)
                logging.debug(f"Text: {post_content}")
                if post_date.isdigit():
                    post_date_time = datetime.datetime.fromtimestamp(int(post_date) / 1000)
                else:
                    from email.utils import parsedate_to_datetime
                    post_date_time = parsedate_to_datetime(post_date)

                try:
                    import pytz
                    time_difference = pytz.timezone('Europe/Madrid').localize(datetime.datetime.now()) - post_date_time
                    logging.debug(f"Date: {post_date_time} Diff: {time_difference.days}")
                except:
                    # FIXME
                    time_difference = datetime.datetime.now() - datetime.datetime.now()

                if time_difference.days > 7:
                    print(f"Too old ({time_difference.days} days), skipping.")
                    continue

                # Get full email body
                #if "gmail" in api_src.service.lower():
                    # email_result = (
                    #     api_src.getClient()
                    #     .users()
                    #     .messages()
                    #     .get(userId="me", id=post_id)
                    #     .execute()
                    # )
                #email_result = api_src.getMessage(post_id)
                email_result = post
                print(f"email: {email_result}")
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
                    f" y serán fechas iguales o "
                    f"posteriores a {post_date_time}. "
                    f"El texto es:\n{email_text}"
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
                    rules_all = rules.selectRule(api_dst_type, "")
                    print(f"Rules all: {rules_all}")
                    api_dst_name = rules_all[0]
                    # api_dst_name = rules.selectRule(api_dst_type, "")[0]
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
                print(f"==================================")
                print(f"Subject: {post_title}")
                print(f"Start: {start_time}")
                print(f"End: {end_time}")
                print(f"==================================")

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
                    print(f"Calendar event created") #: {calendar_result}")
                    # print(f"Calendar event created: {calendar_result.get('htmlLink')}")
                except googleapiclient.errors.HttpError as e:
                    logging.error(f"Error creating calendar event: {e}")

                # Delete email (optional)
                if args.delete:
                    input("Delete tag? (Press Enter to continue)")
                    if True: #"gmail" in api_src.service.lower():
                        # label = api_src.getLabels(api_src.getChannel())
                        # logging.debug(f"Msg: {post}")
                        # logging.info(f"Labellls: {label}")
                        res = api_src.modifyLabels(post_id, api_src.getChannel(), None)
                        #label_id = api_src.getLabels(api_src.getChannel())[0]["id"]
                        # api_src.getClient().users().messages().modify(
                        #     userId="me", id=post_id, body={"removeLabelIds": [label_id]}
                        # ).execute()
                        # logging.info(f"email {post_id} deleted.")
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

import datetime
import time
import json
import googleapiclient
import logging
from socialModules import moduleImap, moduleRules
from socialModules.configMod import CONFIGDIR, DATADIR, checkFile, fileNamePath, logMsg, select_from_list, safe_get
from collections import namedtuple

from manage_agenda.utils_base import setup_logging, write_file, format_time#, select_from_list
from manage_agenda.utils_llm import OllamaClient, GeminiClient, MistralClient

Args = namedtuple("args", ["interactive", "delete", "source", "verbose", "destination", "text"])


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
def adjust_event_times(event):
    """Adjusts event start/end times if one is missing."""
    start = event.get("start")
    end = event.get("end")

    if not isinstance(start, dict):
        start = {}
        event["start"] = start
    if not isinstance(end, dict):
        end = {}
        event["end"] = end

    start_time = start.get("dateTime")
    end_time = end.get("dateTime")

    if start_time and not end_time:
        end["dateTime"] = start_time
    elif end_time and not start_time:
        start["dateTime"] = end_time

    if "dateTime" in start:
        start.setdefault("timeZone", "Europe/Madrid")
    if "dateTime" in end:
        end.setdefault("timeZone", "Europe/Madrid")

    if not safe_get(event, ["start", "timeZone"]):
        event["start"]["timeZone"] = "Europe/Madrid"
    if not safe_get(event, ["end", "timeZone"]):
        event["end"]["timeZone"] = "Europe/Madrid"
    return event

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

def authorize(args):
    rules = moduleRules.moduleRules()
    rules.checkRules()
    if args.interactive:
        service = input("Service? ")
        api_src = rules.selectRuleInteractive(service)
    else:
        # The first configured service in .rssBlogs
        rules_all = rules.selectRule("", "")
        if not rules_all:
            logging.warning("No services configured.")
            return None
        source_name = rules_all[0]
        source_details = rules.more.get(source_name, {})
        logging.info(f"Source: {source_name} - {source_details}")
        api_src = rules.readConfigSrc("", source_name, source_details)
    return api_src

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
                post_id = api_src.getPostId(post)
                post_date = api_src.getPostDate(post)
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
    if args.verbose:
        print(f"Label: {label}")
    if len(label) > 0:
        api_src.setChannel(label[0])
        api_src.setPosts()

        if api_src.getPosts():
            for i, post in enumerate(api_src.getPosts()):
                post_id = api_src.getPostId(post)
                post_date = api_src.getPostDate(post)
                post_title = api_src.getPostTitle(post)

                print(f"Processing Title: {post_title}", flush=True)
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
                    if args.interactive:
                        confirmation = input(
                            f"El correo tiene {time_difference.days} dias. ¿Desea procesarlo? (y/n): "
                        )
                        if confirmation.lower() != "y":
                            continue
                    else:
                        if args.verbose:
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
                if args.verbose:
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
                    # "Si no se indica otra cosa la fecha y hora "
                    # "es local en España "
                    f"El texto es:\n{email_text}"
                    " No añadas comentarios al resultado, que"
                    " se representará como un JSON."
                )
                if args.verbose:
                    print(f"Prompt:\n{prompt}")
                    print(f"\nEnd Prompt:")

                # Get AI reply
                print(f"Calling LLM")
                start_time = time.time()
                llm_response = model.generate_text(prompt)
                end_time = time.time()
                elapsed_time = end_time - start_time
                print(f"AI call took {format_time(elapsed_time)} ({elapsed_time:.2f} seconds)")
                if not llm_response:
                    print("Failed to get response from LLM, skipping.")
                    continue  # Skip to the next email

                if args.verbose:
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
                    if args.verbose:
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

                # --- New logic starts here ---
                retries = 0
                max_retries = 3 # Limit AI retries
                data_complete = False

                while not data_complete and retries <= max_retries:
                    summary = event.get('summary')
                    start_datetime = event.get('start', {}).get('dateTime')

                    if summary and start_datetime:
                        data_complete = True
                        break

                    if args.interactive:
                        print("Missing event information:")
                        if not summary:
                            print("- Summary")
                        if not start_datetime:
                            print("- Start Date/Time")

                        choice = input("Options: (m)anual input, (a)nother AI, (s)kip email: ").lower()

                        if choice == 'm':
                            if not summary:
                                new_summary = input("Enter Summary: ")
                                if new_summary:
                                    event['summary'] = new_summary
                            if not start_datetime:
                                new_start_datetime_str = input("Enter Start Date/Time (YYYY-MM-DD HH:MM:SS): ")
                                if new_start_datetime_str:
                                    try:
                                        # Assuming YYYY-MM-DD HH:MM:SS format for simplicity
                                        new_start_datetime = datetime.datetime.strptime(new_start_datetime_str, "%Y-%m-%d %H:%M:%S")
                                        event.setdefault('start', {})['dateTime'] = new_start_datetime.isoformat()
                                        event['start'].setdefault('timeZone', 'Europe/Madrid') # Set default timezone
                                    except ValueError:
                                        print("Invalid date/time format. Please use YYYY-MM-DD HH:MM:SS.")
                                        # Do not set data_complete to True, so loop continues
                                        continue # Continue the while loop
                            data_complete = True # Assume data is complete after manual input attempt
                        elif choice == 'a':
                            retries += 1
                            if retries > max_retries:
                                print("Max AI retries reached. Skipping email.")
                                break # Exit the while loop to skip this email

                            print("Selecting another AI model...")
                            # Temporarily store current model and args to restore later if needed
                            original_model = model
                            original_args_source = args.source

                            # Create new args for select_llm to allow user to choose
                            # Ensure all args are passed to select_llm
                            new_args = Args(
                                interactive=True, # Force interactive selection for new AI
                                delete=args.delete,
                                source=None, # Let user choose
                                verbose=args.verbose,
                                destination=args.destination,
                                text=args.text
                            )
                            new_model = select_llm(new_args)

                            if new_model:
                                model = new_model # Use the newly selected model
                                print(f"Trying with new AI model: {model.__class__.__name__}")
                                llm_response = model.generate_text(prompt)
                                if llm_response:
                                    vcal_json = extract_json(llm_response)
                                    try:
                                        event = json.loads(vcal_json)
                                        # Data completeness will be checked at the start of the next loop iteration
                                    except json.JSONDecodeError as e:
                                        logging.error(f"Invalid JSON from new AI: {vcal_json}. Error: {e}")
                                        # Keep data_complete as False, loop will continue or exit if retries exhausted
                                else:
                                    print("New AI model failed to generate a response.")
                                    # Keep data_complete as False, loop will continue or exit if retries exhausted
                            else:
                                print("No new AI model selected or available. Skipping email.")
                                break # Exit the while loop to skip this email
                        elif choice == 's':
                            # Skip email logic will go here
                            break # Exit the while loop to skip this email
                        else:
                            print("Invalid choice. Please try again.")
                            retries += 1 # Count as a retry if invalid choice
                            continue # Continue the while loop
                    else: # Non-interactive mode
                        if not summary or not start_datetime:
                            logging.warning(f"Missing summary or start_datetime for email {post_id}. Skipping.")
                            break # Exit the while loop to skip this email
                        else:
                            data_complete = True # Should not happen if we are here

                if not data_complete:
                    continue # Skip to the next email if data is still not complete after loop
                # --- New logic ends here ---

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
                delete_confirmed = False
                if args.interactive:
                    confirmation = input("Do you want to remove the label from the email? (y/n): ")
                    if confirmation.lower() == 'y':
                        delete_confirmed = True
                elif args.delete: # Only auto-confirm if not interactive but delete flag is set
                    delete_confirmed = True

                if delete_confirmed:
                        if "imap" not in api_src.service.lower():
                            res = api_src.modifyLabels(post_id, api_src.getChannel(), None)
                            logging.info(f"Label removed from email {post_id}.")
                        else:
                            flag = "\\Deleted"
                            try:
                                api_src.getClient().store(post_id, "+FLAGS", flag)
                                logging.info(f"Email {post_id} marked for deletion.")
                            except Exception as e:
                                logging.warning(f"IMAP store failed: {e}. Reconnecting and retrying...")
                                try:
                                    api_src.checkConnected()
                                    api_src.getClient().store(post_id, "+FLAGS", flag)
                                    logging.info(f"Email {post_id} marked for deletion after reconnect.")
                                except Exception as e2:
                                    logging.error(f"Failed to mark email for deletion after reconnect: {e2}")
        else:
            print(f"There are no posts tagged with label {folder}")

import urllib.request
import re

from bs4 import BeautifulSoup

def process_web_cli(args, model):
    """Processes web pages and creates calendar events."""

    rules = moduleRules.moduleRules()
    rules.checkRules()

    url = input("URL: ")

    print(f"Processing URL: {url}", flush=True)

    post_date_time = datetime.datetime.now()

    try:
        with urllib.request.urlopen(url) as response:
            web_content_html = response.read().decode('utf-8')

        soup = BeautifulSoup(web_content_html, 'html.parser')
        web_content = soup.get_text()

        web_content = re.sub(r'\n{3,}', '\n\n', web_content)

        print("\n--- First 10 lines of web content ---")
        for i, line in enumerate(web_content.splitlines()):
            if i >= 10:
                break
            print(line)
        print("-------------------------------------")

    except Exception as e:
        print(f"Error fetching or parsing URL: {e}")
        return


    # Generate event data
    event = create_event_dict()

    prompt = (
        f"Rellenar los datos del diccionario {event}.\n"
        "Buscamos datos relativos a una actividad. "
        "El inicio y el fin se pondrán en "
        " los campos event['start']['dateTime']  y "
        " event['end']['dateTime'] respectivamente',"
        f" y serán fechas iguales o "
        f"posteriores a {post_date_time}. "
        f"El texto es:\n{web_content}"
        " No añadas comentarios al resultado, que"
        " se representará como un JSON."
    )
    if args.verbose:
        print(f"Prompt:\n{prompt}")
        print(f"\nEnd Prompt:")

    # Get AI reply
    print(f"Calling LLM")
    start_time = time.time()
    llm_response = model.generate_text(prompt)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"AI call took {format_time(elapsed_time)} ({elapsed_time:.2f} seconds)")
    if not llm_response:
        print("Failed to get response from LLM, skipping.")
        return

    if args.verbose:
        print(f"Reply:\n{llm_response}")

    vcal_json = extract_json(llm_response)

    # Select calendar
    api_dst_type = "gcalendar"
    if args.interactive:
        api_dst = rules.selectRuleInteractive(api_dst_type)
    else:

        rules_all = rules.selectRule(api_dst_type, "")
        if args.verbose:
            print(f"Rules all: {rules_all}")
        api_dst_name = rules_all[0]

        api_dst_details = rules.more.get(api_dst_name, {})
        api_dst = rules.readConfigSrc("", api_dst_name, api_dst_details)

    try:
        event = json.loads(vcal_json)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in vCal data: {vcal_json}")
        logging.error(f"Error: {e}")
        return

    # --- New logic starts here ---
    retries = 0
    max_retries = 3 # Limit AI retries
    data_complete = False

    while not data_complete and retries <= max_retries:
        summary = event.get('summary')
        start_datetime = event.get('start', {}).get('dateTime')

        if summary and start_datetime:
            data_complete = True
            break

        if args.interactive:
            print("Missing event information:")
            if not summary:
                print("- Summary")
            if not start_datetime:
                print("- Start Date/Time")

            choice = input("Options: (m)anual input, (a)nother AI, (s)kip email: ").lower()

            if choice == 'm':
                if not summary:
                    new_summary = input("Enter Summary: ")
                    if new_summary:
                        event['summary'] = new_summary
                if not start_datetime:
                    new_start_datetime_str = input("Enter Start Date/Time (YYYY-MM-DD HH:MM:SS): ")
                    if new_start_datetime_str:
                        try:

                            new_start_datetime = datetime.datetime.strptime(new_start_datetime_str, "%Y-%m-%d %H:%M:%S")
                            event.setdefault('start', {})['dateTime'] = new_start_datetime.isoformat()
                            event['start'].setdefault('timeZone', 'Europe/Madrid') # Set default timezone
                        except ValueError:
                            print("Invalid date/time format. Please use YYYY-MM-DD HH:MM:SS.")

                            continue # Continue the while loop
                data_complete = True # Assume data is complete after manual input attempt
            elif choice == 'a':
                retries += 1
                if retries > max_retries:
                    print("Max AI retries reached. Skipping email.")
                    break # Exit the while loop to skip this email

                print("Selecting another AI model...")

                original_model = model
                original_args_source = args.source


                new_args = Args(
                    interactive=True, # Force interactive selection for new AI
                    delete=args.delete,
                    source=None, # Let user choose
                    verbose=args.verbose,
                    destination=args.destination,
                    text=args.text
                )
                new_model = select_llm(new_args)

                if new_model:
                    model = new_model # Use the newly selected model
                    print(f"Trying with new AI model: {model.__class__.__name__}")
                    llm_response = model.generate_text(prompt)
                    if llm_response:
                        vcal_json = extract_json(llm_response)
                        try:
                            event = json.loads(vcal_json)

                        except json.JSONDecodeError as e:
                            logging.error(f"Invalid JSON from new AI: {vcal_json}. Error: {e}")

                    else:
                        print("New AI model failed to generate a response.")

                else:
                    print("No new AI model selected or available. Skipping email.")
                    break # Exit the while loop to skip this email
            elif choice == 's':

                break # Exit the while loop to skip this email
            else:
                print("Invalid choice. Please try again.")
                retries += 1 # Count as a retry if invalid choice
                continue # Continue the while loop
        else: # Non-interactive mode
            if not summary or not start_datetime:
                logging.warning(f"Missing summary or start_datetime for url {url}. Skipping.")
                break # Exit the while loop to skip this email
            else:
                data_complete = True # Should not happen if we are here

    if not data_complete:
        return
    # --- New logic ends here ---

    description = safe_get(event, ['description']) or ''
    event['description'] = f"URL: {url}\n\n{description}\n\n{web_content}"
    event['attendees'] = []


    event = adjust_event_times(event)


    start_time = safe_get(event, ["start", "dateTime"])

    end_time = safe_get(event, ["end", "dateTime"])
    print(f"==================================")
    print(f"Subject: {url}")
    print(f"Start: {start_time}")
    print(f"End: {end_time}")
    print(f"==================================")

    selected_calendar = select_calendar(api_dst)
    if not selected_calendar:
        print("No calendar selected, skipping event creation.")
        return

    try:

        calendar_result = api_dst.publishPost(
            post={"event": event, "idCal": selected_calendar}, api=api_dst
        )
        print(f"Calendar event created")

    except googleapiclient.errors.HttpError as e:
        logging.error(f"Error creating calendar event: {e}")

def select_llm(args):
    """Selects and initializes the appropriate LLM client."""
    if args.interactive:
        selection = input("Local/mistral/gemini model )(l/m/g)? ")
        if selection == "l":
            args = Args(
                interactive=args.interactive, delete=args.delete, source="ollama", verbose=args.verbose, destination=args.destination, text=args.text
            )
        elif selection == "m":
            args = Args(
                interactive=args.interactive, delete=args.delete, source="mistral", verbose=args.verbose, destination=args.destination, text=args.text
            )
        else:
            args = Args(
                interactive=args.interactive, delete=args.delete, source="gemini", verbose=args.verbose, destination=args.destination, text=args.text
            )
    else:
        args = Args(interactive=args.interactive, delete=args.delete, source="gemini", verbose=args.verbose, destination=args.destination, text=args.text)

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

def copy_events_cli(args):
    """Copies events from a source calendar to a destination calendar."""
    rules = moduleRules.moduleRules()
    rules.checkRules()
    api_cal = rules.selectRuleInteractive("gcalendar")

    if args.source:
        my_calendar = args.source
    else:
        my_calendar = select_calendar(api_cal)

    today = datetime.datetime.now()
    the_date = today.isoformat(timespec="seconds") + "Z"

    res = (
        api_cal.getClient().events()
                .list(
                    calendarId=my_calendar,
                    timeMin=the_date,
                    singleEvents=True,
                    eventTypes='default',
                    orderBy="startTime",
                )
                .execute()
           )

    print("Upcoming events (up to 20):")
    for event in res['items'][:20]:
        print(f"- {api_cal.getPostTitle(event)}")

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    events_to_copy = []
    for event in res['items']:
        if api_cal.getPostTitle(event):
            if text_filter in api_cal.getPostTitle(event):
                events_to_copy.append(event)

    if not events_to_copy:
        print("No events found matching the criteria.")
        return

    print("Select events to copy:")
    for i, event in enumerate(events_to_copy):
        print(f"{i}) {api_cal.getPostTitle(event)}")

    print(f"{len(events_to_copy)}) All")

    selection = input("Which event(s) to copy? (comma-separated, or 'all') ")

    selected_events = []
    if selection.lower() == 'all' or selection == str(len(events_to_copy)):
        selected_events = events_to_copy
    else:
        try:
            indices = [int(i.strip()) for i in selection.split(',')]
            for i in indices:
                if 0 <= i < len(events_to_copy):
                    selected_events.append(events_to_copy[i])
        except ValueError:
            print("Invalid selection.")
            return

    if args.destination:
        my_calendar_dst = args.destination
    else:
        my_calendar_dst = select_calendar(api_cal)

    for event in selected_events:
        my_event = {'summary': event['summary'],
                   'description': event['description'],
                   'start': event['start'],
                   'end': event['end'],
                   }
        if 'location' in event:
                   my_event['location'] = event['location']

        api_cal.getClient().events().insert(calendarId=my_calendar_dst, body=my_event).execute()
        print(f"Copied event: {my_event['summary']}")

def delete_events_cli(args):
    """Deletes events from a calendar."""
    rules = moduleRules.moduleRules()
    rules.checkRules()
    api_cal = rules.selectRuleInteractive("gcalendar")

    if args.source:
        my_calendar = args.source
    else:
        my_calendar = select_calendar(api_cal)

    today = datetime.datetime.now()
    the_date = today.isoformat(timespec="seconds") + "Z"

    res = (
        api_cal.getClient().events()
                .list(
                    calendarId=my_calendar,
                    timeMin=the_date,
                    singleEvents=True,
                    eventTypes='default',
                    orderBy="startTime",
                )
                .execute()
           )

    print("Upcoming events (up to 20):")
    for event in res['items'][:20]:
        print(f"- {api_cal.getPostTitle(event)}")

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    events_to_delete = []
    for event in res['items']:
        if api_cal.getPostTitle(event):
            if text_filter in api_cal.getPostTitle(event):
                events_to_delete.append(event)

    if not events_to_delete:
        print("No events found matching the criteria.")
        return

    print("Select events to delete:")
    for i, event in enumerate(events_to_delete):
        print(f"{i}) {api_cal.getPostTitle(event)}")

    print(f"{len(events_to_delete)}) All")

    selection = input("Which event(s) to delete? (comma-separated, or 'all') ")

    selected_events = []
    if selection.lower() == 'all' or selection == str(len(events_to_delete)):
        selected_events = events_to_delete
    else:
        try:
            indices = [int(i.strip()) for i in selection.split(',')]
            for i in indices:
                if 0 <= i < len(events_to_delete):
                    selected_events.append(events_to_delete[i])
        except ValueError:
            print("Invalid selection.")
            return

    for event in selected_events:
        api_cal.getClient().events().delete(calendarId=my_calendar, eventId=event['id']).execute()
        print(f"Deleted event: {event['summary']}")

def move_events_cli(args):
    """Moves events from a source calendar to a destination calendar."""
    rules = moduleRules.moduleRules()
    rules.checkRules()
    api_cal = rules.selectRuleInteractive("gcalendar")

    if args.source:
        my_calendar = args.source
    else:
        my_calendar = select_calendar(api_cal)

    today = datetime.datetime.now()
    the_date = today.isoformat(timespec="seconds") + "Z"

    res = (
        api_cal.getClient().events()
                .list(
                    calendarId=my_calendar,
                    timeMin=the_date,
                    singleEvents=True,
                    eventTypes='default',
                    orderBy="startTime",
                )
                .execute()
           )

    print("Upcoming events (up to 20):")
    for event in res['items'][:20]:
        print(f"- {api_cal.getPostTitle(event)}")

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    events_to_move = []
    for event in res['items']:
        if api_cal.getPostTitle(event):
            if text_filter in api_cal.getPostTitle(event):
                events_to_move.append(event)

    if not events_to_move:
        print("No events found matching the criteria.")
        return

    print("Select events to move:")
    for i, event in enumerate(events_to_move):
        print(f"{i}) {api_cal.getPostTitle(event)}")

    print(f"{len(events_to_move)}) All")

    selection = input("Which event(s) to move? (comma-separated, or 'all') ")

    selected_events = []
    if selection.lower() == 'all' or selection == str(len(events_to_move)):
        selected_events = events_to_move
    else:
        try:
            indices = [int(i.strip()) for i in selection.split(',')]
            for i in indices:
                if 0 <= i < len(events_to_move):
                    selected_events.append(events_to_move[i])
        except ValueError:
            print("Invalid selection.")
            return

    if args.destination:
        my_calendar_dst = args.destination
    else:
        my_calendar_dst = select_calendar(api_cal)

    for event in selected_events:
        my_event = {'summary': event['summary'],
                   'description': event['description'],
                   'start': event['start'],
                   'end': event['end'],
                   }
        if 'location' in event:
                   my_event['location'] = event['location']

        api_cal.getClient().events().insert(calendarId=my_calendar_dst, body=my_event).execute()
        print(f"Copied event: {my_event['summary']}")
        api_cal.getClient().events().delete(calendarId=my_calendar, eventId=event['id']).execute()
        print(f"Deleted event: {event['summary']}")
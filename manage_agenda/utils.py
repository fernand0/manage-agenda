import datetime
from datetime import timedelta
import time
import json
import googleapiclient
import logging
import pytz  # Added pytz import

import urllib.request
import re

from bs4 import BeautifulSoup

from socialModules import moduleImap, moduleRules, moduleHtml
from socialModules.configMod import (
    CONFIGDIR,
    DATADIR,
    checkFile,
    fileNamePath,
    logMsg,
    select_from_list,
    safe_get,
)
from collections import namedtuple

# Define the default CET timezone using a specific IANA name.
# 'CET' is an abbreviation, so we use a common IANA timezone that observes CET.
# For example, 'Europe/Berlin' or 'Europe/Paris'. Let's use 'Europe/Berlin'.
try:
    DEFAULT_NAIVE_TIMEZONE = pytz.timezone("Europe/Berlin")
except pytz.exceptions.UnknownTimeZoneError:
    print(
        "Error: 'Europe/Berlin' is not a recognized timezone by pytz. Falling back to UTC."
    )
    DEFAULT_NAIVE_TIMEZONE = pytz.utc

from manage_agenda.utils_base import (
    setup_logging,
    write_file,
    format_time,
)  # , select_from_list
from manage_agenda.utils_llm import OllamaClient, GeminiClient, MistralClient

Args = namedtuple(
    "args", ["interactive", "delete", "source", "verbose", "destination", "text"]
)

def get_add_sources():
    """Returns a list of available sources for the add command."""
    from socialModules import moduleRules
    rules = moduleRules.moduleRules()
    rules.checkRules()
    email_sources = rules.selectRule("gmail", "") + rules.selectRule("imap", "")
    return email_sources + ["web"]


def print_first_10_lines(content, content_type="content"):
    """Prints the first 10 lines of the given content."""
    print(f"\n--- First 10 lines of {content_type} ---")
    for i, line in enumerate(content.splitlines()):
        if i >= 10:
            break
        print(line)
    print("-------------------------------------\n")


def select_calendar(calendar_api):
    """Selects a Google Calendar.
    FIXME: maybe it should be in socialModules?

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
        #"attendees": [],
    }


def process_event_data(event, content):
    """Processes event data, adding the email content to the description.

    Args:
        event (dict): The event dictionary.
        content (str): The content of the email.
    """
    event["description"] = f"{safe_get(event, ['description'])}\n\nMessage:\n{content}"
    #event["attendees"] = []  # Clear attendees
    return event


def adjust_event_times(event):
    """Adjusts event start/end times, localizing naive times to CET and converting all to UTC."""

    def _process_single_time_field(time_str, input_tz_name, field_name_for_logging):
        """
        Processes a single datetime string, localizes it, and converts to UTC.
        Returns (processed_iso_string, True if successful, False otherwise).
        """
        if not time_str:
            return None, False

        try:
            dt_obj = datetime.datetime.fromisoformat(time_str)

            if dt_obj.tzinfo is None:  # Naive datetime
                if input_tz_name:
                    try:
                        local_tz = pytz.timezone(input_tz_name)
                        dt_obj = local_tz.localize(dt_obj)
                    except pytz.exceptions.UnknownTimeZoneError:
                        print(
                            f"Validation Error: Unknown timezone "
                            f"'{input_tz_name}' for {field_name_for_logging} "
                            "time. Falling back to default CET."
                        )
                        dt_obj = DEFAULT_NAIVE_TIMEZONE.localize(dt_obj)
                else:
                    dt_obj = DEFAULT_NAIVE_TIMEZONE.localize(dt_obj)

            return dt_obj.astimezone(pytz.utc).isoformat(), True
        except ValueError:
            print(
                f"Validation Error: {field_name_for_logging} "
                f"time '{time_str}' is not a valid ISO 8601 format."
                "Skipping adjustment."
            )
            return None, False

    def _infer_missing_time(existing_dt_iso, target_field_dict, infer_type):
        """
        Infers a missing start or end time based on an existing time.
        existing_dt_iso: ISO formatted string of the existing datetime
        (already UTC).  target_field_dict: The 'start' or 'end' dictionary to
        update.  infer_type: 'start' to infer start from end, 'end' to infer
        end from start.
        """
        if not existing_dt_iso:
            return

        try:
            existing_dt = datetime.datetime.fromisoformat(
                existing_dt_iso
            )  # This is already UTC

            if infer_type == "start":
                inferred_dt = existing_dt - timedelta(minutes=30)
            elif infer_type == "end":
                inferred_dt = existing_dt + timedelta(minutes=30)
            else:
                return  # Should not happen

            target_field_dict["dateTime"] = inferred_dt.isoformat()
            target_field_dict["timeZone"] = "UTC"
        except ValueError:
            print(f"Error inferring {infer_type} time from existing time.")

    # Ensure start and end are dictionaries
    event.setdefault("start", {})
    event.setdefault("end", {})
    start = event["start"]
    end = event["end"]

    # Process start time
    start_time_str = start.get("dateTime")
    input_start_tz_name = start.get("timeZone")
    processed_start_time, start_success = _process_single_time_field(
        start_time_str, input_start_tz_name, "Start"
    )

    if start_success:
        start["dateTime"] = processed_start_time
        start["timeZone"] = "UTC"

    # Process end time
    end_time_str = end.get("dateTime")
    input_end_tz_name = end.get("timeZone")
    processed_end_time, end_success = _process_single_time_field(
        end_time_str, input_end_tz_name, "End"
    )

    if end_success:
        end["dateTime"] = processed_end_time
        end["timeZone"] = "UTC"

    # Inference logic
    if not start.get("dateTime") and end.get("dateTime"):
        _infer_missing_time(end["dateTime"], start, "start")

    if not end.get("dateTime") and start.get("dateTime"):
        _infer_missing_time(start["dateTime"], end, "end")

    # Ensure end time is after start time
    if start.get("dateTime") and end.get("dateTime"):
        try:
            start_dt = datetime.datetime.fromisoformat(start["dateTime"])
            end_dt = datetime.datetime.fromisoformat(end["dateTime"])

            if end_dt <= start_dt:
                print("Validation Warning: End time is not after start time. Adjusting end time.")
                end_dt = start_dt + timedelta(minutes=30)
                end["dateTime"] = end_dt.isoformat()
                end["timeZone"] = "UTC"  # Ensure timezone is set if adjusted
        except ValueError:
            print("Error comparing start and end times. Skipping adjustment.")

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

    if not text.startswith('{'):
        pos = text.find('{')
        if pos != -1:
            text = text[pos:]
    if not text.endswith('}'):
        pos = text.rfind('}')
        if pos != -1:
            text = text[:pos+1]
    vcal_json = text
    # if "```" in text:
    #     start_index = text.find("```")
    #     end_index = text.find("```", start_index + 1)
    #     vcal_json = text[
    #         start_index + 8 : end_index
    #     ].strip()  # extract content between backticks
    # elif "<think>" in text:
    #     start_index = text.find("/think")
    #     vcal_json = text[start_index + 9 :].strip()
    # else:
    #     vcal_json = text

    return vcal_json


def get_event_from_llm(model, prompt, verbose=False):
    """Gets event data from LLM, handling response and JSON parsing."""
    print("Calling LLM")
    event, vcal_json = None, None
    start_time = time.time()
    llm_response = model.generate_text(prompt)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"AI call took {format_time(elapsed_time)} ({elapsed_time:.2f} seconds)")

    if not llm_response:
        print("Failed to get response from LLM.")

    if verbose:
        print(f"Reply:\n{llm_response}")
        print(f"End Reply")
    llm_response = llm_response.replace("\\", "").replace("\n", " ")

    try:
        import ast

        vcal_json = ast.literal_eval(extract_json(llm_response))
        if verbose:
            print(f"Json:\n{vcal_json}")
            print(f"Json:\n{type(vcal_json)}")
        event = vcal_json
        print(f"Event: {event}")

        # event = json.loads(vcal_json)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in vCal data: {vcal_json}")
        logging.error(f"Error: {e}")
    except SyntaxError as e:
        logging.error(f"Syntax error: {vcal_json}")
        logging.error(f"Error: {e}")
    print("Aquíiii")

    return event, vcal_json


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


def select_api_source(args, api_src_type):
    """Selects an API source, interactive or not."""
    rules = moduleRules.moduleRules()
    rules.checkRules()

    if args.interactive:
        api_src = rules.selectRuleInteractive(api_src_type)
    else:
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


def _get_emails_from_folder(args, source_name=None):
    """Helper function to get emails from a specific folder."""
    "FIXME: maybe a folder argument?"
    if source_name:
        from socialModules import moduleRules
        rules = moduleRules.moduleRules()
        rules.checkRules()
        source_details = rules.more.get(source_name, {})
        api_src = rules.readConfigSrc("", source_name, source_details)
    else:
        api_src_type = ["gmail", "imap"]
        api_src = select_api_source(args, api_src_type)

    if not api_src.getClient():
        print("Some problem with the account")
        return None, None

    folder = "INBOX/zAgenda" if "imap" in api_src.service.lower() else "zAgenda"
    api_src.setPostsType("posts")
    api_src.setLabels()
    label = api_src.getLabels(folder)
    if not label:
        print(f"There are no posts tagged with label {folder}")
        return api_src, None

    label_id = safe_get(label[0], ["id"])
    api_src.setChannel(folder)
    api_src.setPosts()
    posts = api_src.getPosts()

    if not posts:
        print(f"There are no posts tagged with label {folder}")
        return api_src, None

    return api_src, posts


def list_emails_folder(args):
    """Lists emails and in folder."""
    api_src, posts = _get_emails_from_folder(args)
    if posts:
        for i, post in enumerate(posts):
            # post_id = api_src.getPostId(post)
            # post_date = api_src.getPostDate(post)
            post_title = api_src.getPostTitle(post)
            print(f"{i}) {post_title}")


def _create_llm_prompt(event, content_text, reference_date_time):
    """Constructs the LLM prompt for event extraction."""
    content_text = content_text.replace('\r','')
    return (
        "Rellenar los datos del JSON:\n"
        f"{event}\n"
        "Puedes obtener los datos en el cuerpo del mensaje ('Message:') o en "
        "el asunto ('Subject:'). "
        "La fecha que se marca con 'Message date:' se usa como una referencia "
        "cuando se indican fechas relativas como por ejemplo, 'el próximo jueves'.\n"
        "Si no se indica otra cosa la timezone es CET.\n"
        "El resultado incluye un json y sus campos y contenidos deben ir entre comillas dobles. "
        "El inicio y el fin de la actividad son fechas y se pondrán en los campos event['start']['dateTime']  y "
        " event['end']['dateTime'] respectivamente" #, y serán fechas iguales o "
        # f"posteriores a {reference_date_time}. "
        "No traduzcas el texto, conserva la información en el idioma en que se presenta.\n"
        "No añadas comentarios al resultado que se representará como un JSON."
        f"El texto es:\n"
        f"{content_text}.\n"
    )


def _interactive_date_confirmation(args, event):
    """Interactively confirms and corrects event dates."""
    if args.interactive:
        confirmation = input("Are the dates correct? (y/n): ").lower()
        if confirmation != 'y':
            new_start_str = input("Enter new start time (YYYY-MM-DD HH:MM:SS) or leave empty: ")
            if new_start_str:
                event.setdefault("start", {})["dateTime"] = new_start_str
                try:
                    start_dt = datetime.datetime.strptime(new_start_str, "%Y-%m-%d %H:%M:%S")
                    end_dt = start_dt + timedelta(minutes=45)
                    new_end_str_default = end_dt.strftime("%Y-%m-%d %H:%M:%S")

                    modify_end_time = input(f"Default end time will be {new_end_str_default}. Do you want to modify it? (y/n): ").lower()
                    if modify_end_time == 'y':
                        new_end_str = input("Enter new end time (YYYY-MM-DD HH:MM:SS) or leave empty: ")
                    else:
                        new_end_str = new_end_str_default
                except ValueError:
                    print("Invalid start time format. Please use YYYY-MM-DD HH:MM:SS.")
                    new_end_str = ""
            else:
                new_end_str = input("Enter new end time (YYYY-MM-DD HH:MM:SS) or leave empty: ")

            if new_end_str:
                event.setdefault("end", {})["dateTime"] = new_end_str

            event = adjust_event_times(event)

            # Update and print new times
            start_time = safe_get(event, ["start", "dateTime"])
            end_time = safe_get(event, ["end", "dateTime"])
            print("--- Updated Event Times ---")
            print(f"Start: {start_time}")
            print(f"End: {end_time}")
            print("---------------------------")
    return event


def _process_event_with_llm_and_calendar(
    args,
    model,
    content_text,
    reference_date_time,
    post_identifier,
    subject_for_print,
):
    """
    Common logic for processing an event with LLM, adjusting times, and publishing to calendar.
    """
    # Create initial event dict for helper

    event = create_event_dict()
    prompt = _create_llm_prompt(event, content_text, reference_date_time)
    if args.verbose:
        print(f"Prompt:\n{prompt}")
        print(f"\nEnd Prompt:")

    # Get AI reply
    event, vcal_json = get_event_from_llm(model, prompt, args.verbose)
    print(f"Event: {event}")
    process_event_data(event, content_text)
    adjust_event_times(event)

    if not event:
        return None, None  # Indicate failure

    write_file(f"{post_identifier}.vcal", vcal_json)  # Save vCal data

    api_dst_type = "gcalendar"
    api_dst = select_api_source(args, api_dst_type)

    # --- LLM Response Validation/Retry Loop ---
    retries = 0
    max_retries = 3  # Limit AI retries
    data_complete = False

    while not data_complete and retries <= max_retries:
        summary = event.get("summary")
        start_datetime = event.get("start", {}).get("dateTime")

        if not summary:
            print("- Summary")
            summary = subject_for_print
            if summary:
                event["summary"] = summary

        if summary and start_datetime:
            data_complete = True
            break

        if args.interactive:
            print("Missing event information:")
            if not summary:
                print("- Summary")
            if not start_datetime:
                print("- Start Date/Time")

            choice = input(
                "Options: (m)anual input, (a)nother AI, (s)kip item: "
            ).lower()  # Generalized message

            if choice == "m":
                if not summary:
                    new_summary = input("Enter Summary: ")
                    if new_summary:
                        event["summary"] = new_summary
                if not start_datetime:
                    new_start_datetime_str = input(
                        "Enter Start Date/Time (YYYY-MM-DD HH:MM:SS): "
                    )
                    if new_start_datetime_str:
                        try:
                            new_start_datetime = datetime.datetime.strptime(
                                new_start_datetime_str, "%Y-%m-%d %H:%M:%S"
                            )
                            event.setdefault("start", {})["dateTime"] = (
                                new_start_datetime.isoformat()
                            )
                            # Removed event['start'].setdefault('timeZone', 'Europe/Madrid') as adjust_event_times handles it
                        except ValueError:
                            print(
                                "Invalid date/time format. Please use YYYY-MM-DD HH:MM:SS."
                            )
                            continue
                data_complete = True
            elif choice == "a":
                retries += 1
                if retries > max_retries:
                    print(
                        "Max AI retries reached. Skipping item."
                    )  # Generalized message
                    break

                print("Selecting another AI model...")
                original_model = model
                original_args_source = args.source

                new_args = Args(
                    interactive=True,
                    delete=args.delete,
                    source=None,
                    verbose=args.verbose,
                    destination=args.destination,
                    text=args.text,
                )
                new_model = select_llm(new_args)

                if new_model:
                    model = new_model
                    print(f"Trying with new AI model: {model.__class__.__name__}")
                    new_event, new_vcal_json = get_event_from_llm(
                        model, prompt, args.verbose
                    )
                    if new_event:
                        event = new_event
                        vcal_json = new_vcal_json
                    else:
                        print("New AI model failed to generate a response.")
                else:
                    print(
                        "No new AI model selected or available. Skipping item."
                    )  # Generalized message
                    break
            elif choice == "s":
                break
            else:
                print("Invalid choice. Please try again.")
                retries += 1
                continue
        else:  # Non-interactive mode
            if not summary or not start_datetime:
                logging.warning(
                    f"Missing summary or start_datetime for {post_identifier}. Skipping."
                )
                break
            else:
                data_complete = True

    if not data_complete:
        return None, None  # Indicate failure

    # --- Event Adjustment ---
    event = adjust_event_times(event)
    write_file(f"{post_identifier}.json", json.dumps(event))  # Save event JSON
    write_file(
        f"{post_identifier}_times.json", json.dumps(event)
    )  # Save event JSON (redundant, but existing)

    start_time = safe_get(event, ["start", "dateTime"])
    end_time = safe_get(event, ["end", "dateTime"])

    start_time_local = (
        datetime.datetime.fromisoformat(start_time).astimezone()
        if start_time
        else "N/A"
    )
    end_time_local = (
        datetime.datetime.fromisoformat(end_time).astimezone() if end_time else "N/A"
    )

    print(f"=====================================")
    print(f"Subject: {subject_for_print}")  # Use dynamic subject
    print(f"Start: {start_time_local}")
    print(f"End: {end_time_local}")
    print(f"=====================================")

    event = _interactive_date_confirmation(args, event)

    selected_calendar = select_calendar(api_dst)
    if not selected_calendar:
        print("No calendar selected, skipping event creation.")
        return None, None

    try:
        calendar_result = api_dst.publishPost(
            post={"event": event, "idCal": selected_calendar}, api=api_dst
        )
        print(f"Calendar event created")
        return event, calendar_result  # Return event and result for further processing
    except googleapiclient.errors.HttpError as e:
        logging.error(f"Error creating calendar event: {e}")
        return None, None


def _get_post_datetime_and_diff(post_date):
    """
    Calculates the post datetime and the difference in days from now.

    Args:
        post_date (str): The date of the post.

    Returns:
        tuple: A tuple containing the post datetime and the time difference in days.
    """
    if post_date.isdigit():
        post_date_time = datetime.datetime.fromtimestamp(int(post_date) / 1000)
    else:
        from email.utils import parsedate_to_datetime

        post_date_time = parsedate_to_datetime(post_date)

    try:
        import pytz

        time_difference = (
            pytz.timezone("Europe/Madrid").localize(datetime.datetime.now())
            - post_date_time
        )
        logging.debug(f"Date: {post_date_time} Diff: {time_difference.days}")
    except:
        # FIXME
        time_difference = datetime.datetime.now() - datetime.datetime.now()

    return post_date_time, time_difference


def _delete_email(args, api_src, post_id):
    """Deletes an email, handling interactive confirmation."""
    delete_confirmed = False
    if args.interactive:
        confirmation = input(
            "Do you want to remove the label from the email? (y/n): "
        )
        if confirmation.lower() == "y":
            delete_confirmed = True
    elif (
        args.delete
    ):  # Only auto-confirm if not interactive but delete flag is set
        delete_confirmed = True

    if delete_confirmed:
        if "imap" not in api_src.service.lower():
            print(f"label: {api_src.getChannel()}")
            logging.info(f"label: {api_src.getChannel()}")
            folder = api_src.getChannel()
            label = api_src.getLabels(folder)
            logging.info(f"label: {label}")
            res = api_src.modifyLabels(post_id, label[0], None)
            logging.info(f"Label removed from email {post_id}.")
        else:
            api_src.deletePostId(post_id)

def _is_email_too_old(args, time_difference):
    """Checks if an email is too old and confirms processing if interactive."""
    if time_difference.days > 7:
        if args.interactive:
            confirmation = input(
                f"El correo tiene {time_difference.days} dias. ¿Desea procesarlo? (y/n): "
            )
            if confirmation.lower() != "y":
                return True
        else:
            if args.verbose:
                print(f"Too old ({time_difference.days} days), skipping.")
            return True
    return False

def process_email_cli(args, model, source_name=None):
    """Processes emails and creates calendar events."""

    api_src, posts = _get_emails_from_folder(args, source_name)

    if posts:
        processed_any_event = False
        for post in posts:
            post_id = api_src.getPostId(post)
            post_date = api_src.getPostDate(post)
            post_title = api_src.getPostTitle(post)

            print(f"Processing Title: {post_title}", flush=True)
            post_date_time, time_difference = _get_post_datetime_and_diff(post_date)

            if _is_email_too_old(args, time_difference):
                continue

            full_email_content = api_src.getPostBody(post)

            if isinstance(full_email_content, bytes):
                # FIXME: does this belong here?
                full_email_content = full_email_content.decode("utf-8")

            full_email_content = re.sub(r"\n{3,}", "\n\n", full_email_content)

            email_text = (
                    f"Subject: {post_title}\n"
                    f"Message: {full_email_content}\n"
                    f"Message date: {post_date_time}\n"
            )
            write_file(f"{post_id}.txt", email_text)  # Save email text

            print_first_10_lines(email_text, "email content")

            # Call the common helper function
            processed_event, calendar_result = _process_event_with_llm_and_calendar(
                args,
                model,
                email_text,
                post_date_time,
                post_id,
                post_title,
            )

            if processed_event is None:
                continue  # Skip to the next email if helper failed
            else:
                processed_any_event = (
                    True  # Mark that at least one event was processed
                )

            _delete_email(args, api_src, post_id)

        return processed_any_event  # Return True if any event was processed, False otherwise
    return False  # Default return if something went wrong before the main logic

def process_web_cli(args, model):

    """Processes web pages and creates calendar events."""

    urls = input("Enter URLs separated by spaces: ").split()

    if urls:
        processed_any_event = False
        page = moduleHtml.moduleHtml()
        print(urls)
        page.setUrl(urls)
        page.setApiPosts()
        print(page.getPosts())
        for i, post in enumerate(page.getPosts()):
            url = page.url[i]
            print(f"Processing URL: {page.url}", flush=True)

            rules = moduleRules.moduleRules()
            post_id = rules.cleanUrlRule(url)
            post_title = page.getPostTitle(post)
            post_date = datetime.datetime.now()

            print(f"Processing Title: {post_title}", flush=True)

            # if isinstance(web_content_html, bytes):
            #     web_content_html = web_content_html.decode("utf-8", errors="ignore")

            # soup = BeautifulSoup(web_content_html, "html.parser")

            # web_content = soup.get_text()
            # web_content = re.sub(r"\n{3,}", "\n\n", web_content)

            web_content_text = (
                    f"Url: {url}\n"
                    f"Message date: {post_date}\n"
                    f"Subject: {post_title}\n"
                    f"Message: {page.getPostContent(post)}"
            )

            write_file(f"{post_id}.txt", web_content_text)  # Save email text

            print_first_10_lines(web_content_text, "web content")

            # Call the common helper function

            processed_event, calendar_result = _process_event_with_llm_and_calendar(
                args,
                model,
                web_content_text,
                post_date,
                post_id,
                post_title,  # post_identifier and subject_for_print can both be url
            )


            if processed_event is None:
                continue  # Skip if helper failed
            else:
                processed_any_event = (
                    True  # Mark that at least one event was processed
                )

        return processed_any_event  # Return True if any event was processed, False otherwise

    return False  # Default return if something went wrong before the main logic


def select_email_prompt(args):
    """Interactively selects an email and returns its content."""
    api_src_type = ["gmail", "imap"]
    api_src = select_api_source(args, api_src_type)

    if not api_src.getClient():
        print("Failed to connect to the email account.")
        return None

    api_src.setLabels()
    labels = api_src.getLabels()
    # names = [safe_get(label, ["name"]) for label in labels]

    label_name = "INBOX/zAgenda" if "imap" in api_src.service.lower() else "zAgenda"
    api_src.setChannel(label_name)
    api_src.setPosts()
    posts = api_src.getPosts()

    if not posts:
        print(f"No emails found in folder '{label_name}'.")
        return None

    titles = [api_src.getPostTitle(post) for post in posts]
    sel, post_title = select_from_list(titles)

    selected_post = posts[sel]

    full_email_content = api_src.getPostBody(selected_post)
    if isinstance(full_email_content, bytes):
        full_email_content = full_email_content.decode("utf-8")

    return full_email_content


def select_llm(args):
    """Selects and initializes the appropriate LLM client."""
    if args.interactive:
        selection = input("Local/mistral/gemini model )(l/m/g)? ")
        if selection == "l":
            args = Args(
                interactive=args.interactive,
                delete=args.delete,
                source="ollama",
                verbose=args.verbose,
                destination=args.destination,
                text=args.text,
            )
        elif selection == "m":
            args = Args(
                interactive=args.interactive,
                delete=args.delete,
                source="mistral",
                verbose=args.verbose,
                destination=args.destination,
                text=args.text,
            )
        else:
            args = Args(
                interactive=args.interactive,
                delete=args.delete,
                source="gemini",
                verbose=args.verbose,
                destination=args.destination,
                text=args.text,
            )
    else:
        args = Args(
            interactive=args.interactive,
            delete=args.delete,
            source="gemini",
            verbose=args.verbose,
            destination=args.destination,
            text=args.text,
        )

    if args.source == "ollama":
        model = OllamaClient()
        return model
    elif args.source == "gemini":
        if args.interactive:
            model = GeminiClient()
        else:
            model = GeminiClient("gemini-2.5-flash")
        return model
    elif args.source == "mistral":
        model = MistralClient()
        return model
    else:
        logging.error(f"Invalid LLM source: {args.source}")
        return None


def copy_events_cli(args):
    """Copies events from a source calendar to a destination calendar."""
    api_cal = select_api_source(args, "gcalendar")

    if args.source:
        my_calendar = args.source
    else:
        my_calendar = select_calendar(api_cal)

    today = datetime.datetime.now()
    the_date = today.isoformat(timespec="seconds") + "Z"

    res = (
        api_cal.getClient()
        .events()
        .list(
            calendarId=my_calendar,
            timeMin=the_date,
            singleEvents=True,
            eventTypes="default",
            orderBy="startTime",
        )
        .execute()
    )

    print("Upcoming events (up to 20):")
    for event in res["items"][:20]:
        print(f"- {api_cal.getPostTitle(event)}")

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    events_to_copy = []
    for event in res["items"]:
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
    if selection.lower() == "all" or selection == str(len(events_to_copy)):
        selected_events = events_to_copy
    else:
        try:
            indices = [int(i.strip()) for i in selection.split(",")]
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
        my_event = {
            "summary": event["summary"],
            "description": event["description"],
            "start": event["start"],
            "end": event["end"],
        }
        if "location" in event:
            my_event["location"] = event["location"]

        api_cal.getClient().events().insert(
            calendarId=my_calendar_dst, body=my_event
        ).execute()
        print(f"Copied event: {my_event['summary']}")


def delete_events_cli(args):
    """Deletes events from a calendar."""
    api_cal = select_api_source(args, "gcalendar")

    if args.source:
        my_calendar = args.source
    else:
        my_calendar = select_calendar(api_cal)

    today = datetime.datetime.now()
    the_date = today.isoformat(timespec="seconds") + "Z"

    res = (
        api_cal.getClient()
        .events()
        .list(
            calendarId=my_calendar,
            timeMin=the_date,
            singleEvents=True,
            eventTypes="default",
            orderBy="startTime",
        )
        .execute()
    )

    print("Upcoming events (up to 20):")
    for event in res["items"][:20]:
        print(f"- {api_cal.getPostTitle(event)}")

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    events_to_delete = []
    for event in res["items"]:
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
    if selection.lower() == "all" or selection == str(len(events_to_delete)):
        selected_events = events_to_delete
    else:
        try:
            indices = [int(i.strip()) for i in selection.split(",")]
            for i in indices:
                if 0 <= i < len(events_to_delete):
                    selected_events.append(events_to_delete[i])
        except ValueError:
            print("Invalid selection.")
            return

    for event in selected_events:
        api_cal.getClient().events().delete(
            calendarId=my_calendar, eventId=event["id"]
        ).execute()
        print(f"Deleted event: {event['summary']}")


def move_events_cli(args):
    """Moves events from a source calendar to a destination calendar."""
    api_cal = select_api_source(args, "gcalendar")

    if args.source:
        my_calendar = args.source
    else:
        my_calendar = select_calendar(api_cal)

    today = datetime.datetime.now()
    the_date = today.isoformat(timespec="seconds") + "Z"

    res = (
        api_cal.getClient()
        .events()
        .list(
            calendarId=my_calendar,
            timeMin=the_date,
            singleEvents=True,
            eventTypes="default",
            orderBy="startTime",
        )
        .execute()
    )

    print("Upcoming events (up to 20):")
    for event in res["items"][:20]:
        print(f"- {api_cal.getPostTitle(event)}")

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    events_to_move = []
    for event in res["items"]:
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
    if selection.lower() == "all" or selection == str(len(events_to_move)):
        selected_events = events_to_move
    else:
        try:
            indices = [int(i.strip()) for i in selection.split(",")]
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
        my_event = {
            "summary": event["summary"],
            "description": event["description"],
            "start": event["start"],
            "end": event["end"],
        }
        if "location" in event:
            my_event["location"] = event["location"]

        api_cal.getClient().events().insert(
            calendarId=my_calendar_dst, body=my_event
        ).execute()
        print(f"Copied event: {my_event['summary']}")
        api_cal.getClient().events().delete(
            calendarId=my_calendar, eventId=event["id"]
        ).execute()
        print(f"Deleted event: {event['summary']}")

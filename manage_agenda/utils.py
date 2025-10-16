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

from socialModules import moduleImap, moduleRules
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
                            f"Validation Error: Unknown timezone '{input_tz_name}' for {field_name_for_logging} time. Falling back to default CET."
                        )
                        dt_obj = DEFAULT_NAIVE_TIMEZONE.localize(dt_obj)
                else:
                    dt_obj = DEFAULT_NAIVE_TIMEZONE.localize(dt_obj)

            return dt_obj.astimezone(pytz.utc).isoformat(), True
        except ValueError:
            print(
                f"Validation Error: {field_name_for_logging} time '{time_str}' is not a valid ISO 8601 format. Skipping adjustment."
            )
            return None, False

    def _infer_missing_time(existing_dt_iso, target_field_dict, infer_type):
        """
        Infers a missing start or end time based on an existing time.
        existing_dt_iso: ISO formatted string of the existing datetime (already UTC).
        target_field_dict: The 'start' or 'end' dictionary to update.
        infer_type: 'start' to infer start from end, 'end' to infer end from start.
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
    if "```" in text:
        start_index = text.find("```")
        end_index = text.find("```", start_index + 1)
        vcal_json = text[
            start_index + 8 : end_index
        ].strip()  # extract content between backticks
    elif "<think>" in text:
        start_index = text.find("/think")
        vcal_json = text[start_index + 9 :].strip()
    else:
        vcal_json = text

    return vcal_json


def get_event_from_llm(model, prompt, verbose=False):
    """Gets event data from LLM, handling response and JSON parsing."""
    print("Calling LLM")
    start_time = time.time()
    llm_response = model.generate_text(prompt)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"AI call took {format_time(elapsed_time)} ({elapsed_time:.2f} seconds)")

    if not llm_response:
        print("Failed to get response from LLM.")
        return None, None

    if verbose:
        print(f"Reply:\n{llm_response}")
    llm_response = llm_response.replace("\\", "").replace("\n", " ")

    try:
        import ast

        vcal_json = ast.literal_eval(extract_json(llm_response))
        if verbose:
            print(f"Json:\n{vcal_json}")
            print(f"Json:\n{type(vcal_json)}")
        event = vcal_json

        # event = json.loads(vcal_json)
        return event, vcal_json
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in vCal data: {vcal_json}")
        logging.error(f"Error: {e}")
        return None, None


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
                    if True:  # i < 10:
                        post_id = api_src.getPostId(post)
                        post_date = api_src.getPostDate(post)
                        post_title = api_src.getPostTitle(post)
                        print(f"{i}) {post_title}")
    else:
        print("Some problem with the account")


def _create_llm_prompt(event, content_text, reference_date_time):
    """Constructs the LLM prompt for event extraction."""
    return (
        f"Rellenar los datos del diccionario {event}.\n"
        "Buscamos datos relativos a una actividad. "
        "El inicio y el fin se pondrán en "
        " los campos event['start']['dateTime']  y "
        " event['end']['dateTime'] respectivamente,"
        f" y serán fechas iguales o "
        f"posteriores a {reference_date_time}. "
        "La fecha del mensaje que se indica con 'Date:' "
        "es una referencia. Si no se indica otra cosa "
        "la timezone es Central European Time (CET)"
        " No añadas comentarios al resultado, que"
        " se representará como un JSON."
        "El resultado incluye un json y sus campos y "
        "contenidos deben ir entre comillas dobles. "
        f"El texto es:\n{content_text}"
    )


def _process_event_with_llm_and_calendar(
    args,
    model,
    event_dict,
    content_text,
    reference_date_time,
    post_identifier,
    subject_for_print,
):
    """
    Common logic for processing an event with LLM, adjusting times, and publishing to calendar.
    """
    event = event_dict  # Use the passed-in event_dict
    prompt = _create_llm_prompt(event, content_text, reference_date_time)
    if args.verbose:
        print(f"Prompt:\n{prompt}")
        print(f"\nEnd Prompt:")

    # Get AI reply
    event, vcal_json = get_event_from_llm(model, prompt, args.verbose)
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
    print(f"====================================")
    print(f"Subject: {subject_for_print}")  # Use dynamic subject
    print(f"Start: {start_time}")
    print(f"End: {end_time}")
    print(f"====================================")

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


def process_email_cli(args, model):
    """Processes emails and creates calendar events."""

    api_src_type = ["gmail", "imap"]
    api_src = select_api_source(args, api_src_type)

    # Process emails
    folder = "INBOX/zAgenda" if "imap" in api_src.service.lower() else "zAgenda"
    # folder = "zAgenda"
    api_src.setPostsType("posts")
    api_src.setLabels()
    label = api_src.getLabels(folder)
    if args.verbose:
        print(f"Label: {label}")
    if len(label) > 0:
        api_src.setChannel(label[0])
        api_src.setPosts()

        if api_src.getPosts():
            processed_any_event = False
            for i, post in enumerate(api_src.getPosts()):
                post_id = api_src.getPostId(post)
                post_date = api_src.getPostDate(post)
                post_title = api_src.getPostTitle(post)

                print(f"Processing Title: {post_title}", flush=True)
                post_content = api_src.getPostContent(post)
                logging.debug(f"Text: {post_content}")
                if post_date.isdigit():
                    post_date_time = datetime.datetime.fromtimestamp(
                        int(post_date) / 1000
                    )
                else:
                    from email.utils import parsedate_to_datetime

                    post_date_time = parsedate_to_datetime(post_date)

                try:
                    import pytz

                    time_difference = (
                        pytz.timezone("Europe/Madrid").localize(datetime.datetime.now())
                        - post_date_time
                    )
                    logging.debug(
                        f"Date: {post_date_time} Diff: {time_difference.days}"
                    )
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

                email_result = post
                if args.verbose:
                    print(f"email: {email_result}")
                full_email_content = api_src.getPostBody(email_result)

                if hasattr(full_email_content, "decode"):
                    full_email_content = full_email_content.decode("utf-8")

                email_text = (
                    f"{post_title}\nDate:{post_date_time}\n{full_email_content}"
                )
                write_file(f"{post_id}.txt", email_text)  # Save email text

                # Create initial event dict for helper
                initial_event = create_event_dict()
                # Call the common helper function
                processed_event, calendar_result = _process_event_with_llm_and_calendar(
                    args,
                    model,
                    initial_event,
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

                # --- CORRECCIÓN DE TIMEZONE --- (Email specific, uses calendar_result from helper)
                # calendar_result can be None if _process_event_with_llm_and_calendar failed before publishing
                if (
                    calendar_result
                    and "Invalid time zone definition for end time.'"
                    in str(calendar_result)
                ):  # Ensure calendar_result is string for check
                    print("Corrigiendo zona horaria inválida en 'end'...")
                    # Re-assign event for email-specific correction
                    event_for_correction = processed_event
                    if event_for_correction.get("end"):
                        event_for_correction["end"]["timeZone"] = "Europe/Madrid"
                    if event_for_correction.get("start"):
                        event_for_correction["start"]["timeZone"] = "Europe/Madrid"
                    try:
                        # Re-select api_dst and calendar as they are created inside the helper
                        api_dst = select_api_source(
                            args, "gcalendar"
                        )  # Need to re-select api_dst
                        selected_calendar = select_calendar(
                            api_dst
                        )  # Need to re-select calendar
                        _ = api_dst.publishPost(  # _ is used as this is a re-publish, calendar_result not updated here
                            post={
                                "event": event_for_correction,
                                "idCal": selected_calendar,
                            },
                            api=api_dst,
                        )
                        print("Calendar event re-creado tras corregir zona horaria.")
                    except Exception as e:
                        logging.error(f"Error tras corregir zona horaria: {e}")

                # Delete email (optional)
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
                        res = api_src.modifyLabels(post_id, api_src.getChannel(), None)
                        logging.info(f"Label removed from email {post_id}.")
                    else:
                        flag = "\\Deleted"
                        try:
                            api_src.getClient().store(post_id, "+FLAGS", flag)
                            logging.info(f"Email {post_id} marked for deletion.")
                        except Exception as e:
                            logging.warning(
                                f"IMAP store failed: {e}. Reconnecting and retrying..."
                            )
                            try:
                                api_src.checkConnected()
                                api_src.getClient().store(post_id, "+FLAGS", flag)
                                logging.info(
                                    f"Email {post_id} marked for deletion after reconnect."
                                )
                            except Exception as e2:
                                logging.error(
                                    f"Failed to mark email for deletion after reconnect: {e2}"
                                )
            return processed_any_event  # Return True if any event was processed, False otherwise
        else:
            print(f"There are no posts tagged with label {folder}")
            return True  # No posts, but not an error
    else:
        print(f"There are no posts tagged with label {folder}")
        return True  # No labels, but not an error
    return False  # Default return if something went wrong before the main logic

def process_web_cli(args, model):
    """Processes web pages and creates calendar events."""

    rules = moduleRules.moduleRules()
    rules.checkRules()

    url = input("URL: ")

    print(f"Processing URL: {url}", flush=True)

    post_date_time = datetime.datetime.now()

    if True:
        with urllib.request.urlopen(url) as response:
            web_content_html = response.read()

        if args.verbose:
            print(f"Web content html: {web_content_html}")
            print(web_content_html[416])
            print(web_content_html[410:419])

        if isinstance(web_content_html, bytes):
            web_content_html = web_content_html.decode("utf-8", errors="ignore")

        if args.verbose:
            print(f"Web content html: {web_content_html}")

        soup = BeautifulSoup(web_content_html, "html.parser")
        print(f"Soup: {soup}")
        web_content = soup.get_text()

        print(f"Web content: {web_content}")

        web_content = re.sub(r"\n{3,}", "\n\n", web_content)

        print("\n--- First 10 lines of web content ---")
        for i, line in enumerate(web_content.splitlines()):
            if i >= 10:
                break
            print(line)
        print("-------------------------------------")

    else:  # except Exception as e:
        print(f"Error fetching or parsing URL: {e}")
        return

    # Create initial event dict and add web-specific description
    initial_event = create_event_dict()
    description = safe_get(initial_event, ["description"]) or ""
    initial_event["description"] = f"URL: {url}\n\n{description}\n\n{web_content}"
    #initial_event["attendees"] = []  # Clear attendees as per original logic

    # Call the common helper function
    processed_event, _ = _process_event_with_llm_and_calendar(
        args,
        model,
        initial_event,
        web_content,
        post_date_time,
        url,
        url,  # post_identifier and subject_for_print can both be url
    )

    if processed_event is None:
        return  # Skip if helper failed


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
    if hasattr(full_email_content, "decode"):
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

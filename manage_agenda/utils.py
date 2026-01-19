import datetime
import json
import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

import googleapiclient
import pytz
from socialModules import moduleHtml, moduleRules
from socialModules.configMod import (
    safe_get,
    select_from_list,
)

from manage_agenda.config import config
from manage_agenda.exceptions import (
    CalendarError,
)

# Constant for date confirmation prompt to avoid duplication
DATE_CONFIRMATION_PROMPT_NO_RETRY = (
    "Are the dates correct? "
    "Ye(s), "
    "(Y)ear, (M)onth, (D)ay, (h)our, m(i)nute, (f)ull date/time: "
)

DATE_CONFIRMATION_PROMPT_WITH_R_OPTION = (
    "Are the dates correct? "
    "Ye(s), (r)etry with LLM, "
    "(Y)ear, (M)onth, (D)ay, (h)our, m(i)nute, (f)ull date/time: "
)

# Define the default timezone from config
try:
    DEFAULT_NAIVE_TIMEZONE = pytz.timezone(config.DEFAULT_TIMEZONE)
except pytz.exceptions.UnknownTimeZoneError:
    logging.error(f"Invalid timezone '{config.DEFAULT_TIMEZONE}' in config. Falling back to UTC.")
    DEFAULT_NAIVE_TIMEZONE = pytz.utc

from manage_agenda.utils_base import (
    format_time,
    write_file,
)
from manage_agenda.utils_llm import GeminiClient, MistralClient, OllamaClient
from manage_agenda.utils_web import reduce_html

@dataclass
class Args:
    """Arguments container for CLI commands."""

    interactive: bool = False
    delete: Optional[bool] = None
    source: Optional[str] = None
    verbose: bool = False
    destination: Optional[str] = None
    text: Optional[str] = None




def get_add_sources(rules=None):
    """Returns a list of available sources for the add command."""
    if rules is None:
        from socialModules import moduleRules
        rules = moduleRules.moduleRules()
        rules.checkRules()
    email_sources = rules.selectRule("gmail", "") + rules.selectRule("imap", "")
    return email_sources + ["Web (Enter URL)"]


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

    Args:
        calendar_api: An object to interact with the Google Calendar API.

    Returns:
        The ID of the selected calendar.

    Raises:
        CalendarError: If calendar selection fails.
    """
    try:
        calendar_api.setCalendarList()
        calendars = calendar_api.getCalendarList()

        if not calendars:
            raise CalendarError("No calendars found in your Google Calendar account")

        eligible_calendars = [cal for cal in calendars if "reader" not in cal.get("accessRole", "")]

        if not eligible_calendars:
            raise CalendarError("No writable calendars found. Check your calendar permissions.")

        selection, cal = select_from_list(eligible_calendars, "summary")

        if selection < 0 or selection >= len(eligible_calendars):
            raise CalendarError(f"Invalid calendar selection: {selection}")

        calendar_id = eligible_calendars[selection]["id"]
        logging.info(f"Selected calendar: {safe_get(cal, ['summary'])} (ID: {calendar_id})")

        return calendar_id

    except (KeyError, IndexError, TypeError) as e:
        raise CalendarError(f"Failed to select calendar: {e}") from e
    except Exception as e:
        raise CalendarError(f"Unexpected error selecting calendar: {e}") from e


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
        # "attendees": [],
    }


def process_event_data(event, content):
    """Processes event data, adding the email content to the description.

    Args:
        event (dict): The event dictionary.
        content (str): The content of the email.
    """
    event["description"] = f"{safe_get(event, ['description'])}\n\nMessage:\n{content}"
    # event["attendees"] = []  # Clear attendees
    return event


def filter_events_by_title(api_cal, events, text_filter):
    """
    Helper function to filter events by title text.

    Args:
        api_cal: Calendar API object
        events: List of events to filter
        text_filter: Text to filter by (can be None)

    Returns:
        List of filtered events
    """
    filtered_events = []
    for event in events:
        title = api_cal.getPostTitle(event)
        if title and text_filter and text_filter.lower() in title.lower():
            filtered_events.append(event)
        elif not text_filter:  # If no filter, include all events with titles
            if title:
                filtered_events.append(event)

    return filtered_events


def adjust_event_times(event):
    """Adjusts event start/end times, localizing naive times and converting to UTC.

    Args:
        event (dict): Event dictionary with start/end datetime fields.

    Returns:
        dict: Event with adjusted times in UTC.

    Raises:
        ValidationError: If datetime validation fails critically.
    """

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
                        logging.warning(
                            f"Unknown timezone '{input_tz_name}' for {field_name_for_logging}. "
                            f"Using default timezone: {config.DEFAULT_TIMEZONE}"
                        )
                        dt_obj = DEFAULT_NAIVE_TIMEZONE.localize(dt_obj)
                else:
                    dt_obj = DEFAULT_NAIVE_TIMEZONE.localize(dt_obj)

            return dt_obj.astimezone(pytz.utc).isoformat(), True
        except ValueError as e:
            logging.error(
                f"Invalid datetime format for {field_name_for_logging}: '{time_str}'. Error: {e}"
            )
            return None, False
        except Exception as e:
            logging.error(f"Unexpected error processing {field_name_for_logging}: {e}")
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
            existing_dt = datetime.datetime.fromisoformat(existing_dt_iso)  # This is already UTC

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

    if not text.startswith("{"):
        pos = text.find("{")
        if pos != -1:
            text = text[pos:]
    if not text.endswith("}"):
        pos = text.rfind("}")
        if pos != -1:
            text = text[: pos + 1]
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

    memory_error_occurred = False

    if not llm_response:
        print("Failed to get response from LLM.")
    elif 'Memory' in llm_response:
        print("LLM failed due to insufficient memory. Model requires more"
              "system memory than available.")
        # Set a flag to indicate memory error occurred
        memory_error_occurred = True
    else:
        if verbose:
            print(f"Reply:\n{llm_response}")
            print("End Reply")

        llm_response = llm_response.replace("\\", "").replace("\n", " ")

        try:
            import ast

            vcal_json = ast.literal_eval(extract_json(llm_response))
            if verbose:
                print(f"Json:\n{vcal_json}")
            event = vcal_json
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in vCal data: {vcal_json}")
            logging.error(f"Error: {e}")
        except SyntaxError as e:
            logging.error(f"Syntax error: {vcal_json}")
            logging.error(f"Error: {e}")

    # Return appropriate values based on whether memory error occurred
    if memory_error_occurred:
        event = None
        vcal_json = "MemoryError"
    return event, vcal_json, elapsed_time


def get_event_from_llm_with_retry(model, prompt, args):
    """Wrapper for get_event_from_llm with consistent retry and error handling logic."""
    event = None
    vcal_json = None
    elapsed_time = 0
    memory_error_occurred = False

    while not event and not memory_error_occurred:
        event, vcal_json, elapsed_time = get_event_from_llm(model,
                                                            prompt,
                                                            args.verbose)

        # Handle memory error specifically
        if vcal_json == "MemoryError":
            print("Switching to a different LLM due to memory constraints...")

            # Determine source based on interactive mode
            source = None if args.interactive else "gemini"
            if not args.interactive:
                # In non-interactive mode, try to switch to a lighter model automatically
                print("Trying to switch to a lighter model automatically...")

            new_args = Args(
                interactive=args.interactive,
                delete=args.delete,
                source=source,
                verbose=args.verbose,
                destination=args.destination,
                text=args.text,
            )

            # Select a new model based on the args
            new_model = select_llm(new_args)

            if new_model:
                model = new_model
                if args.interactive:
                    print(f"Selected new AI model: "
                          f"{model.__class__.__name__}")
                else:
                    print(f"Switched to lighter AI model: "
                          f"{model.__class__.__name__}")

                # Instead of calling get_event_from_llm directly, let the loop
                # continue to make the call Reset event to None to continue the
                # loop
                event = None
                vcal_json = None
            else:
                if args.interactive:
                    print("No alternative model selected. Skipping event processing.")
                else:
                    print("Could not switch to a lighter model. Skipping event processing.")
                memory_error_occurred = True
        # For other types of failures (no event and not memory error), the loop continues naturally
        # due to the while condition "while not event and not memory_error_occurred"
        # No explicit action needed here

    return event, vcal_json, elapsed_time


def authorize(args, rules=None):
    if rules is None:
        from socialModules import moduleRules
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


def _get_sources_by_type(source_type, rules):
    """Helper function to get sources based on type."""
    if source_type == 'email':
        return rules.selectRule("gmail", "") + rules.selectRule("imap", "")
    else:
        # For API sources and others, use the direct approach
        return rules.selectRule(source_type, "")


def select_source_by_type(args, source_type, rules=None):
    """Factory function to select sources by type."""
    if rules is None:
        from socialModules import moduleRules
        rules = moduleRules.moduleRules()
        rules.checkRules()

    sources = _get_sources_by_type(source_type, rules)

    if args.interactive:
        if source_type == 'email':
            selected_source, _ = select_from_list(sources)
            return selected_source
        else:
            # For API sources and others
            api_src = rules.selectRuleInteractive(source_type)
            return api_src
    else:
        if not sources:
            logging.warning(f"No {source_type} sources configured.")
            return None

        if source_type == 'email':
            # For email sources, return the source name
            return sources[0]
        else:
            # For API sources, load the configuration
            source_name = sources[0]
            source_details = rules.more.get(source_name, {})
            logging.info(f"Source: {source_name} - {source_details}")
            api_src = rules.readConfigSrc("", source_name, source_details)
            return api_src


def select_api_source(args, api_src_type, rules=None):
    """Selects an API source, interactive or not."""
    return select_source_by_type(args, api_src_type, rules)


def list_events_folder(args, api_src, calendar=""):
    """Lists events in calendar."""
    if api_src.getClient():
        api_src.setPosts()
        if api_src.getPosts():
            for i, post in enumerate(api_src.getPosts()):
                post_date = api_src.getPostDate(post)
                post_title = api_src.getPostTitle(post)
                print(f"{i}) {post_title}")
    else:
        print("Some problem with the account")


def _get_emails_from_folder(args, source_name, rules=None):
    """Helper function to get emails from a specific folder."""
    "FIXME: maybe a folder argument?"
    if rules is None:
        from socialModules import moduleRules
        rules = moduleRules.moduleRules()
        rules.checkRules()
    source_details = rules.more.get(source_name, {})
    api_src = rules.readConfigSrc("", source_name, source_details)

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

    #label_id = safe_get(label[0], ["id"])
    api_src.setChannel(folder)
    api_src.setPosts()
    posts = api_src.getPosts()

    if not posts:
        print(f"There are no posts tagged with label {folder}")
        posts = None

    return api_src, posts


def select_email_source(args, rules=None):
    """Selects an email source, interactive or not."""
    return select_source_by_type(args, 'email', rules)


def list_emails_folder(args, rules=None):
    """Lists emails and in folder."""
    source_name = select_email_source(args, rules=rules)
    api_src, posts = _get_emails_from_folder(args, source_name, rules=rules)
    if posts:
        for i, post in enumerate(posts):
            # post_id = api_src.getPostId(post)
            # post_date = api_src.getPostDate(post)
            post_title = api_src.getPostTitle(post)
            print(f"{i}) {post_title}")


def _create_llm_prompt(content_text, reference_date_time):
    """Constructs the LLM prompt for event extraction."""
    import os
    from pathlib import Path

    content_text = content_text.replace("\r", "")

    # Create the event template for the LLM to fill in
    event = create_event_dict()

    # Get the path to the prompt template
    prompt_dir = Path(__file__).parent / "prompts"
    prompt_file = prompt_dir / "event_extraction_prompt.txt"

    # Read the prompt template
    if prompt_file.exists():
        prompt_template = prompt_file.read_text(encoding='utf-8')
    else:
        # Fallback to the original prompt if file is not found
        prompt_template = (
            "Extract event information from the provided text and fill in the JSON structure below.\n\n"
            f"JSON structure to fill:\n{event}\n\n"
            "INSTRUCTIONS:\n"
            "1. Extract event details from the message body ('Message:') and subject ('Subject:').\n"
            "2. Use the reference date marked with 'Message date:' when interpreting relative dates (e.g., 'next Thursday').\n"
            "3. Default timezone is CET if not specified otherwise.\n"
            "4. The result must be a valid JSON with all fields and values enclosed in double quotes.\n"
            "5. Replace any double or single quotes in the extracted content with single quotes (') to avoid JSON parsing errors.\n"
            "6. Place the start and end times in event['start']['dateTime'] and event['end']['dateTime'] respectively.\n"
            "7. Do not translate the text; keep all information in the original language.\n"
            "8. Return ONLY the completed JSON structure without any additional comments or explanations.\n\n"
            "SOURCE TEXT:\n"
            f"{content_text}.\n"
        )

    # Fill in the template with actual values
    return prompt_template.format(event=event, content_text=content_text)


def _interactive_date_confirmation(args, event, model=None, content_text=None, reference_date_time=None, post_identifier=None, subject_for_print=None):
    """Interactively confirms and corrects event dates."""
    if not args.interactive:
        return event, False  # Return event and a flag indicating if user wants to retry

    # Get current start and end times
    current_start_str = safe_get(event, ["start", "dateTime"])
    current_end_str = safe_get(event, ["end", "dateTime"])

    # Parse current times if they exist
    if current_start_str:
        try:
            current_start = datetime.datetime.fromisoformat(current_start_str.replace('Z', '+00:00'))
        except ValueError:
            # Handle cases where the format isn't ISO
            try:
                current_start = datetime.datetime.strptime(current_start_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                current_start = None
                print("Could not parse start time, using empty value")
    else:
        current_start = None

    if current_end_str:
        try:
            current_end = datetime.datetime.fromisoformat(current_end_str.replace('Z', '+00:00'))
        except ValueError:
            # Handle cases where the format isn't ISO
            try:
                current_end = datetime.datetime.strptime(current_end_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                current_end = None
                print("Could not parse end time, using empty value")
    else:
        current_end = None

    print(f"\nCurrent start time: {current_start}")
    print(f"Current end time: {current_end}")

    # Extended prompt with options for individual components (includes 'r' option for retry)
    confirmation = input(DATE_CONFIRMATION_PROMPT_WITH_R_OPTION).lower()

    # Check if user wants to retry with LLM
    if confirmation == "r":
        return event, True  # Return event and True to indicate retry is needed

    if confirmation == "s":
        # Yes, dates are correct
        return event, False  # No retry needed
    elif confirmation in ["m", "d", "h", "f", "y", "i"]:  # Process all options
        if confirmation == "f":
            # Full date/time modification
            new_start_str = input("Enter new start time (YYYY-MM-DD HH:MM:SS) or leave empty: ")
            if new_start_str:
                event.setdefault("start", {})["dateTime"] = new_start_str
                try:
                    start_dt = datetime.datetime.strptime(new_start_str, "%Y-%m-%d %H:%M:%S")
                    end_dt = start_dt + timedelta(minutes=45)
                    new_end_str_default = end_dt.strftime("%Y-%m-%d %H:%M:%S")

                    modify_end_time = input(
                        f"Default end time will be {new_end_str_default}. Do you want to modify it? (y/n): "
                    ).lower()
                    if modify_end_time == "y":
                        new_end_str = input(
                            "Enter new end time (YYYY-MM-DD HH:MM:SS) or leave empty: "
                        )
                    else:
                        new_end_str = new_end_str_default
                except ValueError:
                    print("Invalid start time format. Please use YYYY-MM-DD HH:MM:SS.")
                    new_end_str = ""
            else:
                new_end_str = input("Enter new end time (YYYY-MM-DD HH:MM:SS) or leave empty: ")

            if new_end_str:
                event.setdefault("end", {})["dateTime"] = new_end_str

        elif confirmation in ["m", "d", "h", "y", "i"]:  # Individual component modifications
            # Determine which component to modify
            component_map = {
                'y': 'year',
                'm': 'month',
                'd': 'day',
                'h': 'hour',
                'i': 'minute'
            }
            component = component_map.get(confirmation)

            # Modify the selected component for both start and end times
            if current_start and component:
                new_start = _modify_single_component(current_start, component, "start")
                event.setdefault("start", {})["dateTime"] = new_start.isoformat()

            if current_end and component:
                new_end = _modify_single_component(current_end, component, "end")
                event.setdefault("end", {})["dateTime"] = new_end.isoformat()

        # Process the event after modifications
        event = adjust_event_times(event)

        # Update and print new times
        start_time = safe_get(event, ["start", "dateTime"])
        end_time = safe_get(event, ["end", "dateTime"])
        print("--- Updated Event Times ---")
        print(f"Start: {start_time}")
        print(f"End: {end_time}")
        print("---------------------------")

    # Return the event and flag indicating no retry needed
    return event, False


def _interactive_date_confirmation_with_choice(args, event, confirmation, content_text, reference_date_time, post_identifier, subject_for_print):
    """Handle specific user choice for date confirmation."""
    if not args.interactive:
        return event, False

    # Get current start and end times
    current_start_str = safe_get(event, ["start", "dateTime"])
    current_end_str = safe_get(event, ["end", "dateTime"])

    # Parse current times if they exist
    if current_start_str:
        try:
            current_start = datetime.datetime.fromisoformat(current_start_str.replace('Z', '+00:00'))
        except ValueError:
            # Handle cases where the format isn't ISO
            try:
                current_start = datetime.datetime.strptime(current_start_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                current_start = None
                print("Could not parse start time, using empty value")
    else:
        current_start = None

    if current_end_str:
        try:
            current_end = datetime.datetime.fromisoformat(current_end_str.replace('Z', '+00:00'))
        except ValueError:
            # Handle cases where the format isn't ISO
            try:
                current_end = datetime.datetime.strptime(current_end_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                current_end = None
                print("Could not parse end time, using empty value")
    else:
        current_end = None

    print(f"\nCurrent start time: {current_start}")
    print(f"Current end time: {current_end}")

    # Process the specific confirmation choice
    if confirmation in ["m", "d", "h", "f", "y", "i"]:  # Process all options
        if confirmation == "f":
            # Full date/time modification
            new_start_str = input("Enter new start time (YYYY-MM-DD HH:MM:SS) or leave empty: ")
            if new_start_str:
                event.setdefault("start", {})["dateTime"] = new_start_str
                try:
                    start_dt = datetime.datetime.strptime(new_start_str, "%Y-%m-%d %H:%M:%S")
                    end_dt = start_dt + timedelta(minutes=45)
                    new_end_str_default = end_dt.strftime("%Y-%m-%d %H:%M:%S")

                    modify_end_time = input(
                        f"Default end time will be {new_end_str_default}. Do you want to modify it? (y/n): "
                    ).lower()
                    if modify_end_time == "y":
                        new_end_str = input(
                            "Enter new end time (YYYY-MM-DD HH:MM:SS) or leave empty: "
                        )
                    else:
                        new_end_str = new_end_str_default
                except ValueError:
                    print("Invalid start time format. Please use YYYY-MM-DD HH:MM:SS.")
                    new_end_str = ""
            else:
                new_end_str = input("Enter new end time (YYYY-MM-DD HH:MM:SS) or leave empty: ")

            if new_end_str:
                event.setdefault("end", {})["dateTime"] = new_end_str

        elif confirmation in ["m", "d", "h", "y", "i"]:  # Individual component modifications
            # Determine which component to modify
            component_map = {
                'y': 'year',
                'm': 'month',
                'd': 'day',
                'h': 'hour',
                'i': 'minute'
            }
            component = component_map.get(confirmation)

            # Modify the selected component for both start and end times
            if current_start and component:
                new_start = _modify_single_component(current_start, component, "start")
                event.setdefault("start", {})["dateTime"] = new_start.isoformat()

            if current_end and component:
                new_end = _modify_single_component(current_end, component, "end")
                event.setdefault("end", {})["dateTime"] = new_end.isoformat()

        # Process the event after modifications
        event = adjust_event_times(event)

        # Update and print new times
        start_time = safe_get(event, ["start", "dateTime"])
        end_time = safe_get(event, ["end", "dateTime"])
        print("--- Updated Event Times ---")
        print(f"Start: {start_time}")
        print(f"End: {end_time}")
        print("---------------------------")

    # Return the event and flag indicating no retry needed
    return event, False


def _modify_single_component(dt, component, time_label):
    """
    Modify a single component of a datetime object.

    Args:
        dt: datetime object to modify
        component: component to modify ('year', 'month', 'day', 'hour', 'minute')
        time_label: label for the time being modified ('start' or 'end')

    Returns:
        Modified datetime object
    """
    print(f"\nModifying {component} for {time_label} time:")
    print(f"Current: {dt}")

    # Get user input for the specific component
    value_str = input(f"New {component} ({getattr(dt, component)}): ").strip()
    if value_str:
        try:
            new_value = int(value_str)
            # Create new datetime with modified component
            if component == 'year':
                new_dt = dt.replace(year=new_value)
            elif component == 'month':
                new_dt = dt.replace(month=new_value)
            elif component == 'day':
                new_dt = dt.replace(day=new_value)
            elif component == 'hour':
                new_dt = dt.replace(hour=new_value)
            elif component == 'minute':
                new_dt = dt.replace(minute=new_value)
            else:
                print(f"Unknown component: {component}. Keeping original time.")
                return dt

            print(f"New {time_label} time: {new_dt}")
            return new_dt
        except ValueError as e:
            print(f"Invalid value: {e}. Keeping original time.")
            return dt
    else:
        # User pressed Enter, keep original value
        return dt


def _modify_datetime_components(dt, time_label):
    """
    Interactively modify individual components of a datetime object.

    Args:
        dt: datetime object to modify
        time_label: label for the time being modified ('start' or 'end')

    Returns:
        Modified datetime object
    """
    print(f"\nModifying {time_label} time components:")
    print(f"Current: {dt}")

    # Get user input for each component
    year = input(f"Year ({dt.year}): ").strip()
    year = int(year) if year else dt.year

    month = input(f"Month ({dt.month}): ").strip()
    month = int(month) if month else dt.month

    day = input(f"Day ({dt.day}): ").strip()
    day = int(day) if day else dt.day

    hour = input(f"Hour ({dt.hour}): ").strip()
    hour = int(hour) if hour else dt.hour

    minute = input(f"Minute ({dt.minute}): ").strip()
    minute = int(minute) if minute else dt.minute

    # Create new datetime with modified components
    try:
        new_dt = dt.replace(year=year, month=month, day=day, hour=hour, minute=minute)
        print(f"New {time_label} time: {new_dt}")
        return new_dt
    except ValueError as e:
        print(f"Invalid date/time combination: {e}. Keeping original time.")
        return dt


def _process_and_display_event(event, content_text, subject_for_print, elapsed_time=None):
    """
    Process event data, adjust times, and display information consistently.

    Args:
        event: Event dictionary to process
        content_text: Content text for processing
        subject_for_print: Subject/title to display
        elapsed_time: Optional time taken for AI processing

    Returns:
        Processed and adjusted event
    """
    process_event_data(event, content_text)
    event = adjust_event_times(event)
    _display_event_info(event, subject_for_print, elapsed_time)
    return event


def _extract_event_with_llm_retry(args, model, content_text,
                                  reference_date_time, post_identifier,
                                  subject_for_print): 
    """
    Extract event information using LLM with retry logic.

    Args:
        args: Arguments object
        model: LLM model to use
        content_text: Content text to extract event from
        reference_date_time: Reference date/time for relative dates
        post_identifier: Identifier for the post
        subject_for_print: Subject/title to display

    Returns:
        tuple: (event, vcal_json, elapsed_time, success_flag, need_restart,
        need_another_ai) where success_flag indicates if extraction was
        successful and need_restart indicates if the whole process should
        restart """
    # Create initial event dict for helper
    prompt = _create_llm_prompt(content_text, reference_date_time)
    if args.verbose:
        print(f"Prompt:\n{prompt}")
        print("\nEnd Prompt:")

    # Get AI reply with retry logic
    event, vcal_json, elapsed_time = get_event_from_llm_with_retry(model, prompt, args)

    # Check for memory error
    memory_error = (event is None and vcal_json == "MemoryError")

    if memory_error:
        return event, vcal_json, elapsed_time, False, False, False  
        # Not successful, don't restart, don't need another AI

    # Process event data
    event = process_event_data(event, content_text)
    event = adjust_event_times(event)

    # Check if event processing was successful
    processing_failed = not event

    # Save vCal data
    write_file(f"{post_identifier}.vcal", vcal_json)  # Save vCal data

    # If basic processing failed, return with failure
    if processing_failed:
        return event, vcal_json, elapsed_time, False, False, False

    # Now validate the event and handle interactive completion if needed
    validated_event, validated_vcal_json, need_restart, need_another_ai = _validate_and_complete_event_interactively(
        args, event, vcal_json, elapsed_time, post_identifier, subject_for_print,
        model, content_text, reference_date_time
    )

    # If validation failed completely
    if validated_event is None:
        return validated_event, validated_vcal_json, elapsed_time, False, need_restart, need_another_ai

    # Success - return validated event
    return validated_event, validated_vcal_json, elapsed_time, True, need_restart, need_another_ai


def _validate_and_complete_event_interactively(args, event, vcal_json, elapsed_time, post_identifier, subject_for_print, model, content_text, reference_date_time):
    """
    Validate the event and handle interactive completion if needed.

    Args:
        args: Arguments object
        event: Event dictionary to validate
        vcal_json: vCal JSON data
        elapsed_time: Time taken for AI processing
        post_identifier: Identifier for the post
        subject_for_print: Subject/title to display
        model: Current LLM model
        content_text: Content text
        reference_date_time: Reference date/time

    Returns:
        tuple: (event, vcal_json, need_restart, need_another_ai) where need_restart indicates if the whole process should restart
               and need_another_ai indicates if another AI call is needed
    """
    # --- LLM Response Validation/Retry Loop ---
    retries = 0
    max_retries = 3  # Limit AI retries
    data_complete = False
    should_skip = False
    need_restart = False
    need_another_ai = False

    # Process until completion or termination condition
    while not data_complete and retries <= max_retries and not should_skip and not need_restart and not need_another_ai:
        summary = event.get("summary")
        start_datetime = event.get("start", {}).get("dateTime")

        if not summary:
            print("- Summary")
            summary = subject_for_print
            if summary:
                event["summary"] = summary

        if summary and start_datetime:
            data_complete = True
        else:
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
                        new_start_datetime_str = input("Enter Start Date/Time (YYYY-MM-DD HH:MM:SS): ")
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
                                print("Invalid date/time format. Please use YYYY-MM-DD HH:MM:SS.")
                                # Just continue with the loop, but don't mark as complete
                                # We'll continue to the next iteration by not setting data_complete = True
                    data_complete = True
                elif choice == "a":
                    retries += 1
                    if retries > max_retries:
                        print("Max AI retries reached. Skipping item.")  # Generalized message
                        should_skip = True
                    else:
                        need_another_ai = True  # Signal that another AI call is needed
                        # Instead of break, we'll set a flag to indicate we should exit the loop
                        # The loop will naturally terminate on the next iteration due to the condition
                        # But we need to make sure the loop condition will be false next time
                        # We'll set data_complete to True to exit the loop
                        data_complete = True  # This will cause the loop to exit on next evaluation
                elif choice == "s":
                    should_skip = True
                elif choice == "r":  # User wants to restart from the beginning
                    need_restart = True
                else:
                    print("Invalid choice. Please try again.")
                    retries += 1
                    # Just continue with the loop
            else:  # Non-interactive mode
                if not summary or not start_datetime:
                    logging.warning(
                        f"Missing summary or start_datetime for {post_identifier}. Skipping."
                    )
                    should_skip = True
                else:
                    data_complete = True

    # Determine return values based on flags
    if should_skip or not data_complete:
        return None, None, need_restart, need_another_ai  # Return flags
    else:
        return event, vcal_json, need_restart, need_another_ai  # Return validated event and flags


def _display_event_info(event, subject_for_print, elapsed_time=None):
    """
    Display event information consistently across the application.

    Args:
        event: Event dictionary containing start and end times
        subject_for_print: Subject/title to display
        elapsed_time: Optional time taken for AI processing

    Returns:
        Tuple of (start_time_local, end_time_local) for potential reuse
    """
    start_time = safe_get(event, ["start", "dateTime"])
    end_time = safe_get(event, ["end", "dateTime"])

    # Convert to local timezone for display
    try:
        start_time_local = (
            datetime.datetime.fromisoformat(start_time).astimezone() if start_time else "N/A"
        )
        end_time_local = (
            datetime.datetime.fromisoformat(end_time).astimezone() if end_time else "N/A"
        )
    except ValueError:
        start_time_local = start_time
        end_time_local = end_time

    print("=====================================")
    print(f"Subject: {subject_for_print}")
    print(f"Start: {start_time_local}")
    print(f"End: {end_time_local}")

    if elapsed_time is not None:
        print(f"AI call took {format_time(elapsed_time)} ({elapsed_time:.2f} seconds)")

    print("=====================================")

    return start_time_local, end_time_local


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
    # Initialize result variables
    event = None
    calendar_result = None
    success = False
    should_process = True

    # Process until success or definitive failure
    while should_process and not success:
        # Extract event with LLM and validate it
        event, vcal_json, elapsed_time, extraction_success, need_restart, need_another_ai = _extract_event_with_llm_retry(
            args, model, content_text, reference_date_time, post_identifier, subject_for_print
        )

        # Handle restart case first
        if need_restart:
            # Loop will continue to restart the process
            pass  # Intentionally do nothing, just let the loop continue
        elif need_another_ai:
            # Need to get another AI response and try again
            # This means we need to repeat the process with a new AI call
            # We'll just continue the loop to repeat the process
            pass  # Intentionally do nothing, just let the loop continue
        else:
            # Check if extraction was unsuccessful
            if not extraction_success:
                should_process = False  # Indicate failure due to memory error or other issues
            else:
                api_dst_type = "gcalendar"
                api_dst = select_api_source(args, api_dst_type)

                if event is None:
                    should_process = False  # Indicate failure
                else:
                    # --- Event Adjustment ---
                    event = adjust_event_times(event)
                    write_file(f"{post_identifier}.json", json.dumps(event))  # Save event JSON
                    write_file(
                        f"{post_identifier}_times.json", json.dumps(event)
                    )  # Save event JSON (redundant, but existing)

                    if args.interactive:
                        start_time = safe_get(event, ["start", "dateTime"])
                        end_time = safe_get(event, ["end", "dateTime"])
                        print(f"Start time: {start_time}")
                        print(f"End time: {end_time}")

                    _display_event_info(event, subject_for_print, elapsed_time)

                    # Check if user wants to retry with LLM from the beginning or make date
                    # corrections Always call _interactive_date_confirmation, which handles
                    # both interactive and non-interactive modes
                    event, retry_needed = _interactive_date_confirmation(args, event,
                                                                         model,
                                                                         content_text,
                                                                         reference_date_time,
                                                                         post_identifier,
                                                                         subject_for_print)

                    if not (retry_needed and model and content_text and reference_date_time):
                        # Successful completion of main processing, proceed to calendar creation
                        should_process = False

                        # If we have an event, proceed with calendar creation
                        if event is not None:
                            selected_calendar = select_calendar(api_dst)
                            if selected_calendar:
                                try:
                                    calendar_result = api_dst.publishPost(
                                        post={"event": event, "idCal": selected_calendar}, api=api_dst
                                    )
                                    print("Calendar event created")
                                    success = True  # Indicate successful completion
                                except googleapiclient.errors.HttpError as e:
                                    logging.error(f"Error creating calendar event: {e}")
                            else:
                                print("No calendar selected, skipping event creation.")

    # Return appropriate values based on success
    if success:
        return event, calendar_result  # Return event and result for further processing
    else:
        return None, None


def _get_post_datetime_and_diff(post_date):
    """
    Calculates the post datetime and the difference in days from now.

    Args:
        post_date (str or datetime.datetime): The date of the post.

    Returns:
        tuple: A tuple containing the post datetime and the time difference in days.
    """
    if isinstance(post_date, datetime.datetime):
        post_date_time = post_date
    elif post_date.isdigit():
        post_date_time = datetime.datetime.fromtimestamp(int(post_date) / 1000)
    else:
        from email.utils import parsedate_to_datetime

        post_date_time = parsedate_to_datetime(post_date)

    try:
        import pytz

        # Define the timezone
        madrid_tz = pytz.timezone("Europe/Madrid")

        # Make post_date_time timezone-aware if it's naive
        if post_date_time.tzinfo is None:
            post_date_time = madrid_tz.localize(post_date_time)

        # Get the current time as timezone-aware
        now_aware = datetime.datetime.now(madrid_tz)

        time_difference = now_aware - post_date_time
        logging.debug(f"Date: {post_date_time} Diff: {time_difference.days}")
    except Exception as e:
        logging.error(f"Error processing post date: {e}")
        time_difference = datetime.timedelta(0)

    return post_date_time, time_difference


def _delete_email(args, api_src, post_id, source_name, rules=None):
    """Deletes an email, handling interactive confirmation and connection errors."""
    delete_confirmed = False
    if args.interactive:
        confirmation = input("Do you want to remove the label from the email? (y/n): ")
        if confirmation.lower() == "y":
            delete_confirmed = True
    elif args.delete:  # Only auto-confirm if not interactive but delete flag is set
        delete_confirmed = True

    if delete_confirmed:
        max_retries = 1
        label = None
        for attempt in range(max_retries + 1):
            try:
                print(f"Service: {api_src.service.lower()}")
                res = ""
                if "imap" not in api_src.service.lower():
                    print(f"label: {api_src.getChannel()}")
                    logging.info(f"label: {api_src.getChannel()}")
                    folder = api_src.getChannel()
                    label = api_src.getLabels(folder)
                    logging.info(f"label: {label}")
                    res = api_src.modifyLabels(post_id, label[0], None)
                    logging.info(f"Label removed from email {post_id}.")
                else:
                    label = api_src.getChannel()
                    api_src.getClient().select(label)
                    res = api_src.deletePostId(post_id)
                    logging.info(f"State: {api_src.getClient().state}")
                if not "Fail!" in res:
                    logging.info(f"Email {post_id} processed successfully.")
                    return  # Success
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} of {max_retries + 1} failed: {e}")
                if attempt < max_retries:
                    logging.info("Retrying to connect to the email server...")

                    if rules is None:
                        from socialModules import moduleRules
                        rules = moduleRules.moduleRules()
                        rules.checkRules()
                    source_details = rules.more.get(source_name, {})
                    api_src = rules.readConfigSrc("", source_name, source_details)
                    if label:
                        api_src.setChannel(label)
                else:
                    logging.error(f"Could not delete email {post_id} after {max_retries + 1} attempts: {e}")
                    return # Exit after last attempt failure


def _is_post_too_old(args, time_difference):
    """Checks if an email is too old and confirms processing if interactive."""
    if time_difference.days > 7:
        if args.interactive:
            confirmation = input(
                f"The post has {time_difference.days} days. Do you want to process it? (y/n): "
            )
            if confirmation.lower() != "y":
                return True
        else:
            if args.verbose:
                print(f"Too old ({time_difference.days} days), skipping.")
            return True
    return False

def _process_common_flow(args, model, items, metadata_extractor, content_extractor, item_cleaner=None):
    """
    Common flow for processing items (emails, web pages).

    metadata_extractor: func(item, index) -> (post_id, post_title, post_date)
    content_extractor: func(item, index, post_date_time, post_title) -> content_text
    item_cleaner: func(item, index, post_id) -> void
    """
    processed_any_event = False
    for i, item in enumerate(items):
        # 1. Metadata
        post_id, post_title, post_date = metadata_extractor(item, i)

        print(f"Processing Title: {post_title}", flush=True)

        # 2. Check Age
        post_date_time, time_difference = _get_post_datetime_and_diff(post_date)
        if _is_post_too_old(args, time_difference):
            continue

        # 3. Content
        content_text = content_extractor(item, i, post_date_time, post_title)
        if not content_text:
            continue

        # 4. Save & Print (Common)
        write_file(f"{post_id}.txt", content_text)
        print_first_10_lines(content_text, "content")

        # 5. Process with LLM
        processed_event, calendar_result = _process_event_with_llm_and_calendar(
            args,
            model,
            content_text,
            post_date_time,
            post_id,
            post_title,
        )

        if processed_event:
            processed_any_event = True
            # 6. Post-process
            if item_cleaner:
                item_cleaner(item, i, post_id)

    return processed_any_event


def process_email_cli(args, model, source_name=None, rules=None):
    """Processes emails and creates calendar events."""

    if not source_name:
        source_name = select_email_source(args, rules=rules)

    api_src, posts = _get_emails_from_folder(args, source_name, rules=rules)

    if posts:
        def metadata_extractor(post, i):
            return api_src.getPostIdM(post), api_src.getPostTitle(post), api_src.getPostDate(post)

        def content_extractor(post, i, post_date_time, post_title):
            full_email_content = api_src.getPostBody(post)
            date_message = str(post_date_time).split(' ')[0]
            return (
                f"Subject: {post_title}\n"
                f"Message: {full_email_content}\n"
                f"Message date: {date_message}\n"
            )

        def item_cleaner(post, i, post_id):
            if "imap" in api_src.service.lower():
                post_pos = i + 1
            else:
                post_pos = post_id
            _delete_email(args, api_src, post_pos, source_name, rules=rules)

        return _process_common_flow(
            args, model, posts, metadata_extractor, content_extractor, item_cleaner
        )
    return False  # Default return if something went wrong before the main logic

def _get_pages_from_urls(args, urls):

    page = moduleHtml.moduleHtml()
    if args.verbose:
        print(f"Urls: {urls}")
    page.setUrl(urls)
    page.setApiPosts()
    posts = page.getPosts()

    if not posts:
        print(f"There are no posts with these urls {urls}")
        posts = None

    return page, posts

def process_web_cli(args, model, urls=None, force_refresh=False):
    """Processes web pages and creates calendar events."""

    if not urls:
        urls = input("Enter URLs separated by spaces: ").split()

    api_src, posts = _get_pages_from_urls(args, urls)

    if posts:
        def metadata_extractor(post, i):
            title = api_src.getPostTitle(post)
            if not title:
                title = urls[i]
            return api_src.getPostId(post), title, datetime.datetime.now()

        def content_extractor(post, i, post_date_time, post_title):
            web_content_reduced = reduce_html(urls[i], post, force_refresh=force_refresh)
            if not web_content_reduced:
                print(f"Could not process {urls[i]}, skipping.")
                return None

            date_message = str(post_date_time).split(' ')[0]
            return (
                f"Url: {urls[i]}\n"
                f"Subject: {post_title}\n"
                f"Message: {web_content_reduced}\n"
                f"Message date: {date_message}\n"
            )

        return _process_common_flow(
            args, model, posts, metadata_extractor, content_extractor
        )

    return False  # Default return if something went wrong before the main logic


def select_email_prompt(args):
    """Interactively selects an email and returns its content."""
    api_src_type = ["gmail", "imap"]
    api_src = select_api_source(args, api_src_type)

    if not api_src.getClient():
        print("Failed to connect to the email account.")
        return None

    api_src.setLabels()
    # labels = api_src.getLabels()
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
    # pattern_generic = re.compile(
    #                             #r'[\u200c\u00a0\u2007\u00ad\u200b\u200e\ufeff]',
    #                             #r'[\p{Cf}\p{Cc}\p{Zs}\
    #                             r'[\p{Cf}\p{Cc}\p{Zs}]',
    #                             re.UNICODE
    #                             )
    # full_email_content = pattern_generic.sub('', full_email_content)
    # print(f"Email: {full_email_content}")

    # sys.exit()

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


def copy_action(api_cal, event, my_calendar, my_calendar_dst):
    """Action function to copy an event."""
    my_event = {
        "summary": event["summary"],
        "description": event["description"],
        "start": event["start"],
        "end": event["end"],
    }
    if "location" in event:
        my_event["location"] = event["location"]

    api_cal.getClient().events().insert(calendarId=my_calendar_dst, body=my_event).execute()
    print(f"Copied event: {my_event['summary']}")


def copy_events_cli(args):
    """Copies events from a source calendar to a destination calendar."""
    process_calendar_events(args, "copy", copy_action, destination_needed=True)


def select_events_by_user_input(api_cal, events_list, action_verb="copy"):
    """
    Common function to handle user input for selecting events.

    Args:
        api_cal: Calendar API object
        events_list: List of events to select from
        action_verb: String describing the action (e.g., 'copy', 'delete')

    Returns:
        List of selected events
    """
    print(f"Select events to {action_verb}:")
    for i, event in enumerate(events_list):
        print(f"{i}) {api_cal.getPostTitle(event)}")

    print(f"{len(events_list)}) All")

    selection = input(f"Which event(s) to {action_verb}? (comma-separated numbers, text to match, or 'all') ")

    selected_events = []
    if selection.lower() == "all" or selection == str(len(events_list)):
        selected_events = events_list
    else:
        # First, try to parse as numbers (original functionality)
        try:
            indices = [int(i.strip()) for i in selection.split(",")]
            # Check if all indices are valid (within range)
            all_valid = all(0 <= idx < len(events_list) for idx in indices)

            if all_valid:
                # All numbers are valid indices, use number-based selection
                for i in indices:
                    if 0 <= i < len(events_list):
                        selected_events.append(events_list[i])
            else:
                # At least one number is out of range, treat as text-based selection
                search_terms = selection.split(',')
                for term in search_terms:
                    term = term.strip().lower()
                    for i, event in enumerate(events_list):
                        event_title = api_cal.getPostTitle(event).lower()
                        if term in event_title and events_list[i] not in selected_events:
                            selected_events.append(events_list[i])
        except ValueError:
            # If parsing as integers fails, treat as text-based selection
            search_terms = selection.split(',')
            for term in search_terms:
                term = term.strip().lower()
                for i, event in enumerate(events_list):
                    event_title = api_cal.getPostTitle(event).lower()
                    if term in event_title and events_list[i] not in selected_events:
                        selected_events.append(events_list[i])

    return selected_events


def process_calendar_events(args, action_verb, action_func, destination_needed=False, api_src_type="gcalendar"):
    """
    Generic function to handle complete calendar event processing from initialization to action.

    Args:
        args: Arguments object
        action_verb: String describing the action (e.g., 'copy', 'delete', 'move')
        action_func: Function to perform the specific action on selected events
        destination_needed: Boolean indicating if destination calendar is needed
        api_src_type: Type of API source (default: "gcalendar")

    Returns:
        None
    """
    # Initialize API and calendar
    api_cal = select_api_source(args, api_src_type)

    if args.source:
        my_calendar = args.source
    else:
        my_calendar = select_calendar(api_cal)

    # Set the active calendar using socialModules method
    api_cal.setActive(my_calendar)

    # Fetch events from calendar using socialModules methods
    api_cal.setPostsType("posts")
    api_cal.setPosts()
    all_posts = api_cal.getPosts()

    # Filter out past events - get only future events
    today = datetime.datetime.now()
    future_events = []
    for post in all_posts:
        post_date = api_cal.getPostDate(post)
        if post_date and post_date >= today:
            future_events.append(post)

    print("Upcoming events (up to 20):")
    for event in future_events[:20]:
        print(f"- {api_cal.getPostTitle(event)}")

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    # Use the helper function to filter events by title
    filtered_events = filter_events_by_title(api_cal, future_events, text_filter)

    if not filtered_events:
        print("No events found matching the criteria.")
        return

    selected_events = select_events_by_user_input(api_cal, filtered_events, action_verb)

    # Handle destination calendar if needed
    my_calendar_dst = None
    if destination_needed:
        if args.destination:
            my_calendar_dst = args.destination
        else:
            my_calendar_dst = select_calendar(api_cal)

    # Perform the specific action on selected events
    for event in selected_events:
        action_func(api_cal, event, my_calendar, my_calendar_dst)


def delete_action(api_cal, event, my_calendar, my_calendar_dst):
    """Action function to delete an event."""
    api_cal.getClient().events().delete(calendarId=my_calendar, eventId=event["id"]).execute()
    print(f"Deleted event: {event['summary']}")


def delete_events_cli(args):
    """Deletes events from a calendar."""
    process_calendar_events(args, "delete", delete_action)


def move_action(api_cal, event, my_calendar, my_calendar_dst):
    """Action function to move an event (copy then delete)."""
    my_event = {
        "summary": event["summary"],
        "description": event["description"],
        "start": event["start"],
        "end": event["end"],
    }
    if "location" in event:
        my_event["location"] = event["location"]

    api_cal.getClient().events().insert(calendarId=my_calendar_dst, body=my_event).execute()
    print(f"Copied event: {my_event['summary']}")
    api_cal.getClient().events().delete(calendarId=my_calendar, eventId=event["id"]).execute()
    print(f"Deleted event: {event['summary']}")


def move_events_cli(args):
    """Moves events from a source calendar to a destination calendar."""
    process_calendar_events(args, "move", move_action, destination_needed=True)


def update_event_status_cli(args):
    """Update event status from busy to available for selected events."""
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
        status = event.get("transparency", "opaque")  # "opaque" means busy, "transparent" means free
        title = api_cal.getPostTitle(event) or "No Title"
        print(f"- [{status}] {title}")

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    events_to_update = []
    for event in res["items"]:
        title = api_cal.getPostTitle(event) or "No Title"
        if text_filter in title:
            # Only include events that are currently "busy" (opaque)
            if event.get("transparency", "opaque") == "opaque":
                events_to_update.append(event)

    if not events_to_update:
        print("No busy events found matching the criteria.")
        return

    selected_events = select_events_by_user_input(api_cal, events_to_update, "update")

    for event in selected_events:
        # Update the event's transparency to "transparent" (available/free)
        event["transparency"] = "transparent"

        # Perform the update
        updated_event = (
            api_cal.getClient()
            .events()
            .update(
                calendarId=my_calendar,
                eventId=event["id"],
                body=event
            )
            .execute()
        )

        title = api_cal.getPostTitle(event) or "No Title"
        print(f"Updated event status to available: {title}")


def clean_events_cli(args):
    """Combined command to clean calendar entries (select between copy or delete)."""
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

    # Use the helper function to filter events by title
    events_to_process = filter_events_by_title(api_cal, res["items"], text_filter)

    if not events_to_process:
        print("No events found matching the criteria.")
        return

    selected_events = select_events_by_user_input(api_cal, events_to_process, "process")

    # Ask user whether to copy or delete
    actions = ['Delete', 'Copy']
    msg = "Select operation:"
    for i, act in enumerate(actions):
        msg = f"{msg}\n{i}) {act}"
    msg = f"{msg}\n"

    action_sel = input(msg)

    my_calendar_dst = None
    if action_sel == '1':  # Copy action
        if args.destination:
            my_calendar_dst = args.destination
        else:
            my_calendar_dst = select_calendar(api_cal)

    for event in selected_events:
        if action_sel == '1':  # Copy
            copy_action(api_cal, event, my_calendar, my_calendar_dst)
        else:  # Delete
            delete_action(api_cal, event, my_calendar, my_calendar_dst)

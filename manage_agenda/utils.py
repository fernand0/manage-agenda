import datetime
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import dateparser
import googleapiclient
from socialModules import moduleHtml
from socialModules.moduleContent import display_posts
from socialModules.moduleRules import moduleRules
from socialModules.configMod import (
    safe_get,
    select_from_list,
)

from manage_agenda.config import config
from manage_agenda.exceptions import (
    CalendarError,
)

from manage_agenda.utils_base import (
    format_time,
    write_file,
)
from manage_agenda.utils_llm import select_llm
from manage_agenda.utils_web import reduce_html


@dataclass
class Args:
    """Arguments container for CLI commands."""

    interactive: bool = False
    delete: Optional[bool] = None
    source: Optional[str] = None
    ai: Optional[str] = None
    verbose: bool = False
    destination: Optional[str] = None
    text: Optional[str] = None
    output: str = "calendar"
    force_refresh: bool = False


def get_add_sources(rules=None):
    """Returns a list of available sources for the add command."""
    rules = rules or moduleRules.from_config()
    email_sources = rules.selectRule(["gmail", "imap"])
    return email_sources, [("web/http", "set", "(Enter URLs or leave empty)")] + [
        ("text", "set", "(enter filenames or leave empty)")
    ]


def print_first_10_lines(content, content_type="content"):
    """Prints the first 10 lines of the given content."""
    print(f"\n--- First 10 lines of {content_type} ---")
    for i, line in enumerate(content.splitlines()):
        if i >= 10:
            break
        print(line)
    print("-------------------------------------\n")


def _get_text_snippet(original_content: str) -> Optional[str]:
    """Get a text snippet from the user and preserve the Message date.

    Args:
        original_content: Original content to extract Message date from

    Returns:
        The new content text with Message date preserved, or None if no input
    """
    print("Paste the relevant part of the text here (finish with Ctrl-D):")
    lines = []
    while True:
        try:
            line = input()
            lines.append(line)
        except EOFError:
            break

    new_content_text = None
    if lines:
        new_content_text = "\n".join(lines)
        # Try to preserve Message date for relative date processing
        for line in original_content.splitlines():
            if line.startswith("Message date:"):
                new_content_text += f"\n{line}"
                break
    return new_content_text


def _print_context_and_options(content: str, options_prompt: str) -> str:
    """Print URL (if found), first 10 lines of content, and prompt for options.

    Args:
        content: The source text to display context from
        options_prompt: The prompt string showing available options

    Returns:
        The user's choice (lowered and stripped)
    """
    # Show URL if available in original content
    for line in content.splitlines():
        if line.startswith("Url: "):
            print(line)
            break

    if args.verbose:
        print_first_10_lines(content, "source text")

    return input(options_prompt).lower().strip()


def select_calendar(calendar_api, title="", args=None):
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

        if (args and args.interactive) or not args:
            selection, cal = select_from_list(eligible_calendars, "summary", title=title)
        else:
            term = "kkk"
            matches = [item for item in eligible_calendars if term in item["summary"]]
            cal = matches[0] if matches else None
            selection = eligible_calendars.index(cal)

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


def add_message_to_event_description(event, content):
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
        else:
            abstract = api_cal.getPostAbstract(event)
            if abstract and text_filter and text_filter.lower() in abstract.lower():
                filtered_events.append(event)
            elif not text_filter:  # If no filter, include all events with titles
                if title:
                    filtered_events.append(event)

    return filtered_events


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

    return vcal_json


def get_event_from_llm(model, prompt, post_id, verbose=False):
    """Gets event data from LLM, handling response and JSON parsing."""
    print(f"Calling LLM {model.model_name}")
    event, vcal_json = None, None
    start_time = time.time()
    llm_response = model.generate_text(prompt)
    write_file(f"log/{model.model_name}/{post_id}_llm.txt", llm_response)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"AI call took {format_time(elapsed_time)} ({elapsed_time:.2f} seconds)")

    memory_error_occurred = False
    json_error_occurred = True

    if not llm_response:
        print("Failed to get response from LLM.")
    elif "model requires more system memory" in llm_response:
        print(
            "LLM failed due to insufficient memory. Model requires more"
            "system memory than available."
        )
        # Set a flag to indicate memory error occurred
        memory_error_occurred = True
    else:
        if verbose:
            print(f"Reply:\n{llm_response}")
            print("End Reply")

        response = llm_response.replace("\n", " ")
        llm_response = response

        try:
            import ast

            # If there are several comma-separated jsons it creates a tuple
            vcal_json = ast.literal_eval(extract_json(llm_response))
            write_file(
                f"log/{model.model_name}/{post_id}_vcal_extracted.txt", json.dumps(vcal_json)
            )
            if verbose:
                print(f"Json:\n{vcal_json}")
            event = vcal_json
            json_error_occurred = False
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in vCal data: {vcal_json}")
            logging.error(f"Error: {e}")
        except SyntaxError as e:
            logging.error(f"Syntax error: {vcal_json}")
            logging.error(f"Error: {e}")
        except ValueError as e:
            logging.error(f"Value error: {vcal_json}")
            logging.error(f"Error: {e}")

    # Return appropriate values based on whether memory error occurred
    if memory_error_occurred or json_error_occurred:
        event = None
        if memory_error_occurred:
            vcal_json = "MemoryError"
        else:
            vcal_json = "JsonError"
    return event, vcal_json, elapsed_time


def get_event_from_llm_with_retry(model, prompt, post_id, args):
    """Wrapper for get_event_from_llm with consistent retry and error handling logic."""
    event = None
    vcal_json = None
    elapsed_time = 0
    memory_error_occurred = False
    json_error_occurred = False
    retries = 0
    max_retries = 3

    event_old = create_event_dict()
    # while not event and not memory_error_occurred and not json_error_occurred and retries < max_retries:
    while (
        args.interactive
        and not event
        and not memory_error_occurred
        and not json_error_occurred
        and retries < max_retries
    ) or (
        not args.interactive
        and (
            not event
            or (
                event
                and (
                    (event[0] if isinstance(event, (list, tuple)) else event)["start"]["dateTime"]
                    != event_old["start"]["dateTime"]
                )
                and retries < 2
            )
        )
    ):
        if event and not args.interactive:
            event_old = event[0] if isinstance(event, (list, tuple)) else event
        event, vcal_json, elapsed_time = get_event_from_llm(model, prompt, post_id, args.verbose)
        retries += 1

        # Handle memory error specifically
        if vcal_json == "MemoryError":
            print("Switching to a different LLM due to memory constraints...")

            # Determine source based on interactive mode
            # FIXME: what if we have another model?
            source = None if args.interactive else model.model_name  # "gemini"
            if not args.interactive:
                # In non-interactive mode, try to switch to a lighter model automatically
                print("Trying to switch to a lighter model automatically...")
            print(f"Source: {source}")

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
                    print(f"Selected new AI model: " f"{model.__class__.__name__}")
                else:
                    print(f"Switched to lighter AI model: " f"{model.__class__.__name__}")

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
        elif vcal_json == "JsonError":
            event = None
            vcal_json = None
            json_error_occurred = False
            print("Error in generated Json...")
    if event and (
        (event[0] if isinstance(event, (list, tuple)) else event)["start"]["dateTime"]
        != event_old["start"]["dateTime"]
    ):
        print("Events matching")

    if not event and retries >= max_retries:
        vcal_json = "RetryError"
        print("Max retries reached. Skipping event processing.")
        # For other types of failures (no event and not memory error), the loop continues naturally
        # due to the while condition "while not event and not memory_error_occurred"
        # No explicit action needed here

    return event, vcal_json, elapsed_time


def authorize(args, rules=None):
    rules = rules or moduleRules.from_config()
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


def select_api(args, api_type, rules=None, title=""):
    """Selects an API, interactive or not."""
    rules = rules or moduleRules.from_config()

    if api_type == "email":
        service = ["gmail", "imap"]
    else:
        service = list(api_type) if isinstance(api_type, (list, tuple)) else [api_type]

    if args.interactive:
        api = rules.selectRuleInteractive(service, title=title)
    else:
        sources = rules.selectRule(service, "")
        if not sources:
            logging.warning(f"No {api_type} sources configured.")
            return None
        selected_source = sources[0]
        source_details = rules.more.get(selected_source, {})
        logging.info(f"Source: {selected_source} - {source_details}")
        api = rules.readConfigSrc("", selected_source, source_details)

    return api


def _get_msgs_from_folder(args, source_name, rules=None):
    """Helper function to get posts stored in some folder."""
    # FIXME: maybe a folder argument?

    if source_name and isinstance(source_name, list):
        txt_files = source_name
    else:
        target_dir = Path(config.MSG_TXT_DIR)
        txt_files = target_dir.glob("*.txt")

    posts = []
    for file_path in txt_files:
        file_path = Path(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            file_name = file_path.stem
            posts.append([file_name, content])

    if not posts:
        if not os.path.exists(target_dir):
            print(f"There is no {target_dir} directory")
        else:
            print(f"There are no posts in {target_dir}")
        posts = None

    return None, posts

def _get_events_from_calendar(args, api_src, calendar=None):
    """Helper function to get events from a specific calendar."""
    "FIXME: maybe a folder argument?"

    if calendar:
        api_src.setCalendar(calendar)
    api_src.setPosts()
    posts = api_src.getPosts()

    return(posts)


def _get_emails_from_folder(args, api_src, folder=None):
    """Helper function to get emails from a specific folder."""
    "FIXME: maybe a folder argument?"

    posts = None

    if not folder:
        folder = "INBOX/zAgenda" if "imap" in api_src.service.lower() else "zAgenda"
    api_src.setPostsType("posts")
    api_src.setLabels()
    label = api_src.getLabels(folder)
    if not label:
        print(f"There are no posts tagged with label {folder}")
    else:
        api_src.setChannel(folder)
        api_src.setPosts()
        posts = api_src.getPosts()

    return posts


def list_folder(args, service):
    """List posts from the selected folder for a supported service."""
    rules = moduleRules.from_config()
    if service in ["email", "imap", "gmail"]:
        api_src = rules.selectRuleInteractive(service=service, title="Select mail account")
        posts = _get_emails_from_folder(args, api_src)
    elif service == "gcalendar":
        api_src = rules.selectRuleInteractive(service=service, title="Select calendar account")
        posts = _get_events_from_calendar(args, api_src)
    else:
        raise ValueError(f"Unsupported folder service: {service}")
    display_posts(api_src, posts)


def _create_llm_prompt(*args):
    """Constructs the LLM prompt for event extraction."""
    from pathlib import Path

    if len(args) == 2:
        content_text, reference_date_time = args
        event = create_event_dict()
    elif len(args) == 3:
        event, content_text, reference_date_time = args
    else:
        raise TypeError(
            f"_create_llm_prompt() takes 2 or 3 positional arguments but {len(args)} were given"
        )

    content_text = content_text.replace("\r", "")

    # Create the event template for the LLM to fill in

    # Get the path to the prompt template
    prompt_dir = Path(__file__).parent / "prompts"
    prompt_file = prompt_dir / "event_extraction_prompt.txt"

    # Read the prompt template
    if prompt_file.exists():
        prompt_template = prompt_file.read_text(encoding="utf-8")
    else:
        # Fallback to the original prompt if file is not found
        prompt_template = (
            "Extract event information from the provided text and fill in the JSON structure below.\n\n"
            f"JSON structure to fill:\n'{event}'\n\n"
            "INSTRUCTIONS:\n"
            "1. Extract event details from the message body ('Message:') and subject ('Subject:').\n"
            "2. Use the reference date marked with 'Message date:' when interpreting relative dates (e.g., 'next Thursday').\n"
            "3. Default timezone is CET if not specified otherwise.\n"
            "4. The result must be a valid JSON with all fields and values enclosed in double quotes.\n"
            "5. Replace any double or single quotes inside the extracted content with single quotes (') to avoid JSON parsing errors.\n"
            "6. Place the start and end times in event['start']['dateTime'] and event['end']['dateTime'] respectively.\n"
            "7. Do not translate the text; keep all information in the original language.\n"
            "8. Return ONLY the completed JSON structure without any additional comments or explanations.\n\n"
            "SOURCE TEXT:\n"
            f"{content_text}.\n"
        )

    # Fill in the template with actual values
    return prompt_template.format(event=event, content_text=content_text)


def _extract_event_with_llm_retry(
    args, model, content_text, reference_date_time, post_identifier, subject_for_print
):
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
        restart"""
    from manage_agenda.utils_events import adjust_event_times

    original_content = content_text
    prompt_content = content_text
    total_elapsed_time = 0

    while True:
        # Create initial event dict for helper
        prompt = _create_llm_prompt(prompt_content, reference_date_time)
        write_file(f"log/{post_identifier}_prompt.txt", prompt)
        if args.verbose:
            print(f"Prompt:\n{prompt}")
            print("\nEnd Prompt:")

        # Get AI reply with retry logic
        event, vcal_json, elapsed_time = get_event_from_llm_with_retry(
            model, prompt, post_identifier, args
        )
        total_elapsed_time += elapsed_time

        # Check for memory error
        if args.verbose:
            print(f"Event: {event}")
        memory_error = event is None and vcal_json == "MemoryError"
        retry_error = event is None and vcal_json == "RetryError"

        if memory_error or retry_error:
            return event, vcal_json, total_elapsed_time, False, False, False
            # Not successful, don't restart, don't need another AI

        # Process event data
        if event:
            if not isinstance(event, (list, tuple)):
                event = [
                    event,
                ]
            # if isinstance(event, (list, tuple)):
            processed_events = []
            for single_event in event:
                if args.verbose:
                    print(f"Single event: {single_event}")
                if isinstance(single_event, dict):
                    single_event = add_message_to_event_description(single_event, original_content)
                    single_event = adjust_event_times(single_event)
                    processed_events.append(single_event)
            event = processed_events if processed_events else None
            if args.verbose:
                print(f"Proc event: {processed_events}")
            break

        # If we got here, extraction failed (event is None)
        # Save whatever we got for debugging
        write_file(
            f"log/{post_identifier}_fail.vcal",
            json.dumps(vcal_json) if vcal_json else "Failed extraction",
        )

        if not args.interactive:
            return None, vcal_json, total_elapsed_time, False, False, False

        # Interactive fallback
        print("\nLLM failed to extract event information.")
        choice = _print_context_and_options(
            original_content, "Options: (r)etry, (p)rovide relevant text snippet, (s)kip item: "
        )

        if choice == "r":
            prompt_content = original_content  # Reset to original content for retry
            continue
        elif choice == "p":
            snippet = _get_text_snippet(original_content)
            if snippet:
                prompt_content = snippet
                continue

        # Skip or invalid choice
        return None, vcal_json, total_elapsed_time, False, False, False

    write_file(
        f"log/{model.model_name}/{post_identifier}_event_processed.vcal",
        json.dumps(event) if isinstance(event, (dict, list)) else str(event),
    )
    # Save final successful vCal data
    if isinstance(event, (list, tuple)):
        # if isinstance(vcal_json, (list, tuple)) and len(vcal_json) == len(event):
        #     for idx, event_vcal in enumerate(vcal_json, start=1):
        #         print(f"Id: {post_identifier}")
        #         write_file(f"log/{post_identifier}_{idx}.vcal", json.dumps(event_vcal) if isinstance(event_vcal, (dict, list)) else str(event_vcal))
        # else:
        for idx in range(len(event)):
            write_file(
                f"log/{model.model_name}/{post_identifier}_{idx+1}.vcal",
                json.dumps(event[idx]) if isinstance(event[idx], (dict, list)) else str(event[idx]),
            )
    else:
        write_file(
            f"log/{post_identifier}.vcal",
            json.dumps(event) if isinstance(event, (dict, list)) else str(event),
        )

    return event, vcal_json, total_elapsed_time, True, False, False


def _display_event_info(
    event, subject_for_print, elapsed_time=None, model=None, post_identifier=""
):
    """
    Display event information consistently across the application.

    Args:
        event: Event dictionary containing start and end times
        subject_for_print: Subject/title to display
        elapsed_time: Optional time taken for AI processing

    Returns:
        Tuple of (start_time_local, end_time_local) for potential reuse
    """
    from manage_agenda.utils_events import _format_datetime_for_display

    start_time = safe_get(event, ["start", "dateTime"])
    end_time = safe_get(event, ["end", "dateTime"])

    # Convert to local timezone for display
    start_time_local = _format_datetime_for_display(start_time)
    end_time_local = _format_datetime_for_display(end_time)

    # Use extracted summary if available, otherwise fallback to subject_for_print
    event_summary = safe_get(event, ["summary"]) or subject_for_print

    print("=====================================")
    print(f"Summary: {event_summary}")
    if post_identifier:
        print(f"File: {post_identifier}")
    print(f"Start: {start_time_local}")
    print(f"End: {end_time_local}")
    print(f"Model: {model.model_name}")

    if elapsed_time is not None:
        print(f"Time: {format_time(elapsed_time)} ({elapsed_time:.2f} seconds)")
    # FIXME we should add the number of retries

    print("=====================================")

    return start_time_local, end_time_local


def _process_event_with_llm_and_calendar(
    args,
    model,
    content_text,
    reference_date_time,
    post_identifier,
    subject_for_print,
    rules=None,
):
    """
    Common logic for processing an event with LLM, adjusting times, and publishing to calendar.
    """
    from manage_agenda.utils_events import (
        _validate_event_dates_interactive,
        _validate_event_dates_non_interactive,
        adjust_event_times,
    )

    # Initialize result variables
    event = None
    calendar_result = None
    success = False
    should_process = True
    date_validation_retries = 0
    max_date_validation_retries = 3

    # Process until success or definitive failure
    while should_process and not success:
        if date_validation_retries >= max_date_validation_retries:
            print(
                f"Max date validation retries ({max_date_validation_retries}) "
                f"reached for {post_identifier}. Skipping event processing."
            )
            should_process = False
            break
        # Extract event with LLM and validate it
        event, vcal_json, elapsed_time, extraction_success, need_restart, need_another_ai = (
            _extract_event_with_llm_retry(
                args, model, content_text, reference_date_time, post_identifier, subject_for_print
            )
        )

        # Handle restart case first
        if need_restart or need_another_ai:
            # Loop will continue to restart the process
            # Need to get another AI response and try again
            pass  # Intentionally do nothing, just let the loop continue
        else:
            # Check if extraction was unsuccessful
            if not extraction_success:
                should_process = False  # Indicate failure due to memory error or other issues
            else:
                if event is None:
                    should_process = False  # Indicate failure
                else:
                    # In case it is not a list we will make a list
                    events = list(event)
                    if getattr(args, "output", "calendar") == "calendar":
                        api_dst_type = "gcalendar"
                        title = events[0]["summary"]
                        api_dst = select_api(
                            args, api_dst_type, rules=rules, title="Select Calendar"
                        )
                        selected_calendar = select_calendar(api_dst, title=title, args=args)
                    else:
                        api_dst = None
                        selected_calendar = None

                    calendar_results = []

                    if getattr(args, "output", "calendar") == "calendar" and not selected_calendar:
                        print("No calendar selected, skipping event creation.")
                    else:
                        for idx, single_event in enumerate(events, start=1):
                            single_event = adjust_event_times(single_event)
                            write_file(
                                f"log/{model.model_name}/{post_identifier}_{idx}.json",
                                json.dumps(single_event),
                            )

                            _display_event_info(
                                single_event,
                                subject_for_print,
                                elapsed_time,
                                model,
                                post_identifier,
                            )

                            retry_needed = False
                            if args.interactive:
                                single_event, is_valid, _ = _validate_event_dates_interactive(
                                    single_event, post_identifier
                                )
                                retry_needed = not is_valid
                            else:
                                single_event, is_valid, validation_errors = (
                                    _validate_event_dates_non_interactive(
                                        single_event, post_identifier
                                    )
                                )
                                if not is_valid:
                                    print(f"Date validation errors for {post_identifier}:")
                                    for err in validation_errors:
                                        print(f"  - {err}")
                                    date_validation_retries += 1
                                    should_process = True
                                    break

                            if retry_needed and model and content_text and reference_date_time:
                                date_validation_retries += 1
                                should_process = True
                                break

                            if single_event is not None:
                                _add_ai_metadata_to_event(single_event, model, elapsed_time)
                                file_name = f"log/{post_identifier}_{idx}_times.json"
                                if getattr(args, "output", "calendar") == "calendar":
                                    published, calendar_result = _publish_event_to_calendar(
                                        api_dst, single_event, selected_calendar
                                    )
                                else:
                                    file_name_res = (
                                        f"log/{model.model_name}/{post_identifier}_{idx}_times"
                                    )
                                    write_file(f"{file_name_res}.json", json.dumps(single_event))
                                    calendar_result = f"{post_identifier}_{idx}_times.json"
                                    published = True

                                if published:
                                    calendar_results.append(calendar_result)
                                    if getattr(args, "output", "calendar") == "calendar":
                                        print("Calendar event created")
                                    else:
                                        print(f"File {post_identifier}_{idx}_times.json created")
                                    success = True
                                    write_file(file_name, json.dumps(single_event))
                    print(f"Success: {success}")
                    if success:
                        if args.verbose:
                            print(f"Events: {events}")
                            print(f"Results: {calendar_results}")
                        return events, calendar_results
                    else:
                        return None, None
        return None, None


def _publish_event_to_calendar(api_dst, event, selected_calendar):
    """
    Publish an event to Google Calendar with timezone error handling.

    Args:
        api_dst: Calendar API destination
        event: Event dictionary to publish
        selected_calendar: Calendar ID to publish to

    Returns:
        tuple: (success, calendar_result) where success is a bool and
               calendar_result is the publish result on success, None on failure.
    """
    from manage_agenda.utils_events import _ensure_valid_event_timezones

    try:
        calendar_result = api_dst.publishPost(
            post={"event": event, "idCal": selected_calendar},
            api=api_dst,
        )
        return True, calendar_result
    except googleapiclient.errors.HttpError as e:
        logging.error(f"Error creating calendar event: {e}")
        if "Invalid time zone definition for end time'" in str(e):
            logging.info(
                "Detected invalid timezone definition for end time. Correcting event timezones and retrying."
            )
            event = _ensure_valid_event_timezones(event, fallback_tz="UTC")
            try:
                calendar_result = api_dst.publishPost(
                    post={"event": event, "idCal": selected_calendar},
                    api=api_dst,
                )
                return True, calendar_result
            except Exception as retry_e:
                logging.error(f"Retry after timezone correction failed: {retry_e}")
    return False, None


def _add_ai_metadata_to_event(event, model, elapsed_time, confidence_score=None):
    """
    Add AI model metadata to the event for tracking and transparency.

    Args:
        event (dict): The event dictionary
        model: The AI model used to process the event
        elapsed_time (float): Time taken for AI processing in seconds
        confidence_score (float, optional): Confidence score of the AI response
    """
    import datetime

    # Get model name - try multiple approaches in order of preference
    model_name = "unknown"
    if model:
        from unittest.mock import Mock

        def is_mock(val):
            return isinstance(val, Mock)

        val = getattr(model, "model_name", None)
        if val is not None and not is_mock(val):
            model_name = str(val)
        elif hasattr(model, "get_name") and callable(model.get_name):
            try:
                res = model.get_name()
                if res is not None and not is_mock(res):
                    model_name = str(res)
            except NotImplementedError:
                pass

        if model_name == "unknown":
            val = getattr(model, "name", None)
            if val is not None and not is_mock(val):
                model_name = str(val)
            elif not is_mock(model):
                model_name = str(model)

    # Add extended properties for programmatic access
    event.setdefault("extendedProperties", {}).setdefault("private", {}).update(
        {
            "ai_model_used": model_name,
            "processing_timestamp": datetime.datetime.now(datetime.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "processing_elapsed_time_seconds": f"{elapsed_time:.2f}",
        }
    )

    if confidence_score is not None:
        event["extendedProperties"]["private"]["confidence_score"] = f"{confidence_score:.2f}"

    # Add information to description for human visibility
    ai_metadata_text = f"\n\n---\nAI Processing Info:\n- Model: {model_name}\n- Processing time: {elapsed_time:.2f} seconds"

    if confidence_score is not None:
        ai_metadata_text += f"\n- Confidence: {confidence_score:.2f}"

    # Append to the description
    current_description = event.get("description", "")
    event["description"] = current_description + ai_metadata_text


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

        try:
            post_date_time = parsedate_to_datetime(post_date)
        except (ValueError, TypeError):
            parsed = dateparser.parse(post_date)
            if parsed is not None:
                post_date_time = parsed
            else:
                try:
                    parts = [int(p) for p in post_date.split("-") if p.isdigit()]
                    post_date_time = datetime.datetime(parts[0], parts[1], parts[2])
                except (IndexError, ValueError):
                    post_date_time = datetime.datetime.now()

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
                logging.info(f"Res: {res}")
                if "Fail!" not in res:
                    logging.info(f"Email {post_id} processed successfully.")
                    return  # Success
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} of {max_retries + 1} failed: {e}")
                if attempt < max_retries:
                    logging.info("Retrying to connect to the email server...")

                    rules = rules or moduleRules.from_config()
                    logging.info(f"Source: {source_name}")
                    source_details = rules.more.get(source_name, {})
                    api_src = rules.readConfigSrc("", source_name, source_details)
                    if label:
                        api_src.setChannel(label)
                else:
                    logging.error(
                        f"Could not delete email {post_id} after {max_retries + 1} attempts: {e}"
                    )
                    return  # Exit after last attempt failure


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


def _process_common_flow(
    args, model, items, metadata_extractor, content_extractor, item_cleaner=None, rules=None
):
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
        write_file(f"log/{post_id}_text.txt", content_text)
        if args.verbose:
            print_first_10_lines(content_text, "content")

        # 5. Process with LLM
        processed_event, calendar_result = _process_event_with_llm_and_calendar(
            args, model, content_text, post_date_time, post_id, post_title, rules=rules
        )

        # processed_event = True

        if processed_event:
            processed_any_event = True
            # 6. Post-process
            if item_cleaner:
                item_cleaner(item, i, post_id)

    return processed_any_event


def process_txt_cli(args, model, source_name=None, rules=None):
    """Processes txt files and creates calendar events."""

    if not source_name:
        source_name = input(
            f"Enter filenames separated by spaces (leave empty to use {config.MSG_TXT_DIR}): "
        ).split()
        if not source_name:
            print(f"No filenames entered. Extracting texts from {config.MSG_TXT_DIR}...")

    api_src, posts = _get_msgs_from_folder(args, source_name, rules=rules)

    if posts:

        def metadata_extractor(post, i):
            # Use getPostIdM if it exists, otherwise use getPostId
            if hasattr(api_src, "getPostIdM"):
                post_id = api_src.getPostIdM(post)
            else:
                post_id = post[0]

            # print(f"Post id: {post_id}")
            # print(f"Post id: {post_id}")
            lines_txt = post[1].split("\n")
            import re

            date = ""
            for line in reversed(lines_txt):
                match = re.search(r"(?i)date:\s*([^\s\n]+)", line)
                if match:
                    date = match.group(1)
                    break

            if not date and len(lines_txt) > 1:
                last_line = lines_txt[-1].strip() or lines_txt[-2].strip()
                if last_line:
                    parts = last_line.split(": ")
                    if len(parts) > 1:
                        date = "".join(parts[1:])

            if not date and len(lines_txt) > 1:
                date = lines_txt[1].split(" ")[-1]

            if " " in date:
                date = date.split(" ")[0]

            if not args.interactive:
                date = datetime.datetime.today()

            if "Subject: " in lines_txt:
                title = next((i for i, s in enumerate(lines_txt) if "Subject: " in s), -1)
            else:
                title = lines_txt[0]
            logging.info(f"Extracted info. PostId: {post_id} Title: {title} Date: {date}")
            return post_id, title, date

        def content_extractor(post, i, post_date_time, post_title):
            lines_txt = post[1].split("\n")
            if "Subject: " in lines_txt:
                post_title = next((i for i, s in enumerate(lines_txt) if "Subject: " in s), -1)
            else:
                post_title = lines_txt[0]
            full_email_content = "".join(lines_txt[3:-1])
            date_message = lines_txt[-1].split(" ")[-1]
            # FIXME is this ok?
            date_message = datetime.datetime.today()
            return (
                f"Subject: {post_title}\n"
                f"Message: {full_email_content}\n"
                f"Message date: {date_message}\n"
            )

        def item_cleaner(post, i, post_id):
            pass

        return _process_common_flow(
            args, model, posts, metadata_extractor, content_extractor, item_cleaner, rules=rules
        )
    return False  # Default return if something went wrong before the main logic


def process_email_cli(args, model, source_name=None, api_src=None, rules=None):
    """Processes emails and creates calendar events."""

    if not api_src:
        if source_name:
            rules = rules or moduleRules.from_config()
            source_details = rules.more.get(source_name, {})
            api_src = rules.readConfigSrc("", source_name, source_details)
        else:
            api_src = select_api(args, "email", rules=rules)

    posts = _get_emails_from_folder(args, api_src)

    if posts:

        def metadata_extractor(post, i):
            # Use getPostIdM if it exists, otherwise use getPostId
            if hasattr(api_src, "getPostIdM"):
                post_id = api_src.getPostIdM(post)
            else:
                post_id = api_src.getPostId(post)
            return post_id, api_src.getPostTitle(post), api_src.getPostDate(post)

        def content_extractor(post, i, post_date_time, post_title):
            full_email_content = api_src.getPostBody(post)
            date_message = str(post_date_time).split(" ")[0]
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
            args, model, posts, metadata_extractor, content_extractor, item_cleaner, rules=rules
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


def _get_links_from_notes():
    """Extracts URLs from all notes in ~/notes."""
    try:
        from note_app import NoteManager

        notes_dir = os.path.expanduser("~/notes")
        if not os.path.exists(notes_dir):
            logging.warning(f"Notes directory {notes_dir} does not exist.")
            return {}

        manager = NoteManager(storage_dir=notes_dir)
        titles = manager.list_notes()
        url_to_notes = {}
        for title in titles:
            note = manager.read_note(title)
            if note:
                # get_urls() returns explicitly added URLs
                # get_links() returns URLs extracted from content
                note_urls = set(note.get_urls()) | set(note.get_links())
                for url in note_urls:
                    if url not in url_to_notes:
                        url_to_notes[url] = []
                    url_to_notes[url].append(title)
        return url_to_notes
    except ImportError:
        logging.warning("note_app not found. Cannot extract links from notes.")
        return {}
    except Exception as e:
        logging.error(f"Error extracting links from notes: {e}")
        return {}


def process_web_cli(args, model, urls=None, force_refresh=False, rules=None):
    """Processes web pages and creates calendar events."""

    url_to_notes = {}
    urls_input = None
    if not urls:
        if args.interactive:
            urls_input = input(
                "Enter URLs separated by spaces (leave empty to use ~/notes): "
            ).split()
        if not urls_input or not args.interactive:
            print("No URLs entered. Extracting links from ~/notes...")
            url_to_notes = _get_links_from_notes()
            if not url_to_notes:
                print("No links found in ~/notes.")
                return False
            print(f"Found notes: {url_to_notes}")
            urls = list(url_to_notes.keys())
            print(f"Found total of links: {len(urls)}")
            print(f"Found links: {urls}")
        else:
            urls = urls_input

    api_src, posts = _get_pages_from_urls(args, urls)

    if posts:
        # Instantiate manager if we might need to delete notes
        manager = None
        if url_to_notes:
            try:
                from note_app import NoteManager

                notes_dir = os.path.expanduser("~/notes")
                manager = NoteManager(storage_dir=notes_dir)
            except ImportError:
                pass

        def metadata_extractor(post, i):
            title = api_src.getPostTitle(post)
            if not title:
                title = urls[i]

            # Generate a safe, readable filename from the URL
            from .utils_web import extract_domain_and_path_from_url
            import re

            processed_url = extract_domain_and_path_from_url(urls[i])
            # Replace unsafe characters with underscores
            safe_id = re.sub(r"[^a-zA-Z0-9.-]", "_", processed_url)

            hash_value = hash(urls[i])

            # Truncate to a safe length (e.g., 150 chars) to avoid "File name
            # too long" errors
            if len(safe_id) > 130:
                safe_id = safe_id[:130]
            safe_id = f"{safe_id}_{hash_value}"

            return safe_id, title, datetime.datetime.now()

        def content_extractor(post, i, post_date_time, post_title):
            web_content_reduced = reduce_html(urls[i], post, force_refresh=force_refresh)
            if not web_content_reduced:
                print(f"Could not process {urls[i]}, skipping.")
                return None

            date_message = str(post_date_time).split(" ")[0]
            return (
                f"Url: {urls[i]}\n"
                f"Subject: {post_title}\n"
                f"Message: {web_content_reduced}\n"
                f"Message date: {date_message}\n"
            )

        def item_cleaner(post, i, post_id):
            url = urls[i]
            if url in url_to_notes and manager:
                for note_title in url_to_notes[url]:
                    print(f"Deleting note: {note_title}")
                    manager.delete_note(note_title)

        return _process_common_flow(
            args, model, posts, metadata_extractor, content_extractor, item_cleaner, rules=rules
        )

    return False  # Default return if something went wrong before the main logic


def add_events_cli(args, rules=None):
    """Add entries to the calendar from various sources (email, web, text)."""
    rules = rules or moduleRules.from_config()

    model = select_llm(args)

    print(f"Selected model: {model.model_name}")

    # source = args.source or ""
    # if source in ("email", "gmail", "imap"):
    #    api_src = select_source_by_type(args, source, rules=rules)
    #    process_email_cli(args, model, api_src=api_src, rules=rules)
    # elif source == "web":
    #    process_web_cli(args, model, force_refresh=args.force_refresh)
    # elif source == "text":
    #    process_txt_cli(args, model, rules=rules)
    # else:
    # if True:
    #    # Fallback: select from all sources interactively
    sources, more_options = get_add_sources(rules=rules)
    sources = ["gmail", "imap"]
    if args.verbose:
        print(f"Sources: {sources}")
    if args.interactive:
        # sel, selected = select_from_list(sources, more_options=more_options, title="Sources of information")
        selected = rules.selectRuleInteractive(
            sources, title="Select Rule", more_options=more_options
        )
    else:
        print(f"Selecting: {args.source}")
        matches = [item for item in sources if args.source in item]
        selected = matches[0] if matches else None
        print(f"Selected: {selected}")
    if selected:
        print(f"\nSelected source: {selected}")
        if hasattr(selected, "__iter__") and (
            ("web" in str(selected)) or ("http" in str(selected))
        ):
            url_list = None
            if isinstance(selected, str) and "http" in selected:
                url_list = selected.split(" ")
            process_web_cli(
                args, model, urls=url_list, force_refresh=args.force_refresh, rules=rules
            )
        elif hasattr(selected, "__iter__") and (("text" in selected) or os.path.exists(selected)):
            file_list = None
            if isinstance(selected, str) and "." in selected:
                file_list = selected.split(" ")
            process_txt_cli(args, model, source_name=file_list, rules=rules)
        else:
            process_email_cli(args, model, api_src=selected, rules=rules)

"""LLM-driven calendar event extraction and publication helpers."""

import ast
import datetime
import json
import logging
import time
from copy import copy
from dataclasses import is_dataclass, replace
from pathlib import Path

import googleapiclient
from socialModules.configMod import safe_get

from manage_agenda.base import format_time, write_file
from manage_agenda.connections import select_api, select_calendar
from manage_agenda.llm import select_llm


def create_event_dict():
    """Create the template dictionary used for extracted calendar events."""
    return {
        "summary": "",
        "location": "",
        "description": "",
        "start": {"dateTime": "", "timeZone": ""},
        "end": {"dateTime": "", "timeZone": ""},
        "recurrence": [],
    }


def add_message_to_event_description(event, content):
    """Add the source content to an extracted event description."""
    event["description"] = f"{safe_get(event, ['description'])}\n\nMessage:\n{content}"
    return event


def _get_text_snippet(original_content):
    """Get replacement source text while preserving its message date."""
    print("Paste the relevant part of the text here (finish with Ctrl-D):")
    lines = []
    while True:
        try:
            lines.append(input())
        except EOFError:
            break

    if not lines:
        return None

    new_content_text = "\n".join(lines)
    for line in original_content.splitlines():
        if line.startswith("Message date:"):
            new_content_text += f"\n{line}"
            break
    return new_content_text


def _print_context_and_options(content, options_prompt, verbose=False):
    """Display the source context and return the selected fallback action."""
    for line in content.splitlines():
        if line.startswith("Url: "):
            print(line)
            break
    if verbose:
        print("\n--- First 10 lines of source text ---")
        for line in content.splitlines()[:10]:
            print(line)
        print("-------------------------------------\n")
    return input(options_prompt).lower().strip()


def extract_json(text):
    """Return the JSON-like portion of an LLM response."""
    if not text.startswith("{"):
        pos = text.find("{")
        if pos != -1:
            text = text[pos:]
    if not text.endswith("}"):
        pos = text.rfind("}")
        if pos != -1:
            text = text[: pos + 1]
    return text


def get_event_from_llm(model, prompt, post_id, verbose=False):
    """Get event data from an LLM and parse its calendar JSON response."""
    print(f"Calling LLM {model.model_name}")
    event, vcal_json = None, None
    start_time = time.time()
    llm_response = model.generate_text(prompt)
    write_file(f"log/{model.model_name}/{post_id}_llm.txt", llm_response)
    elapsed_time = time.time() - start_time
    print(f"AI call took {format_time(elapsed_time)} ({elapsed_time:.2f} seconds)")

    memory_error_occurred = False
    json_error_occurred = True
    if not llm_response:
        print("Failed to get response from LLM.")
    elif "model requires more system memory" in llm_response:
        print(
            "LLM failed due to insufficient memory. Model requires more "
            "system memory than available."
        )
        memory_error_occurred = True
    else:
        if verbose:
            print(f"Reply:\n{llm_response}")
            print("End Reply")
        try:
            vcal_json = ast.literal_eval(extract_json(llm_response.replace("\n", " ")))
            write_file(
                f"log/{model.model_name}/{post_id}_vcal_extracted.txt", json.dumps(vcal_json)
            )
            if verbose:
                print(f"Json:\n{vcal_json}")
            event = vcal_json
            json_error_occurred = False
        except json.JSONDecodeError as error:
            logging.error(f"Invalid JSON in vCal data: {vcal_json}")
            logging.error(f"Error: {error}")
        except SyntaxError as error:
            logging.error(f"Syntax error: {vcal_json}")
            logging.error(f"Error: {error}")
        except ValueError as error:
            logging.error(f"Value error: {vcal_json}")
            logging.error(f"Error: {error}")

    if memory_error_occurred or json_error_occurred:
        event = None
        vcal_json = "MemoryError" if memory_error_occurred else "JsonError"
    return event, vcal_json, elapsed_time


def _with_source(args, source):
    """Clone arguments for alternate-model selection without importing sources.Args."""
    if is_dataclass(args):
        return replace(args, source=source)
    if hasattr(args, "_replace"):
        return args._replace(source=source)
    new_args = copy(args)
    new_args.source = source
    return new_args


def get_event_from_llm_with_retry(model, prompt, post_id, args):
    """Call an LLM repeatedly and switch models if a memory error occurs."""
    event = None
    vcal_json = None
    elapsed_time = 0
    memory_error_occurred = False
    json_error_occurred = False
    retries = 0
    max_retries = 3
    event_old = create_event_dict()

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

        if vcal_json == "MemoryError":
            print("Switching to a different LLM due to memory constraints...")
            source = None if args.interactive else model.model_name
            if not args.interactive:
                print("Trying to switch to a lighter model automatically...")
            print(f"Source: {source}")
            new_model = select_llm(_with_source(args, source))
            if new_model:
                model = new_model
                if args.interactive:
                    print(f"Selected new AI model: {model.__class__.__name__}")
                else:
                    print(f"Switched to lighter AI model: {model.__class__.__name__}")
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
    return event, vcal_json, elapsed_time


def _create_llm_prompt(*args):
    """Construct the LLM prompt for calendar event extraction."""
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
    prompt_file = Path(__file__).parent / "prompts" / "event_extraction_prompt.txt"
    if prompt_file.exists():
        prompt_template = prompt_file.read_text(encoding="utf-8")
    else:
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
            f"SOURCE TEXT:\n{content_text}.\n"
        )
    return prompt_template.format(event=event, content_text=content_text)


def _extract_event_with_llm_retry(
    args, model, content_text, reference_date_time, post_identifier, subject_for_print
):
    """Extract, normalize, and optionally retry an LLM-generated event."""
    from manage_agenda.events import adjust_event_times

    original_content = content_text
    prompt_content = content_text
    total_elapsed_time = 0
    while True:
        prompt = _create_llm_prompt(prompt_content, reference_date_time)
        write_file(f"log/{post_identifier}_prompt.txt", prompt)
        if args.verbose:
            print(f"Prompt:\n{prompt}")
            print("\nEnd Prompt:")

        event, vcal_json, elapsed_time = get_event_from_llm_with_retry(
            model, prompt, post_identifier, args
        )
        total_elapsed_time += elapsed_time
        if args.verbose:
            print(f"Event: {event}")
        if event is None and vcal_json in {"MemoryError", "RetryError"}:
            return event, vcal_json, total_elapsed_time, False, False, False

        if event:
            if not isinstance(event, (list, tuple)):
                event = [event]
            processed_events = []
            for single_event in event:
                if args.verbose:
                    print(f"Single event: {single_event}")
                if isinstance(single_event, dict):
                    single_event = add_message_to_event_description(single_event, original_content)
                    processed_events.append(adjust_event_times(single_event))
            event = processed_events or None
            if args.verbose:
                print(f"Proc event: {processed_events}")
            break

        write_file(
            f"log/{post_identifier}_fail.vcal",
            json.dumps(vcal_json) if vcal_json else "Failed extraction",
        )
        if not args.interactive:
            return None, vcal_json, total_elapsed_time, False, False, False

        print("\nLLM failed to extract event information.")
        choice = _print_context_and_options(
            original_content,
            "Options: (r)etry, (p)rovide relevant text snippet, (s)kip item: ",
            args.verbose,
        )
        if choice == "r":
            prompt_content = original_content
            continue
        if choice == "p":
            snippet = _get_text_snippet(original_content)
            if snippet:
                prompt_content = snippet
                continue
        return None, vcal_json, total_elapsed_time, False, False, False

    write_file(
        f"log/{model.model_name}/{post_identifier}_event_processed.vcal",
        json.dumps(event) if isinstance(event, (dict, list)) else str(event),
    )
    if isinstance(event, (list, tuple)):
        for idx, single_event in enumerate(event, start=1):
            write_file(
                f"log/{model.model_name}/{post_identifier}_{idx}.vcal",
                json.dumps(single_event)
                if isinstance(single_event, (dict, list))
                else str(single_event),
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
    """Display a normalized event consistently."""
    from manage_agenda.events import _format_datetime_for_display

    start_time_local = _format_datetime_for_display(safe_get(event, ["start", "dateTime"]))
    end_time_local = _format_datetime_for_display(safe_get(event, ["end", "dateTime"]))
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
    """Extract events, validate their dates, and publish or write them."""
    from manage_agenda.events import (
        _validate_event_dates_interactive,
        _validate_event_dates_non_interactive,
        adjust_event_times,
    )

    success = False
    should_process = True
    date_validation_retries = 0
    max_date_validation_retries = 3
    while should_process and not success:
        if date_validation_retries >= max_date_validation_retries:
            print(
                f"Max date validation retries ({max_date_validation_retries}) "
                f"reached for {post_identifier}. Skipping event processing."
            )
            break

        event, _, elapsed_time, extraction_success, need_restart, need_another_ai = (
            _extract_event_with_llm_retry(
                args, model, content_text, reference_date_time, post_identifier, subject_for_print
            )
        )
        if need_restart or need_another_ai:
            return None, None
        if not extraction_success or event is None:
            return None, None

        events = list(event)
        if getattr(args, "output", "calendar") == "calendar":
            api_dst = select_api(args, "gcalendar", rules=rules, title="Select Calendar")
            selected_calendar = select_calendar(api_dst, title=events[0]["summary"], args=args)
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
                    single_event, subject_for_print, elapsed_time, model, post_identifier
                )

                retry_needed = False
                if args.interactive:
                    single_event, is_valid, _ = _validate_event_dates_interactive(
                        single_event, post_identifier
                    )
                    retry_needed = not is_valid
                else:
                    single_event, is_valid, validation_errors = _validate_event_dates_non_interactive(
                        single_event, post_identifier
                    )
                    if not is_valid:
                        print(f"Date validation errors for {post_identifier}:")
                        for error in validation_errors:
                            print(f"  - {error}")
                        date_validation_retries += 1
                        break

                if retry_needed and model and content_text and reference_date_time:
                    date_validation_retries += 1
                    break
                if single_event is None:
                    continue

                _add_ai_metadata_to_event(single_event, model, elapsed_time)
                file_name = f"log/{post_identifier}_{idx}_times.json"
                if getattr(args, "output", "calendar") == "calendar":
                    published, calendar_result = _publish_event_to_calendar(
                        api_dst, single_event, selected_calendar
                    )
                else:
                    write_file(
                        f"log/{model.model_name}/{post_identifier}_{idx}_times.json",
                        json.dumps(single_event),
                    )
                    calendar_result = f"{post_identifier}_{idx}_times.json"
                    published = True
                if published:
                    calendar_results.append(calendar_result)
                    print(
                        "Calendar event created"
                        if getattr(args, "output", "calendar") == "calendar"
                        else f"File {post_identifier}_{idx}_times.json created"
                    )
                    success = True
                    write_file(file_name, json.dumps(single_event))

        print(f"Success: {success}")
        if success:
            if args.verbose:
                print(f"Events: {events}")
                print(f"Results: {calendar_results}")
            return events, calendar_results
        return None, None
    return None, None


def _publish_event_to_calendar(api_dst, event, selected_calendar):
    """Publish an event, retrying once after correcting invalid timezones."""
    from manage_agenda.events import _ensure_valid_event_timezones

    try:
        return True, api_dst.publishPost(
            post={"event": event, "idCal": selected_calendar},
            api=api_dst,
        )
    except googleapiclient.errors.HttpError as error:
        logging.error(f"Error creating calendar event: {error}")
        if "Invalid time zone definition for end time'" in str(error):
            logging.info(
                "Detected invalid timezone definition for end time. Correcting event timezones and retrying."
            )
            event = _ensure_valid_event_timezones(event, fallback_tz="UTC")
            try:
                return True, api_dst.publishPost(
                    post={"event": event, "idCal": selected_calendar},
                    api=api_dst,
                )
            except Exception as retry_error:
                logging.error(f"Retry after timezone correction failed: {retry_error}")
    return False, None


def _add_ai_metadata_to_event(event, model, elapsed_time, confidence_score=None):
    """Add machine-readable and human-readable LLM processing metadata."""
    from unittest.mock import Mock

    def is_mock(value):
        return isinstance(value, Mock)

    model_name = "unknown"
    if model:
        value = getattr(model, "model_name", None)
        if value is not None and not is_mock(value):
            model_name = str(value)
        elif hasattr(model, "get_name") and callable(model.get_name):
            try:
                value = model.get_name()
                if value is not None and not is_mock(value):
                    model_name = str(value)
            except NotImplementedError:
                pass
        if model_name == "unknown":
            value = getattr(model, "name", None)
            if value is not None and not is_mock(value):
                model_name = str(value)
            elif not is_mock(model):
                model_name = str(model)

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

    ai_metadata_text = (
        f"\n\n---\nAI Processing Info:\n- Model: {model_name}"
        f"\n- Processing time: {elapsed_time:.2f} seconds"
    )
    if confidence_score is not None:
        ai_metadata_text += f"\n- Confidence: {confidence_score:.2f}"
    event["description"] = event.get("description", "") + ai_metadata_text

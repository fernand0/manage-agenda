import datetime
import logging
from datetime import timedelta

import dateparser
import pytz
from socialModules.configMod import safe_get
from socialModules.moduleContent import display_posts

from manage_agenda import connections
from manage_agenda.config import config
from manage_agenda.connections import select_calendar

# Constants for date confirmation and interactive date/time modification.
DATE_CONFIRM_PROMPT = (
    "Are the dates correct? "
    "Ye(s), (r)etry with LLM, "
    "(Y)ear, (M)onth, (D)ay, (h)our, m(i)nute, (f)ull date/time: "
)
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATETIME_INPUT_PROMPT = "Enter new {field} time (YYYY-MM-DD HH:MM:SS) or leave empty: "


try:
    DEFAULT_NAIVE_TIMEZONE = pytz.timezone(config.DEFAULT_TIMEZONE)
except pytz.exceptions.UnknownTimeZoneError:
    logging.error(f"Invalid timezone '{config.DEFAULT_TIMEZONE}' in config. Falling back to UTC.")
    DEFAULT_NAIVE_TIMEZONE = pytz.utc


def filter_events_by_title(api_cal, events, text_filter):
    """Filter calendar events by title or abstract text."""
    filtered_events = []
    for event in events:
        title = api_cal.getPostTitle(event)
        if title and text_filter and text_filter.lower() in title.lower():
            filtered_events.append(event)
        else:
            abstract = api_cal.getPostAbstract(event)
            if abstract and text_filter and text_filter.lower() in abstract.lower():
                filtered_events.append(event)
            elif not text_filter and title:
                filtered_events.append(event)

    return filtered_events


def _get_datetime_input(field_name):
    """Get datetime input from user with a consistent prompt."""
    return input(DATETIME_INPUT_PROMPT.format(field=field_name))


def _process_full_datetime_modification(event):
    """Process full date/time modification (confirmation == 'f')."""
    new_start_str = _get_datetime_input("start")
    if new_start_str:
        event.setdefault("start", {})["dateTime"] = new_start_str
        try:
            start_dt = datetime.datetime.strptime(new_start_str, DATETIME_FORMAT)
            end_dt = start_dt + timedelta(minutes=45)
            new_end_str_default = end_dt.strftime(DATETIME_FORMAT)

            modify_end_time = input(
                f"Default end time will be {new_end_str_default}. Do you want to modify it? (y/n): "
            ).lower()
            if modify_end_time == "y":
                new_end_str = _get_datetime_input("end")
            else:
                new_end_str = new_end_str_default
        except ValueError:
            print("Invalid start time format. Please use YYYY-MM-DD HH:MM:SS.")
            new_end_str = ""
    else:
        new_end_str = _get_datetime_input("end")

    if new_end_str:
        event.setdefault("end", {})["dateTime"] = new_end_str

    return event


def _parse_datetime_to_utc(dt_str, tz_name=None):
    """Parse a datetime string, localize it if naive, and convert it to UTC."""
    if not dt_str:
        return None

    if isinstance(dt_str, str):
        normalized_str = dt_str.replace("Z", "+00:00")
    else:
        return None

    try:
        dt_obj = datetime.datetime.fromisoformat(normalized_str)
    except ValueError:
        try:
            dt_obj = datetime.datetime.strptime(normalized_str, DATETIME_FORMAT)
        except ValueError as parse_err:
            logging.error(f"Invalid datetime format: '{dt_str}'. Error: {parse_err}")
            return None

    if dt_obj.tzinfo is None:
        if tz_name:
            try:
                local_tz = pytz.timezone(tz_name)
                dt_obj = local_tz.localize(dt_obj)
            except pytz.exceptions.UnknownTimeZoneError:
                logging.warning(
                    f"Unknown timezone '{tz_name}'. "
                    f"Using default timezone: {config.DEFAULT_TIMEZONE}"
                )
                dt_obj = DEFAULT_NAIVE_TIMEZONE.localize(dt_obj)
        else:
            dt_obj = DEFAULT_NAIVE_TIMEZONE.localize(dt_obj)

    return dt_obj.astimezone(pytz.utc)


def _parse_event_times(event):
    """Parse event start and end times into UTC datetime objects."""
    start_str = safe_get(event, ["start", "dateTime"])
    start_tz = safe_get(event, ["start", "timeZone"])
    end_str = safe_get(event, ["end", "dateTime"])
    end_tz = safe_get(event, ["end", "timeZone"])

    current_start = _parse_datetime_to_utc(start_str, start_tz)
    if start_str and current_start is None:
        print("Could not parse start time, using empty value")

    current_end = _parse_datetime_to_utc(end_str, end_tz)
    if end_str and current_end is None:
        print("Could not parse end time, using empty value")

    return current_start, current_end


def adjust_event_times(event):
    """Adjust event start/end times, localizing naive times and converting to UTC."""
    if not isinstance(event.get("start"), dict):
        event["start"] = {}
    if not isinstance(event.get("end"), dict):
        event["end"] = {}
    start = event["start"]
    end = event["end"]

    start_dt, end_dt = _parse_event_times(event)

    if start_dt:
        start["dateTime"] = start_dt.isoformat()
        start["timeZone"] = "UTC"

    if end_dt:
        end["dateTime"] = end_dt.isoformat()
        end["timeZone"] = "UTC"

    if not start_dt and end_dt:
        start_dt = end_dt - timedelta(minutes=30)
        start["dateTime"] = start_dt.isoformat()
        start["timeZone"] = "UTC"

    if not end_dt and start_dt:
        end_dt = start_dt + timedelta(minutes=30)
        end["dateTime"] = end_dt.isoformat()
        end["timeZone"] = "UTC"

    if start_dt and end_dt and end_dt <= start_dt:
        print("Validation Warning: End time is not after start time. Adjusting end time.")
        end_dt = start_dt + timedelta(minutes=30)
        end["dateTime"] = end_dt.isoformat()
        end["timeZone"] = "UTC"

    return event


def _ensure_valid_event_timezones(event, fallback_tz="UTC"):
    """Ensure both start and end have valid timeZone values."""
    if not isinstance(event, dict):
        return event

    for when in ("start", "end"):
        field = event.setdefault(when, {})
        tz_name = field.get("timeZone")
        if not tz_name:
            field["timeZone"] = fallback_tz
            continue

        try:
            pytz.timezone(tz_name)
        except Exception:
            logging.warning(
                f"Invalid timezone '{tz_name}' for event {when}; using fallback '{fallback_tz}'."
            )
            field["timeZone"] = fallback_tz

    return event


def _process_individual_component_modification(event, confirmation, current_start, current_end):
    """Process an individual year, month, day, hour, or minute modification."""
    component_map = {"y": "year", "m": "month", "d": "day", "h": "hour", "i": "minute"}
    component = component_map.get(confirmation)

    for time_key, event_key, current_time in [
        ("start", "start", current_start),
        ("end", "end", current_end),
    ]:
        if current_time and component:
            new_time = _modify_single_component(current_time, component, time_key)
            event.setdefault(event_key, {})["dateTime"] = new_time.isoformat()

    return event


def _process_date_modification(event, confirmation, current_start, current_end):
    """Modify an event date according to the interactive confirmation choice."""
    if confirmation == "f":
        event = _process_full_datetime_modification(event)
    elif confirmation in ["m", "d", "h", "y", "i"]:
        event = _process_individual_component_modification(
            event, confirmation, current_start, current_end
        )

    event = adjust_event_times(event)

    start_time = safe_get(event, ["start", "dateTime"])
    end_time = safe_get(event, ["end", "dateTime"])
    print("--- Updated Event Times ---")
    print(f"Start: {_format_datetime_for_display(start_time)}")
    print(f"End: {_format_datetime_for_display(end_time)}")
    print("---------------------------")

    return event


def _validate_event_dates_interactive(event, post_identifier=None):
    """Interactively confirm and correct event dates."""
    errors = []
    is_valid = True
    label = f"[{post_identifier}] " if post_identifier else ""

    confirmed = False
    while not confirmed:
        current_start, current_end = _parse_event_times(event)
        confirmation = input(f"{label}{DATE_CONFIRM_PROMPT}").lower()

        if confirmation == "r":
            is_valid = False
            confirmed = True
        elif confirmation in ("s", ""):
            confirmed = True
        else:
            event = _process_date_modification(event, confirmation, current_start, current_end)

    return event, is_valid, errors


def _validate_event_dates_non_interactive(event, post_identifier=None):
    """Validate event dates in non-interactive mode."""
    errors = []
    warnings = []
    label = f"[{post_identifier}] " if post_identifier else ""

    current_start, current_end = _parse_event_times(event)
    if current_start is None or current_end is None:
        errors.append(f"{label}Event is missing valid start or end dateTime")

    now = datetime.datetime.now(datetime.timezone.utc)
    reasonable_past = now - timedelta(days=730)
    reasonable_future = now + timedelta(days=1825)

    for field_name, dt in [("start", current_start), ("end", current_end)]:
        if dt is None:
            continue
        if dt < reasonable_past:
            warnings.append(
                f"{label}Event {field_name} time ({dt.strftime(DATETIME_FORMAT)}) "
                f"is unreasonably far in the past (> 2 years)"
            )
        if dt > reasonable_future:
            warnings.append(
                f"{label}Event {field_name} time ({dt.strftime(DATETIME_FORMAT)}) "
                f"is unreasonably far in the future (> 5 years)"
            )

    for warning in warnings:
        print(f"WARNING: {warning}")

    return event, len(errors) == 0, errors


def _modify_single_component(dt, component, time_label):
    """Modify one datetime component based on interactive input."""
    print(f"\nModifying {component} for {time_label} time:")
    print(f"Current: {dt}")

    value_str = input(f"New {component} ({getattr(dt, component)}): ").strip()
    if value_str:
        try:
            new_value = int(value_str)
            if component == "year":
                new_dt = dt.replace(year=new_value)
            elif component == "month":
                new_dt = dt.replace(month=new_value)
            elif component == "day":
                new_dt = dt.replace(day=new_value)
            elif component == "hour":
                new_dt = dt.replace(hour=new_value)
            elif component == "minute":
                new_dt = dt.replace(minute=new_value)
            else:
                print(f"Unknown component: {component}. Keeping original time.")
                return dt

            print(f"New {time_label} time: {new_dt}")
            return new_dt
        except ValueError as error:
            print(f"Invalid value: {error}. Keeping original time.")
            return dt

    return dt


def _format_datetime_for_display(dt_value):
    """Format a datetime value for display in the local timezone."""
    if dt_value is None or dt_value == "":
        return "N/A"

    if isinstance(dt_value, datetime.datetime):
        if dt_value.tzinfo is None:
            dt_value = dt_value.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)
        dt_string = dt_value.isoformat()
    else:
        dt_string = dt_value

    try:
        dt_local = datetime.datetime.fromisoformat(dt_string).astimezone()
        tz_name = dt_local.tzname()
        return dt_local.strftime(f"%Y-%m-%d %H:%M:%S {tz_name}")
    except ValueError:
        return dt_string


def clean_action(api_cal, event, my_calendar, my_calendar_dst):
    pass


def copy_action(api_cal, event, my_calendar, my_calendar_dst):
    """Action function to copy an event."""
    my_event = {
        "summary": event["summary"],
        "description": (
            event["description"] if "description" in event and event["description"] else ""
        ),
        "start": event["start"],
        "end": event["end"],
    }
    if "location" in event:
        my_event["location"] = event["location"]

    my_calendar_dst.getClient().events().insert(calendarId=my_calendar, body=my_event).execute()
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
    display_posts(api_cal, events_list)

    print(f"{len(events_list)}) All")

    selection = input(
        f"Which event(s) to {action_verb}? (comma-separated numbers, text to match, or 'all') "
    )

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
                search_terms = selection.split(",")
                for term in search_terms:
                    term = term.strip().lower()
                    for i, event in enumerate(events_list):
                        event_title = api_cal.getPostTitle(event).lower()
                        if term in event_title and events_list[i] not in selected_events:
                            selected_events.append(events_list[i])
        except ValueError:
            # If parsing as integers fails, treat as text-based selection
            search_terms = selection.split(",")
            for term in search_terms:
                term = term.strip().lower()
                for i, event in enumerate(events_list):
                    event_title = api_cal.getPostTitle(event).lower()
                    if term in event_title and events_list[i] not in selected_events:
                        selected_events.append(events_list[i])

    return selected_events


def process_calendar_events(
    args, action_verb, action_func, destination_needed=False, api_src_type="gcalendar"
):
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
    api_cal = connections.select_api(args, "gcalendar", rules=None, title="Select Rule")
    if getattr(args, "source", None):
        selected_calendar = args.source
    else:
        selected_calendar = select_calendar(api_cal, title="Select calendar", args=args)

    # Set the active calendar using socialModules method
    api_cal.setActive(selected_calendar)

    today = datetime.datetime.now()
    today = datetime.datetime.now(datetime.timezone.utc)


    # Fetch events from calendar using socialModules methods
    all_posts = []
    try:
        api_cal.setPostsType("posts")
        api_cal.setPosts(date=today)
        all_posts = api_cal.getPosts()
    except Exception:
        all_posts = []

    today = datetime.datetime.now()
    today = datetime.datetime.now(datetime.timezone.utc)

    # If interactive, present all fetched posts (tests expect interactive flows
    # to show items regardless of date)
    if args.interactive:
        future_events = all_posts
    else:
        future_events = []
        for post in all_posts:
            post_date = api_cal.getPostDate(post)
            print(f"Date: {post_date}")

            if not isinstance(post_date, str):
                if isinstance(post, dict):
                    start = post.get("start", {})
                    post_date = start.get("dateTime") or start.get("date")

            if isinstance(post_date, str):
                post_date = dateparser.parse(post_date)
                # Normalize naive datetimes to UTC for comparison
                if post_date and post_date.tzinfo is None:
                    try:
                        post_date = pytz.utc.localize(post_date)
                    except Exception:
                        pass
            else:
                post_date = None

            if post_date and post_date >= today:
                future_events.append(post)

    print("Upcoming events (up to 20):")
    for event in future_events[:20]:
        print(f"- {api_cal.getPostTitle(event)} ({api_cal.getPostDate(event)})")

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    # Use the helper function to filter events by title
    filtered_events = filter_events_by_title(api_cal, future_events, text_filter)

    if not filtered_events:
        print("No events found matching the criteria.")
        return

    selected_events = select_events_by_user_input(api_cal, filtered_events, action_verb)

    if "clean" in action_func.__name__:
        actions = ["Delete", "Copy", "Move"]
        msg = "Select operation:"
        for i, act in enumerate(actions):
            msg = f"{msg}\n{i}) {act}"
        msg = f"{msg}\n"

        action_sel = input(msg)
        destination_needed = True
        if action_sel == "1":  # Copy
            action_verb = "copy"
            action_func = copy_action
        elif action_sel == "2":  # Move
            action_verb = "move"
            action_func = move_action
        else:  # Delete
            action_verb = "delete"
            action_func = delete_action
            destination_needed = False

    # Handle destination calendar if needed
    if destination_needed:
        my_calendar_dst = connections.select_api(
            args, "gcalendar", rules=None, title="Select rule"
        )
        if getattr(args, "destination", None):
            my_calendar = args.destination
        else:
            my_calendar = select_calendar(
                my_calendar_dst, title="Select destination calendar", args=args
            )
    else:
        my_calendar = None
        my_calendar_dst = None

    # Perform the specific action on selected events
    for event in selected_events:
        action_func(api_cal, event, my_calendar, my_calendar_dst)


def delete_action(api_cal, event, my_calendar, my_calendar_dst):
    """Action function to delete an event."""
    api_cal.getClient().events().delete(
        calendarId=api_cal.getActive(), eventId=event["id"]
    ).execute()
    print(f"Deleted event: {event['summary']}")


def delete_events_cli(args):
    """Deletes events from a calendar."""
    process_calendar_events(args, "delete", delete_action)


def move_action(api_cal, event, my_calendar, my_calendar_dst):
    """Action function to move an event (copy then delete)."""
    my_event = {
        "summary": event["summary"],
        "description": event["description"] if "description" in event else "",
        "start": event["start"],
        "end": event["end"],
    }
    if "location" in event:
        my_event["location"] = event["location"]

    my_calendar_dst.getClient().events().insert(calendarId=my_calendar, body=my_event).execute()
    print(f"Copied event: {my_event['summary']}")
    api_cal.getClient().events().delete(
        calendarId=api_cal.getActive(), eventId=event["id"]
    ).execute()
    print(f"Deleted event: {event['summary']}")


def move_events_cli(args):
    """Moves events from a source calendar to a destination calendar."""
    process_calendar_events(args, "move", move_action, destination_needed=True)


def update_event_status_cli(args):
    """Update event status from busy to available for selected events."""
    api_cal = connections.select_api(args, "gcalendar", rules=None, title="Select Rule")

    if args.source:
        my_calendar = args.source
    else:
        my_calendar = select_calendar(api_cal)

    api_cal.setActive(my_calendar)
    api_cal.setPosts(max_results=None, event_types="default", show_active=False)
    events = api_cal.getPosts() or []
    display_posts(
        api_cal,
        events,
        format_post=lambda event: (
            f"[{event.get('transparency', 'opaque')}] "
            f"{api_cal.getPostTitle(event) or 'No Title'}"
        ),
        limit=20,
        title="Upcoming events (up to 20):",
    )

    text_filter = args.text
    if args.interactive and not text_filter:
        text_filter = input("Text to filter by (leave empty for no filter): ")

    events_to_update = []
    for event in events:
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
        api_cal.getClient().events().update(
            calendarId=my_calendar, eventId=event["id"], body=event
        ).execute()

        title = api_cal.getPostTitle(event) or "No Title"
        print(f"Updated event status to available: {title}")


def clean_events_cli(args):
    """Combined command to clean calendar entries (select between copy or delete)."""
    process_calendar_events(args, "clean", clean_action, destination_needed=True)

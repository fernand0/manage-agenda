"""Select configured external-service connections."""

import logging

from socialModules.configMod import safe_get, select_from_list
from socialModules.moduleRules import moduleRules

from manage_agenda.exceptions import CalendarError


def authorize(args, rules=None):
    """Authorize and return a configured service connection."""
    rules = rules or moduleRules.from_config()
    if args.interactive:
        service = input("Service? ")
        return rules.selectRuleInteractive(service)

    rules_all = rules.selectRule("", "")
    if not rules_all:
        logging.warning("No services configured.")
        return None
    source_name = rules_all[0]
    source_details = rules.more.get(source_name, {})
    logging.info(f"Source: {source_name} - {source_details}")
    return rules.readConfigSrc("", source_name, source_details)


def select_api(args, api_type, rules=None, title=""):
    """Select a configured service connection, interactively or not."""
    rules = rules or moduleRules.from_config()
    service = ["gmail", "imap"] if api_type == "email" else (
        list(api_type) if isinstance(api_type, (list, tuple)) else [api_type]
    )

    if args.interactive:
        return rules.selectRuleInteractive(service, title=title)

    sources = rules.selectRule(service, "")
    if not sources:
        logging.warning(f"No {api_type} sources configured.")
        return None
    selected_source = sources[0]
    source_details = rules.more.get(selected_source, {})
    logging.info(f"Source: {selected_source} - {source_details}")
    return rules.readConfigSrc("", selected_source, source_details)


def select_calendar(calendar_api, title="", args=None):
    """Select a writable Google Calendar from a configured calendar API."""
    try:
        calendar_api.setCalendarList()
        calendars = calendar_api.getCalendarList()
        if not calendars:
            raise CalendarError("No calendars found in your Google Calendar account")

        eligible_calendars = [
            calendar for calendar in calendars if "reader" not in calendar.get("accessRole", "")
        ]
        if not eligible_calendars:
            raise CalendarError("No writable calendars found. Check your calendar permissions.")

        if (args and args.interactive) or not args:
            selection, calendar = select_from_list(eligible_calendars, "summary", title=title)
        else:
            matches = [calendar for calendar in eligible_calendars if "kkk" in calendar["summary"]]
            calendar = matches[0] if matches else None
            selection = eligible_calendars.index(calendar)

        if selection < 0 or selection >= len(eligible_calendars):
            raise CalendarError(f"Invalid calendar selection: {selection}")

        calendar_id = eligible_calendars[selection]["id"]
        logging.info(f"Selected calendar: {safe_get(calendar, ['summary'])} (ID: {calendar_id})")
        return calendar_id
    except (KeyError, IndexError, TypeError) as error:
        raise CalendarError(f"Failed to select calendar: {error}") from error
    except CalendarError:
        raise
    except Exception as error:
        raise CalendarError(f"Unexpected error selecting calendar: {error}") from error

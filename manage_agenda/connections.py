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
    logging.info("Source: %s - %s", source_name, source_details)
    return rules.readConfigSrc("", source_name, source_details)


def select_api(args, api_type, rules=None, title=""):
    """Select a configured service connection, interactively or not."""
    rules = rules or moduleRules.from_config()
    service = ["gmail", "imap"] if api_type == "email" else (
        list(api_type) if isinstance(api_type, (list, tuple)) else [api_type]
    )

    if args.interactive:
        result = rules.selectRuleInteractive(service, title=title)
    else:
        sources = rules.selectRule(service, "")
        if not sources:
            logging.warning("No %s sources configured", api_type)
            return None
        selected_source = sources[0]
        source_details = rules.more.get(selected_source, {})
        logging.info("Source: %s - %s", selected_source, source_details)
        result = rules.readConfigSrc("", selected_source, source_details)
    return result


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
        logging.info("Selected calendar: %s (ID: %s)", safe_get(calendar, ["summary"]), calendar_id)
        return calendar_id
    except (KeyError, IndexError, TypeError) as error:
        raise CalendarError(f"Failed to select calendar: {error}") from error
    except CalendarError:
        raise
    except Exception as error:
        raise CalendarError(f"Unexpected error selecting calendar: {error}") from error


def select_calendar_from_all_rules(args, title="", rules=None):
    """Select a writable calendar from all configured gcalendar rules.

    Aggregates calendars from every configured gcalendar rule into a single
    flat list. Each entry is displayed as "Calendar Name (rule-name)" so the
    user can tell accounts apart. Returns an (api, calendar_id) tuple.
    """
    rules = rules or moduleRules.from_config()
    rule_names = rules.get_rules_for_services("gcalendar")
    if not rule_names:
        raise CalendarError("No gcalendar sources configured")

    # Collect (api, calendar_dict, rule_name) for every writable calendar.
    entries = []
    for rule_name in rule_names:
        source_details = rules.more.get(rule_name, {})
        api = rules.readConfigSrc("", rule_name, source_details)
        if not api:
            logging.warning("Could not instantiate API for rule %s, skipping", rule_name)
            continue
        try:
            api.setCalendarList()
            calendars = api.getCalendarList() or []
        except Exception as exc:
            logging.warning("Failed to fetch calendars for rule %s: %s", rule_name, exc)
            continue
        for cal in calendars:
            if "reader" not in cal.get("accessRole", ""):
                entries.append((api, cal, rule_name))

    if not entries:
        raise CalendarError("No writable calendars found across all configured rules")

    # Build display labels: "Summary (rule-name)"
    labels = [
        f"{safe_get(cal, ['summary'])} ({rule_name})"
        for _api, cal, rule_name in entries
    ]

    selection, _label = select_from_list(labels, title=title)

    if selection < 0 or selection >= len(entries):
        raise CalendarError(f"Invalid calendar selection: {selection}")

    selected_api, selected_cal, rule_name = entries[selection]
    calendar_id = selected_cal["id"]
    logging.info(
        "Selected calendar: %s (ID: %s, rule: %s)",
        safe_get(selected_cal, ["summary"]),
        calendar_id,
        rule_name,
    )
    return selected_api, calendar_id

def _validate_event_dates_non_interactive(event, post_identifier=None):
    """Validate event dates in non-interactive mode.

    Performs basic sanity checks:
    - Start and end dateTime fields are present and parseable (hard error)
    - End time is after start time (hard error)
    - Dates are not unreasonably far in the past (> 2 years ago) or future
      (> 5 years from now) — logged as warning, does not block processing

    Args:
        event: Event dictionary with start/end dateTime fields.
        post_identifier: Optional identifier for logging context.

    Returns:
        Tuple of (is_valid: bool, errors: list[str]).
    """
    errors = []
    warnings = []
    label = f"[{post_identifier}] " if post_identifier else ""

    current_start, current_end = _parse_event_times(event)

    if current_start is None:
        errors.append(f"{label}Event is missing a valid start dateTime")
    if current_end is None:
        errors.append(f"{label}Event is missing a valid end dateTime")

    if current_start is not None and current_end is not None:
        if current_end <= current_start:
            errors.append(
                f"{label}Event end ({current_end.strftime(DATETIME_FORMAT)}) "
                f"is not after start ({current_start.strftime(DATETIME_FORMAT)})"
            )

    now = datetime.datetime.now(datetime.timezone.utc)
    reasonable_past = now - timedelta(days=730)  # 2 years ago
    reasonable_future = now + timedelta(days=1825)  # 5 years from now

    for field_name, dt in [("start", current_start), ("end", current_end)]:
        if dt is None:
            continue
        # Make naive UTC for comparison if timezone-aware
        dt_cmp = dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
        if dt_cmp < reasonable_past.replace(tzinfo=None):
            warnings.append(
                f"{label}Event {field_name} time ({dt_cmp.strftime(DATETIME_FORMAT)}) "
                f"is unreasonably far in the past (> 2 years)"
            )
        if dt_cmp > reasonable_future.replace(tzinfo=None):
            warnings.append(
                f"{label}Event {field_name} time ({dt_cmp.strftime(DATETIME_FORMAT)}) "
                f"is unreasonably far in the future (> 5 years)"
            )

    # Print warnings but don't block processing
    for w in warnings:
        print(f"WARNING: {w}")

    return len(errors) == 0, errors



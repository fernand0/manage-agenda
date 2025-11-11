"""
Validation utilities for manage-agenda.
"""
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
import pytz

from manage_agenda.exceptions import ValidationError
from manage_agenda.config import config

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """Validate email format.
    
    Args:
        email: Email address to validate.
        
    Returns:
        True if valid, False otherwise.
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """Validate URL format.
    
    Args:
        url: URL to validate.
        
    Returns:
        True if valid, False otherwise.
    """
    pattern = r'^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)$'
    return bool(re.match(pattern, url))


def validate_timezone(tz_name: str) -> bool:
    """Validate timezone name.
    
    Args:
        tz_name: IANA timezone name to validate.
        
    Returns:
        True if valid, False otherwise.
    """
    try:
        pytz.timezone(tz_name)
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        return False


def validate_datetime_iso(dt_str: str) -> bool:
    """Validate ISO 8601 datetime string.
    
    Args:
        dt_str: ISO formatted datetime string.
        
    Returns:
        True if valid, False otherwise.
    """
    try:
        datetime.fromisoformat(dt_str)
        return True
    except (ValueError, TypeError):
        return False


def validate_event_dict(event: Dict[str, Any]) -> List[str]:
    """Validate Google Calendar event dictionary.
    
    Args:
        event: Event dictionary to validate.
        
    Returns:
        List of validation error messages (empty if valid).
    """
    errors = []
    
    # Required fields
    if not event.get('summary'):
        errors.append("Event must have a summary (title)")
    
    # Validate start time
    start = event.get('start', {})
    if not start.get('dateTime'):
        errors.append("Event must have a start dateTime")
    elif not validate_datetime_iso(start['dateTime']):
        errors.append(f"Invalid start dateTime format: {start['dateTime']}")
    
    # Validate end time
    end = event.get('end', {})
    if not end.get('dateTime'):
        errors.append("Event must have an end dateTime")
    elif not validate_datetime_iso(end['dateTime']):
        errors.append(f"Invalid end dateTime format: {end['dateTime']}")
    
    # Validate timezones if provided
    if start.get('timeZone') and not validate_timezone(start['timeZone']):
        errors.append(f"Invalid start timezone: {start['timeZone']}")
    
    if end.get('timeZone') and not validate_timezone(end['timeZone']):
        errors.append(f"Invalid end timezone: {end['timeZone']}")
    
    # Validate that end is after start
    if start.get('dateTime') and end.get('dateTime'):
        try:
            start_dt = datetime.fromisoformat(start['dateTime'])
            end_dt = datetime.fromisoformat(end['dateTime'])
            if end_dt <= start_dt:
                errors.append("Event end time must be after start time")
        except ValueError:
            pass  # Already caught by datetime validation
    
    # Validate description length (Google Calendar limit)
    description = event.get('description', '')
    if len(description) > 8192:
        errors.append(f"Description too long: {len(description)} chars (max 8192)")
    
    # Validate summary length
    summary = event.get('summary', '')
    if len(summary) > 1024:
        errors.append(f"Summary too long: {len(summary)} chars (max 1024)")
    
    return errors


def validate_llm_response(response: str) -> Optional[Dict[str, Any]]:
    """Validate and parse LLM JSON response.
    
    Args:
        response: JSON string response from LLM.
        
    Returns:
        Parsed dictionary if valid, None otherwise.
        
    Raises:
        ValidationError: If response is invalid.
    """
    import json
    
    if not response or not response.strip():
        raise ValidationError("LLM returned empty response")
    
    try:
        # Try to extract JSON from markdown code blocks
        if '```json' in response:
            start = response.find('```json') + 7
            end = response.find('```', start)
            response = response[start:end].strip()
        elif '```' in response:
            start = response.find('```') + 3
            end = response.find('```', start)
            response = response[start:end].strip()
        
        data = json.loads(response)
        
        # Validate it's a dictionary
        if not isinstance(data, dict):
            raise ValidationError("LLM response must be a JSON object")
        
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.debug(f"Response was: {response[:500]}")
        raise ValidationError(f"Invalid JSON response from LLM: {e}")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters.
    
    Args:
        filename: Filename to sanitize.
        
    Returns:
        Sanitized filename.
    """
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    return filename


def validate_api_key(api_key: Optional[str], service: str) -> bool:
    """Validate API key format.
    
    Args:
        api_key: API key to validate.
        service: Service name (for logging).
        
    Returns:
        True if valid, False otherwise.
    """
    if not api_key:
        logger.warning(f"No API key provided for {service}")
        return False
    
    if len(api_key) < 20:
        logger.warning(f"API key for {service} seems too short")
        return False
    
    return True

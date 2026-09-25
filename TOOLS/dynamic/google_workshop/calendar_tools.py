import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_cal_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "google", "calendar_handlers.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("list_upcoming_events")
def list_upcoming_events(days: int = 7) -> str:
    """List upcoming calendar events."""
    return _run_cal_mcp("list_upcoming_events", {"days": days})

@action_logger("create_calendar_event")
def create_calendar_event(title: str, start_datetime: str, end_datetime: str, description: str = '', location: str = '') -> str:
    """Create a new calendar event."""
    return _run_cal_mcp("create_calendar_event", {"title": title, "start_datetime": start_datetime, "end_datetime": end_datetime, "description": description, "location": location})

@action_logger("update_calendar_event")
def update_calendar_event(event_id: str, title: str = '', start_datetime: str = '', end_datetime: str = '', description: str = '', location: str = '') -> str:
    """Update a calendar event."""
    return _run_cal_mcp("update_calendar_event", {"event_id": event_id, "title": title, "start_datetime": start_datetime, "end_datetime": end_datetime, "description": description, "location": location})

@action_logger("get_calendar_event")
def get_calendar_event(event_id: str) -> str:
    """Get calendar event details by ID."""
    return _run_cal_mcp("get_calendar_event", {"event_id": event_id})

@action_logger("delete_calendar_event")
def delete_calendar_event(event_id: str) -> str:
    """Delete a calendar event."""
    return _run_cal_mcp("delete_calendar_event", {"event_id": event_id})

@action_logger("search_calendar_events")
def search_calendar_events(query: str, max_results: int = 5) -> str:
    """Search calendar events."""
    return _run_cal_mcp("search_calendar_events", {"query": query, "max_results": max_results})

@action_logger("list_events_date_range")
def list_events_date_range(start_date: str, end_date: str, max_results: int = 30) -> str:
    """List calendar events within a specific date range."""
    return _run_cal_mcp("list_events_date_range", {"start_date": start_date, "end_date": end_date, "max_results": max_results})

@action_logger("list_calendars")
def list_calendars() -> str:
    """List user calendars."""
    return _run_cal_mcp("list_calendars", {})

@action_logger("add_event_attendees")
def add_event_attendees(event_id: str, emails_json: str) -> str:
    """Add attendees to a calendar event. Expects emails_json as a JSON array."""
    return _run_cal_mcp("add_event_attendees", {"event_id": event_id, "emails_json": emails_json})

@action_logger("create_all_day_event")
def create_all_day_event(title: str, start_date: str, end_date: str, description: str = '') -> str:
    """Create an all-day calendar event."""
    return _run_cal_mcp("create_all_day_event", {"title": title, "start_date": start_date, "end_date": end_date, "description": description})

@action_logger("duplicate_calendar_event")
def duplicate_calendar_event(event_id: str, new_start_datetime: str, new_end_datetime: str) -> str:
    """Duplicate a calendar event with new times."""
    return _run_cal_mcp("duplicate_calendar_event", {"event_id": event_id, "new_start_datetime": new_start_datetime, "new_end_datetime": new_end_datetime})

@action_logger("set_event_reminder")
def set_event_reminder(event_id: str, minutes_before: int = 30) -> str:
    """Set a popup reminder for a calendar event."""
    return _run_cal_mcp("set_event_reminder", {"event_id": event_id, "minutes_before": minutes_before})

@action_logger("move_event_to_calendar")
def move_event_to_calendar(event_id: str, target_calendar_id: str) -> str:
    """Move a calendar event to a different calendar."""
    return _run_cal_mcp("move_event_to_calendar", {"event_id": event_id, "target_calendar_id": target_calendar_id})

@action_logger("find_free_time")
def find_free_time(date_str: str, duration_minutes: int = 30, start_hour: int = 9, end_hour: int = 17) -> str:
    """Finds free time slots on a specific date for a given duration."""
    return _run_cal_mcp("find_free_time", {"date_str": date_str, "duration_minutes": duration_minutes, "start_hour": start_hour, "end_hour": end_hour})

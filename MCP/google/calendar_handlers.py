"""
📅 Google Calendar Handler Tools
"""
from datetime import datetime, timedelta, timezone
from mcp.server.fastmcp import FastMCP
from google_common import get_service

mcp = FastMCP("Google-Calendar-Tools")


def _cal():
    return get_service('calendar', 'v3')


def _fmt_event(ev: dict) -> str:
    start = ev['start'].get('dateTime', ev['start'].get('date', ''))
    return (
        f"🗓️  {ev.get('summary', '(No Title)')}\n"
        f"   🕐 {start}\n"
        f"   📍 {ev.get('location', 'N/A')}\n"
        f"   🔑 ID: {ev['id']}\n"
        f"{'─'*40}\n"
    )


@mcp.tool()
def list_upcoming_events(days: int = 7) -> str:
    """List upcoming calendar events."""
    try:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)
        events = _cal().events().list(
            calendarId='primary', timeMin=now.isoformat(), timeMax=end.isoformat(),
            maxResults=20, singleEvents=True, orderBy='startTime'
        ).execute().get('items', [])
        if not events:
            return f"📅 No upcoming events in the next {days} days."
        output = f"📅 UPCOMING — {days} DAYS\n{'─'*40}\n"
        for ev in events:
            output += _fmt_event(ev)
        return output
    except Exception as e:
        return f"❌ Error listing events: {e}"


@mcp.tool()
def create_calendar_event(
    title: str, start_datetime: str, end_datetime: str,
    description: str = "", location: str = ""
) -> str:
    """Create a new calendar event."""
    try:
        event = {
            'summary': title, 'location': location, 'description': description,
            'start': {'dateTime': start_datetime, 'timeZone': 'Asia/Colombo'},
            'end': {'dateTime': end_datetime, 'timeZone': 'Asia/Colombo'},
        }
        created = _cal().events().insert(calendarId='primary', body=event).execute()
        return (
            f"✅ Event created: {title}\n"
            f"   🔑 ID: {created['id']}\n"
            f"   🔗 {created.get('htmlLink', '')}\n"
            f"   💡 Use ID for update/delete."
        )
    except Exception as e:
        return f"❌ Error creating event: {e}"


@mcp.tool()
def update_calendar_event(
    event_id: str,

    title: str = "",
    start_datetime: str = "",
    end_datetime: str = "",
    description: str = "",
    location: str = "",
) -> str:
    """Update a calendar event."""
    event_id = event_id.strip()
    try:
        body = {}
        if title:
            body['summary'] = title
        if description:
            body['description'] = description
        if location:
            body['location'] = location
        if start_datetime:
            body['start'] = {'dateTime': start_datetime, 'timeZone': 'Asia/Colombo'}
        if end_datetime:
            body['end'] = {'dateTime': end_datetime, 'timeZone': 'Asia/Colombo'}
        if not body:
            return "❌ Provide at least one field to update."
        updated = _cal().events().patch(
            calendarId='primary', eventId=event_id, body=body
        ).execute()
        return f"✅ Event updated: {updated.get('summary')} (ID: {event_id})"
    except Exception as e:
        return f"❌ Error updating event: {e}"


@mcp.tool()
def get_calendar_event(event_id: str) -> str:
    """Get calendar event details by ID."""
    event_id = event_id.strip()
    try:
        ev = _cal().events().get(calendarId='primary', eventId=event_id).execute()
        attendees = ', '.join(a.get('email', '') for a in ev.get('attendees', []))
        start = ev['start'].get('dateTime', ev['start'].get('date', ''))
        end = ev['end'].get('dateTime', ev['end'].get('date', ''))
        return (
            f"📅 EVENT\n{'═'*40}\n"
            f"Title: {ev.get('summary')}\nStart: {start}\nEnd: {end}\n"
            f"Location: {ev.get('location', 'N/A')}\n"
            f"Description: {(ev.get('description') or '')[:200]}\n"
            f"Attendees: {attendees or 'None'}\n"
            f"ID: {event_id}\nLink: {ev.get('htmlLink', 'N/A')}\n"
        )
    except Exception as e:
        return f"❌ Error getting event: {e}"


@mcp.tool()
def delete_calendar_event(event_id: str) -> str:
    """Delete a calendar event."""
    event_id = event_id.strip()
    try:
        _cal().events().delete(calendarId='primary', eventId=event_id).execute()
        return f"🗑️ Event deleted (ID: {event_id})."
    except Exception as e:
        return f"❌ Error deleting event: {e}"


@mcp.tool()
def search_calendar_events(query: str, max_results: int = 5) -> str:
    """Search calendar events."""
    try:
        events = _cal().events().list(
            calendarId='primary', q=query, maxResults=max_results,
            singleEvents=True, orderBy='startTime',
            timeMin=datetime.now(timezone.utc).isoformat()
        ).execute().get('items', [])
        if not events:
            return f"🔍 '{query}' events found."
        output = f"🔍 SEARCH: '{query}'\n{'─'*40}\n"
        for ev in events:
            output += _fmt_event(ev)
        return output
    except Exception as e:
        return f"❌ Error searching calendar: {e}"


@mcp.tool()
def list_events_date_range(start_date: str, end_date: str, max_results: int = 30) -> str:
    """List calendar events within a specific date range."""
    try:
        tmin = start_date if 'T' in start_date else f"{start_date}T00:00:00Z"
        tmax = end_date if 'T' in end_date else f"{end_date}T23:59:59Z"
        events = _cal().events().list(
            calendarId='primary', timeMin=tmin, timeMax=tmax,
            maxResults=max_results, singleEvents=True, orderBy='startTime'
        ).execute().get('items', [])
        if not events:
            return f"📅 No events between {start_date} and {end_date}."
        output = f"📅 EVENTS {start_date} → {end_date}\n{'─'*40}\n"
        for ev in events:
            output += _fmt_event(ev)
        return output
    except Exception as e:
        return f"❌ Error listing date range: {e}"


@mcp.tool()
def list_calendars() -> str:
    """List user calendars."""
    try:
        items = _cal().calendarList().list().execute().get('items', [])
        if not items:
            return "No calendars found."
        output = f"📅 CALENDARS — {len(items)}\n{'─'*40}\n"
        for c in items:
            output += f"  📌 {c.get('summary')} (ID: {c['id']}, primary: {c.get('primary', False)})\n"
        return output
    except Exception as e:
        return f"❌ Error listing calendars: {e}"


@mcp.tool()
def add_event_attendees(event_id: str, emails_json: str) -> str:
    """Add attendees to a calendar event. Expects emails_json as a JSON array."""
    event_id = event_id.strip()
    try:
        import json
        ev = _cal().events().get(calendarId='primary', eventId=event_id).execute()
        existing = ev.get('attendees', [])
        new_emails = json.loads(emails_json)
        if not isinstance(new_emails, list):
            return "❌ emails_json must be a JSON array."

        for email in new_emails:
            existing.append({'email': email})
        updated = _cal().events().patch(
            calendarId='primary', eventId=event_id,
            body={'attendees': existing}, sendUpdates='all'
        ).execute()
        return f"✅ Attendees added to '{updated.get('summary')}' ({len(new_emails)} new)."
    except Exception as e:
        return f"❌ Error adding attendees: {e}"


@mcp.tool()
def create_all_day_event(title: str, start_date: str, end_date: str, description: str = "") -> str:
    """Create an all-day calendar event."""
    try:
        event = {
            'summary': title, 'description': description,
            'start': {'date': start_date}, 'end': {'date': end_date},
        }
        created = _cal().events().insert(calendarId='primary', body=event).execute()
        return f"✅ All-day event '{title}' created. ID: {created['id']}"
    except Exception as e:
        return f"❌ Error creating all-day event: {e}"


@mcp.tool()
def duplicate_calendar_event(event_id: str, new_start_datetime: str, new_end_datetime: str) -> str:
    """Duplicate a calendar event with new times."""
    event_id = event_id.strip()
    try:
        ev = _cal().events().get(calendarId='primary', eventId=event_id).execute()
        for key in ('id', 'htmlLink', 'created', 'updated', 'etag', 'iCalUID', 'sequence'):
            ev.pop(key, None)
        ev['start'] = {'dateTime': new_start_datetime, 'timeZone': 'Asia/Colombo'}
        ev['end'] = {'dateTime': new_end_datetime, 'timeZone': 'Asia/Colombo'}
        created = _cal().events().insert(calendarId='primary', body=ev).execute()
        return f"✅ Duplicated event. New ID: {created['id']}"
    except Exception as e:
        return f"❌ Error duplicating event: {e}"


@mcp.tool()
def set_event_reminder(event_id: str, minutes_before: int = 30) -> str:
    """Set a popup reminder for a calendar event."""
    event_id = event_id.strip()
    try:
        updated = _cal().events().patch(
            calendarId='primary', eventId=event_id,
            body={'reminders': {
                'useDefault': False,
                'overrides': [{'method': 'popup', 'minutes': minutes_before}],
            }}
        ).execute()
        return f"✅ Reminder set {minutes_before} min before '{updated.get('summary')}'."
    except Exception as e:
        return f"❌ Error setting reminder: {e}"


@mcp.tool()
def move_event_to_calendar(event_id: str, target_calendar_id: str) -> str:
    """Move a calendar event to a different calendar."""
    event_id = event_id.strip()
    try:
        moved = _cal().events().move(
            calendarId='primary', eventId=event_id, destination=target_calendar_id
        ).execute()
        return f"✅ Moved '{moved.get('summary')}' to calendar {target_calendar_id}."
    except Exception as e:
        return f"❌ Error moving event: {e}"



@mcp.tool()
def find_free_time(date_str: str, duration_minutes: int = 30, start_hour: int = 9, end_hour: int = 17) -> str:
    """Finds free time slots on a specific date for a given duration."""
    try:
        start_time = f"{date_str}T{start_hour:02d}:00:00Z"
        end_time = f"{date_str}T{end_hour:02d}:00:00Z"
        
        body = {
            "timeMin": start_time,
            "timeMax": end_time,
            "items": [{"id": "primary"}]
        }
        
        freebusy = _cal().freebusy().query(body=body).execute()
        busy_slots = freebusy.get('calendars', {}).get('primary', {}).get('busy', [])
        
        return f"📅 Free time slots logic can be parsed from these busy slots:\n{busy_slots}"
    except Exception as e:
        return f"❌ Error finding free time: {e}"

if __name__ == "__main__":
    mcp.run(transport='stdio')

import json
from datetime import datetime, timedelta, timezone
from mcp.server.fastmcp import FastMCP
from google_common import get_service

mcp = FastMCP("Google-Calendar-Tools")


def _cal():
    return get_service("calendar", "v3")


def _fmt_event(ev: dict) -> str:
    start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
    return (
        f"Event   : {ev.get('summary', '(No Title)')}\n"
        f"Time    : {start}\n"
        f"Location: {ev.get('location', 'N/A')}\n"
        f"ID      : {ev.get('id', '')}\n"
        f"{'-'*40}\n"
    )


@mcp.tool()
def calendar_events(
    action: str,
    calendar_id: str = "primary",
    event_id: str = "",
    title: str = "",
    start_datetime: str = "",
    end_datetime: str = "",
    start_date: str = "",
    end_date: str = "",
    days: int = 7,
    query: str = "",
    description: str = "",
    location: str = "",
    text: str = "",
    target_calendar_id: str = "",
    attendee_emails: str = "",
    minutes_before: int = 30,
    duration_minutes: int = 30,
    max_results: int = 20,
) -> str:
    """Manage calendar events: list_upcoming, list_range, search, get, create, quick_add, update, delete, duplicate, move, add_attendees, set_reminder, find_free_time."""
    action_clean = (action or "").strip().lower()

    try:
        svc = _cal()

        if action_clean in ("list_upcoming", "upcoming"):
            now = datetime.now(timezone.utc)
            end = now + timedelta(days=days)
            events = svc.events().list(
                calendarId=calendar_id, timeMin=now.isoformat(), timeMax=end.isoformat(),
                maxResults=max_results, singleEvents=True, orderBy="startTime"
            ).execute().get("items", [])
            if not events:
                return f"No upcoming events in the next {days} days."
            output = f"UPCOMING - {days} DAYS\n{'-'*40}\n"
            for ev in events:
                output += _fmt_event(ev)
            return output

        elif action_clean in ("list_range", "range"):
            if not start_date or not end_date:
                return "Error: 'start_date' and 'end_date' (YYYY-MM-DD or RFC3339) are required."
            t_min = f"{start_date}T00:00:00Z" if "T" not in start_date else start_date
            t_max = f"{end_date}T23:59:59Z" if "T" not in end_date else end_date
            events = svc.events().list(
                calendarId=calendar_id, timeMin=t_min, timeMax=t_max,
                maxResults=max_results, singleEvents=True, orderBy="startTime"
            ).execute().get("items", [])
            if not events:
                return f"No events found between {start_date} and {end_date}."
            output = f"EVENTS {start_date} TO {end_date}\n{'-'*40}\n"
            for ev in events:
                output += _fmt_event(ev)
            return output

        elif action_clean == "search":
            if not query:
                return "Error: 'query' parameter is required for search."
            events = svc.events().list(
                calendarId=calendar_id, q=query, maxResults=max_results, singleEvents=True
            ).execute().get("items", [])
            if not events:
                return f"No events found matching '{query}'."
            output = f"SEARCH: '{query}' - {len(events)} RESULTS\n{'-'*40}\n"
            for ev in events:
                output += _fmt_event(ev)
            return output

        elif action_clean in ("get", "get_event"):
            if not event_id:
                return "Error: 'event_id' parameter is required."
            ev = svc.events().get(calendarId=calendar_id, eventId=event_id.strip()).execute()
            start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
            end = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date", ""))
            attendees = [a.get("email", "") for a in ev.get("attendees", [])]
            lines = [
                f"Summary    : {ev.get('summary', 'No Title')}",
                f"Start      : {start}",
                f"End        : {end}",
                f"Location   : {ev.get('location', 'N/A')}",
                f"Description: {ev.get('description', '')}",
                f"Attendees  : {', '.join(attendees) if attendees else 'None'}",
                f"Link       : {ev.get('htmlLink', '')}",
                f"ID         : {ev.get('id', '')}",
            ]
            return "\n".join(lines)

        elif action_clean == "create":
            if not title or not start_datetime or not end_datetime:
                return "Error: 'title', 'start_datetime', and 'end_datetime' are required."
            body = {
                "summary": title,
                "location": location,
                "description": description,
                "start": {"dateTime": start_datetime, "timeZone": "Asia/Colombo"},
                "end": {"dateTime": end_datetime, "timeZone": "Asia/Colombo"},
            }
            if attendee_emails:
                emails = [e.strip() for e in attendee_emails.split(",") if e.strip()]
                body["attendees"] = [{"email": e} for e in emails]
            created = svc.events().insert(calendarId=calendar_id, body=body).execute()
            return f"Event created: '{title}'. ID: {created['id']} Link: {created.get('htmlLink', '')}"

        elif action_clean == "quick_add":
            if not text:
                return "Error: 'text' parameter is required for quick_add (e.g. 'Lunch with Bob at noon tomorrow')."
            created = svc.events().quickAdd(calendarId=calendar_id, text=text).execute()
            return f"Event quick-added: '{created.get('summary')}'. ID: {created['id']}"

        elif action_clean in ("update", "patch"):
            if not event_id:
                return "Error: 'event_id' parameter is required for update."
            body = {}
            if title:
                body["summary"] = title
            if description:
                body["description"] = description
            if location:
                body["location"] = location
            if start_datetime:
                body["start"] = {"dateTime": start_datetime, "timeZone": "Asia/Colombo"}
            if end_datetime:
                body["end"] = {"dateTime": end_datetime, "timeZone": "Asia/Colombo"}
            if not body:
                return "Error: Provide at least one field to update (title, description, location, start_datetime, end_datetime)."
            updated = svc.events().patch(calendarId=calendar_id, eventId=event_id.strip(), body=body).execute()
            return f"Event {event_id} updated successfully: '{updated.get('summary')}'."

        elif action_clean == "delete":
            if not event_id:
                return "Error: 'event_id' parameter is required for delete."
            svc.events().delete(calendarId=calendar_id, eventId=event_id.strip()).execute()
            return f"Event {event_id} deleted."

        elif action_clean == "duplicate":
            if not event_id or not start_datetime or not end_datetime:
                return "Error: 'event_id', 'start_datetime', and 'end_datetime' are required to duplicate."
            orig = svc.events().get(calendarId=calendar_id, eventId=event_id.strip()).execute()
            new_body = {
                "summary": orig.get("summary", ""),
                "location": orig.get("location", ""),
                "description": orig.get("description", ""),
                "start": {"dateTime": start_datetime, "timeZone": "Asia/Colombo"},
                "end": {"dateTime": end_datetime, "timeZone": "Asia/Colombo"},
            }
            duplicated = svc.events().insert(calendarId=calendar_id, body=new_body).execute()
            return f"Event duplicated. New Event ID: {duplicated['id']}"

        elif action_clean == "move":
            if not event_id or not target_calendar_id:
                return "Error: 'event_id' and 'target_calendar_id' are required to move event."
            moved = svc.events().move(
                calendarId=calendar_id, eventId=event_id.strip(), destination=target_calendar_id.strip()
            ).execute()
            return f"Event moved to {target_calendar_id}. New ID: {moved['id']}"

        elif action_clean == "add_attendees":
            if not event_id or not attendee_emails:
                return "Error: 'event_id' and 'attendee_emails' are required."
            ev = svc.events().get(calendarId=calendar_id, eventId=event_id.strip()).execute()
            existing = ev.get("attendees", [])
            new_list = [e.strip() for e in attendee_emails.split(",") if e.strip()]
            for em in new_list:
                if not any(a.get("email") == em for a in existing):
                    existing.append({"email": em})
            svc.events().patch(calendarId=calendar_id, eventId=event_id.strip(), body={"attendees": existing}).execute()
            return f"Added attendees to event {event_id}."

        elif action_clean == "set_reminder":
            if not event_id:
                return "Error: 'event_id' parameter is required."
            reminders = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": minutes_before}],
            }
            svc.events().patch(calendarId=calendar_id, eventId=event_id.strip(), body={"reminders": reminders}).execute()
            return f"Reminder set for {minutes_before} minutes before event {event_id}."

        elif action_clean == "find_free_time":
            target_date = start_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_iso = f"{target_date}T09:00:00Z"
            end_iso = f"{target_date}T17:00:00Z"
            body = {
                "timeMin": start_iso,
                "timeMax": end_iso,
                "items": [{"id": calendar_id}],
            }
            fb = svc.freebusy().query(body=body).execute()
            busy = fb.get("calendars", {}).get(calendar_id, {}).get("busy", [])
            return f"Busy slots on {target_date} for {calendar_id}: {json.dumps(busy)}"

        else:
            return f"Unknown event action '{action}'. Valid actions: list_upcoming, list_range, search, get, create, quick_add, update, delete, duplicate, move, add_attendees, set_reminder, find_free_time."

    except Exception as e:
        return f"Calendar event operation failed: {e}"


@mcp.tool()
def calendar_manage(
    action: str,
    calendar_id: str = "",
    summary: str = "",
    description: str = "",
    time_zone: str = "Asia/Colombo",
) -> str:
    """Manage calendars lifecycle: list_calendars, get_calendar, create_calendar, update_calendar, delete_calendar, clear_primary."""
    action_clean = (action or "").strip().lower()

    try:
        svc = _cal()

        if action_clean in ("list_calendars", "list"):
            clist = svc.calendarList().list().execute().get("items", [])
            if not clist:
                return "No calendars found."
            lines = [f"CALENDARS - {len(clist)} FOUND", "-" * 30]
            for c in clist:
                lines.append(f"  {c.get('summary')} (ID: {c.get('id')}) | Primary: {c.get('primary', False)}")
            return "\n".join(lines)

        elif action_clean in ("get_calendar", "get"):
            target_id = calendar_id or "primary"
            meta = svc.calendars().get(calendarId=target_id).execute()
            return f"Calendar: {meta.get('summary')}, ID: {meta.get('id')}, TimeZone: {meta.get('timeZone')}, Description: {meta.get('description', '')}"

        elif action_clean in ("create_calendar", "create"):
            if not summary:
                return "Error: 'summary' parameter is required to create calendar."
            body = {"summary": summary, "description": description, "timeZone": time_zone}
            created = svc.calendars().insert(body=body).execute()
            return f"Calendar created: '{summary}'. ID: {created['id']}"

        elif action_clean in ("update_calendar", "update"):
            if not calendar_id:
                return "Error: 'calendar_id' parameter is required."
            body = {}
            if summary:
                body["summary"] = summary
            if description:
                body["description"] = description
            if time_zone:
                body["timeZone"] = time_zone
            updated = svc.calendars().patch(calendarId=calendar_id.strip(), body=body).execute()
            return f"Calendar {calendar_id} updated: '{updated.get('summary')}'."

        elif action_clean in ("delete_calendar", "delete"):
            if not calendar_id or calendar_id == "primary":
                return "Error: 'calendar_id' is required and primary calendar cannot be deleted (use clear_primary instead)."
            svc.calendars().delete(calendarId=calendar_id.strip()).execute()
            return f"Calendar {calendar_id} deleted."

        elif action_clean == "clear_primary":
            svc.calendars().clear(calendarId="primary").execute()
            return "Primary calendar cleared of all events."

        else:
            return f"Unknown calendar management action '{action}'. Valid actions: list_calendars, get_calendar, create_calendar, update_calendar, delete_calendar, clear_primary."

    except Exception as e:
        return f"Calendar management operation failed: {e}"


@mcp.tool()
def calendar_sharing(
    action: str,
    calendar_id: str = "primary",
    rule_id: str = "",
    email: str = "",
    role: str = "reader",
) -> str:
    """Manage calendar sharing and access control (ACL): list_permissions, get_permission, share, update_permission, unshare."""
    action_clean = (action or "").strip().lower()

    try:
        svc = _cal()

        if action_clean in ("list_permissions", "list"):
            acls = svc.acl().list(calendarId=calendar_id).execute().get("items", [])
            if not acls:
                return f"No sharing permissions found for {calendar_id}."
            lines = [f"PERMISSIONS FOR {calendar_id}", "-" * 30]
            for a in acls:
                scope = a.get("scope", {})
                lines.append(f"  Rule ID: {a.get('id')} | Role: {a.get('role')} | User: {scope.get('value')}")
            return "\n".join(lines)

        elif action_clean in ("get_permission", "get"):
            if not rule_id:
                return "Error: 'rule_id' parameter is required."
            rule = svc.acl().get(calendarId=calendar_id, ruleId=rule_id.strip()).execute()
            return f"Rule ID: {rule.get('id')}, Role: {rule.get('role')}, Scope: {json.dumps(rule.get('scope', {}))}"

        elif action_clean in ("share", "insert"):
            if not email:
                return "Error: 'email' parameter is required to share calendar."
            body = {
                "role": role if role in ("none", "freeBusyReader", "reader", "writer", "owner") else "reader",
                "scope": {"type": "user", "value": email.strip()},
            }
            created = svc.acl().insert(calendarId=calendar_id, body=body).execute()
            return f"Calendar shared with {email} as {created.get('role')}. Rule ID: {created.get('id')}"

        elif action_clean in ("update_permission", "update"):
            if not rule_id:
                return "Error: 'rule_id' parameter is required."
            body = {"role": role}
            updated = svc.acl().patch(calendarId=calendar_id, ruleId=rule_id.strip(), body=body).execute()
            return f"Permission {rule_id} updated to role {updated.get('role')}."

        elif action_clean in ("unshare", "delete"):
            if not rule_id:
                return "Error: 'rule_id' parameter is required to unshare."
            svc.acl().delete(calendarId=calendar_id, ruleId=rule_id.strip()).execute()
            return f"Permission {rule_id} removed from {calendar_id}."

        else:
            return f"Unknown sharing action '{action}'. Valid actions: list_permissions, get_permission, share, update_permission, unshare."

    except Exception as e:
        return f"Calendar sharing operation failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")

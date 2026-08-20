---
name: Google Calendar
description: Manage calendar events and schedules.
---

# Google Calendar Skill (MCP)
**IMPORTANT:** The MCP server path is `MCP/google/calendar_handlers.py` (relative to the project root).

## Available Tools:
- `list_upcoming_events`
- `create_calendar_event`
- `update_calendar_event`
- `get_calendar_event`
- `delete_calendar_event`
- `search_calendar_events`
- `list_events_date_range`
- `list_calendars`
- `add_event_attendees`
- `create_all_day_event`
- `duplicate_calendar_event`
- `set_event_reminder`
- `move_event_to_calendar`
- `find_free_time`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(os.path.abspath(os.path.join(os.getcwd(), "..")), "MCP", "google", "calendar_handlers.py"),
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```

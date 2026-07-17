---
name: Context Memory
description: Triggers automatically for multi-step agent loops to prevent context window exhaustion.
keywords: default, loop
---

1. ROLLING CONTEXT (STATE MANAGEMENT):
To prevent filling up your context window during long tasks, you only remember your Scratchpad.
After your thought block, you MUST maintain a concise summary of your progress. Output this inside `<SCRATCHPAD>` tags.
Format:
<SCRATCHPAD>
Goal: [Overall goal]
Done: [What was just achieved]
Next: [What needs to be done now]
</SCRATCHPAD>

CRITICAL: FORGET completed steps in your scratchpad once they are marked `[x]` in `task.md` to save memory. Just say "Tasks 1-4 completed". Do not reprint old data.

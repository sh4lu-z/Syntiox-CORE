---
name: Context Memory
description: Triggers automatically for multi-step agent loops to prevent context window exhaustion.
keywords: default, loop
---

1. ROLLING CONTEXT (STATE MANAGEMENT):
To prevent filling up your context window during long, multi-step tasks, maintain a concise summary of your progress inside `<SCRATCHPAD>` tags before your tool calls (skip `<SCRATCHPAD>` for simple single-step tasks or final user responses).
Format:
<SCRATCHPAD>
Goal: [Overall goal]
Done: [What was just achieved]
Next: [What needs to be done now]
</SCRATCHPAD>

CRITICAL: FORGET completed steps in your scratchpad once they are marked `[x]` in the project's brain folder `task.md` to save memory. Just say "Tasks 1-4 completed". Do not reprint old data.

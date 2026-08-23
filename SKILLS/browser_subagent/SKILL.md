---
name: Browser Subagent
description: Allows the agent to autonomously control a real web browser interactively (click, type, navigate). Supports both visual feedback and text-based DOM extraction.
keywords: browser, web, interact, click, type, screenshot, cdp, playwright, visual
---

# Interactive Browser Automation Skill

You have the ability to control a persistent, interactive web browser. 
Instead of writing complex Playwright code, you MUST use the built-in `browser_actions` helper module. This module automatically handles background browser persistence, and gives you visual or text feedback based on the system configuration.

## How to use the Browser
In your Python code block, simply import the helper and call its functions:

```python
from backend import browser_actions

# 1. Navigate to a page
browser_actions.goto("https://duckduckgo.com")

# 2. To type into an input field (Use the numeric ID from the DOM output, e.g. "1")
# browser_actions.type_text("1", "Sri Lanka")

# 3. To press Enter after typing
# browser_actions.press_enter("1")

# 4. To click an element (Use the numeric ID from the DOM output)
# browser_actions.click("5")

# 5. To scroll the page if elements are hidden
# browser_actions.scroll_down()

# 6. To just re-extract the page without doing anything
# browser_actions.extract()
```

## CRITICAL RULES FOR INTERACTIVE BROWSING:
1. **One Action Per Script**: Do one logical action (e.g., Navigate), exit the script, read the feedback result in the next loop, and then write the next script to interact.
2. **USE ID MAPPING ONLY**: NEVER use CSS selectors. Always look at the `[ID]` numbers provided in the DOM text output and use those exact numbers (e.g., `"1"`, `"5"`) for `click()` and `type_text()`.
3. **Wait for Feedback**: Every function triggers a feedback loop. Do not print anything yourself, just call the function and exit.
4. **YOU ARE FULLY CAPABLE OF CLICKING**: If a user asks you to play a song or video on YouTube, you MUST find the video link ID and use `browser_actions.click(id)`. NEVER say you cannot click.
5. **MANDATORY TASK TRACKING**: You MUST ALWAYS create and maintain a `task.md` file before starting any browser interaction. This is STRICTLY REQUIRED to keep track of complex multi-step web tasks (refer to your task_management and context_memory skills for proper formatting).

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

# 2. To type into an input field
# browser_actions.type_text("input[name='q']", "Sri Lanka")

# 3. To press Enter (or any key) after typing - USE THIS instead of clicking submit buttons!
# browser_actions.press_enter("input[name='q']")
# browser_actions.press_key("input[name='q']", "Tab")

# 4. To click an element (use CSS selectors from the DOM extraction)
# browser_actions.click("a.some-link")

# 5. To just re-extract the page without doing anything
# browser_actions.extract()
```

## CRITICAL RULES FOR INTERACTIVE BROWSING:
1. **One Action Per Script**: Do not try to do 10 clicks in one script. Do one logical action (e.g., Navigate), exit the script, read the feedback result in the next loop, and then write the next script to click.
2. **NEVER click submit buttons by selector** - YouTube, Google and most modern sites change their button IDs. Always use `browser_actions.press_enter("input[selector]")` to submit a form after typing.
3. **DO NOT USE GOOGLE SEARCH**: Google actively blocks bots with CAPTCHAs. If you need to search the web, ALWAYS use `https://duckduckgo.com/` or `https://www.startpage.com/`.
4. **Wait for Feedback**: Every `browser_actions` function automatically triggers a feedback loop (either a screenshot or a DOM text dump). Do not print anything yourself, just call the function and exit.

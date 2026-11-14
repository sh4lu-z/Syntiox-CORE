import inspect
import io
import json
import os
import re
import sys
import time
from contextlib import redirect_stdout
from tools.logger import action_logger

MAX_BROWSER_STEPS = 20
MAX_STEP_OUTPUT_CHARS = 4200
MAX_HISTORY_SUMMARY_CHARS = 1600
MAX_PROMPT_FINDINGS_CHARS = 1600
MAX_HANDOFF_DOM_CHARS = 8000
MAX_SNAPSHOT_CHARS = 2500


def _normalize_tool_args(parsed: dict) -> dict:
    """Support nested arguments dicts as well as flat keys emitted by some models."""
    raw_args = parsed.get("arguments")
    if raw_args is None:
        raw_args = parsed.get("args", parsed.get("parameters"))

    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except Exception:
            raw_args = {}

    if isinstance(raw_args, dict) and raw_args:
        return raw_args

    return {
        k: v for k, v in parsed.items()
        if k not in ("name", "arguments", "args", "parameters")
    }


def extract_tool_calls(text: str) -> tuple:
    cleaned_text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    tool_calls = []
    parse_errors = []

    for match in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", cleaned_text, flags=re.DOTALL):
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict) and "name" in parsed:
                tool_calls.append({
                    "function": {
                        "name": str(parsed["name"]).strip(),
                        "arguments": _normalize_tool_args(parsed),
                    }
                })
        except Exception as e:
            parse_errors.append(str(e))

    if not tool_calls and not parse_errors:
        stripped = cleaned_text.strip()
        fenced_matches = list(re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL))
        candidates = [m.group(1).strip() for m in fenced_matches]
        if not candidates:
            # Allow prose around a bare JSON object
            start, end = stripped.find("{"), stripped.rfind("}")
            if 0 <= start < end:
                candidates = [stripped[start:end + 1]]

        for candidate in candidates:
            if not (candidate.startswith("{") and candidate.endswith("}")):
                continue
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and "name" in parsed:
                    tool_calls.append({
                        "function": {
                            "name": str(parsed["name"]).strip(),
                            "arguments": _normalize_tool_args(parsed),
                        }
                    })
            except Exception as e:
                if '"name"' in candidate or "'name'" in candidate:
                    parse_errors.append(str(e))

    return tool_calls, parse_errors


def _parse_page_meta(output: str) -> tuple[str, str]:
    m = re.search(r"\[CURRENT PAGE\]\s*Title:\s*'(.*?)'\s*\|\s*URL:\s*(\S+)", output or "")
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", ""


def _record_visited_page(output: str, memory_state: dict) -> tuple[str, str]:
    title, url = _parse_page_meta(output)
    if url and url not in ("about:blank", "chrome://newtab/") and url not in memory_state["visited_urls"]:
        memory_state["visited_urls"].append(url)
    if url:
        memory_state["last_url"] = url
        memory_state["last_title"] = title
    return title, url


def _resolve_element_label(dom_output: str, element_id) -> str:
    if element_id is None or str(element_id).strip() == "":
        return ""
    target = str(element_id).strip()
    marker = "--- INTERACTABLE ELEMENTS (ON SCREEN) ---"
    search_area = dom_output.split(marker, 1)[1] if marker in (dom_output or "") else (dom_output or "")
    match = re.search(rf"^\[{re.escape(target)}\]\s+(.+)$", search_area, flags=re.MULTILINE)
    return f"[{target}] {match.group(1).strip()}" if match else ""


def _extract_dom_text_for_handoff(raw_output: str) -> tuple[str, str]:
    text = (raw_output or "").strip()
    if not text:
        return "", ""

    text = re.sub(r"\[IMAGE_RESULT\]\s*[^\n\r]+\n?", "", text)
    text = re.sub(
        r"--- INTERACTABLE ELEMENTS \(ON SCREEN\) ---.*?(?=\[TEXT_RESULT\]|--- PAGE CONTENT SUMMARY ---|\Z)",
        "",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"\[Tool:\s*[^\]]+\]\s*Result:\s*", "", text)
    text = re.sub(r"\[TEXT_RESULT\]\s*(?:Page extracted successfully\.[^\n]*|OK)\s*\n?", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    page_match = re.search(r"--- PAGE CONTENT SUMMARY ---\s*(.*)$", text, flags=re.DOTALL)
    page_text = page_match.group(1).strip() if page_match else ""
    return page_text, text


def _record_dom_snapshot(memory_state: dict, step: int, action: str, title: str, url: str, raw_output: str):
    if "--- INTERACTABLE ELEMENTS (ON SCREEN) ---" in (raw_output or "") or "[CURRENT PAGE]" in (raw_output or ""):
        memory_state["last_dom_elements"] = raw_output

    page_text, clean_dom = _extract_dom_text_for_handoff(raw_output)
    if not clean_dom:
        return

    norm_url = url or memory_state.get("last_url", "")
    prev = memory_state["dom_snapshots"][-1] if memory_state["dom_snapshots"] else None
    if prev and prev.get("page_text") and page_text and prev["page_text"] == page_text and (prev.get("url") or "") == norm_url:
        return

    memory_state["dom_snapshots"].append({
        "step": step,
        "action": action,
        "url": norm_url,
        "title": title or memory_state.get("last_title", ""),
        "page_text": page_text,
        "content": clean_dom,
    })


def _extract_action_error_note(raw_output: str) -> str:
    for line in (raw_output or "").splitlines():
        s = line.strip()
        if s.startswith("[ERROR]") or s.startswith("Tool execution failed:"):
            return s[:200]
    return ""


def _compact_dom_output(output: str, keep_elements: bool = True, max_chars: int = MAX_STEP_OUTPUT_CHARS) -> str:
    text = (output or "").strip()
    if not keep_elements:
        text = re.sub(
            r"--- INTERACTABLE ELEMENTS \(ON SCREEN\) ---.*?(?=\[TEXT_RESULT\]|--- PAGE CONTENT SUMMARY ---|\Z)",
            "[Earlier page elements omitted]\n",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(r"\[IMAGE_RESULT\]\s*[^\n\r]+\n?", "", text)

    if len(text) <= max_chars:
        return text

    note_match = re.search(r"(\[Note: Page has \d+ total characters[^\n]*\])", text)
    note_line = f"\n{note_match.group(1)}" if note_match else ""
    elem_idx = text.find("--- INTERACTABLE ELEMENTS (ON SCREEN) ---")
    if keep_elements and elem_idx > 0:
        # Head must stop before the elements block so it is not repeated in the tail
        head_budget = min(elem_idx, max(800, max_chars // 2))
        head = text[:head_budget].rstrip()
        if note_line and note_line.strip() in head:
            note_line = ""
        sep = "\n...[DOM text truncated]" if head_budget < elem_idx else ""
        rem_budget = max(800, max_chars - len(head) - len(sep) - len(note_line) - 20)
        page_idx = text.find("--- PAGE CONTENT SUMMARY ---", elem_idx)
        if page_idx != -1:
            elems_raw = text[elem_idx:page_idx].rstrip()
            elem_budget = min(len(elems_raw), max(400, rem_budget // 2))
            page_budget = max(400, rem_budget - elem_budget)
            elems_part = elems_raw[:elem_budget].rstrip()
            page_part = text[page_idx : page_idx + page_budget].rstrip()
            tail = f"{elems_part}\n\n{page_part}"
        else:
            tail = text[elem_idx : elem_idx + rem_budget].rstrip()
        return f"{head}{sep}{note_line}\n\n{tail}"
    return f"{text[:max_chars - 30].rstrip()}\n...[output truncated]{note_line}"


def _fold_steps_into_summary(aged_steps: list, memory_state: dict, safe_groq_chat):
    if not aged_steps:
        return

    chunk_lines = []
    has_substantive_dom = False
    for rec in aged_steps:
        out_excerpt = _compact_dom_output(rec.get("raw_output", ""), keep_elements=False, max_chars=450)
        if len(rec.get("raw_output", "")) > 350:
            has_substantive_dom = True
        page_label = f"{rec.get('title') or ''} ({rec.get('url') or ''})".strip()
        chunk_lines.append(
            f"- Step {rec['step']}: action={rec['action']} | page={page_label or 'unknown'}\n  result: {out_excerpt}"
        )

    aged_block = "\n".join(chunk_lines)
    prev_summary = memory_state.get("history_summary", "").strip()

    new_summary = ""
    if has_substantive_dom and (len(aged_block) > 450 or (prev_summary and len(prev_summary) > 1000)):
        prompt = (
            f"Previous Browser History Summary:\n{prev_summary or '(none)'}\n\n"
            f"Newly Completed Browser Steps:\n{aged_block[:3000]}"
        )
        sys_msg = (
            "Summarize the browser subagent's earlier progress in concise bullet points. "
            "Preserve exact URLs visited, searches performed, key facts/answers seen on pages, "
            "and any errors. Max 180 words. Plain bullet lines only."
        )
        try:
            ai_sum = safe_groq_chat(prompt, system_prompt=sys_msg, max_tokens=700)
            if ai_sum and ai_sum.strip():
                new_summary = ai_sum.strip()
        except Exception:
            new_summary = ""

    if not new_summary:
        fallback_lines = []
        for rec in aged_steps:
            page_info = rec.get("url") or "page"
            cleaned = re.sub(r"\[Tool:\s*[^\]]+\]\s*Result:\s*", "", rec.get("raw_output", ""))
            cleaned = re.sub(r"--- PAGE CONTENT SUMMARY ---", "", cleaned)
            snippet = re.sub(r"\s+", " ", _compact_dom_output(cleaned, keep_elements=False, max_chars=220)).strip()
            fallback_lines.append(f"- Step {rec['step']} ({rec['action']} @ {page_info}): {snippet}")
        combined = f"{prev_summary}\n" + "\n".join(fallback_lines) if prev_summary else "\n".join(fallback_lines)
        new_summary = combined.strip()

    if len(new_summary) > MAX_HISTORY_SUMMARY_CHARS:
        new_summary = "...\n" + new_summary[-(MAX_HISTORY_SUMMARY_CHARS - 4):]
    memory_state["history_summary"] = new_summary


def _format_tasks_block(tasks: list) -> str:
    if not tasks:
        return ""
    lines = []
    for item in tasks:
        status = item.get("status", "pending")
        mark = "[x]" if status == "done" else ("[~]" if status == "in_progress" else "[ ]")
        lines.append(f"{mark} {item.get('task', '')}")
    return "\n".join(lines)


def _format_findings_block(findings: list, max_chars: int = None) -> str:
    if not findings:
        return ""
    blocks = []
    for idx, f in enumerate(findings, 1):
        src = f.get("source") or "unknown source"
        blocks.append(f"{idx}. {f.get('title', 'Note')} | Source: {src}\n   {f.get('notes', '')}")
    joined = "\n".join(blocks)
    if max_chars and len(joined) > max_chars:
        # Shorten each note instead of dropping the oldest entries
        per_note = max(80, max_chars // len(findings) - 60)
        blocks = []
        for idx, f in enumerate(findings, 1):
            src = f.get("source") or "unknown source"
            notes = str(f.get("notes", ""))
            if len(notes) > per_note:
                notes = notes[:per_note].rstrip() + "..."
            blocks.append(f"{idx}. {f.get('title', 'Note')} | Source: {src}\n   {notes}")
        joined = "\n".join(blocks)
        if len(joined) > max_chars:
            joined = joined[:max_chars - 4].rstrip() + "\n..."
    return joined


def _build_memory_header(task: str, memory_state: dict) -> str:
    parts = [f"Task: {task}"]

    tasks_str = _format_tasks_block(memory_state["tasks"])
    if tasks_str:
        parts.append(f"[TASK CHECKLIST]\n{tasks_str}")

    findings_str = _format_findings_block(memory_state["findings"], max_chars=MAX_PROMPT_FINDINGS_CHARS)
    if findings_str:
        parts.append(f"[SAVED RESEARCH MEMORY & SOURCES]\n{findings_str}")

    if memory_state["visited_urls"]:
        urls_preview = ", ".join(memory_state["visited_urls"][-8:])
        parts.append(f"[VISITED URLS]: {urls_preview}")

    if memory_state["history_summary"]:
        parts.append(f"[HISTORY SUMMARY (EARLIER STEPS)]\n{memory_state['history_summary']}")

    return "\n\n".join(parts)


def _handle_memory_tool(t_name: str, t_args: dict, memory_state: dict) -> str | None:
    if t_name == "update_tasks":
        raw_tasks = t_args.get("tasks", t_args.get("items", []))
        if isinstance(raw_tasks, str):
            raw_tasks = [line.strip() for line in raw_tasks.splitlines() if line.strip()]
        if not isinstance(raw_tasks, list):
            return "[TEXT_RESULT] update_tasks expects a list of tasks."

        normalized = []
        for entry in raw_tasks:
            if isinstance(entry, dict):
                label = str(entry.get("task") or entry.get("title") or entry.get("name") or "").strip()
                status = str(entry.get("status", "pending")).lower().strip()
                if status not in ("pending", "in_progress", "done"):
                    status = "done" if entry.get("done") else "pending"
                if label:
                    normalized.append({"task": label, "status": status})
            else:
                text = str(entry).strip()
                status = "pending"
                if text.lower().startswith(("[x]", "✓", "done:")):
                    status = "done"
                    text = re.sub(r"^(\[x\]|✓|done:)\s*", "", text, flags=re.IGNORECASE).strip()
                elif text.lower().startswith(("[~]", "in_progress:")):
                    status = "in_progress"
                    text = re.sub(r"^(\[~\]|in_progress:)\s*", "", text, flags=re.IGNORECASE).strip()
                elif text.startswith("[ ]"):
                    text = text[3:].strip()
                if text:
                    normalized.append({"task": text, "status": status})

        memory_state["tasks"] = normalized
        done_count = sum(1 for t in normalized if t["status"] == "done")
        return f"[TEXT_RESULT] Task checklist updated ({done_count}/{len(normalized)} done):\n{_format_tasks_block(normalized)}"

    if t_name == "save_memory":
        title = str(t_args.get("title") or t_args.get("topic") or t_args.get("name") or "Note").strip()
        notes = str(t_args.get("notes") or t_args.get("content") or t_args.get("summary") or t_args.get("data") or "").strip()
        source = str(t_args.get("source_url") or t_args.get("url") or t_args.get("source") or memory_state.get("last_url") or "").strip()

        if not notes:
            return "[TEXT_RESULT] save_memory skipped: 'notes' cannot be empty."

        for existing in memory_state["findings"]:
            if existing["title"].lower() == title.lower() and existing["source"] == source:
                existing["notes"] = notes
                return f"[TEXT_RESULT] Updated memory entry '{title}' (Source: {source or 'current session'})."

        memory_state["findings"].append({
            "title": title,
            "source": source,
            "notes": notes,
        })
        return f"[TEXT_RESULT] Saved to memory (#{len(memory_state['findings'])}): '{title}' (Source: {source or 'current session'})."

    return None


def _format_action_log(action_log: list) -> str:
    if not action_log:
        return ""
    lines = []
    for item in action_log:
        arg_parts = []
        for k, v in (item.get("args") or {}).items():
            v_str = repr(v)
            if len(v_str) > 120:
                v_str = v_str[:117] + "..."
            arg_parts.append(f"{k}={v_str}")
        args_str = ", ".join(arg_parts)
        line = f"- Step {item['step']}: {item['tool']}({args_str})"
        if item.get("target"):
            line += f" | target: {item['target']}"
        if item.get("url"):
            line += f" | page: {item['url']}"
        if item.get("note"):
            line += f" | note: {item['note']}"
        lines.append(line)
    return "\n".join(lines)


def _format_dom_snapshots(dom_snapshots: list, max_chars: int = MAX_HANDOFF_DOM_CHARS) -> str:
    if not dom_snapshots:
        return ""
    # Keep the newest snapshots within budget
    blocks = []
    used = 0
    for snap in reversed(dom_snapshots):
        header = f"--- Step {snap['step']} ({snap['action']})"
        if snap.get("title"):
            header += f" | {snap['title']}"
        if snap.get("url"):
            header += f" | {snap['url']}"
        header += " ---"
        content = snap["content"]
        if len(content) > MAX_SNAPSHOT_CHARS:
            content = content[:MAX_SNAPSHOT_CHARS].rstrip() + "\n...[snapshot truncated]"
        block = f"{header}\n{content}"
        if blocks and used + len(block) > max_chars:
            blocks.append(f"[{len(dom_snapshots) - len(blocks)} older snapshot(s) omitted]")
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(reversed(blocks))


def _build_final_handoff(status_text: str, memory_state: dict) -> str:
    status_text = str(status_text or "").strip() or "Browser session ended."
    sections = [status_text]

    tasks_str = _format_tasks_block(memory_state["tasks"])
    if tasks_str:
        sections.append(f"[TASK CHECKLIST]\n{tasks_str}")

    findings_str = _format_findings_block(memory_state["findings"])
    if findings_str:
        sections.append(f"[COLLECTED RESEARCH & SOURCES]\n{findings_str}")

    if memory_state["visited_urls"]:
        sections.append("[VISITED URLS]\n" + "\n".join(f"- {u}" for u in memory_state["visited_urls"]))

    # Summary goes before the large logs so it survives result truncation
    if memory_state["history_summary"] and (
        memory_state["findings"]
        or len(memory_state["visited_urls"]) > 1
        or any(k in status_text.lower() for k in ("stopped", "step limit", "error"))
    ):
        sections.append(f"[BROWSER SESSION SUMMARY]\n{memory_state['history_summary']}")

    action_str = _format_action_log(memory_state.get("action_log", []))
    if action_str:
        sections.append(f"[BROWSER ACTION & CLICK LOG]\n{action_str}")

    dom_str = _format_dom_snapshots(memory_state.get("dom_snapshots", []))
    if dom_str:
        sections.append(f"[CAPTURED DOM TEXT BY STEP]\n{dom_str}")

    return "\n\n".join(sections)


def _call_browser_action(func, t_args: dict) -> str:
    sig = inspect.signature(func)
    params = sig.parameters
    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    filtered_args = t_args if accepts_kwargs else {k: v for k, v in t_args.items() if k in params}

    f = io.StringIO()
    with redirect_stdout(f):
        try:
            func(**filtered_args)
        except Exception as e:
            print(f"Tool execution failed: {e}")
    return f.getvalue()


@action_logger("browser_subagent")
def browser_subagent(task: str) -> str:
    """
    Start a browser subagent to perform actions in the browser with the given task description.
    The subagent will autonomously navigate, click, type, manage tabs, track research memory/tasks, and request human help when needed.
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    from backend import state, event_bus
    from backend.browser import browser_actions
    from backend import cloud_llm
    from backend.cloud_llm import (
        safe_generate_groq,
        safe_generate_content_gemini,
        safe_groq_chat,
        is_groq_model,
        BROWSER_MODEL,
        GOOGLE_MODEL,
    )
    from google.genai import types

    sys_prompt = (
        "You are an advanced Browser Subagent. Complete the user's browser task accurately.\n"
        "Use EXACT XML format for tool calls (NO markdown code blocks):\n"
        "<tool_call>{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"val\"}}</tool_call>\n\n"
        "BROWSER TOOLS:\n"
        "1. goto(url: string)\n"
        "2. click(element_id: string)\n"
        "3. type_text(element_id: string, text: string)\n"
        "4. press_key(element_id: string, key: string)\n"
        "5. press_enter(element_id: string)\n"
        "6. scroll_down() / 7. scroll_up()\n"
        "8. extract(offset: int, length: int) - Read further DOM text when truncated.\n"
        "9. new_tab(url: string) / 10. switch_tab(index: int) / 11. close_tab(index: int) / 12. list_tabs()\n"
        "13. request_human_intervention(reason: string) - Call IMMEDIATELY on CAPTCHA, Cloudflare, 2FA, or Login.\n\n"
        "MEMORY & PLANNING TOOLS (for multi-step / research tasks):\n"
        "14. update_tasks(tasks: list) - Track subtasks e.g. [{\"task\": \"Search topic\", \"status\": \"done\"}, {\"task\": \"Compare pricing\", \"status\": \"in_progress\"}].\n"
        "15. save_memory(title: string, notes: string, source_url: string) - Save key facts, data, and exact source URLs BEFORE navigating away from a page. All saved entries are handed to the main agent.\n\n"
        "RULES:\n"
        "- Execute ONE browser action per turn (you may update_tasks or save_memory alongside finish or before leaving a page).\n"
        "- NO shortcuts to search URLs; navigate normally and use page search inputs/links.\n"
        "- For research/multi-page tasks, use update_tasks early and save_memory on each useful source so findings persist after old DOMs are compacted.\n"
        "- When done, call <tool_call>{\"name\": \"finish\", \"arguments\": {\"result\": \"complete final answer including key findings\"}}</tool_call>."
    )

    print(f"\n[Browser Subagent] Initializing browser for task: {task}")
    try:
        browser_actions.set_agent_active(True, task)
    except Exception as e:
        print(f"[Browser Subagent] Note on active setup: {e}")

    f_init = io.StringIO()
    with redirect_stdout(f_init):
        try:
            browser_actions.list_tabs()
            browser_actions.extract(offset=0, length=2000)
        except Exception as e:
            print(f"[ERROR] Could not fetch initial browser context: {e}")

    init_context = f_init.getvalue()
    memory_state = {
        "tasks": [],
        "findings": [],
        "visited_urls": [],
        "history_summary": "",
        "last_url": "",
        "last_title": "",
        "last_dom_elements": "",
        "action_log": [],
        "dom_snapshots": [],
    }
    init_title, init_url = _record_visited_page(init_context, memory_state)
    _record_dom_snapshot(memory_state, 0, "startup", init_title, init_url, init_context)

    step_records = [{
        "step": 0,
        "action": "startup",
        "url": init_url,
        "title": init_title,
        "model_text": "",
        "raw_output": init_context,
    }]

    groq_cooldown_until = 0.0
    summary_cooldown_until = 0.0
    gemini_fallback_model = GOOGLE_MODEL if (not is_groq_model(GOOGLE_MODEL) and "gemma" not in GOOGLE_MODEL.lower()) else None
    has_gemini_fallback = bool(getattr(cloud_llm, "API_KEYS", None)) and bool(gemini_fallback_model)

    def _summary_chat(*args, **kwargs):
        nonlocal summary_cooldown_until
        now = time.time()
        if now < groq_cooldown_until or now < summary_cooldown_until:
            return None
        res = safe_groq_chat(*args, **kwargs)
        if res is None and getattr(cloud_llm, "GROQ_API_KEYS", None):
            summary_cooldown_until = time.time() + 30.0
        return res

    def _browser_stream_cb(token):
        state.emit_event({"event": "token", "agent_id": "browser_subagent", "data": token})

    def _browser_thought_cb(chunk):
        state.emit_event({"event": "thinking", "agent_id": "browser_subagent", "data": chunk})

    event_bus.push_agent("browser_subagent")
    try:
        for step in range(MAX_BROWSER_STEPS):
            if browser_actions.is_stopped_by_user():
                print("[Browser Subagent] Stopped by user.")
                return _build_final_handoff(
                    "The user manually stopped the browser subagent using the STOP button. "
                    "Please use `ask_user` if you need clarification on how to continue.",
                    memory_state,
                )

            step_num = step + 1
            step_t0 = time.time()
            state.emit_event({
                "event": "step_start",
                "agent_id": "browser_subagent",
                "step": step_num,
                "max_steps": MAX_BROWSER_STEPS,
            })

            def _emit_browser_step_end(s_res=None):
                s_res = s_res if isinstance(s_res, dict) else {}
                state.emit_event({
                    "event": "step_end",
                    "agent_id": "browser_subagent",
                    "step": step_num,
                    "model": s_res.get("model"),
                    "usage": s_res.get("usage"),
                    "finish_reason": s_res.get("finish_reason"),
                    "duration_ms": round((time.time() - step_t0) * 1000),
                })

            # Keep only the latest 2 turns active; fold older steps into summary
            if len(step_records) > 2:
                aged = step_records[:-2]
                step_records = step_records[-2:]
                _fold_steps_into_summary(aged, memory_state, _summary_chat)

            # Build structured prompt contents from working memory + active window
            memory_header = _build_memory_header(task, memory_state)
            contents = []
            has_first_model = bool(step_records and step_records[0].get("model_text"))
            if has_first_model:
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=memory_header)]))

            vision_on = getattr(state, "VISION_ENABLED", False)
            last_idx = len(step_records) - 1
            for idx, rec in enumerate(step_records):
                if rec.get("model_text"):
                    contents.append(types.Content(role="model", parts=[types.Part.from_text(text=rec["model_text"])]))

                is_latest = idx == last_idx
                raw_out = rec.get("raw_output", "")
                dom_text = _compact_dom_output(raw_out, keep_elements=is_latest)
                # Non-page turns (memory tools, invalid replies) would hide element IDs otherwise
                if is_latest and "--- INTERACTABLE ELEMENTS (ON SCREEN) ---" not in raw_out and memory_state.get("last_dom_elements"):
                    page_state = _compact_dom_output(memory_state["last_dom_elements"], keep_elements=True)
                    dom_text = f"{dom_text}\n\n[LAST KNOWN PAGE STATE]\n{page_state}"
                user_parts = []

                if idx == 0 and not has_first_model:
                    user_parts.append(types.Part.from_text(text=memory_header))

                if is_latest and vision_on:
                    img_matches = re.findall(r"\[IMAGE_RESULT\]\s*([^\n\r]+)", rec.get("raw_output", ""))
                    if img_matches:
                        img_path = img_matches[-1].strip()
                        if os.path.exists(img_path):
                            try:
                                with open(img_path, "rb") as img_file:
                                    user_parts.append(types.Part.from_bytes(data=img_file.read(), mime_type="image/png"))
                            except Exception as e:
                                print(f"[Browser Subagent] Failed to load image: {e}")

                label = "[CURRENT BROWSER VIEW]" if is_latest else f"[PREVIOUS STEP {rec['step']} RESULT]"
                user_parts.append(types.Part.from_text(text=f"{label}\n{dom_text}"))
                contents.append(types.Content(role="user", parts=user_parts))

            # Hybrid routing: Groq primary -> seamless Gemini failover on rate limit / 503
            ai_text = ""
            res = {}
            try:
                use_groq_now = is_groq_model(BROWSER_MODEL) and time.time() >= groq_cooldown_until
                if use_groq_now:
                    try:
                        res = safe_generate_groq(
                            contents,
                            sys_prompt=sys_prompt,
                            model=BROWSER_MODEL,
                            stream_callback=_browser_stream_cb,
                            thought_callback=_browser_thought_cb,
                            reasoning_effort="none",
                            max_busy_retries=1 if has_gemini_fallback else None,
                            quota_wait_max_seconds=0 if has_gemini_fallback else 25,
                        )
                        ai_text = res.get("content", "")
                    except Exception as groq_err:
                        if not has_gemini_fallback:
                            raise groq_err
                        retry_hint = cloud_llm._extract_groq_retry_after(groq_err)
                        cooldown_s = min(max((retry_hint or 35.0) + 2.0, 15.0), 60.0)
                        groq_cooldown_until = time.time() + cooldown_s
                        err_brief = str(groq_err).splitlines()[0][:120]
                        print(f"\033[93m[Browser Subagent] Groq fallback -> {gemini_fallback_model} for {cooldown_s:.0f}s ({err_brief})\033[0m")
                        state.emit_event({
                            "event": "retry",
                            "agent_id": "browser_subagent",
                            "provider": "groq",
                            "reason": "failover",
                            "attempt": 1,
                            "max": 1,
                            "wait_s": round(cooldown_s, 1),
                        })
                        res = safe_generate_content_gemini(
                            contents,
                            sys_prompt=sys_prompt,
                            model=gemini_fallback_model,
                            stream_callback=_browser_stream_cb,
                            thought_callback=_browser_thought_cb,
                        )
                        ai_text = res.get("content", "")
                else:
                    fallback_model = gemini_fallback_model if is_groq_model(BROWSER_MODEL) else BROWSER_MODEL
                    res = safe_generate_content_gemini(
                        contents,
                        sys_prompt=sys_prompt,
                        model=fallback_model,
                        stream_callback=_browser_stream_cb,
                        thought_callback=_browser_thought_cb,
                    )
                    ai_text = res.get("content", "")
            except Exception as e:
                _emit_browser_step_end(res)
                return _build_final_handoff(f"Browser Agent Error: {e}", memory_state)

            tool_calls, parse_errors = extract_tool_calls(ai_text)
            if not tool_calls:
                _emit_browser_step_end(res)
                err_note = (
                    f"Your <tool_call> JSON was malformed ({parse_errors[0]}). Output valid JSON inside <tool_call>...</tool_call>."
                    if parse_errors
                    else "You did not call a tool. Perform a browser/memory tool call or call 'finish'."
                )
                step_records.append({
                    "step": step + 1,
                    "action": "invalid_response",
                    "url": memory_state["last_url"],
                    "title": memory_state["last_title"],
                    "model_text": ai_text or "(empty response)",
                    "raw_output": err_note,
                })
                continue

            if browser_actions.is_stopped_by_user():
                _emit_browser_step_end(res)
                print("[Browser Subagent] Stopped by user before executing tools.")
                return _build_final_handoff(
                    "The user manually stopped the browser subagent using the STOP button. "
                    "Please use `ask_user` if you need clarification on how to continue.",
                    memory_state,
                )

            execution_results = []
            executed_names = []
            # finish skips browser actions regardless of its position in the turn
            finished = any(tc.get("function", {}).get("name") == "finish" for tc in tool_calls)
            final_result = ""

            for tc_idx, tc in enumerate(tool_calls):
                t_name = tc.get("function", {}).get("name", "")
                t_args = tc.get("function", {}).get("arguments", {})
                if not isinstance(t_args, dict):
                    t_args = {}
                call_id = f"browser_step_{step + 1}_call_{tc_idx}"

                if t_name == "finish":
                    res_val = t_args.get("result")
                    if isinstance(res_val, str) and res_val.strip():
                        final_result = res_val
                    elif res_val:
                        final_result = json.dumps(res_val, ensure_ascii=False, default=str)
                    else:
                        final_result = "Completed successfully."
                    state.emit_event({
                        "event": "tool_call",
                        "agent_id": "browser_subagent",
                        "tool": "finish",
                        "args": t_args,
                        "call_id": call_id,
                    })
                    capped_fin, fin_trunc = event_bus.cap(final_result)
                    state.emit_event({
                        "event": "tool_result",
                        "agent_id": "browser_subagent",
                        "tool": "finish",
                        "call_id": call_id,
                        "ok": True,
                        "duration_ms": 0,
                        "truncated": fin_trunc,
                        "output": capped_fin,
                    })
                    continue

                tool_t0 = time.time()
                mem_out = _handle_memory_tool(t_name, t_args, memory_state)
                if mem_out is not None:
                    executed_names.append(t_name)
                    print(f"[Browser Subagent Step {step + 1}] Memory tool: {t_name}")
                    state.emit_event({
                        "event": "tool_call",
                        "agent_id": "browser_subagent",
                        "tool": t_name,
                        "args": t_args,
                        "call_id": call_id,
                    })
                    capped_mem, mem_trunc = event_bus.cap(str(mem_out))
                    state.emit_event({
                        "event": "tool_result",
                        "agent_id": "browser_subagent",
                        "tool": t_name,
                        "call_id": call_id,
                        "ok": True,
                        "duration_ms": round((time.time() - tool_t0) * 1000),
                        "truncated": mem_trunc,
                        "output": capped_mem,
                    })
                    memory_state["action_log"].append({
                        "step": step + 1,
                        "tool": t_name,
                        "args": t_args,
                        "target": "",
                        "url": memory_state["last_url"],
                        "note": "",
                    })
                    execution_results.append(f"[Tool: {t_name}] Result:\n{mem_out}")
                    continue

                if finished:
                    continue

                func = getattr(browser_actions, t_name, None)
                if func:
                    executed_names.append(t_name)
                    target_label = _resolve_element_label(memory_state.get("last_dom_elements", ""), t_args.get("element_id"))
                    print(f"[Browser Subagent Step {step + 1}] Executing: {t_name}({t_args})")
                    state.emit_event({"event": "state", "agent_id": "browser_subagent", "status": f"Browser: {t_name}"})
                    state.emit_event({
                        "event": "tool_call",
                        "agent_id": "browser_subagent",
                        "tool": t_name,
                        "args": t_args,
                        "call_id": call_id,
                    })
                    out = _call_browser_action(func, t_args)
                    tool_dur = round((time.time() - tool_t0) * 1000)
                    step_title, step_url = _record_visited_page(out, memory_state)
                    state.emit_event({
                        "event": "browser_page",
                        "agent_id": "browser_subagent",
                        "url": step_url or memory_state["last_url"],
                        "title": step_title or memory_state["last_title"],
                        "action": t_name,
                    })
                    _record_dom_snapshot(memory_state, step + 1, t_name, step_title, step_url, out)
                    err_note = _extract_action_error_note(out)
                    memory_state["action_log"].append({
                        "step": step + 1,
                        "tool": t_name,
                        "args": t_args,
                        "target": target_label,
                        "url": step_url or memory_state["last_url"],
                        "note": err_note,
                    })
                    capped_out, out_trunc = event_bus.cap(out.strip())
                    ok = not err_note and not out.lstrip().startswith(("Error:", "Tool execution failed"))
                    state.emit_event({
                        "event": "tool_result",
                        "agent_id": "browser_subagent",
                        "tool": t_name,
                        "call_id": call_id,
                        "ok": ok,
                        "duration_ms": tool_dur,
                        "truncated": out_trunc,
                        "output": capped_out,
                    })
                    execution_results.append(f"[Tool: {t_name}] Result:\n{out}")
                else:
                    err_msg = f"Error: Tool '{t_name}' not found."
                    state.emit_event({
                        "event": "tool_call",
                        "agent_id": "browser_subagent",
                        "tool": t_name,
                        "args": t_args,
                        "call_id": call_id,
                    })
                    memory_state["action_log"].append({
                        "step": step + 1,
                        "tool": t_name,
                        "args": t_args,
                        "target": "",
                        "url": memory_state["last_url"],
                        "note": err_msg,
                    })
                    state.emit_event({
                        "event": "tool_result",
                        "agent_id": "browser_subagent",
                        "tool": t_name,
                        "call_id": call_id,
                        "ok": False,
                        "duration_ms": 0,
                        "truncated": False,
                        "output": err_msg,
                    })
                    execution_results.append(err_msg)

            _emit_browser_step_end(res)
            if finished:
                print(f"[Browser Subagent] Finished: {final_result}")
                return _build_final_handoff(final_result, memory_state)

            step_records.append({
                "step": step + 1,
                "action": ", ".join(executed_names) or "unknown",
                "url": memory_state["last_url"],
                "title": memory_state["last_title"],
                "model_text": ai_text,
                "raw_output": "\n".join(execution_results),
            })

        return _build_final_handoff(
            f"Browser Agent reached the {MAX_BROWSER_STEPS}-step limit before calling finish.",
            memory_state,
        )
    finally:
        event_bus.pop_agent()
        try:
            browser_actions.set_agent_active(False)
        except Exception:
            pass

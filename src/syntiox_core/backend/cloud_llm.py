import os
import glob
import time
import datetime
import base64
import json
import re
import httpx
from backend import state
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from backend.config_paths import ENV_FILE, SCRATCH_DIR

load_dotenv(ENV_FILE)

# --- Key Rotation Setup ---
raw_keys = os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

if not API_KEYS:
    print("\033[91m[Syntiox CORE] WARNING: No GEMINI_API_KEY found in .env.\033[0m")
else:
    print(f"\033[92m[Syntiox CORE] Loaded {len(API_KEYS)} Gemini API Key(s) for rotation.\033[0m")

current_key_idx = 0
INVALID_API_KEYS = set()
BUSY_RETRY_DELAYS = [5, 10, 15, 15, 15, 15, 15]

# Read model from .env, fallback to gemini-3.5-flash-lite if not set
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-3.5-flash-lite")
THINKING_LEVEL = os.getenv("THINKING_LEVEL", "MEDIUM").strip().upper()
print(f"\033[92m[Syntiox CORE] Google Model: {GOOGLE_MODEL} (Thinking: {THINKING_LEVEL})\033[0m")

try:
    from groq import (
        Groq,
        APIConnectionError as GroqConnectionError,
        APITimeoutError as GroqTimeoutError,
        APIStatusError as GroqStatusError,
        AuthenticationError as GroqAuthError,
        PermissionDeniedError as GroqPermissionError,
        NotFoundError as GroqNotFoundError,
        BadRequestError as GroqBadRequestError,
        UnprocessableEntityError as GroqUnprocessableError,
        RateLimitError as GroqRateLimitError,
        InternalServerError as GroqServerError,
    )
except ImportError:
    Groq = None
    GroqConnectionError = GroqTimeoutError = GroqStatusError = ()
    GroqAuthError = GroqPermissionError = GroqNotFoundError = GroqBadRequestError = ()
    GroqUnprocessableError = GroqRateLimitError = GroqServerError = ()

# Groq key rotation setup
raw_groq_keys = os.getenv("GROQ_API_KEY", "")
GROQ_API_KEYS = [k.strip() for k in raw_groq_keys.split(",") if k.strip()]
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
current_groq_key_idx = 0
INVALID_GROQ_KEYS = set()

if GROQ_API_KEYS:
    print(f"\033[92m[Syntiox CORE] Loaded {len(GROQ_API_KEYS)} Groq API Key(s) for fast routing/summary.\033[0m")
    print(f"\033[92m[Syntiox CORE] Groq Model: {GROQ_MODEL}\033[0m")

BROWSER_MODEL = os.getenv("BROWSER_MODEL", "qwen/qwen3.8-27b" if GROQ_API_KEYS else GOOGLE_MODEL)
if GROQ_API_KEYS or API_KEYS:
    print(f"\033[92m[Syntiox CORE] Browser Model: {BROWSER_MODEL}\033[0m")

def get_valid_groq_keys():
    return [k for k in GROQ_API_KEYS if k not in INVALID_GROQ_KEYS]

def mark_current_groq_key_invalid():
    global current_groq_key_idx
    if GROQ_API_KEYS and 0 <= current_groq_key_idx < len(GROQ_API_KEYS):
        bad_key = GROQ_API_KEYS[current_groq_key_idx]
        if bad_key not in INVALID_GROQ_KEYS:
            INVALID_GROQ_KEYS.add(bad_key)
            print(f"\033[91m[System] Groq API Key #{current_groq_key_idx + 1} is invalid. Saved in RAM and skipping permanently.\033[0m")

def get_groq_client():
    global current_groq_key_idx
    if not GROQ_API_KEYS or Groq is None:
        return None
    if not get_valid_groq_keys():
        raise Exception("All configured Groq API keys are invalid.")
    for _ in range(len(GROQ_API_KEYS)):
        if GROQ_API_KEYS[current_groq_key_idx] not in INVALID_GROQ_KEYS:
            break
        current_groq_key_idx = (current_groq_key_idx + 1) % len(GROQ_API_KEYS)
    return Groq(api_key=GROQ_API_KEYS[current_groq_key_idx], max_retries=0)

def rotate_groq_key():
    global current_groq_key_idx
    if GROQ_API_KEYS:
        if not get_valid_groq_keys():
            return
        for _ in range(len(GROQ_API_KEYS)):
            current_groq_key_idx = (current_groq_key_idx + 1) % len(GROQ_API_KEYS)
            if GROQ_API_KEYS[current_groq_key_idx] not in INVALID_GROQ_KEYS:
                print(f"\033[93m[System] Rotated to Groq API Key #{current_groq_key_idx + 1}.\033[0m")
                break

def is_groq_invalid_key_error(err) -> bool:
    if GroqAuthError and isinstance(err, (GroqAuthError, GroqPermissionError)):
        return True
    if GroqStatusError and isinstance(err, GroqStatusError):
        if getattr(err, "status_code", None) in (401, 403):
            return True
    err_str = str(err).lower()
    return any(k in err_str for k in (
        "invalid_api_key",
        "invalid api key",
        "api key not valid",
        "expired_api_key",
    ))

def is_groq_quota_error(err) -> bool:
    if GroqRateLimitError and isinstance(err, GroqRateLimitError):
        return True
    if GroqStatusError and isinstance(err, GroqStatusError):
        if getattr(err, "status_code", None) in (429, 498):
            return True
    err_str = str(err).lower()
    return any(k in err_str for k in ("rate_limit", "429", "too many requests", "quota", "capacity exceeded"))

def is_groq_server_busy_error(err) -> bool:
    if GroqServerError and isinstance(err, (GroqServerError, GroqConnectionError, GroqTimeoutError)):
        return True
    if GroqStatusError and isinstance(err, GroqStatusError):
        code = getattr(err, "status_code", 0) or 0
        if code >= 500 or code == 408:
            return True
    if isinstance(err, (httpx.HTTPError, ConnectionError, TimeoutError)):
        return True
    # Rate limit messages carry token counts like "Limit 500000", so check quota first
    if is_groq_quota_error(err):
        return False
    err_str = str(err).lower()
    if re.search(r"\b(500|502|503|504)\b", err_str):
        return True
    return any(k in err_str for k in ("overloaded", "service unavailable", "bad gateway", "gateway timeout", "timed out"))

def _extract_groq_retry_after(err):
    resp = getattr(err, "response", None)
    headers = getattr(resp, "headers", None) if resp is not None else None
    if headers:
        try:
            ms_hdr = headers.get("retry-after-ms")
            if ms_hdr is not None:
                return float(ms_hdr) / 1000.0
        except (TypeError, ValueError):
            pass
        try:
            sec_hdr = headers.get("retry-after")
            if sec_hdr is not None:
                return float(sec_hdr)
        except (TypeError, ValueError):
            pass
    m = re.search(r"try again in\s+([0-9.]+)s", str(err), flags=re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except (TypeError, ValueError):
            pass
    return None

def is_groq_non_retryable_error(err) -> bool:
    if GroqBadRequestError and isinstance(err, (GroqBadRequestError, GroqNotFoundError, GroqUnprocessableError)):
        return not is_groq_invalid_key_error(err)
    if GroqStatusError and isinstance(err, GroqStatusError):
        if getattr(err, "status_code", None) in (400, 404, 413, 422):
            return not is_groq_invalid_key_error(err)
    return False

def safe_groq_chat(prompt: str, system_prompt: str = None, json_mode: bool = False, max_tokens: int = None) -> str:
    if not GROQ_API_KEYS or Groq is None or not get_valid_groq_keys():
        return None

    quota_attempts = 0
    while True:
        try:
            client = get_groq_client()
            if not client:
                return None

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            kwargs = {
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.1
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except Exception as e:
            if is_groq_invalid_key_error(e):
                mark_current_groq_key_invalid()
                if not get_valid_groq_keys():
                    return None
                rotate_groq_key()
                continue
            if is_groq_non_retryable_error(e):
                return None
            if is_groq_quota_error(e) or is_groq_server_busy_error(e):
                quota_attempts += 1
                valid_count = len(get_valid_groq_keys())
                if quota_attempts >= max(1, valid_count):
                    return None
                rotate_groq_key()
                time.sleep(0.3)
                continue
            return None

def is_groq_model(model_name: str) -> bool:
    if not model_name:
        return False
    m = model_name.lower().strip()
    if m.startswith("groq/") or m.startswith("groq:"):
        return True
    if m.startswith("google/") or m.startswith("google:") or m.startswith("gemini") or m.startswith("gemma"):
        return False
    if any(m.startswith(p) for p in (
        "qwen/", "openai/", "meta-llama/", "allam-", "canopylabs/",
        "llama-", "llama3", "mixtral", "whisper", "deepseek",
        "moonshotai/", "compound-", "playai-"
    )):
        return True
    return False

def _convert_tools_for_groq(tools) -> list:
    if not tools:
        return []
    groq_tools = []
    for t in tools:
        if isinstance(t, dict):
            if "function" in t:
                groq_tools.append({"type": "function", "function": t["function"]})
            elif "name" in t:
                groq_tools.append({"type": "function", "function": t})
        elif hasattr(t, "function_declarations") and t.function_declarations:
            for fd in t.function_declarations:
                fn_def = {
                    "name": getattr(fd, "name", ""),
                    "description": getattr(fd, "description", "") or "",
                }
                params = getattr(fd, "parameters", None)
                if params:
                    if isinstance(params, dict):
                        fn_def["parameters"] = params
                    elif hasattr(params, "model_dump"):
                        fn_def["parameters"] = params.model_dump(exclude_none=True)
                groq_tools.append({"type": "function", "function": fn_def})
    return groq_tools

def _build_native_call_parts_from_groq(tool_calls) -> list:
    parts = []
    if not tool_calls:
        return parts
    for tc in tool_calls:
        fn = getattr(tc, "function", None) or (tc.get("function") if isinstance(tc, dict) else None)
        if not fn:
            continue
        name = getattr(fn, "name", None) if not isinstance(fn, dict) else fn.get("name")
        raw_args = getattr(fn, "arguments", "{}") if not isinstance(fn, dict) else fn.get("arguments", "{}")
        if isinstance(raw_args, dict):
            args_dict = raw_args
        else:
            try:
                args_dict = json.loads(raw_args) if raw_args else {}
            except Exception:
                args_dict = {}
        if name:
            try:
                parts.append(types.Part(function_call=types.FunctionCall(name=name, args=args_dict)))
            except Exception:
                pass
    return parts

def safe_generate_groq(prompt_or_contents, image_base64=None, stream_callback=None, sys_prompt=None, tools=None, response_schema=None, response_mime_type=None, max_output_tokens=None, retry_on_busy=True, model=None, target_model=None, reasoning_effort=None, max_busy_retries=None, quota_wait_max_seconds=25):
    """
    Synchronous Groq generation wrapper with invalid key tracking, rate-limit key rotation,
    server busy backoff, and optional streaming/tool support.
    """
    if not GROQ_API_KEYS or Groq is None:
        raise Exception("Groq API keys not configured or groq package not installed.")

    resolved_model = (model or target_model or GROQ_MODEL).strip()
    clean_model = resolved_model
    if clean_model.lower().startswith("groq/"):
        clean_model = clean_model[5:]
    elif clean_model.lower().startswith("groq:"):
        clean_model = clean_model[5:]

    messages = []
    if sys_prompt:
        messages.append({"role": "system", "content": sys_prompt})

    if isinstance(prompt_or_contents, str):
        if image_base64:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_or_contents},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]
            })
        else:
            messages.append({"role": "user", "content": prompt_or_contents})
    elif isinstance(prompt_or_contents, list):
        for item in prompt_or_contents:
            if isinstance(item, dict):
                r = item.get("role", "user")
                role = "assistant" if r in ("model", "assistant") else ("system" if r == "system" else "user")
                c = item.get("content", "")
                img_b64 = item.get("image_base64")
                if img_b64 and role == "user" and isinstance(c, str):
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": c},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                        ]
                    })
                else:
                    messages.append({"role": role, "content": c})
            elif hasattr(item, "role") and hasattr(item, "parts"):
                role = "assistant" if getattr(item, "role", "") == "model" else "user"
                text_parts = []
                image_parts = []
                for p in item.parts:
                    if hasattr(p, "text") and p.text:
                        text_parts.append(p.text)
                    elif hasattr(p, "function_call") and getattr(p, "function_call", None):
                        fc = p.function_call
                        fc_args = dict(fc.args) if getattr(fc, "args", None) else {}
                        text_parts.append(f"[Called tool {fc.name} with args: {json.dumps(fc_args)}]")
                    elif hasattr(p, "function_response") and getattr(p, "function_response", None):
                        fr = p.function_response
                        fr_res = dict(fr.response) if getattr(fr, "response", None) else {}
                        text_parts.append(f"[Tool {fr.name} result]: {fr_res.get('result', fr_res)}")
                    elif hasattr(p, "inline_data") and getattr(p.inline_data, "data", None):
                        raw_data = p.inline_data.data
                        mime = getattr(p.inline_data, "mime_type", "image/png")
                        if isinstance(raw_data, bytes):
                            b64_img = base64.b64encode(raw_data).decode("utf-8")
                        else:
                            b64_img = str(raw_data)
                        image_parts.append(f"data:{mime};base64,{b64_img}")

                combined_text = "\n".join(text_parts)
                if image_parts and role == "user":
                    content_arr = [{"type": "text", "text": combined_text}] if combined_text else []
                    for img_url in image_parts:
                        content_arr.append({"type": "image_url", "image_url": {"url": img_url}})
                    messages.append({"role": role, "content": content_arr})
                elif combined_text:
                    messages.append({"role": role, "content": combined_text})

    groq_tools = _convert_tools_for_groq(tools)
    last_error = None
    busy_retries = 0
    effective_max_busy = len(BUSY_RETRY_DELAYS) if max_busy_retries is None else max(0, int(max_busy_retries))
    quota_attempts = 0
    quota_wait_retries = 0
    restored_state = False

    while True:
        try:
            client = get_groq_client()
            if not client:
                raise Exception("Unable to initialize Groq client.")

            kwargs = {
                "model": clean_model,
                "messages": messages,
                "temperature": 0.2
            }
            if reasoning_effort and clean_model.lower().startswith("qwen/"):
                kwargs["reasoning_effort"] = reasoning_effort
            if max_output_tokens:
                kwargs["max_tokens"] = max_output_tokens
            if groq_tools:
                kwargs["tools"] = groq_tools
                kwargs["tool_choice"] = "auto"
            elif response_mime_type == "application/json":
                kwargs["response_format"] = {"type": "json_object"}

            if stream_callback:
                stream = client.chat.completions.create(stream=True, **kwargs)
                full_text = ""
                streamed_tool_calls = {}
                raw_response = None
                for chunk in stream:
                    raw_response = chunk
                    if (busy_retries > 0 or quota_wait_retries > 0) and not restored_state:
                        state.set_ui_state("Thinking")
                        restored_state = True
                    if getattr(state, "STOP_REQUESTED", False):
                        full_text += "\n\n[System: Generation stopped by user]\n<task_complete />"
                        break
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            full_text += delta.content
                            stream_callback(delta.content)
                        if getattr(delta, "tool_calls", None):
                            for tc_delta in delta.tool_calls:
                                idx = getattr(tc_delta, "index", 0)
                                if idx not in streamed_tool_calls:
                                    streamed_tool_calls[idx] = {"function": {"name": "", "arguments": ""}}
                                if getattr(tc_delta, "function", None):
                                    if tc_delta.function.name:
                                        streamed_tool_calls[idx]["function"]["name"] += tc_delta.function.name
                                    if tc_delta.function.arguments:
                                        streamed_tool_calls[idx]["function"]["arguments"] += tc_delta.function.arguments

                native_parts = _build_native_call_parts_from_groq(list(streamed_tool_calls.values()))
                return {"content": full_text, "native_function_call_parts": native_parts, "raw_response": raw_response}
            else:
                resp = client.chat.completions.create(**kwargs)
                if (busy_retries > 0 or quota_wait_retries > 0) and not restored_state:
                    state.set_ui_state("Thinking")
                    restored_state = True
                msg = resp.choices[0].message if resp.choices else None
                text = (msg.content or "") if msg else ""
                native_parts = _build_native_call_parts_from_groq(getattr(msg, "tool_calls", None)) if msg else []
                return {"content": text, "native_function_call_parts": native_parts, "raw_response": resp}

        except Exception as e:
            last_error = e

            if is_groq_invalid_key_error(e):
                mark_current_groq_key_invalid()
                if not get_valid_groq_keys():
                    raise Exception("All configured Groq API keys are invalid.")
                rotate_groq_key()
                continue

            if is_groq_non_retryable_error(e):
                print(f"\033[91m[Groq API Error - Non Retryable] {e}\033[0m")
                raise e

            if is_groq_server_busy_error(e):
                if not retry_on_busy or effective_max_busy <= 0:
                    raise e
                busy_retries += 1
                if busy_retries > effective_max_busy:
                    state.set_ui_state("Server Very Busy")
                    raise Exception(f"Groq server is very busy right now (Unavailable after {effective_max_busy}/{effective_max_busy} retries). Last error: {last_error}")

                err_reason = str(e).splitlines()[0][:140]
                print(f"\n\033[93m[Syntiox CORE] Groq busy ({type(e).__name__}: {err_reason})\033[0m")

                wait_seconds = BUSY_RETRY_DELAYS[min(busy_retries - 1, len(BUSY_RETRY_DELAYS) - 1)]
                rotate_groq_key()
                quota_attempts = 0

                for remaining in range(wait_seconds, 0, -1):
                    if getattr(state, "STOP_REQUESTED", False):
                        raise Exception("Generation stopped by user.")
                    status_text = f"Groq Unavailable - Retrying in {remaining}s ({busy_retries}/{effective_max_busy})"
                    state.set_ui_state(status_text)
                    print(f"\r\033[93m[Syntiox CORE] {status_text}   \033[0m", end="", flush=True)
                    time.sleep(1)
                print()
                state.set_ui_state(f"Groq Unavailable - Retrying now ({busy_retries}/{effective_max_busy})")
                continue

            if is_groq_quota_error(e):
                quota_attempts += 1
                valid_count = len(get_valid_groq_keys())
                if quota_attempts >= max(1, valid_count):
                    wait_s = _extract_groq_retry_after(e)
                    if quota_wait_max_seconds > 0 and quota_wait_retries < 2 and wait_s is not None and 0 <= wait_s <= quota_wait_max_seconds:
                        sleep_s = min(max(1, int(round(wait_s + 1.0))), int(quota_wait_max_seconds))
                        for remaining in range(sleep_s, 0, -1):
                            if getattr(state, "STOP_REQUESTED", False):
                                raise Exception("Generation stopped by user.")
                            status_text = f"Groq Rate Limit - Retrying in {remaining}s"
                            state.set_ui_state(status_text)
                            print(f"\r\033[93m[Syntiox CORE] {status_text}   \033[0m", end="", flush=True)
                            time.sleep(1)
                        print()
                        quota_wait_retries += 1
                        quota_attempts = 0
                        rotate_groq_key()
                        continue
                    raise Exception(f"All {valid_count} valid Groq API keys failed due to quota/rate limits. Last error: {last_error}")
                rotate_groq_key()
                time.sleep(0.5)
                continue

            print(f"\033[91m[Groq API Error - Non Retryable] {e}\033[0m")
            raise e


def get_valid_keys():
    return [k for k in API_KEYS if k not in INVALID_API_KEYS]

def mark_current_key_invalid():
    global current_key_idx
    if API_KEYS and 0 <= current_key_idx < len(API_KEYS):
        bad_key = API_KEYS[current_key_idx]
        if bad_key not in INVALID_API_KEYS:
            INVALID_API_KEYS.add(bad_key)
            print(f"\033[91m[System] API Key #{current_key_idx + 1} is invalid (API_KEY_INVALID). Saved in RAM and skipping permanently.\033[0m")

def get_current_client():
    global current_key_idx
    if API_KEYS:
        if not get_valid_keys():
            raise Exception("All configured Gemini API keys are invalid (API_KEY_INVALID).")
        for _ in range(len(API_KEYS)):
            if API_KEYS[current_key_idx] not in INVALID_API_KEYS:
                break
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
        return genai.Client(api_key=API_KEYS[current_key_idx])
    return genai.Client()

def rotate_key():
    global current_key_idx
    if API_KEYS:
        if not get_valid_keys():
            return
        for _ in range(len(API_KEYS)):
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
            if API_KEYS[current_key_idx] not in INVALID_API_KEYS:
                print(f"\033[93m[System] Rotated to API Key #{current_key_idx + 1}.\033[0m")
                break

def is_invalid_key_error(err) -> bool:
    if isinstance(err, genai_errors.APIError):
        code = getattr(err, "code", None)
        status = str(getattr(err, "status", "") or "").upper()
        msg = str(getattr(err, "message", "") or str(err)).lower()
        if code in (401, 403) or status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
            return True
        if code == 400 and any(k in msg for k in (
            "api_key_invalid",
            "api key not valid",
            "api_key_not_valid",
            "invalid api key",
            "api_key_expired",
        )):
            return True
        return False

    error_str = str(err).lower()
    return any(k in error_str for k in (
        "api_key_invalid",
        "api key not valid",
        "api_key_not_valid",
        "invalid api key",
        "api_key_expired",
        "unauthenticated",
        "permission_denied",
    ))

def is_server_busy_error(err) -> bool:
    if isinstance(err, genai_errors.ServerError):
        return True
    if isinstance(err, genai_errors.APIError):
        code = getattr(err, "code", None)
        status = str(getattr(err, "status", "") or "").upper()
        if code in (408, 499, 500, 502, 503, 504) or status in ("UNAVAILABLE", "INTERNAL", "DEADLINE_EXCEEDED"):
            return True
        return False
    if isinstance(err, (httpx.HTTPError, ConnectionError, TimeoutError)):
        return True

    error_str = str(err).lower()
    return any(k in error_str for k in (
        "503",
        "unavailable",
        "overloaded",
        "high demand",
        "service_unavailable",
        "temporarily unavailable",
        "server is busy",
        "500",
        "internal error",
        "502",
        "bad gateway",
        "504",
        "deadline_exceeded",
        "gateway timeout",
        "disconnected",
        "eof",
    ))

def is_quota_error(err) -> bool:
    if isinstance(err, genai_errors.APIError):
        code = getattr(err, "code", None)
        status = str(getattr(err, "status", "") or "").upper()
        msg = str(getattr(err, "message", "") or str(err)).lower()
        if code == 429 or status == "RESOURCE_EXHAUSTED":
            return True
        if code not in (400, 401, 403, 404) and any(k in msg for k in ("resource_exhausted", "quota", "rate_limit", "too many requests")):
            return True
        return False

    error_str = str(err).lower()
    return any(k in error_str for k in (
        "429",
        "resource_exhausted",
        "quota",
        "exhausted",
        "too many requests",
        "rate_limit",
    ))

def is_missing_thought_signature_error(err) -> bool:
    error_str = str(err).lower()
    return "thought_signature" in error_str or "missing_thought_signature" in error_str

def _sanitize_unsigned_function_calls(contents: list) -> tuple[list, bool]:
    """Converts model turns whose function_call parts lack thought_signatures (and matching responses) to text."""
    changed = False
    sanitized = list(contents)
    i = 0
    while i < len(sanitized):
        item = sanitized[i]
        if getattr(item, "role", None) == "model" and getattr(item, "parts", None):
            fc_parts = [p for p in item.parts if getattr(p, "function_call", None)]
            if fc_parts and not any(getattr(p, "thought_signature", None) for p in fc_parts):
                changed = True
                new_model_parts = []
                for p in item.parts:
                    fc = getattr(p, "function_call", None)
                    if fc:
                        fc_args = dict(fc.args) if getattr(fc, "args", None) else {}
                        new_model_parts.append(types.Part.from_text(
                            text=f"[Called tool {fc.name} with args: {json.dumps(fc_args, ensure_ascii=False)}]"
                        ))
                    else:
                        new_model_parts.append(p)
                sanitized[i] = types.Content(role="model", parts=new_model_parts)

                if i + 1 < len(sanitized) and getattr(sanitized[i + 1], "role", None) == "user" and getattr(sanitized[i + 1], "parts", None):
                    new_user_parts = []
                    for p in sanitized[i + 1].parts:
                        fr = getattr(p, "function_response", None)
                        if fr:
                            fr_res = dict(fr.response) if getattr(fr, "response", None) else {}
                            new_user_parts.append(types.Part.from_text(
                                text=f"[Tool {fr.name} result]: {fr_res.get('result', fr_res)}"
                            ))
                        else:
                            new_user_parts.append(p)
                    sanitized[i + 1] = types.Content(role="user", parts=new_user_parts)
        i += 1
    return sanitized, changed

def _extract_text_call_spans(content: str) -> list:
    """Finds <call:...> tool invocations with balanced braces."""
    spans = []
    header_re = re.compile(r'<call:(?:[a-zA-Z0-9_]+:)?([a-zA-Z0-9_]+)\{')
    pos = 0
    while pos < len(content):
        m = header_re.search(content, pos)
        if not m:
            break
        name = m.group(1)
        brace_start = m.end() - 1
        depth = 0
        in_quote = None
        escaped = False
        end_idx = None
        idx = brace_start
        while idx < len(content):
            ch = content[idx]
            if escaped:
                escaped = False
            elif ch == '\\' and in_quote:
                escaped = True
            elif in_quote:
                if ch == in_quote:
                    in_quote = None
            elif ch in ('"', "'"):
                in_quote = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end_idx = idx + 1
                    if end_idx < len(content) and content[end_idx] == '>':
                        end_idx += 1
                    break
            idx += 1
        if end_idx is None:
            pos = m.end()
            continue
        raw_args = content[brace_start + 1:idx]
        spans.append((m.start(), end_idx, name, raw_args))
        pos = end_idx
    return spans

def _split_top_level_kv(raw_args: str) -> list[str]:
    parts = []
    buf = []
    depth = 0
    in_quote = None
    escaped = False
    for ch in raw_args:
        if escaped:
            buf.append(ch)
            escaped = False
        elif ch == '\\' and in_quote:
            buf.append(ch)
            escaped = True
        elif in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
            buf.append(ch)
        elif ch in ('{', '['):
            depth += 1
            buf.append(ch)
        elif ch in ('}', ']'):
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == ',' and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts

def _coerce_unquoted_scalar(val: str):
    stripped = val.strip()
    if len(stripped) >= 2 and ((stripped[0] == '"' and stripped[-1] == '"') or (stripped[0] == "'" and stripped[-1] == "'")):
        return stripped[1:-1]
    low = stripped.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "none"):
        return None
    if re.fullmatch(r'-?\d+', stripped):
        try:
            return int(stripped)
        except Exception:
            pass
    if re.fullmatch(r'-?\d+\.\d+', stripped):
        try:
            return float(stripped)
        except Exception:
            pass
    return stripped

def parse_text_tool_calls(content: str) -> list:
    if not content or "<call:" not in content:
        return []
    calls = []
    for _, _, name, raw_args in _extract_text_call_spans(content):
        args_dict = {}
        try:
            args_dict = json.loads('{' + raw_args + '}')
        except Exception:
            for pair in _split_top_level_kv(raw_args):
                if ':' in pair:
                    k, v = pair.split(':', 1)
                    args_dict[k.strip().strip('"\'')] = _coerce_unquoted_scalar(v)
        calls.append({
            "type": "function",
            "function": {
                "name": name,
                "arguments": args_dict,
            },
            "thought_signature": None,
            "is_text_call": True,
        })
    return calls

def strip_text_tool_calls(content: str) -> str:
    if not content or "<call:" not in content:
        return content
    spans = _extract_text_call_spans(content)
    if not spans:
        return content
    out = []
    last = 0
    for start, end, _, _ in spans:
        out.append(content[last:start])
        last = end
    out.append(content[last:])
    return "".join(out).strip()

def build_tool_turn_contents(
    thought_text: str,
    tool_calls: list,
    default_result: str = "No result.",
    result_char_limit: int = 12000,
    target_model: str = None,
) -> tuple[types.Content, types.Content]:
    """Builds paired model/user Content objects for a tool step, ensuring FC/FR parity and thought_signature safety."""
    resolved_model = (target_model or GOOGLE_MODEL).strip()
    model_parts = []
    has_text_call = any(tc.get("is_text_call") for tc in tool_calls)
    if has_text_call and thought_text:
        thought_text = strip_text_tool_calls(thought_text)
    if thought_text and thought_text.strip():
        model_parts.append(types.Part.from_text(text=thought_text))

    sys_calls = [tc for tc in tool_calls if tc["function"]["name"] in ("system_recovery", "system_continue")]
    non_sys_calls = [tc for tc in tool_calls if tc["function"]["name"] not in ("system_recovery", "system_continue")]

    for tc in sys_calls:
        model_parts.append(types.Part.from_text(text=f"[Internal System Task]: {tc['function']['name']}"))

    has_any_sig = any(tc.get("thought_signature") for tc in non_sys_calls)
    use_native_fc = bool(non_sys_calls) and not has_text_call and (is_groq_model(resolved_model) or has_any_sig)

    fc_parts = []
    fr_parts = []
    if use_native_fc:
        try:
            for tc in non_sys_calls:
                fn_name = tc["function"]["name"]
                fn_args = tc["function"]["arguments"]
                call_id = tc.get("call_id")
                res_text = str(tc.get("result", default_result))[:result_char_limit]
                fc_kwargs = {"name": fn_name, "args": fn_args}
                fr_kwargs = {"name": fn_name, "response": {"result": res_text}}
                if call_id:
                    fc_kwargs["id"] = call_id
                    fr_kwargs["id"] = call_id
                p = types.Part(function_call=types.FunctionCall(**fc_kwargs))
                if tc.get("thought_signature"):
                    p.thought_signature = tc["thought_signature"]
                fc_parts.append(p)
                fr_parts.append(types.Part(function_response=types.FunctionResponse(**fr_kwargs)))
        except Exception:
            fc_parts = []
            fr_parts = []
            use_native_fc = False

    if use_native_fc and fc_parts:
        model_parts.extend(fc_parts)
    else:
        for tc in non_sys_calls:
            fn_name = tc["function"]["name"]
            fn_args = tc["function"]["arguments"]
            model_parts.append(types.Part.from_text(
                text=f"[Called tool {fn_name} with args: {json.dumps(fn_args, ensure_ascii=False)}]"
            ))

    if not model_parts:
        model_parts.append(types.Part.from_text(text="Executing tool."))

    response_parts = []
    for tc in sys_calls:
        res_text = str(tc.get("result", default_result))[:4000]
        response_parts.append(types.Part.from_text(text=f"[SYSTEM NOTIFICATION]: {res_text}"))

    if use_native_fc and fr_parts:
        response_parts.extend(fr_parts)
    else:
        for tc in non_sys_calls:
            fn_name = tc["function"]["name"]
            res_text = str(tc.get("result", default_result))[:result_char_limit]
            response_parts.append(types.Part.from_text(text=f"[Tool {fn_name} result]: {res_text}"))

    model_content = types.Content(role="model", parts=model_parts)
    user_content = types.Content(role="user", parts=response_parts) if response_parts else None
    return model_content, user_content

def _resolve_thinking_config(model_name: str, thinking_level: str = None, include_thoughts: bool = True):
    """Builds types.ThinkingConfig for thinking-capable Gemini models when enabled."""
    if not thinking_level:
        return None
    level_str = str(thinking_level).strip().upper()
    if level_str in ("", "NONE", "OFF", "DISABLED", "FALSE"):
        return None
    m_low = (model_name or "").lower()
    if "gemini" not in m_low or "gemma" in m_low or "gemini-1." in m_low or "gemini-2.0" in m_low:
        return None
    if "gemini-4" in m_low and level_str == "MINIMAL":
        level_str = "LOW"
    level_enum = getattr(types.ThinkingLevel, level_str, types.ThinkingLevel.MEDIUM)
    if "gemini-2.5" in m_low:
        return types.ThinkingConfig(include_thoughts=bool(include_thoughts))
    return types.ThinkingConfig(thinking_level=level_enum, include_thoughts=bool(include_thoughts))


def _collect_response_parts(candidates, function_calls: list, function_call_parts: list) -> tuple[str, str]:
    """Extracts (thought_text, answer_text) from candidate parts while preserving FC parts and signatures."""
    if not candidates:
        return "", ""
    thought_chunks = []
    answer_chunks = []
    for idx, cand in enumerate(candidates):
        if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
            for p in cand.content.parts:
                if getattr(p, "function_call", None):
                    function_calls.append(p.function_call)
                    function_call_parts.append(p)
                elif getattr(p, "thought_signature", None) and function_call_parts:
                    if not getattr(function_call_parts[-1], "thought_signature", None):
                        try:
                            function_call_parts[-1].thought_signature = p.thought_signature
                        except Exception:
                            pass
                if idx == 0 and isinstance(getattr(p, "text", None), str):
                    if isinstance(getattr(p, "thought", None), bool) and p.thought:
                        thought_chunks.append(p.text)
                    else:
                        answer_chunks.append(p.text)
    return "".join(thought_chunks), "".join(answer_chunks)


def safe_generate_content_gemini(
    prompt_or_contents,
    image_base64=None,
    stream_callback=None,
    sys_prompt=None,
    tools=None,
    response_schema=None,
    response_mime_type=None,
    max_output_tokens=None,
    retry_on_busy=True,
    model=None,
    thought_callback=None,
    thinking_level=None,
    include_thoughts=True,
):
    """
    Synchronous Google Gemini wrapper with official SDK error handling,
    invalid key RAM tracking, 429 key rotation, and 5xx/network backoff retries.
    """
    target_model = (model or GOOGLE_MODEL).strip()
    clean_google_model = target_model
    if clean_google_model.lower().startswith("google/"):
        clean_google_model = clean_google_model[7:]
    elif clean_google_model.lower().startswith("google:"):
        clean_google_model = clean_google_model[7:]

    last_error = None
    busy_retries = 0
    max_busy_retries = len(BUSY_RETRY_DELAYS)
    quota_attempts = 0
    sanitized_retried = False
    override_contents = None
    
    while True:
        try:
            client = get_current_client()
            
            contents = []
            if override_contents is not None:
                contents = override_contents
            elif isinstance(prompt_or_contents, str):
                parts = []
                if image_base64:
                    try:
                        img_data = base64.b64decode(image_base64)
                        parts.append(types.Part.from_bytes(data=img_data, mime_type='image/png'))
                    except Exception as e:
                        print(f"\033[91m[Syntiox CORE] Failed to parse image base64: {e}\033[0m")
                parts.append(types.Part.from_text(text=prompt_or_contents))
                contents.append(types.Content(role="user", parts=parts))
            else:
                contents = prompt_or_contents
            
            config = types.GenerateContentConfig()
            thinking_cfg = _resolve_thinking_config(
                clean_google_model,
                thinking_level=thinking_level,
                include_thoughts=include_thoughts,
            )
            if thinking_cfg is not None:
                config.thinking_config = thinking_cfg
            else:
                config.temperature = 0.2
            if sys_prompt:
                config.system_instruction = sys_prompt
            if tools:
                config.tools = tools
            if response_mime_type:
                config.response_mime_type = response_mime_type
            if response_schema:
                config.response_schema = response_schema
            if max_output_tokens:
                config.max_output_tokens = max_output_tokens
            
            response_stream = client.models.generate_content_stream(
                model=clean_google_model,
                contents=contents,
                config=config
            )
            
            full_thinking = ""
            full_response = ""
            function_calls = []
            function_call_parts = []
            raw_response = None
            restored_state = False
            
            for chunk in response_stream:
                raw_response = chunk # Store last chunk for raw access
                if busy_retries > 0 and not restored_state:
                    state.set_ui_state("Thinking")
                    restored_state = True
                if getattr(state, 'STOP_REQUESTED', False):
                    full_response += "\n\n[System: Generation stopped by user]\n<task_complete />"
                    break
                
                thought_chunk, text_chunk = _collect_response_parts(
                    getattr(chunk, "candidates", None), function_calls, function_call_parts
                )
                if thought_chunk:
                    full_thinking += thought_chunk
                    if thought_callback:
                        thought_callback(thought_chunk)
                if text_chunk:
                    full_response += text_chunk
                    if stream_callback:
                        stream_callback(text_chunk)
                        
            # FALLBACK: If streaming produced no answer and no function calls
            if not full_response.strip() and not function_calls:
                stream_finish = ""
                if raw_response and getattr(raw_response, "candidates", None):
                    stream_finish = str(raw_response.candidates[0].finish_reason or "")
                if full_thinking.strip() and ("MALFORMED" in stream_finish or "OTHER" in stream_finish):
                    print(f"\033[93m[System Recovery] Model generated a malformed response ({stream_finish}). Injecting recovery prompt...\033[0m")
                    full_response = (
                        "[System Error: The API generated a malformed response and blocked it. "
                        "This is a Google API backend issue. Please rethink your plan and output your next step differently.]\n"
                        "[SYSTEM_RECOVERY_REQUIRED]"
                    )
                elif not full_thinking.strip():
                    print("\n\033[93m[Syntiox CORE] Streaming failed or empty. Using Non-Streaming Fallback...\033[0m")
                    response = client.models.generate_content(
                        model=clean_google_model,
                        contents=contents,
                        config=config
                    )
                    raw_response = response
                    if busy_retries > 0 and not restored_state:
                        state.set_ui_state("Thinking")
                        restored_state = True
                    
                    fb_thinking, full_response = _collect_response_parts(
                        getattr(response, "candidates", None), function_calls, function_call_parts
                    )
                    if fb_thinking:
                        full_thinking = fb_thinking
                        if thought_callback:
                            thought_callback(fb_thinking)
                    
                    if stream_callback and full_response:
                        for i in range(0, len(full_response), 4):
                            if getattr(state, 'STOP_REQUESTED', False):
                                full_response = full_response[:i] + "\n\n[System: Generation stopped by user]\n<task_complete />"
                                break
                            stream_callback(full_response[i:i+4])
                            time.sleep(0.005)
                            
                    if not full_response.strip() and not function_calls:
                        finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "Unknown"
                        if "MALFORMED" in finish_reason or "OTHER" in finish_reason:
                            print(f"\033[93m[System Recovery] Model generated a malformed response ({finish_reason}). Injecting recovery prompt...\033[0m")
                            full_response = (
                                "[System Error: The API generated a malformed response and blocked it. "
                                "This is a Google API backend issue. Please rethink your plan and output your next step differently.]\n"
                                "[SYSTEM_RECOVERY_REQUIRED]"
                            )
                        elif not full_thinking.strip():
                            raise Exception(f"API returned an empty response even after fallback. Finish Reason: {finish_reason}")
                        
            return {
                "content": full_response,
                "thoughts": full_thinking,
                "native_function_call_parts": function_call_parts,
                "raw_response": raw_response,
            }
            
        except Exception as e:
            last_error = e

            if is_invalid_key_error(e):
                mark_current_key_invalid()
                if API_KEYS and not get_valid_keys():
                    raise Exception("All configured Gemini API keys are invalid (API_KEY_INVALID).")
                rotate_key()
                continue

            if is_server_busy_error(e):
                if not retry_on_busy:
                    raise e
                busy_retries += 1
                if busy_retries > max_busy_retries:
                    state.set_ui_state("Server Very Busy")
                    raise Exception(f"Server is very busy right now (Model Unavailable after {max_busy_retries}/{max_busy_retries} retries). Please try again later.")

                wait_seconds = BUSY_RETRY_DELAYS[min(busy_retries - 1, len(BUSY_RETRY_DELAYS) - 1)]
                rotate_key()
                quota_attempts = 0

                for remaining in range(wait_seconds, 0, -1):
                    if getattr(state, 'STOP_REQUESTED', False):
                        raise Exception("Generation stopped by user.")
                    status_text = f"Model Unavailable - Retrying in {remaining}s ({busy_retries}/{max_busy_retries})"
                    state.set_ui_state(status_text)
                    print(f"\r\033[93m[Syntiox CORE] {status_text}   \033[0m", end="", flush=True)
                    time.sleep(1)
                print()
                state.set_ui_state(f"Model Unavailable - Retrying now ({busy_retries}/{max_busy_retries})")
                continue

            if is_quota_error(e):
                quota_attempts += 1
                valid_count = len(get_valid_keys()) if API_KEYS else 1
                if quota_attempts >= max(1, valid_count):
                    raise Exception(f"All {valid_count} valid API keys failed due to quota/rate limits. Last error: {last_error}")
                rotate_key()
                time.sleep(0.5)
                continue

            if is_missing_thought_signature_error(e) and not sanitized_retried and isinstance(contents, list):
                sanitized, changed = _sanitize_unsigned_function_calls(contents)
                if changed:
                    sanitized_retried = True
                    override_contents = sanitized
                    print("\033[93m[Syntiox CORE] Converted unsigned function calls in history to text and retrying...\033[0m")
                    continue

            print(f"\033[91m[API Error - Non Retryable] {e}\033[0m")
            raise e

def safe_generate_content(prompt_or_contents, image_base64=None, stream_callback=None, sys_prompt=None, tools=None, response_schema=None, response_mime_type=None, max_output_tokens=None, retry_on_busy=True, model=None, thought_callback=None, thinking_level=None, include_thoughts=True):
    """
    Unified router that dispatches generation requests to safe_generate_groq
    or safe_generate_content_gemini based on the target model.
    """
    target_model = (model or GOOGLE_MODEL).strip()
    if is_groq_model(target_model):
        return safe_generate_groq(
            prompt_or_contents=prompt_or_contents,
            image_base64=image_base64,
            stream_callback=stream_callback,
            sys_prompt=sys_prompt,
            tools=tools,
            response_schema=response_schema,
            response_mime_type=response_mime_type,
            max_output_tokens=max_output_tokens,
            retry_on_busy=retry_on_busy,
            model=target_model,
        )
    return safe_generate_content_gemini(
        prompt_or_contents=prompt_or_contents,
        image_base64=image_base64,
        stream_callback=stream_callback,
        sys_prompt=sys_prompt,
        tools=tools,
        response_schema=response_schema,
        response_mime_type=response_mime_type,
        max_output_tokens=max_output_tokens,
        retry_on_busy=retry_on_busy,
        model=target_model,
        thought_callback=thought_callback,
        thinking_level=thinking_level,
        include_thoughts=include_thoughts,
    )

# --- Skills Loading ---
SKILLS_CACHE = []

def preload_skills():
    global SKILLS_CACHE
    if SKILLS_CACHE:
        return
    from backend.config_paths import SKILLS_DIR
    skills_dir = SKILLS_DIR
    skill_files = sorted(glob.glob(os.path.join(skills_dir, "**", "SKILL.md"), recursive=True))
    
    for filepath in skill_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    body = parts[2].strip()
                    keywords_line = next((line for line in frontmatter.split('\n') if line.startswith('keywords:')), None)
                    name_line = next((line for line in frontmatter.split('\n') if line.startswith('name:')), None)
                    desc_line = next((line for line in frontmatter.split('\n') if line.startswith('description:')), None)
                    
                    name = name_line.split('name:')[1].strip() if name_line else "Unknown Skill"
                    description = desc_line.split('description:')[1].strip() if desc_line else ""
                    keywords = [k.strip().lower() for k in keywords_line.split('keywords:')[1].split(',')] if keywords_line else []
                    
                    rel_path = os.path.relpath(filepath, start=skills_dir)
                    rel_path = "skills/" + rel_path.replace("\\", "/")
                    skill_id = os.path.basename(os.path.dirname(filepath)).lower()
                    SKILLS_CACHE.append({
                        "id": skill_id,
                        "path": rel_path,
                        "abs_path": os.path.abspath(filepath).replace("\\", "/"),
                        "name": name,
                        "description": description,
                        "keywords": keywords,
                        "body": body
                    })
        except Exception:
            pass
    print(f"Loaded {len(SKILLS_CACHE)} skills into cache.")

def load_dynamic_skills() -> str:
    preload_skills()
    always_skill_contents = []
    ondemand_skill_lines = []
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")).replace('\\', '\\\\')

    for skill in SKILLS_CACHE:
        kw = skill.get("keywords", [])
        if "always" in kw or "default" in kw:
            body_with_paths = skill["body"].replace("{ROOT_DIR}", root_dir)
            always_skill_contents.append(body_with_paths)
        else:
            skill_id = skill.get("id", "")
            abs_path = skill.get("abs_path", skill.get("path", ""))
            desc = skill.get("description", "")
            ondemand_skill_lines.append(f"- {skill_id} ({abs_path}): {desc}")

    sections = []
    if always_skill_contents:
        sections.append("\n\n".join(always_skill_contents))
    else:
        sections.append("You are Syntiox CORE, an autonomous On-Demand Local OS Agent.")

    if ondemand_skill_lines:
        skills_index = (
            "[AVAILABLE ON-DEMAND SKILLS]\n"
            "If a skill below is relevant to your current task, you MUST read its `SKILL.md` instructions using `view_file` with its exact path before proceeding:\n"
            + "\n".join(ondemand_skill_lines)
        )
        sections.append(skills_index)

    try:
        from backend.mcp_runner import get_mcp_prompt_summary
        mcp_summary = get_mcp_prompt_summary()
        if mcp_summary:
            sections.append(mcp_summary.strip())
    except Exception as e:
        print(f"[MCP] Warning: could not load MCP prompt summary: {e}")

    return "\n\n".join(sections)

SUMMARY_PREFIX = "[System: Summary of older conversation]"
MAX_SUMMARY_INPUT_ENTRY_CHARS = 2000
MAX_RECENT_ENTRY_CHARS = 4000

def _clip_entry(entry, limit: int) -> str:
    entry = str(entry)
    return entry if len(entry) <= limit else entry[:limit].rstrip() + " ...[truncated]"

def summarize_memory(chat_history_list: list) -> list:
    # Keep the last 2 user/assistant pairs verbatim; fold older turns into one summary entry
    if len(chat_history_list) <= 8:
        return chat_history_list
        
    recent_turns = [_clip_entry(t, MAX_RECENT_ENTRY_CHARS) for t in chat_history_list[-4:]]
    old_turns = chat_history_list[:-4]
    prev_summary = old_turns[0] if str(old_turns[0]).startswith(SUMMARY_PREFIX) else None
    old_history_str = "\n".join(_clip_entry(t, MAX_SUMMARY_INPUT_ENTRY_CHARS) for t in old_turns)
    
    sys_prompt = "You are an AI assistant. Please write a highly concise summary of the following past conversation so we don't forget the context. Keep important facts, exact file paths, completed actions, and pending goals. Output only the summary."
    groq_summary = safe_groq_chat(old_history_str, system_prompt=sys_prompt, max_tokens=512) if len(old_history_str) <= 20000 else None
    if groq_summary and groq_summary.strip():
        return [f"{SUMMARY_PREFIX} {groq_summary.strip()}"] + recent_turns

    prompt = f"System: {sys_prompt}\n\nConversation to summarize:\n{old_history_str}"
    try:
        response = safe_generate_content(prompt, retry_on_busy=False)
        summary = (response.get("content") or "").strip()
        if summary:
            return [f"{SUMMARY_PREFIX} {summary}"] + recent_turns
    except Exception:
        pass
    # Summarization failed: keep the previous summary instead of dropping all old context
    return ([prev_summary] if prev_summary else []) + [_clip_entry(t, MAX_RECENT_ENTRY_CHARS) for t in chat_history_list[-6:]]

def generate_session_title(user_prompt: str) -> str:
    sys_prompt = "You are a title generator. Generate a very short (2-5 words) title for this conversation based on the user's first prompt. Do not use quotes or prefixes, just output the plain title."
    groq_title = safe_groq_chat(user_prompt, system_prompt=sys_prompt, max_tokens=256)
    if groq_title and groq_title.strip():
        return groq_title.strip().strip('"\'')

    prompt = f"System: {sys_prompt}\n\nUser Input: {user_prompt}"
    try:
        response = safe_generate_content(prompt, max_output_tokens=32, retry_on_busy=False)
        title = response["content"].strip().strip('"\'')
        return title
    except Exception:
        return "Untitled Session"

def load_global_rules() -> str:
    try:
        from backend.config_paths import CONFIG_DIR
        rules_path = os.path.join(CONFIG_DIR, "prompts", "SYNTIOX_CORE.md")

        if os.path.exists(rules_path):
            with open(rules_path, "r", encoding="utf-8") as f:
                content = f.read()

            words = content.split()
            if len(words) > 2000:
                matches = list(re.finditer(r'\S+', content))
                if len(matches) >= 2000:
                    content = content[:matches[1999].end()] + "\n\n[Rules truncated at 2000 words limit]"

            if content.strip():
                return f"\n\n[USER GLOBAL RULES]\nYou MUST follow these user-defined global rules at all times:\n{content.strip()}\n[/USER GLOBAL RULES]\n"
    except Exception:
        pass
    return ""

def _get_ui_instruction() -> str:
    ui_mode = os.getenv("LAUNCH_UI", "terminal")
    if ui_mode == "web":
        return "\n[SYSTEM INSTRUCTION: The user is using a modern rich Web UI. Always format your responses beautifully using rich Markdown, including headers, tables, bold text, and code blocks. If there are mathematical equations, format them strictly in LaTeX for MathJax rendering.]\n"
    return "\n[SYSTEM INSTRUCTION: The user is using a plain Terminal CLI. Strictly avoid using complex markdown tables, LaTeX math, or heavy formatting. Use simple plain text, bullet points, and basic spacing so it renders cleanly in a standard terminal shell.]\n"

def _get_loop_compaction_thresholds(model_name: str = None) -> dict:
    model = (model_name or GOOGLE_MODEL or "").lower()
    if is_groq_model(model):
        high_chars, low_chars = 28000, 12000
        single_tool_cap, active_hard_cap = 12000, 36000
        max_ledger_chars, max_working_memory_chars = 8000, 8000
    else:
        high_chars, low_chars = 400000, 180000
        single_tool_cap, active_hard_cap = 200000, 450000
        max_ledger_chars, max_working_memory_chars = 24000, 24000

    env_high = os.getenv("AGENT_CONTEXT_HIGH_CHARS")
    env_low = os.getenv("AGENT_CONTEXT_LOW_CHARS")
    try:
        if env_high and int(env_high) > 0:
            high_chars = int(env_high)
            low_chars = min(low_chars, max(1000, high_chars // 2))
            active_hard_cap = max(active_hard_cap, high_chars)
        if env_low and int(env_low) > 0:
            low_chars = min(int(env_low), max(500, high_chars - 500))
    except ValueError:
        pass

    return {
        "high_chars": high_chars,
        "low_chars": low_chars,
        "single_tool_cap": single_tool_cap,
        "active_hard_cap": active_hard_cap,
        "max_ledger_chars": max_ledger_chars,
        "max_working_memory_chars": max_working_memory_chars,
        "min_active_steps": 2,
    }


def _estimate_step_chars(item: dict) -> int:
    total = len(strip_text_tool_calls(item.get("thought", "") or ""))
    total += len(item.get("final_message", "") or "")
    per_tc_results = 0
    for tc in item.get("tool_calls") or []:
        fn = tc.get("function") or {}
        total += len(fn.get("name", "") or "")
        args_str = json.dumps(fn.get("arguments", {}), ensure_ascii=False, default=str)
        total += len(args_str)
        if "result" in tc and tc.get("result") is not None:
            per_tc_results += len(str(tc.get("result")))
    exec_len = len(str(item.get("execution_result", "") or ""))
    total += max(per_tc_results, exec_len)
    return total


def _init_loop_memory() -> dict:
    return {
        "compacted_upto": 0,
        "working_memory": "",
        "ledger": {
            "files_read": {},
            "files_modified": [],
            "mcp_schemas": {},
            "skills_loaded": {},
            "mcp_calls": [],
            "commands": [],
            "searches": [],
            "browser_research": [],
            "errors": [],
        },
    }


def _clean_tool_output(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"^\[ACTION_START\]\s*", "", text)
    text = re.sub(r"\s*\[ACTION_END\]$", "", text)
    return text.strip()


def _strip_line_numbers(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        m = re.match(r"^\s*\d+\s*:\s?(.*)$", line)
        cleaned.append(m.group(1) if m else line)
    return "\n".join(cleaned)


def _extract_mcp_schema_digest(content: str) -> str:
    body = _clean_tool_output(content)
    # Strip optional view_file header lines before JSON object
    json_start = body.find("{")
    if json_start != -1:
        candidate = _strip_line_numbers(body[json_start:])
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                schema = data.get("inputSchema") or data.get("parameters") or {}
                props = schema.get("properties") if isinstance(schema, dict) else {}
                req = schema.get("required") if isinstance(schema, dict) else []
                prop_parts = []
                if isinstance(props, dict):
                    for k, v in list(props.items())[:16]:
                        ptype = v.get("type", "any") if isinstance(v, dict) else "any"
                        pdesc = (v.get("description", "")[:70] if isinstance(v, dict) else "").replace("\n", " ")
                        mark = "*" if isinstance(req, list) and k in req else ""
                        prop_parts.append(f"{k}{mark}:{ptype}" + (f" ({pdesc})" if pdesc else ""))
                desc = str(data.get("description", "")).replace("\n", " ")[:180]
                return f"desc={desc} | required={req} | params=[{'; '.join(prop_parts)}]"
        except Exception:
            pass
    return body.replace("\n", " ")[:900]


def _extract_skill_digest(content: str) -> str:
    body = _strip_line_numbers(_clean_tool_output(content))
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    return " | ".join(lines)[:1200]


def _append_bounded(lst: list, value, limit: int):
    if not value:
        return
    if value not in lst:
        lst.append(value)
        if len(lst) > limit:
            del lst[:len(lst) - limit]


def _update_deterministic_ledger(ledger: dict, evicted_steps: list) -> None:
    if not ledger or not evicted_steps:
        return
    for item in evicted_steps:
        step_num = item.get("step", "?")
        default_res = str(item.get("execution_result", "") or "")
        for tc in item.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = fn.get("name", "?")
            args = fn.get("arguments") or {}
            if not isinstance(args, dict):
                args = {}
            raw_res = str(tc.get("result") if tc.get("result") is not None else default_res)
            clean_res = _clean_tool_output(raw_res)

            if name == "view_file":
                fpath = str(args.get("filepath") or args.get("path") or "").strip()
                if fpath:
                    s_line = args.get("start_line", 1)
                    e_line = args.get("end_line", "end")
                    rng = f"L{s_line}-{e_line}"
                    ranges = ledger["files_read"].setdefault(fpath, [])
                    if rng not in ranges:
                        ranges.append(rng)
                    norm = fpath.replace("\\", "/").lower()
                    if "mcp_schemas/" in norm and norm.endswith(".json"):
                        ledger["mcp_schemas"][fpath] = _extract_mcp_schema_digest(clean_res)
                    elif norm.endswith("/skill.md") or norm == "skill.md":
                        ledger["skills_loaded"][fpath] = _extract_skill_digest(clean_res)

            elif name in ("write_to_file", "replace_file_content", "multi_replace_file_content", "append_to_file"):
                fpath = str(args.get("filepath") or args.get("path") or "").strip()
                res_low = clean_res.lower()
                status = "ERR" if any(k in res_low for k in ("error:", "[system error]", "failed to", "traceback", "not found:", "permissionerror")) else "OK"
                detail = ""
                if name == "replace_file_content":
                    tgt = str(args.get("target", "")).replace("\n", " ")[:60]
                    detail = f"target='{tgt}'"
                elif name == "write_to_file":
                    detail = f"chars={len(str(args.get('content', '')))}"
                entry = f"Step {step_num} [{status}] {name} -> {fpath}" + (f" ({detail})" if detail else "")
                ledger["files_modified"].append(entry)
                if len(ledger["files_modified"]) > 60:
                    del ledger["files_modified"][:len(ledger["files_modified"]) - 60]

            elif name == "call_mcp_tool":
                srv = args.get("server_name", "?")
                tname = args.get("tool_name", "?")
                targs = json.dumps(args.get("arguments", {}), ensure_ascii=False, default=str)[:180]
                out = clean_res.replace("\n", " ")[:220]
                ledger["mcp_calls"].append(f"Step {step_num} {srv}.{tname}({targs}) -> {out}")
                if len(ledger["mcp_calls"]) > 40:
                    del ledger["mcp_calls"][:len(ledger["mcp_calls"]) - 40]

            elif name in ("run_terminal_command", "run_background_command"):
                cmd = str(args.get("command", "")).replace("\n", " ")[:140]
                tail = clean_res.replace("\n", " ")[-200:]
                ledger["commands"].append(f"Step {step_num} `{cmd}` -> {tail}")
                if len(ledger["commands"]) > 30:
                    del ledger["commands"][:len(ledger["commands"]) - 30]

            elif name in ("grep_search", "search_in_files", "find_files_by_name", "list_dir"):
                q = str(args.get("query") or args.get("pattern") or args.get("dirpath") or args.get("directory") or "")[:100]
                d = str(args.get("directory") or args.get("dirpath") or ".")[:80]
                snip = clean_res.replace("\n", " | ")[:180]
                ledger["searches"].append(f"Step {step_num} {name}({q} in {d}) -> {snip}")
                if len(ledger["searches"]) > 25:
                    del ledger["searches"][:len(ledger["searches"]) - 25]

            elif name in ("browser_subagent", "search_web", "read_url_content"):
                handoff_sections = (
                    r"\[TASK CHECKLIST\]|\[COLLECTED RESEARCH & SOURCES\]|\[VISITED URLS\]|"
                    r"\[BROWSER SESSION SUMMARY\]|\[BROWSER ACTION & CLICK LOG\]|\[CAPTURED DOM TEXT BY STEP\]"
                )
                m = re.search(rf"\[COLLECTED RESEARCH & SOURCES\]\n(.*?)(?=\n\n(?:{handoff_sections})|\Z)", raw_res, flags=re.DOTALL)
                if m:
                    _append_bounded(ledger["browser_research"], f"Step {step_num}: {m.group(1).strip()[:2200]}", 12)
                else:
                    compact_res = re.split(r"\n\n\[(?:BROWSER ACTION & CLICK LOG|CAPTURED DOM TEXT BY STEP)\]", clean_res, maxsplit=1)[0]
                    _append_bounded(ledger["browser_research"], f"Step {step_num} ({name}): {compact_res.replace(chr(10), ' ')[:1200]}", 12)

            if any(marker in clean_res for marker in ("Traceback", "Error:", "ERROR:", "[SYSTEM ERROR]", "Exception:")):
                err_snip = clean_res.replace("\n", " ")[:240]
                _append_bounded(ledger["errors"], f"Step {step_num} ({name}): {err_snip}", 15)


def _format_evicted_batch_for_summary(evicted_steps: list, max_total_chars: int = 80000) -> str:
    if not evicted_steps:
        return ""
    per_step_budget = max(1800, max_total_chars // len(evicted_steps))
    blocks = []
    for item in evicted_steps:
        step_num = item.get("step", "?")
        thought = strip_text_tool_calls(item.get("thought") or item.get("thinking") or "").strip()
        final_msg = (item.get("final_message", "") or "").strip()
        parts = [f"### Step {step_num}"]
        if thought:
            parts.append(f"Thought: {thought[:min(1200, per_step_budget // 3)]}")
        if final_msg:
            parts.append(f"Message: {final_msg[:800]}")
        default_res = str(item.get("execution_result", "") or "")
        tcs = item.get("tool_calls") or []
        if tcs:
            per_tool_res = max(600, (per_step_budget - 800) // len(tcs))
            for tc in tcs:
                fn = tc.get("function") or {}
                tname = fn.get("name", "?")
                targs = json.dumps(fn.get("arguments", {}), ensure_ascii=False, default=str)[:400]
                tres = _clean_tool_output(str(tc.get("result") if tc.get("result") is not None else default_res))
                if len(tres) > per_tool_res:
                    head = int(per_tool_res * 0.7)
                    tail = per_tool_res - head
                    tres = tres[:head] + "\n...[clipped]...\n" + tres[-tail:]
                parts.append(f"Tool `{tname}({targs})`:\n{tres}")
        blocks.append("\n".join(parts))
    combined = "\n\n".join(blocks)
    return combined[:max_total_chars]


def _deterministic_memory_fallback(prev_memory: str, evicted_steps: list, max_chars: int = 24000) -> str:
    notes = []
    for item in evicted_steps:
        step_num = item.get("step", "?")
        thought = strip_text_tool_calls(item.get("thought") or item.get("thinking") or "").replace("\n", " ").strip()[:220]
        tools = []
        tool_outs = []
        default_res = str(item.get("execution_result", "") or "")
        tcs = item.get("tool_calls") or []
        per_out_cap = max(120, 360 // max(1, len(tcs)))
        for tc in tcs:
            fn = tc.get("function") or {}
            tname = fn.get("name", "?")
            targs = json.dumps(fn.get("arguments", {}), ensure_ascii=False, default=str)[:140]
            tools.append(f"{tname}({targs})")
            raw_res = tc.get("result") if tc.get("result") is not None else default_res
            res_snip = _clean_tool_output(str(raw_res)).replace("\n", " ")[:per_out_cap]
            if res_snip:
                tool_outs.append(f"{tname}: {res_snip}")
        if not tool_outs and default_res:
            tool_outs.append(_clean_tool_output(default_res).replace("\n", " ")[:360])
        out_str = " | ".join(tool_outs)[:400]
        notes.append(f"- Step {step_num}: Thought='{thought}' | Tools=[{', '.join(tools)}] | Out='{out_str}'")
    merged = (prev_memory.strip() + "\n" + "\n".join(notes)).strip() if prev_memory.strip() else "\n".join(notes)
    if len(merged) > max_chars:
        # Keep the opening baseline plus most recent compacted notes when clipping
        head_keep = max_chars // 3
        tail_keep = max(100, max_chars - head_keep - 40)
        merged = merged[:head_keep] + "\n...[older notes trimmed]...\n" + merged[-tail_keep:]
    return merged


def _distill_working_memory_gemini(prev_memory: str, evicted_steps: list, target_model: str = None, max_chars: int = 24000) -> str:
    if not evicted_steps:
        return prev_memory
    summary_model = os.getenv("AGENT_SUMMARY_MODEL") or target_model or GOOGLE_MODEL
    if is_groq_model(summary_model):
        return _deterministic_memory_fallback(prev_memory, evicted_steps, max_chars=max_chars)

    batch_text = _format_evicted_batch_for_summary(evicted_steps)
    prompt = (
        "Update the Main Agent's cumulative Working Memory from the newly compacted loop steps.\n"
        "Preserve essential codebase knowledge so earlier discoveries are NOT forgotten across long tasks.\n\n"
        "Strict Rules:\n"
        "1. Keep exact file paths, class/function/variable names, signatures, configs, CLI/MCP parameter names, numbers, and error messages.\n"
        "2. Merge EXISTING WORKING MEMORY with NEWLY COMPACTED STEPS into 3 structured sections:\n"
        "   - ## Codebase Architecture & Key Symbols\n"
        "   - ## Edits Applied & Verification Results\n"
        "   - ## Constraints, Quirks & Open Findings\n"
        "3. Do NOT drop still-valid facts from EXISTING WORKING MEMORY unless directly superseded or fixed.\n"
        f"4. Omit raw code blocks already summarized and omit verbose boilerplate; keep output dense, accurate, and under {min(18000, max_chars)} characters.\n\n"
        f"EXISTING WORKING MEMORY:\n{prev_memory or '(none yet)'}\n\n"
        f"NEWLY COMPACTED STEPS:\n{batch_text}\n"
    )
    try:
        res = safe_generate_content_gemini(
            prompt,
            sys_prompt="You maintain lossless, high-density technical working memory for a coding & automation agent. Never invent facts.",
            max_output_tokens=4096,
            retry_on_busy=False,
            model=summary_model,
        )
        distilled = (res.get("content") or "").strip() if isinstance(res, dict) else ""
        if distilled and not distilled.startswith("API Error:") and not distilled.startswith("All Gemini"):
            return distilled[:max_chars]
    except Exception as e:
        print(f"DEBUG: Gemini working-memory distillation fallback triggered: {e}")

    return _deterministic_memory_fallback(prev_memory, evicted_steps, max_chars=max_chars)


def _format_loop_memory_block(loop_memory: dict, max_ledger_chars: int = 24000) -> str:
    ledger = loop_memory.get("ledger") or {}
    lines = [
        "[System Note: Older loop steps were compacted after exceeding the character context threshold. Exact verbatim outputs for those older steps are omitted below, while your accumulated codebase memory and deterministic action ledger remain preserved. Before modifying an existing file whose exact lines are not in the active steps below, call view_file on the target lines first.]",
        "",
        "[DETERMINISTIC WORKSPACE & TOOL LEDGER]",
    ]

    files_read = ledger.get("files_read") or {}
    if files_read:
        items = [f"  - {p} ({', '.join(rngs[-6:])})" for p, rngs in list(files_read.items())[-50:]]
        lines.append("Files Read:\n" + "\n".join(items))

    files_modified = ledger.get("files_modified") or []
    if files_modified:
        lines.append("Files Modified:\n" + "\n".join(f"  - {x}" for x in files_modified[-30:]))

    mcp_schemas = ledger.get("mcp_schemas") or {}
    if mcp_schemas:
        items = [f"  - {k}: {v}" for k, v in list(mcp_schemas.items())[-20:]]
        lines.append("MCP Schemas Inspected:\n" + "\n".join(items))

    skills_loaded = ledger.get("skills_loaded") or {}
    if skills_loaded:
        items = [f"  - {k}: {v}" for k, v in list(skills_loaded.items())[-10:]]
        lines.append("Skills Loaded:\n" + "\n".join(items))

    mcp_calls = ledger.get("mcp_calls") or []
    if mcp_calls:
        lines.append("MCP Calls:\n" + "\n".join(f"  - {x}" for x in mcp_calls[-20:]))

    commands = ledger.get("commands") or []
    if commands:
        lines.append("Commands Run:\n" + "\n".join(f"  - {x}" for x in commands[-15:]))

    searches = ledger.get("searches") or []
    if searches:
        lines.append("Discovery Searches:\n" + "\n".join(f"  - {x}" for x in searches[-15:]))

    research = ledger.get("browser_research") or []
    if research:
        lines.append("Browser & Web Research:\n" + "\n".join(f"  - {x}" for x in research[-8:]))

    errors = ledger.get("errors") or []
    if errors:
        lines.append("Observed Errors:\n" + "\n".join(f"  - {x}" for x in errors[-10:]))

    ledger_block = "\n".join(lines)
    if len(ledger_block) > max_ledger_chars:
        ledger_block = ledger_block[:max_ledger_chars] + "\n...[ledger truncated]..."

    wm = (loop_memory.get("working_memory") or "").strip()
    if wm:
        return f"{ledger_block}\n\n[WORKING MEMORY FROM COMPACTED STEPS]\n{wm}"
    return ledger_block


def _fit_per_tool_limit(lengths: list[int], budget: int, single_cap: int) -> int:
    if not lengths:
        return single_cap
    if budget <= 0:
        return max(250, min(single_cap, 1000 // len(lengths)))
    capped = [min(l, single_cap) for l in lengths]
    if sum(capped) <= budget:
        return single_cap
    rem = budget
    for i, val in enumerate(sorted(capped)):
        left = len(capped) - i
        share = rem // left
        if val <= share:
            rem -= val
        else:
            return max(250, share)
    return single_cap


def compact_and_build_history_contents(
    loop_history: list,
    loop_memory: dict = None,
    target_model: str = None,
) -> list:
    if loop_memory is None:
        loop_memory = _init_loop_memory()

    resolved_model = target_model or GOOGLE_MODEL
    thresholds = _get_loop_compaction_thresholds(resolved_model)
    high_chars = thresholds["high_chars"]
    low_chars = thresholds["low_chars"]
    min_keep = thresholds["min_active_steps"]

    compacted_upto = loop_memory.get("compacted_upto", 0)
    if compacted_upto < 0 or compacted_upto > len(loop_history):
        loop_memory.clear()
        loop_memory.update(_init_loop_memory())
        compacted_upto = 0

    active_slice = loop_history[compacted_upto:]
    step_chars = [_estimate_step_chars(item) for item in active_slice]
    total_active_chars = sum(step_chars)

    if total_active_chars > high_chars and len(active_slice) > 1:
        cut = 0
        remaining_chars = total_active_chars
        while cut < len(active_slice) - min_keep and remaining_chars > low_chars:
            remaining_chars -= step_chars[cut]
            cut += 1
        if remaining_chars > high_chars and (len(active_slice) - cut) > 1:
            while cut < len(active_slice) - 1 and remaining_chars > high_chars:
                remaining_chars -= step_chars[cut]
                cut += 1

        if cut > 0:
            new_upto = compacted_upto + cut
            newly_evicted = loop_history[compacted_upto:new_upto]
            _update_deterministic_ledger(loop_memory["ledger"], newly_evicted)
            loop_memory["working_memory"] = _distill_working_memory_gemini(
                loop_memory.get("working_memory", ""),
                newly_evicted,
                target_model=resolved_model,
                max_chars=thresholds["max_working_memory_chars"],
            )
            loop_memory["compacted_upto"] = new_upto
            compacted_upto = new_upto

    out_contents = []
    recent_steps = loop_history[compacted_upto:]
    if compacted_upto > 0:
        memory_text = _format_loop_memory_block(
            loop_memory,
            max_ledger_chars=thresholds["max_ledger_chars"],
        )
        out_contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=memory_text)]
        ))

    main_result_limit = thresholds["single_tool_cap"]
    # Shared budget across active steps, newest first, so parallel calls cannot overflow context
    remaining_budget = thresholds["active_hard_cap"]
    step_limits = {}
    for idx in range(len(recent_steps) - 1, -1, -1):
        item = recent_steps[idx]
        tcs = item.get("tool_calls") or []
        t_lengths = [
            len(str(tc.get("result") if tc.get("result") is not None else item.get("execution_result", "")))
            for tc in tcs
        ]
        limit = _fit_per_tool_limit(t_lengths, remaining_budget, main_result_limit)
        step_limits[idx] = limit
        spent = sum(min(l, limit) for l in t_lengths)
        remaining_budget = max(0, remaining_budget - spent)

    for idx, item in enumerate(recent_steps):
        if item.get("tool_calls"):
            model_content, user_content = build_tool_turn_contents(
                thought_text=item.get("thought", ""),
                tool_calls=item["tool_calls"],
                default_result=item.get("execution_result", "No result."),
                result_char_limit=step_limits[idx],
                target_model=resolved_model,
            )
            out_contents.append(model_content)
            if user_content:
                out_contents.append(user_content)
        else:
            msg = item.get("final_message", "")
            if msg and msg.strip():
                out_contents.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=msg)]
                ))

    return out_contents


def generate_agent_step(user_prompt: str, loop_history: list, step: int = 1, history_str: str = "", task_list_str: str = "", stream_callback=None, image_base64: str = None, loop_memory: dict = None, thought_callback=None) -> dict:
    from backend.tools_loader import get_json_tools
    from backend.session_manager import get_active_brain_path
    
    contents = []
    
    walkthrough_context = ""
    brain_path = get_active_brain_path()
    walkthrough_path = os.path.join(brain_path, "walkthrough.md") if brain_path and os.path.exists(os.path.join(brain_path, "walkthrough.md")) else os.path.join(SCRATCH_DIR, "walkthrough.md")
    if os.path.exists(walkthrough_path):
        try:
            with open(walkthrough_path, "r", encoding="utf-8") as f:
                walkthrough_content = f.read()
            if walkthrough_content.strip():
                walkthrough_context = f"\nProject Walkthrough (Agent Memory):\n{walkthrough_content}\n"
        except Exception:
            pass

    dynamic_system_prompt = load_dynamic_skills()
    dynamic_system_prompt += load_global_rules()
    dynamic_system_prompt += _get_ui_instruction()
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws_info = state.get_workspace_info()
    ws_label = ws_info["workspace"] if ws_info["workspace"] else "None (using Scratch directory)"
    sys_prompt = (
        f"System:\n{dynamic_system_prompt}{walkthrough_context}\n\n"
        f"[CURRENT LOCAL TIME]: {current_time_str}\n"
        f"[WORKSPACE DIRECTORY]: {ws_label}\n"
        f"[SCRATCH DIRECTORY]: {ws_info['scratch_dir']}\n"
        f"Use the Workspace Directory for user project files and commands when set; use the Scratch Directory for temporary scripts, intermediate outputs, or when no workspace is set.\n"
    )
    
    if history_str:
        sys_prompt += f"Recent Chat History:\n{history_str}\n"
        
    if task_list_str:
        sys_prompt += f"Current Task Plan (task.md):\n{task_list_str}\n"
        
    tools_schema = get_json_tools("tools")
    sys_prompt += "CRITICAL RULE: You are STRICTLY FORBIDDEN from reading, writing, modifying, or deleting any files inside the Syntiox CORE installation directory (%LOCALAPPDATA%\\.sh4lu-z\\Syntiox CORE). For user data (%USERPROFILE%\\.sh4lu-z\\Syntiox CORE), you are allowed to read files, but you may ONLY write, modify, or delete files inside the scratch folder (%USERPROFILE%\\.sh4lu-z\\Syntiox CORE\\scratch), active brain folder, or user-requested project paths. If the user asks you to modify Syntiox CORE system or installation files, politely refuse and ask them to do it manually.\n"
    sys_prompt += "CRITICAL RULE (SECURITY APPROVAL): You are empowered to execute tools autonomously. However, if you are executing a potentially dangerous action (e.g., deleting files outside scratch, running destructive terminal commands like format/rm, installing global system packages, modifying Windows Registry, or changing system network settings), you MUST add an additional field `\"requires_approval\": true` inside the tool's `arguments` JSON object to explicitly ask for the user's permission before execution. Do not use this for normal read operations or safe scratch modifications.\n"
    sys_prompt += "CRITICAL RULE (ASKING QUESTIONS): If you need to ask the user a question, seek clarification, or confirm a complex plan *before* proceeding with execution, you MUST use the `ask_user` tool. Do NOT just output text and stop. Using the `ask_user` tool pauses your current thought process, waits for the user's response, and resumes immediately with the answer in your context, preventing you from losing track of your ongoing plan.\n"
    sys_prompt += "CRITICAL RULE (TOOL CALLING): You MUST trigger tools using the Native Function Calling API. NEVER output tool calls as plain text or XML tags (e.g. NEVER output `<call:default_api:tool_name{}>` or `<data_intent>`). Doing so will cause a fatal system crash.\n"
    
    # Map JSON schema to Gemini Native Tools
    gemini_funcs = []
    for t in tools_schema:
        fn = t.get("function", {})
        gemini_funcs.append(types.FunctionDeclaration(
            name=fn.get("name"),
            description=fn.get("description"),
            parameters=fn.get("parameters")
        ))

    parts = []
    if image_base64:
        try:
            img_data = base64.b64decode(image_base64)
            parts.append(types.Part.from_bytes(data=img_data, mime_type='image/png'))
        except Exception as e:
            pass
            
    parts.append(types.Part.from_text(text=f"User Request: {user_prompt}"))
    contents.append(types.Content(role="user", parts=parts))

    contents.extend(
        compact_and_build_history_contents(
            loop_history,
            loop_memory=loop_memory,
            target_model=GOOGLE_MODEL,
        )
    )

    if contents and contents[-1].role == "model":
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text="Please proceed with the next step or provide your final response.")]
        ))
    
    try:
        response_dict = safe_generate_content(
            contents, 
            stream_callback=stream_callback, 
            sys_prompt=sys_prompt, 
            tools=[types.Tool(function_declarations=gemini_funcs)],
            max_output_tokens=8192,
            thought_callback=thought_callback,
            thinking_level=THINKING_LEVEL,
            include_thoughts=True,
        )
        
        content = response_dict.get("content", "")
        thoughts = response_dict.get("thoughts", "")
        native_call_parts = response_dict.get("native_function_call_parts", [])
        
        # --- PARSE NATIVE TOOL CALLS ---
        tool_calls = []
        if native_call_parts:
            for p in native_call_parts:
                call = p.function_call
                args_dict = {}
                if getattr(call, 'args', None):
                    # args is usually a Map/Dict struct in python SDK
                    args_dict = dict(call.args)
                tool_calls.append({
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": args_dict
                    },
                    "call_id": getattr(call, 'id', None),
                    "thought_signature": getattr(p, 'thought_signature', None)
                })
                
        # Fallback to parse text-based tool calls if native tools failed to capture them
        if not tool_calls and content and "<call:" in content:
            tool_calls = parse_text_tool_calls(content)
        
        status = "CONTINUE" if tool_calls else "COMPLETE"
        
        return {
            "thought": content,
            "thinking": thoughts,
            "tool_calls": tool_calls,
            "status": status,
            "final_message": content if status == "COMPLETE" else "",
            "raw": str(response_dict.get("raw_response"))
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Error communicating with Gemini: {str(e)}"}

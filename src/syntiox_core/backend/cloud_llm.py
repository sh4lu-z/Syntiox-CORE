import os
import glob
import time
import base64
import json
import re
import httpx
from backend import state
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from backend.config_paths import ENV_FILE, WORKSPACE_DIR

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

# Read model from .env, fallback to gemma-4-31b-it if not set
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemma-4-31b-it")
print(f"\033[92m[Syntiox CORE] Google Model: {GOOGLE_MODEL}\033[0m")

try:
    from groq import (
        Groq,
        APIError as GroqAPIError,
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
    GroqAPIError = GroqConnectionError = GroqTimeoutError = GroqStatusError = ()
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
    if isinstance(err, str):
        err_str = err.lower()
        return any(k in err_str for k in ("rate_limit", "429", "too many requests", "quota", "capacity exceeded"))
    return False

def is_groq_server_busy_error(err) -> bool:
    if GroqServerError and isinstance(err, (GroqServerError, GroqConnectionError, GroqTimeoutError)):
        return True
    if GroqStatusError and isinstance(err, GroqStatusError):
        code = getattr(err, "status_code", 0) or 0
        if code >= 500 or code == 408:
            return True
    if isinstance(err, (httpx.HTTPError, ConnectionError, TimeoutError)):
        return True
    if isinstance(err, str):
        err_str = err.lower()
        return any(k in err_str for k in ("500", "502", "503", "504", "overloaded", "service unavailable", "bad gateway", "gateway timeout"))
    return False

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

def safe_generate_groq(prompt_or_contents, image_base64=None, stream_callback=None, sys_prompt=None, tools=None, response_schema=None, response_mime_type=None, max_output_tokens=None, retry_on_busy=True, model=None, target_model=None):
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
    max_busy_retries = len(BUSY_RETRY_DELAYS)
    quota_attempts = 0
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
                    if busy_retries > 0 and not restored_state:
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
                if busy_retries > 0 and not restored_state:
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
                if not retry_on_busy:
                    raise e
                busy_retries += 1
                if busy_retries > max_busy_retries:
                    state.set_ui_state("Server Very Busy")
                    raise Exception(f"Groq server is very busy right now (Unavailable after {max_busy_retries}/{max_busy_retries} retries). Last error: {last_error}")

                wait_seconds = BUSY_RETRY_DELAYS[busy_retries - 1]
                rotate_groq_key()
                quota_attempts = 0

                for remaining in range(wait_seconds, 0, -1):
                    if getattr(state, "STOP_REQUESTED", False):
                        raise Exception("Generation stopped by user.")
                    status_text = f"Groq Unavailable - Retrying in {remaining}s ({busy_retries}/{max_busy_retries})"
                    state.set_ui_state(status_text)
                    print(f"\r\033[93m[Syntiox CORE] {status_text}   \033[0m", end="", flush=True)
                    time.sleep(1)
                print()
                state.set_ui_state(f"Groq Unavailable - Retrying now ({busy_retries}/{max_busy_retries})")
                continue

            if is_groq_quota_error(e):
                quota_attempts += 1
                valid_count = len(get_valid_groq_keys())
                if quota_attempts >= max(1, valid_count):
                    raise Exception(f"All {valid_count} valid Groq API keys failed due to quota/rate limits. Last error: {last_error}")
                rotate_groq_key()
                time.sleep(0.5)
                continue

            print(f"\033[91m[Groq API Error - Non Retryable] {e}\033[0m")
            raise e

_safe_generate_groq_content = safe_generate_groq

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

def safe_generate_content_gemini(prompt_or_contents, image_base64=None, stream_callback=None, sys_prompt=None, tools=None, response_schema=None, response_mime_type=None, max_output_tokens=None, retry_on_busy=True, model=None):
    """
    Synchronous Google Gemini/Gemma wrapper with official SDK error handling,
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
    
    while True:
        try:
            client = get_current_client()
            
            contents = []
            if isinstance(prompt_or_contents, str):
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
                
                # Check for function calls and preserve the raw Part object for thought_signatures
                if getattr(chunk, "candidates", None):
                    for cand in chunk.candidates:
                        if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                            for p in cand.content.parts:
                                if getattr(p, "function_call", None):
                                    function_calls.append(p.function_call)
                                    function_call_parts.append(p)
                                    
                try:
                    text = chunk.text
                except (ValueError, AttributeError):
                    text = None
                if text:
                    full_response += text
                    if stream_callback:
                        stream_callback(text)
                        
            # FALLBACK: If streaming failed/aborted AND no function calls were found
            if not full_response.strip() and not function_calls:
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
                
                if getattr(response, "candidates", None):
                    for cand in response.candidates:
                        if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                            for p in cand.content.parts:
                                if getattr(p, "function_call", None):
                                    function_calls.append(p.function_call)
                                    function_call_parts.append(p)
                
                try:
                    full_response = response.text or ""
                except ValueError:
                    full_response = ""
                    
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
                        full_response = "<thought>\n[System Error: The API generated a malformed response and blocked it. This is a Google API backend issue. Please rethink your plan and output your next step differently.]\n[SYSTEM_RECOVERY_REQUIRED]\n</thought>"
                    else:
                        raise Exception(f"API returned an empty response even after fallback. Finish Reason: {finish_reason}")
                        
            return {"content": full_response, "native_function_call_parts": function_call_parts, "raw_response": raw_response}
            
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

                wait_seconds = BUSY_RETRY_DELAYS[busy_retries - 1]
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

            print(f"\033[91m[API Error - Non Retryable] {e}\033[0m")
            raise e

def safe_generate_content(prompt_or_contents, image_base64=None, stream_callback=None, sys_prompt=None, tools=None, response_schema=None, response_mime_type=None, max_output_tokens=None, retry_on_busy=True, model=None):
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
    )

# --- Skills Loading ---
SKILLS_CACHE = []
ACTIVE_ROUTED_SKILLS = []

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

def load_dynamic_skills(user_prompt: str = "", step: int = 1, history_str: str = "") -> str:
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

def summarize_memory(chat_history_list: list) -> list:
    if len(chat_history_list) <= 6:
        return chat_history_list
        
    recent_turns = chat_history_list[-3:]
    old_turns = chat_history_list[:-3]
    old_history_str = "\n".join(old_turns)
    
    sys_prompt = "You are an AI assistant. Please write a highly concise summary of the following past conversation so we don't forget the context. Keep important facts, exact file paths, completed actions, and pending goals. Output only the summary."
    groq_summary = safe_groq_chat(old_history_str, system_prompt=sys_prompt, max_tokens=512)
    if groq_summary and groq_summary.strip():
        new_history = [f"[System: Summary of older conversation] {groq_summary.strip()}"] + recent_turns
        return new_history

    prompt = f"System: {sys_prompt}\n\nConversation to summarize:\n{old_history_str}"
    try:
        response = safe_generate_content(prompt, retry_on_busy=False)
        summary = response["content"].strip()
        new_history = [f"[System: Summary of older conversation] {summary}"] + recent_turns
        return new_history
    except Exception:
        return chat_history_list[-6:]

def classify_intent(user_prompt: str, manual_override: str = None, history_str: str = "") -> str:
    if manual_override and manual_override.upper() in ["CHAT", "AGENT"]:
        return manual_override.upper()
        
    prompt = f"System: You are an intent classifier. Respond with EXACTLY 'CHAT' or 'AGENT'.\n- If the user wants you to do something on their computer, write code, run commands, inspect local files/paths, execute a plan, search the web, do a math calculation, run python code, or use a tool, you MUST classify it as 'AGENT'.\n- CRITICAL: If the user prompt contains Sinhala action verbs like 'කරන්න' (do), 'හදන්න' (make/create), 'ලියන්න' (write), 'බලන්න' (look/view), 'පෙන්නන්න' (show), 'රන් කරන්න' (run), or 'හොයන්න' (find/search), you MUST classify it as 'AGENT'.\n- ALSO, if the user asks ANY factual question, asks about a person, event, movie, or anything that requires internet/up-to-date knowledge (e.g., 'who is X?', 'what is Y?', 'best movies', 'search for x'), or is replying to continue/confirm a previous agent task, you MUST say 'AGENT'.\n- If they are ONLY greeting you (e.g., 'hello', 'how are you') or making casual conversational remarks that require absolutely no research or tools, say 'CHAT'.\n\nRecent Chat History:\n{history_str}\n\nUser Input: {user_prompt}"
    groq_res = safe_groq_chat(prompt, max_tokens=128)
    if groq_res and groq_res.strip():
        if "AGENT" in groq_res.strip().upper():
            return "AGENT"
        return "CHAT"

    try:
        response = safe_generate_content(prompt, max_output_tokens=16, retry_on_busy=False)
        content = response["content"].strip().upper()
        if "AGENT" in content:
            return "AGENT"
        return "CHAT"
    except Exception as e:
        return "AGENT"

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
                lines = f.readlines()
                rules_text = "".join(lines[:500])
                if rules_text.strip():
                    return f"\n\n[USER GLOBAL RULES]\nYou MUST follow these user-defined global rules at all times:\n{rules_text}\n[/USER GLOBAL RULES]\n"
    except Exception:
        pass
    return ""

def _get_ui_instruction() -> str:
    ui_mode = os.getenv("LAUNCH_UI", "terminal")
    if ui_mode == "web":
        return "\n[SYSTEM INSTRUCTION: The user is using a modern rich Web UI. Always format your responses beautifully using rich Markdown, including headers, tables, bold text, and code blocks. If there are mathematical equations, format them strictly in LaTeX for MathJax rendering.]\n"
    return "\n[SYSTEM INSTRUCTION: The user is using a plain Terminal CLI. Strictly avoid using complex markdown tables, LaTeX math, or heavy formatting. Use simple plain text, bullet points, and basic spacing so it renders cleanly in a standard terminal shell.]\n"

def generate_chat_response(user_prompt: str, history_str: str = "", image_base64: str = None, stream_callback=None) -> str:
    walkthrough_context = ""
    from backend.session_manager import get_active_brain_path
    brain_path = get_active_brain_path()
    walkthrough_path = os.path.join(brain_path, "walkthrough.md") if brain_path and os.path.exists(os.path.join(brain_path, "walkthrough.md")) else os.path.join(WORKSPACE_DIR, "walkthrough.md")
    if os.path.exists(walkthrough_path):
        try:
            with open(walkthrough_path, "r", encoding="utf-8") as f:
                walkthrough_content = f.read()
            walkthrough_context = f"\nProject Walkthrough (Agent Memory):\n{walkthrough_content}\n"
        except Exception:
            pass

    dynamic_system_prompt = "You are Syntiox CORE, a helpful AI assistant. Answer concisely."
    dynamic_system_prompt += load_global_rules()
    dynamic_system_prompt += _get_ui_instruction()
    prompt = f"System:\n{dynamic_system_prompt}{walkthrough_context}\n\nRecent Conversation History:\n{history_str}\n\nUser: {user_prompt}"
    
    try:
        response = safe_generate_content(prompt, image_base64=image_base64, stream_callback=stream_callback)
        content = response["content"]
        return content.strip()
    except Exception as e:
        return f"Error: {e}"

def generate_agent_step(user_prompt: str, loop_history: list, step: int = 1, history_str: str = "", task_list_str: str = "", stream_callback=None, image_base64: str = None) -> dict:
    from backend.tools_loader import get_json_tools
    from backend.session_manager import get_active_brain_path
    import json
    
    contents = []
    
    walkthrough_context = ""
    brain_path = get_active_brain_path()
    walkthrough_path = os.path.join(brain_path, "walkthrough.md") if brain_path and os.path.exists(os.path.join(brain_path, "walkthrough.md")) else os.path.join(WORKSPACE_DIR, "walkthrough.md")
    if os.path.exists(walkthrough_path):
        try:
            with open(walkthrough_path, "r", encoding="utf-8") as f:
                walkthrough_content = f.read()
            if walkthrough_content.strip():
                walkthrough_context = f"\nProject Walkthrough (Agent Memory):\n{walkthrough_content}\n"
        except Exception:
            pass

    dynamic_system_prompt = load_dynamic_skills(user_prompt, step, history_str)
    dynamic_system_prompt += load_global_rules()
    dynamic_system_prompt += _get_ui_instruction()
    sys_prompt = f"System:\n{dynamic_system_prompt}{walkthrough_context}\n"
    
    if history_str:
        sys_prompt += f"Recent Chat History:\n{history_str}\n"
        
    if task_list_str:
        sys_prompt += f"Current Task Plan (task.md):\n{task_list_str}\n"
        
    tools_schema = get_json_tools("tools")
    sys_prompt += "CRITICAL RULE: You are STRICTLY FORBIDDEN from modifying, deleting, or altering any files inside the Syntiox CORE installation directory (%LOCALAPPDATA%\\.sh4lu-z\\Syntiox CORE) or system data folders (%USERPROFILE%\\.sh4lu-z\\Syntiox CORE\\history, skills, or config). You may only modify files inside the workspace, active brain folder, or user-requested project paths. If the user asks you to modify Syntiox CORE system files, politely refuse and ask them to do it manually.\n"
    sys_prompt += "CRITICAL RULE (SECURITY APPROVAL): You are empowered to execute tools autonomously. However, if you are executing a potentially dangerous action (e.g., deleting files outside the workspace, running destructive terminal commands like format/rm, installing global system packages, modifying Windows Registry, or changing system network settings), you MUST add an additional field `\"requires_approval\": true` inside the tool's `arguments` JSON object to explicitly ask for the user's permission before execution. Do not use this for normal read operations or safe workspace modifications.\n"
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
    
    recent_steps = loop_history
    if len(loop_history) > 5:
        old_steps = loop_history[:-5]
        recent_steps = loop_history[-5:]
        
        summary_text = "[System Note: Older steps are summarized to save memory. You DO NOT have the exact code/contents from these older steps anymore. BEFORE writing dependent code, you MUST use tools to read the required files again to avoid hallucinating!]\n\n"
        for old_item in old_steps:
            step_num = old_item.get("step")
            thought = old_item.get("thought", "").replace("\n", " ")
            tools = [tc["function"]["name"] for tc in old_item.get("tool_calls", [])]
            exec_res = str(old_item.get("execution_result", "")).replace("\n", " ").strip()
            summary_text += f"- Step {step_num}: Thought: '{thought[:150]}...'. Tools: {', '.join(tools)}. Result: '{exec_res[:150]}...'\n"
            
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=summary_text)]
        ))

    for item in recent_steps:
        if item.get("tool_calls"):
            # Build model turn: optional thought text + native function call parts
            model_parts = []
            thought_text = item.get("thought", "")
            if thought_text and thought_text.strip():
                model_parts.append(types.Part.from_text(text=thought_text))
            
            native_fc_flags = []
            for tc in item["tool_calls"]:
                fn_name = tc["function"]["name"]
                fn_args = tc["function"]["arguments"]
                if fn_name in ["system_recovery", "system_continue"]:
                    model_parts.append(types.Part.from_text(text=f"[Internal System Task]: {fn_name}"))
                    native_fc_flags.append(False)
                    continue
                try:
                    p = types.Part(function_call=types.FunctionCall(
                        name=fn_name, args=fn_args
                    ))
                    if tc.get("thought_signature"):
                        p.thought_signature = tc.get("thought_signature")
                    model_parts.append(p)
                    native_fc_flags.append(True)
                except Exception:
                    model_parts.append(types.Part.from_text(text=f"Called tool: {fn_name}"))
                    native_fc_flags.append(False)
            
            if not model_parts:
                model_parts.append(types.Part.from_text(text="Executing tool."))
            
            contents.append(types.Content(role="model", parts=model_parts))
            
            # Build function response turn with proper FunctionResponse parts
            exec_result = item.get('execution_result', 'No result.')
            response_parts = []
            for idx, tc in enumerate(item["tool_calls"]):
                fn_name = tc["function"]["name"]
                if fn_name in ["system_recovery", "system_continue"]:
                    response_parts.append(types.Part.from_text(
                        text=f"[SYSTEM NOTIFICATION]: {str(exec_result)[:4000]}"
                    ))
                    continue

                if idx < len(native_fc_flags) and native_fc_flags[idx]:
                    try:
                        response_parts.append(types.Part(function_response=types.FunctionResponse(
                            name=fn_name, response={"result": str(exec_result)[:12000]}
                        )))
                    except Exception:
                        response_parts.append(types.Part.from_text(
                            text=f"[Tool {fn_name} result]: {str(exec_result)[:12000]}"
                        ))
                else:
                    response_parts.append(types.Part.from_text(
                        text=f"[Tool {fn_name} result]: {str(exec_result)[:12000]}"
                    ))
            if response_parts:
                contents.append(types.Content(role="user", parts=response_parts))
        else:
            msg = item.get("final_message", "")
            if msg and msg.strip():
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=msg)]
                ))
            
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
            max_output_tokens=8192
        )
        
        content = response_dict.get("content", "")
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
                    "thought_signature": getattr(p, 'thought_signature', None)
                })
                
        # Fallback to parse text-based tool calls if native tools failed to capture them
        if not tool_calls and content and "<call:" in content:
            import re
            import json
            matches = re.findall(r'<call:(?:[a-zA-Z0-9_]+:)?([a-zA-Z0-9_]+)\{(.*?)\}>?', content)
            for name, raw_args in matches:
                args_dict = {}
                try:
                    args_dict = json.loads('{' + raw_args + '}')
                except Exception:
                    for pair in raw_args.split(','):
                        if ':' in pair:
                            k, v = pair.split(':', 1)
                            args_dict[k.strip().strip('"\'')] = v.strip().strip('"\'')
                tool_calls.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": args_dict
                    },
                    "thought_signature": None
                })
        
        status = "CONTINUE" if tool_calls else "COMPLETE"
        
        return {
            "thought": content,
            "tool_calls": tool_calls,
            "status": status,
            "final_message": content if status == "COMPLETE" else "",
            "raw": str(response_dict.get("raw_response"))
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Error communicating with Gemini: {str(e)}"}

import threading
from tools.logger import action_logger

@action_logger("schedule")
def schedule(duration_seconds: int, prompt: str) -> str:
    """Schedules a timer to remind you about something after duration_seconds."""
    def reminder():
        msg = f"⏰ **[TIMER ALERT]** {prompt}"
        print(f"\n\n\033[93m{msg}\033[0m\n\n")
        try:
            from backend import state
            state.emit_event({
                "event": "timer",
                "agent_id": "main",
                "prompt": prompt,
            })
        except Exception as e:
            print(f"Timer broadcast failed: {e}")
        try:
            import backend.main as main_app
            main_app.chat_history.append(f"System: [TIMER ALERT] {prompt}")
        except Exception:
            pass

    t = threading.Timer(duration_seconds, reminder)
    t.daemon = True
    t.start()
    return f"Timer set for {duration_seconds} seconds. You will be reminded with: '{prompt}'"

@action_logger("ask_user")
def ask_user(question: str, options: list = None, is_multi_select: bool = False, allow_custom: bool = True) -> str:
    """Ask the user a question or seek clarification. The agent loop pauses until the user responds.

    Args:
        question: The question to ask.
        options: Optional list of choices for the user to select from.
        is_multi_select: If true, the user can pick multiple options.
        allow_custom: If true, the user can type a custom response even when options are provided.
    """
    from backend.interaction_manager import request_user_input
    from backend import event_bus

    result = request_user_input(
        agent_id=event_bus.current_agent(),
        question=question,
        options=options,
        is_multi_select=is_multi_select,
        allow_custom=allow_custom,
    )
    return f"User responded: {result}"

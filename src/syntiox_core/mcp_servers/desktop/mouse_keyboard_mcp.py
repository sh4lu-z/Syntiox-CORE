import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Desktop-Control-Tools")

try:
    import pyautogui
    pyautogui.FAILSAFE = True
except Exception:
    pyautogui = None


@mcp.tool()
def mouse_action(action: str, x: int = 0, y: int = 0, button: str = "left", clicks: int = 1, duration: float = 0.5) -> str:
    """Control mouse cursor and actions. Actions: 'position', 'move', 'click', 'double_click', 'right_click', 'drag'."""
    if pyautogui is None:
        return "Error: pyautogui is not installed."

    action_clean = (action or "").strip().lower()

    try:
        if action_clean in ("position", "get_position", "coords"):
            curr_x, curr_y = pyautogui.position()
            return f"Current mouse position: x={curr_x}, y={curr_y}"

        elif action_clean == "move":
            pyautogui.moveTo(x, y, duration=duration)
            return f"Mouse moved to ({x}, {y}) over {duration}s."

        elif action_clean == "click":
            if x != 0 or y != 0:
                pyautogui.click(x=x, y=y, button=button, clicks=clicks)
                return f"Mouse clicked {clicks} times with {button} button at ({x}, {y})."
            pyautogui.click(button=button, clicks=clicks)
            return f"Mouse clicked {clicks} times with {button} button at current position."

        elif action_clean == "double_click":
            if x != 0 or y != 0:
                pyautogui.doubleClick(x=x, y=y)
                return f"Double-clicked at ({x}, {y})."
            pyautogui.doubleClick()
            return "Double-clicked at current position."

        elif action_clean == "right_click":
            if x != 0 or y != 0:
                pyautogui.rightClick(x=x, y=y)
                return f"Right-clicked at ({x}, {y})."
            pyautogui.rightClick()
            return "Right-clicked at current position."

        elif action_clean == "drag":
            pyautogui.dragTo(x, y, duration=duration, button=button)
            return f"Mouse dragged to ({x}, {y}) with {button} button."

        else:
            return f"Unknown mouse action '{action}'. Valid actions: position, move, click, double_click, right_click, drag."
    except Exception as e:
        return f"Mouse action failed: {e}"


@mcp.tool()
def keyboard_action(action: str, text: str = "", key: str = "", keys: list = None, interval: float = 0.05) -> str:
    """Control keyboard typing, key presses, and shortcuts. Actions: 'type', 'press', 'hotkey'."""
    if pyautogui is None:
        return "Error: pyautogui is not installed."

    action_clean = (action or "").strip().lower()

    try:
        if action_clean in ("type", "write"):
            if not text:
                return "Error: 'text' parameter is required for type action."
            pyautogui.write(text, interval=interval)
            return f"Typed text: '{text}'"

        elif action_clean in ("press", "key"):
            target_key = (key or "").strip()
            if not target_key and text:
                target_key = text.strip()
            if not target_key:
                return "Error: 'key' parameter is required for press action."
            pyautogui.press(target_key)
            return f"Pressed key: '{target_key}'"

        elif action_clean in ("hotkey", "shortcut"):
            combo = keys or []
            if not combo and key:
                combo = [k.strip() for k in key.split("+") if k.strip()]
            if not combo and text:
                combo = [k.strip() for k in text.split("+") if k.strip()]
            if not combo:
                return "Error: 'keys' list or 'key' combo string is required for hotkey action."
            pyautogui.hotkey(*combo)
            return f"Pressed hotkey combination: {combo}"

        else:
            return f"Unknown keyboard action '{action}'. Valid actions: type, press, hotkey."
    except Exception as e:
        return f"Keyboard action failed: {e}"


@mcp.tool()
def take_screenshot() -> str:
    """Takes a full desktop screenshot and saves it to scratch."""
    if pyautogui is None:
        return "Error: pyautogui is not installed."

    try:
        from backend.config_paths import SCRATCH_DIR
        out_dir = SCRATCH_DIR
    except Exception:
        out_dir = os.getcwd()

    try:
        os.makedirs(out_dir, exist_ok=True)
        screenshot_path = os.path.join(out_dir, "desktop_view.png")
        pyautogui.screenshot(screenshot_path)
        return f"[IMAGE_RESULT] {screenshot_path}\nDesktop screenshot taken successfully."
    except Exception as e:
        return f"Failed to take screenshot: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")

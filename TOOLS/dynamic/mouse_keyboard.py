import os
try:
    import pyautogui
except ImportError:
    # Fallback if not installed, though user needs to run: pip install pyautogui
    pass

# Configure PyAutoGUI to be safe (stops if mouse is pushed to a corner)
pyautogui.FAILSAFE = True

def get_mouse_position() -> dict:
    """
    Get the current X and Y coordinates of the mouse cursor.
    Returns a dictionary with 'x' and 'y' keys.
    """
    x, y = pyautogui.position()
    return {"x": x, "y": y}

def move_mouse(x: int, y: int, duration: float = 0.5) -> str:
    """
    Move the mouse cursor to the specified X and Y screen coordinates.
    The duration specifies how long (in seconds) the movement should take.
    """
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse moved to ({x}, {y}) over {duration} seconds."

def click_mouse(button: str = "left", clicks: int = 1) -> str:
    """
    Click the mouse at the current position. 
    button: 'left', 'right', or 'middle'.
    clicks: Number of times to click (default is 1).
    """
    pyautogui.click(button=button, clicks=clicks)
    return f"Mouse clicked {clicks} times using {button} button."

def type_text(text: str, interval: float = 0.05) -> str:
    """
    Type the given text using the keyboard.
    interval: Time in seconds between each keystroke (default 0.05).
    """
    pyautogui.write(text, interval=interval)
    return f"Typed text: '{text}'"

def press_key(key: str) -> str:
    """
    Press a specific keyboard key (e.g., 'enter', 'esc', 'tab', 'win', 'ctrl', 'alt', 'space').
    """
    pyautogui.press(key)
    return f"Pressed key: '{key}'"

def hotkey(keys: list) -> str:
    """
    Press a combination of keys at the same time (e.g., ["ctrl", "c"] to copy).
    """
    pyautogui.hotkey(*keys)
    return f"Pressed hotkey combination: {keys}"

def take_screenshot() -> str:
    """
    Takes a screenshot of the entire desktop and returns it to the agent.
    Use this to visually see where to move the mouse or what is on the screen.
    """
    try:
        import pyautogui
        import os
        screenshot_path = os.path.join(os.getcwd(), "desktop_view.png")
        pyautogui.screenshot(screenshot_path)
        # Main agent will intercept [IMAGE_RESULT] and process the image
        return f"[IMAGE_RESULT] {screenshot_path}\nDesktop screenshot taken successfully."
    except Exception as e:
        return f"Failed to take screenshot: {str(e)}"

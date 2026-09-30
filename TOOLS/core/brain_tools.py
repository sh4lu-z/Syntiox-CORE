from TOOLS.core.logger import action_logger
from backend.session_manager import create_new_brain_folder

@action_logger("create_project_brain")
def create_project_brain(project_name: str) -> str:
    """
    Creates a new brain memory folder for a complex multi-step project.
    Always use this tool when starting a new large project instead of saving to the default workspace.
    Returns the absolute path to the new brain folder. Save your task.md and walkthrough.md there!
    """
    try:
        brain_path = create_new_brain_folder(project_name)
        return f"Successfully created new project brain. You MUST write your task.md and walkthrough.md files directly to this path:\n{brain_path}"
    except Exception as e:
        return f"Error creating brain folder: {str(e)}"

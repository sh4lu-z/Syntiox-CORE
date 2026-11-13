import os
import shutil
import zipfile
from tools.logger import action_logger

@action_logger("manage_archive")
def manage_archive(action: str, path: str, destination: str = "") -> str:
    """
    Creates or extracts ZIP archives.
    
    Args:
        action: The operation to perform ('create' or 'extract').
        path: For 'create', the source directory to compress. For 'extract', the path to the .zip file.
        destination: For 'create', the output .zip file path. For 'extract', the target directory to extract into (defaults to current directory).
    """
    act = (action or "").strip().lower()
    if act in ("create", "zip", "compress"):
        source_dir = path.strip()
        output_zip = (destination or f"{source_dir}.zip").strip()
        if not os.path.exists(source_dir):
            return f"Error: Source directory '{source_dir}' does not exist."
        if not os.path.isdir(source_dir):
            return f"Error: '{source_dir}' is not a directory."
            
        if not output_zip.endswith(".zip"):
            output_zip += ".zip"
            
        try:
            base_name = output_zip[:-4]
            shutil.make_archive(base_name, "zip", source_dir)
            return f"Success: Created ZIP archive at '{output_zip}'"
        except Exception as e:
            return f"Error creating ZIP: {str(e)}"

    elif act in ("extract", "unzip", "decompress"):
        zip_path = path.strip()
        extract_to = (destination or ".").strip()
        if not os.path.exists(zip_path):
            return f"Error: ZIP file '{zip_path}' does not exist."
        if not zipfile.is_zipfile(zip_path):
            return f"Error: '{zip_path}' is not a valid ZIP file."
            
        try:
            os.makedirs(os.path.abspath(extract_to), exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_to)
            return f"Success: Extracted '{zip_path}' into '{extract_to}'"
        except Exception as e:
            return f"Error extracting ZIP: {str(e)}"
    else:
        return f"Error: Unknown action '{action}'. Supported actions: 'create', 'extract'."

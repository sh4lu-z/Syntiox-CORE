import os
import shutil
import zipfile
from TOOLS.logger import action_logger

@action_logger("create_zip")
def create_zip(source_dir: str, output_zip: str) -> str:
    """
    Compresses a directory into a ZIP file.
    
    Args:
        source_dir: The path to the folder you want to zip.
        output_zip: The path where the output .zip file should be saved.
    """
    if not os.path.exists(source_dir):
        return f"Error: Source directory '{source_dir}' does not exist."
    if not os.path.isdir(source_dir):
        return f"Error: '{source_dir}' is not a directory."
        
    # Ensure output has .zip extension
    if not output_zip.endswith('.zip'):
        output_zip += '.zip'
        
    try:
        # shutil.make_archive automatically adds .zip, so we strip it for the base name
        base_name = output_zip[:-4]
        shutil.make_archive(base_name, 'zip', source_dir)
        return f"Success: Created ZIP archive at '{output_zip}'"
    except Exception as e:
        return f"Error creating ZIP: {str(e)}"

@action_logger("extract_zip")
def extract_zip(zip_path: str, extract_to: str = ".") -> str:
    """
    Extracts a ZIP file into a specified directory.
    
    Args:
        zip_path: The path to the .zip file.
        extract_to: The directory where contents should be extracted. Defaults to current directory.
    """
    if not os.path.exists(zip_path):
        return f"Error: ZIP file '{zip_path}' does not exist."
    if not zipfile.is_zipfile(zip_path):
        return f"Error: '{zip_path}' is not a valid ZIP file."
        
    try:
        os.makedirs(os.path.abspath(extract_to), exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return f"Success: Extracted '{zip_path}' into '{extract_to}'"
    except Exception as e:
        return f"Error extracting ZIP: {str(e)}"

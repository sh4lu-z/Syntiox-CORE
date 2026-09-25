import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_sheets_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "google", "sheets_handlers.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("list_spreadsheets")
def list_spreadsheets(max_results: int = 10) -> str:
    """List Google Spreadsheets in Drive."""
    return _run_sheets_mcp("list_spreadsheets", {"max_results": max_results})

@action_logger("create_spreadsheet")
def create_spreadsheet(title: str) -> str:
    """Create a new Google Spreadsheet."""
    return _run_sheets_mcp("create_spreadsheet", {"title": title})

@action_logger("read_sheet_data")
def read_sheet_data(spreadsheet_id: str, range_name: str = 'Sheet1!A1:Z100') -> str:
    """Get cell data from a Google Sheet."""
    return _run_sheets_mcp("read_sheet_data", {"spreadsheet_id": spreadsheet_id, "range_name": range_name})

@action_logger("write_sheet_data")
def write_sheet_data(spreadsheet_id: str, range_name: str, values_json: str) -> str:
    """Google Sheet cells ලෙ data ලියයි / edit cells / update range.
Use when user says: 'write to sheet', 'update cells', 'edit cell', 'sheet ලෙ දාන්න', 'sheet එකේ ලියන්න'.
values_json: JSON 2D array — e.g. '[["Name","Age"],["Alice","25"]]'"""
    return _run_sheets_mcp("write_sheet_data", {"spreadsheet_id": spreadsheet_id, "range_name": range_name, "values_json": values_json})

@action_logger("update_single_cell")
def update_single_cell(spreadsheet_id: str, cell_range: str, value: str) -> str:
    """Update a single cell in a Google Sheet."""
    return _run_sheets_mcp("update_single_cell", {"spreadsheet_id": spreadsheet_id, "cell_range": cell_range, "value": value})

@action_logger("update_cells_batch")
def update_cells_batch(spreadsheet_id: str, batch_json: str) -> str:
    """Batch update multiple ranges in a Google Sheet using JSON mapping."""
    return _run_sheets_mcp("update_cells_batch", {"spreadsheet_id": spreadsheet_id, "batch_json": batch_json})

@action_logger("read_sheet_ranges_batch")
def read_sheet_ranges_batch(spreadsheet_id: str, ranges_csv: str) -> str:
    """Batch read multiple ranges in a Google Sheet."""
    return _run_sheets_mcp("read_sheet_ranges_batch", {"spreadsheet_id": spreadsheet_id, "ranges_csv": ranges_csv})

@action_logger("append_row_to_sheet")
def append_row_to_sheet(spreadsheet_id: str, sheet_name: str, row_values_json: str) -> str:
    """Append a new row to a Google Sheet. Expects row_values_json as a JSON array (e.g. '["Val1", "Val2"]')."""
    return _run_sheets_mcp("append_row_to_sheet", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name, "row_values_json": row_values_json})

@action_logger("get_sheet_names")
def get_sheet_names(spreadsheet_id: str) -> str:
    """List all sheet tabs in a Spreadsheet."""
    return _run_sheets_mcp("get_sheet_names", {"spreadsheet_id": spreadsheet_id})

@action_logger("clear_sheet_range")
def clear_sheet_range(spreadsheet_id: str, range_name: str) -> str:
    """Clear a specific range in a Google Sheet."""
    return _run_sheets_mcp("clear_sheet_range", {"spreadsheet_id": spreadsheet_id, "range_name": range_name})

@action_logger("find_replace_in_sheet")
def find_replace_in_sheet(spreadsheet_id: str, sheet_id: int, find_text: str, replace_text: str) -> str:
    """Find and replace text in a specific sheet tab."""
    return _run_sheets_mcp("find_replace_in_sheet", {"spreadsheet_id": spreadsheet_id, "sheet_id": sheet_id, "find_text": find_text, "replace_text": replace_text})

@action_logger("add_sheet_tab")
def add_sheet_tab(spreadsheet_id: str, tab_name: str) -> str:
    """Add a new sheet tab to a Spreadsheet."""
    return _run_sheets_mcp("add_sheet_tab", {"spreadsheet_id": spreadsheet_id, "tab_name": tab_name})

@action_logger("delete_sheet_tab")
def delete_sheet_tab(spreadsheet_id: str, sheet_name: str) -> str:
    """Delete a sheet tab."""
    return _run_sheets_mcp("delete_sheet_tab", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name})

@action_logger("rename_sheet_tab")
def rename_sheet_tab(spreadsheet_id: str, old_name: str, new_name: str) -> str:
    """Rename a sheet tab."""
    return _run_sheets_mcp("rename_sheet_tab", {"spreadsheet_id": spreadsheet_id, "old_name": old_name, "new_name": new_name})

@action_logger("duplicate_sheet_tab")
def duplicate_sheet_tab(spreadsheet_id: str, sheet_name: str, new_name: str = '') -> str:
    """Duplicate a sheet tab."""
    return _run_sheets_mcp("duplicate_sheet_tab", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name, "new_name": new_name})

@action_logger("format_sheet_cells")
def format_sheet_cells(spreadsheet_id: str, sheet_name: str, start_row: int, start_col: int, end_row: int, end_col: int, bold: bool = False, bg_color_hex: str = '') -> str:
    """Format cells (bold, background color)."""
    return _run_sheets_mcp("format_sheet_cells", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name, "start_row": start_row, "start_col": start_col, "end_row": end_row, "end_col": end_col, "bold": bold, "bg_color_hex": bg_color_hex})

@action_logger("auto_resize_columns")
def auto_resize_columns(spreadsheet_id: str, sheet_name: str, start_col: int, end_col: int) -> str:
    """Auto-resize columns."""
    return _run_sheets_mcp("auto_resize_columns", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name, "start_col": start_col, "end_col": end_col})

@action_logger("sort_sheet_range")
def sort_sheet_range(spreadsheet_id: str, sheet_name: str, start_row: int, end_row: int, start_col: int, end_col: int, sort_column_index: int, ascending: bool = True) -> str:
    """Sort a range based on a specific column index."""
    return _run_sheets_mcp("sort_sheet_range", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name, "start_row": start_row, "end_row": end_row, "start_col": start_col, "end_col": end_col, "sort_column_index": sort_column_index, "ascending": ascending})

@action_logger("copy_spreadsheet")
def copy_spreadsheet(spreadsheet_id: str, new_title: str) -> str:
    """Duplicate/copy a Spreadsheet file."""
    return _run_sheets_mcp("copy_spreadsheet", {"spreadsheet_id": spreadsheet_id, "new_title": new_title})

@action_logger("share_spreadsheet")
def share_spreadsheet(spreadsheet_id: str, email: str, role: str = 'reader') -> str:
    """Share a Spreadsheet via email."""
    return _run_sheets_mcp("share_spreadsheet", {"spreadsheet_id": spreadsheet_id, "email": email, "role": role})

@action_logger("delete_spreadsheet")
def delete_spreadsheet(spreadsheet_id: str) -> str:
    """Permanently delete a Spreadsheet."""
    return _run_sheets_mcp("delete_spreadsheet", {"spreadsheet_id": spreadsheet_id})

@action_logger("get_first_empty_row")
def get_first_empty_row(spreadsheet_id: str, sheet_name: str, column: str = 'A') -> str:
    """Finds the first empty row in a specific column."""
    return _run_sheets_mcp("get_first_empty_row", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name, "column": column})

@action_logger("delete_rows")
def delete_rows(spreadsheet_id: str, sheet_name: str, start_row_index: int, end_row_index: int) -> str:
    """Deletes rows from start_row_index to end_row_index (0-based, end_row_index is exclusive)."""
    return _run_sheets_mcp("delete_rows", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name, "start_row_index": start_row_index, "end_row_index": end_row_index})

@action_logger("delete_columns")
def delete_columns(spreadsheet_id: str, sheet_name: str, start_col_index: int, end_col_index: int) -> str:
    """Deletes columns from start_col_index to end_col_index (0-based, end_col_index is exclusive)."""
    return _run_sheets_mcp("delete_columns", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name, "start_col_index": start_col_index, "end_col_index": end_col_index})

@action_logger("clear_formatting")
def clear_formatting(spreadsheet_id: str, sheet_name: str, start_row: int, end_row: int, start_col: int, end_col: int) -> str:
    """Clears all formatting (colors, bold, etc) from a specific range."""
    return _run_sheets_mcp("clear_formatting", {"spreadsheet_id": spreadsheet_id, "sheet_name": sheet_name, "start_row": start_row, "end_row": end_row, "start_col": start_col, "end_col": end_col})

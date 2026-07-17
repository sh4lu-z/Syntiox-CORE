"""
📊 Google Sheets Handler Tools
docs.google.com/spreadsheets
"""
import json
from mcp.server.fastmcp import FastMCP
from google_common import get_service, share_file

mcp = FastMCP("Google-Sheets-Tools")


def _sheets():
    return get_service('sheets', 'v4')


def _drive():
    return get_service('drive', 'v3')


def _sheet_id_by_name(spreadsheet_id: str, sheet_name: str) -> int:
    meta = _sheets().spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for s in meta.get('sheets', []):
        p = s.get('properties', {})
        if p.get('title') == sheet_name:
            return p['sheetId']
    raise ValueError(f"Sheet tab '{sheet_name}' not found")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LIST / CREATE / READ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def list_spreadsheets(max_results: int = 10) -> str:
    """List Google Spreadsheets in Drive."""
    try:
        svc = _drive()
        results = svc.files().list(
            q="mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
            pageSize=max_results,
            fields="files(id, name, modifiedTime, webViewLink)"
        ).execute()
        files = results.get('files', [])
        if not files:
            return "📊 No spreadsheets found."
        output = f"📊 GOOGLE SHEETS — {len(files)} SPREADSHEETS\n{'─'*40}\n"
        for f in files:
            output += (
                f"📊 {f['name']}\n"
                f"   🕐 Modified : {f.get('modifiedTime','')[:10]}\n"
                f"   🔗 Link     : {f.get('webViewLink','N/A')}\n"
                f"   🔑 ID       : {f['id']}\n"
                f"{'─'*40}\n"
            )
        return output
    except Exception as e:
        return f"❌ Error listing spreadsheets: {e}"


@mcp.tool()
def create_spreadsheet(title: str) -> str:
    """Create a new Google Spreadsheet."""
    try:
        result = _sheets().spreadsheets().create(body={'properties': {'title': title}}).execute()
        sid = result['spreadsheetId']
        link = f"https://docs.google.com/spreadsheets/d/{sid}/edit"
        return (
            f"✅ Spreadsheet '{title}' created!\n"
            f"   🔑 ID   : {sid}\n"
            f"   🔗 Link : {link}\n"
            f"   💡 Use this ID for update/delete/share tools."
        )
    except Exception as e:
        return f"❌ Error creating spreadsheet: {e}"


@mcp.tool()
def read_sheet_data(spreadsheet_id: str, range_name: str = "Sheet1!A1:Z100") -> str:
    """Get cell data from a Google Sheet."""
    spreadsheet_id = spreadsheet_id.strip()
    if not spreadsheet_id:
        return "❌ spreadsheet_id cannot be empty."
    try:
        result = _sheets().spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name
        ).execute()
        values = result.get('values', [])
        if not values:
            return f"📊 Range '{range_name}' contains no data."
        output = f"📊 SHEET DATA — {range_name}\n{'─'*40}\n"
        for i, row in enumerate(values[:50], 1):
            output += f"  Row {i:02}: {' | '.join(str(c) for c in row)}\n"
        if len(values) > 50:
            output += f"  ... (total {len(values)} rows)\n"
        return output
    except Exception as e:
        return f"❌ Error reading sheet: {e}"


@mcp.tool()
def write_sheet_data(spreadsheet_id: str, range_name: str, values_json: str) -> str:
    """
    Google Sheet cells ලෙ data ලියයි / edit cells / update range.
    Use when user says: 'write to sheet', 'update cells', 'edit cell', 'sheet ලෙ දාන්න', 'sheet එකේ ලියන්න'.
    values_json: JSON 2D array — e.g. '[["Name","Age"],["Alice","25"]]'
    """
    spreadsheet_id = spreadsheet_id.strip()
    if not spreadsheet_id:
        return "❌ spreadsheet_id cannot be empty."
    try:
        values = json.loads(values_json)
        result = _sheets().spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body={'values': values}
        ).execute()
        updated = result.get('updatedCells', 0)
        return f"✅ {updated} cells Sheet '{range_name}' written to."
    except json.JSONDecodeError:
        return '❌ values_json invalid JSON. Example: [["Name","Age"],["Alice","25"]]'
    except Exception as e:
        return f"❌ Error writing to sheet: {e}"


@mcp.tool()
def update_single_cell(spreadsheet_id: str, cell_range: str, value: str) -> str:
    """Update a single cell in a Google Sheet."""
    spreadsheet_id = spreadsheet_id.strip()
    if not spreadsheet_id:
        return "❌ spreadsheet_id cannot be empty."
    try:
        result = _sheets().spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=cell_range,
            valueInputOption='USER_ENTERED',
            body={'values': [[value]]}
        ).execute()
        return f"✅ Cell '{cell_range}' = '{value}' ({result.get('updatedCells', 1)} cell)."
    except Exception as e:
        return f"❌ Error updating cell: {e}"


@mcp.tool()
def update_cells_batch(spreadsheet_id: str, batch_json: str) -> str:
    """Batch update multiple ranges in a Google Sheet using JSON mapping."""
    try:
        data = json.loads(batch_json)
        if isinstance(data, dict):
            value_ranges = [
                {'range': k, 'values': [[v]] if not isinstance(v, list) else v}
                for k, v in data.items()
            ]
        else:
            value_ranges = data
        result = _sheets().spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'valueInputOption': 'USER_ENTERED', 'data': value_ranges}
        ).execute()
        total = result.get('totalUpdatedCells', 0)
        return f"✅ Batch update: {total} cells updated."
    except json.JSONDecodeError:
        return "❌ batch_json invalid JSON."
    except Exception as e:
        return f"❌ Error in batch update: {e}"


@mcp.tool()
def read_sheet_ranges_batch(spreadsheet_id: str, ranges_csv: str) -> str:
    """Batch read multiple ranges in a Google Sheet."""
    try:
        ranges = [r.strip() for r in ranges_csv.split(',') if r.strip()]
        result = _sheets().spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id, ranges=ranges
        ).execute()
        output = f"📊 BATCH READ — {len(ranges)} ranges\n{'─'*40}\n"
        for vr in result.get('valueRanges', []):
            output += f"\n📋 {vr.get('range', '?')}:\n"
            for row in vr.get('values', [])[:20]:
                output += f"  {' | '.join(str(c) for c in row)}\n"
        return output
    except Exception as e:
        return f"❌ Error in batch read: {e}"


@mcp.tool()
def append_row_to_sheet(spreadsheet_id: str, sheet_name: str, row_values_json: str) -> str:
    """Append a new row to a Google Sheet. Expects row_values_json as a JSON array (e.g. '["Val1", "Val2"]')."""
    spreadsheet_id = spreadsheet_id.strip()
    try:
        row = json.loads(row_values_json)
        if not isinstance(row, list):
            return "❌ row_values_json must be a JSON array."

        result = _sheets().spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=sheet_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body={'values': [row]}
        ).execute()
        updated_range = result.get('updates', {}).get('updatedRange', '')
        return f"✅ Row appended successfully. ({updated_range})"
    except Exception as e:
        return f"❌ Error appending row: {e}"


@mcp.tool()
def get_sheet_names(spreadsheet_id: str) -> str:
    """List all sheet tabs in a Spreadsheet."""
    try:
        result = _sheets().spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = result.get('sheets', [])
        title = result.get('properties', {}).get('title', 'Unknown')
        output = f"📊 '{title}' SHEET TABS\n{'─'*30}\n"
        for s in sheets:
            p = s.get('properties', {})
            output += f"  📋 {p.get('title','?')}  (Index: {p.get('index',0)}, ID: {p.get('sheetId','')})\n"
        return output
    except Exception as e:
        return f"❌ Error getting sheet names: {e}"


@mcp.tool()
def clear_sheet_range(spreadsheet_id: str, range_name: str) -> str:
    """Clear a specific range in a Google Sheet."""
    try:
        _sheets().spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range=range_name
        ).execute()
        return f"🧹 Range '{range_name}' cleared."
    except Exception as e:
        return f"❌ Error clearing range: {e}"


@mcp.tool()
def find_replace_in_sheet(spreadsheet_id: str, sheet_id: int, find_text: str, replace_text: str) -> str:
    """Find and replace text in a specific sheet tab."""
    try:
        result = _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'findReplace': {
                    'find': find_text,
                    'replacement': replace_text,
                    'sheetId': sheet_id,
                    'matchCase': False,
                    'allSheets': False,
                }
            }]}
        ).execute()
        reps = result.get('replies', [{}])[0].get('findReplace', {}).get('occurrencesChanged', 0)
        return f"✅ Replaced {reps} occurrence(s): '{find_text}' → '{replace_text}'."
    except Exception as e:
        return f"❌ Error in find/replace: {e}"


@mcp.tool()
def add_sheet_tab(spreadsheet_id: str, tab_name: str) -> str:
    """Add a new sheet tab to a Spreadsheet."""
    try:
        result = _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{'addSheet': {'properties': {'title': tab_name}}}]}
        ).execute()
        sid = result['replies'][0]['addSheet']['properties']['sheetId']
        return f"✅ Tab '{tab_name}' added (sheetId: {sid})."
    except Exception as e:
        return f"❌ Error adding tab: {e}"


@mcp.tool()
def delete_sheet_tab(spreadsheet_id: str, sheet_name: str) -> str:
    """Delete a sheet tab."""
    try:
        sid = _sheet_id_by_name(spreadsheet_id, sheet_name)
        _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{'deleteSheet': {'sheetId': sid}}]}
        ).execute()
        return f"🗑️ Tab '{sheet_name}' deleted."
    except Exception as e:
        return f"❌ Error deleting tab: {e}"


@mcp.tool()
def rename_sheet_tab(spreadsheet_id: str, old_name: str, new_name: str) -> str:
    """Rename a sheet tab."""
    try:
        sid = _sheet_id_by_name(spreadsheet_id, old_name)
        _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'updateSheetProperties': {
                    'properties': {'sheetId': sid, 'title': new_name},
                    'fields': 'title',
                }
            }]}
        ).execute()
        return f"✅ Tab renamed: '{old_name}' → '{new_name}'."
    except Exception as e:
        return f"❌ Error renaming tab: {e}"


@mcp.tool()
def duplicate_sheet_tab(spreadsheet_id: str, sheet_name: str, new_name: str = "") -> str:
    """Duplicate a sheet tab."""
    try:
        sid = _sheet_id_by_name(spreadsheet_id, sheet_name)
        req = {'duplicateSheet': {'sourceSheetId': sid}}
        if new_name:
            req['duplicateSheet']['newSheetName'] = new_name
        result = _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={'requests': [{'duplicateSheet': req['duplicateSheet']}]}
        ).execute()
        new_sid = result['replies'][0]['duplicateSheet']['properties']['sheetId']
        return f"✅ Tab duplicated (new sheetId: {new_sid})."
    except Exception as e:
        return f"❌ Error duplicating tab: {e}"


@mcp.tool()
def format_sheet_cells(
    spreadsheet_id: str,
    sheet_name: str,
    start_row: int,
    start_col: int,
    end_row: int,
    end_col: int,
    bold: bool = False,
    bg_color_hex: str = "",
) -> str:
    """Format cells (bold, background color)."""
    try:
        sid = _sheet_id_by_name(spreadsheet_id, sheet_name)
        fmt = {}
        fields = []
        if bold:
            fmt['textFormat'] = {'bold': True}
            fields.append('userEnteredFormat.textFormat.bold')
        if bg_color_hex and bg_color_hex.startswith('#') and len(bg_color_hex) == 7:
            r = int(bg_color_hex[1:3], 16) / 255
            g = int(bg_color_hex[3:5], 16) / 255
            b = int(bg_color_hex[5:7], 16) / 255
            fmt['backgroundColor'] = {'red': r, 'green': g, 'blue': b}
            fields.append('userEnteredFormat.backgroundColor')
        if not fields:
            return "❌ Specify bold=True and/or bg_color_hex='#RRGGBB'."
        _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'repeatCell': {
                    'range': {
                        'sheetId': sid,
                        'startRowIndex': start_row,
                        'endRowIndex': end_row + 1,
                        'startColumnIndex': start_col,
                        'endColumnIndex': end_col + 1,
                    },
                    'cell': {'userEnteredFormat': fmt},
                    'fields': ','.join(fields),
                }
            }]}
        ).execute()
        return f"✅ Formatted range on '{sheet_name}'."
    except Exception as e:
        return f"❌ Error formatting cells: {e}"


@mcp.tool()
def auto_resize_columns(spreadsheet_id: str, sheet_name: str, start_col: int, end_col: int) -> str:
    """Auto-resize columns."""
    try:
        sid = _sheet_id_by_name(spreadsheet_id, sheet_name)
        _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'autoResizeDimensions': {
                    'dimensions': {
                        'sheetId': sid,
                        'dimension': 'COLUMNS',
                        'startIndex': start_col,
                        'endIndex': end_col + 1,
                    }
                }
            }]}
        ).execute()
        return f"✅ Columns {start_col}-{end_col} auto-resized on '{sheet_name}'."
    except Exception as e:
        return f"❌ Error auto-resizing columns: {e}"


@mcp.tool()
def sort_sheet_range(
    spreadsheet_id: str,
    sheet_name: str,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
    sort_column_index: int,
    ascending: bool = True,
) -> str:
    """Sort a range based on a specific column index."""
    try:
        sid = _sheet_id_by_name(spreadsheet_id, sheet_name)
        _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'sortRange': {
                    'range': {
                        'sheetId': sid,
                        'startRowIndex': start_row,
                        'endRowIndex': end_row + 1,
                        'startColumnIndex': start_col,
                        'endColumnIndex': end_col + 1,
                    },
                    'sortSpecs': [{
                        'dimensionIndex': sort_column_index,
                        'sortOrder': 'ASCENDING' if ascending else 'DESCENDING',
                    }],
                }
            }]}
        ).execute()
        return f"✅ Sorted range on '{sheet_name}'."
    except Exception as e:
        return f"❌ Error sorting range: {e}"


@mcp.tool()
def copy_spreadsheet(spreadsheet_id: str, new_title: str) -> str:
    """Duplicate/copy a Spreadsheet file."""
    try:
        result = _drive().files().copy(
            fileId=spreadsheet_id, body={'name': new_title}
        ).execute()
        nid = result['id']
        return (
            f"✅ Copied to '{new_title}'.\n"
            f"   🔑 ID: {nid}\n"
            f"   🔗 https://docs.google.com/spreadsheets/d/{nid}/edit"
        )
    except Exception as e:
        return f"❌ Error copying spreadsheet: {e}"


@mcp.tool()
def share_spreadsheet(spreadsheet_id: str, email: str, role: str = "reader") -> str:
    """Share a Spreadsheet via email."""
    try:
        perm = share_file(spreadsheet_id, email, role)
        return f"✅ Shared with {perm.get('emailAddress', email)} as {perm.get('role', role)}."
    except Exception as e:
        return f"❌ Error sharing spreadsheet: {e}"


@mcp.tool()
def delete_spreadsheet(spreadsheet_id: str) -> str:
    """Permanently delete a Spreadsheet."""
    try:
        _drive().files().delete(fileId=spreadsheet_id).execute()
        return f"🗑️ Spreadsheet (ID: {spreadsheet_id}) deleted."
    except Exception as e:
        return f"❌ Error deleting spreadsheet: {e}"



@mcp.tool()
def get_first_empty_row(spreadsheet_id: str, sheet_name: str, column: str = "A") -> str:
    """Finds the first empty row in a specific column."""
    spreadsheet_id = spreadsheet_id.strip()
    try:
        result = _sheets().spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"{sheet_name}!{column}:{column}"
        ).execute()
        values = result.get('values', [])
        return f"First empty row in column {column} is: {len(values) + 1}"
    except Exception as e:
        return f"❌ Error finding empty row: {e}"

@mcp.tool()
def delete_rows(spreadsheet_id: str, sheet_name: str, start_row_index: int, end_row_index: int) -> str:
    """Deletes rows from start_row_index to end_row_index (0-based, end_row_index is exclusive)."""
    spreadsheet_id = spreadsheet_id.strip()
    try:
        sid = _sheet_id_by_name(spreadsheet_id, sheet_name)
        _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'deleteDimension': {
                    'range': {
                        'sheetId': sid,
                        'dimension': 'ROWS',
                        'startIndex': start_row_index,
                        'endIndex': end_row_index
                    }
                }
            }]}
        ).execute()
        return f"✅ Rows {start_row_index} to {end_row_index-1} deleted."
    except Exception as e:
        return f"❌ Error deleting rows: {e}"

@mcp.tool()
def delete_columns(spreadsheet_id: str, sheet_name: str, start_col_index: int, end_col_index: int) -> str:
    """Deletes columns from start_col_index to end_col_index (0-based, end_col_index is exclusive)."""
    spreadsheet_id = spreadsheet_id.strip()
    try:
        sid = _sheet_id_by_name(spreadsheet_id, sheet_name)
        _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'deleteDimension': {
                    'range': {
                        'sheetId': sid,
                        'dimension': 'COLUMNS',
                        'startIndex': start_col_index,
                        'endIndex': end_col_index
                    }
                }
            }]}
        ).execute()
        return f"✅ Columns {start_col_index} to {end_col_index-1} deleted."
    except Exception as e:
        return f"❌ Error deleting columns: {e}"

@mcp.tool()
def clear_formatting(spreadsheet_id: str, sheet_name: str, start_row: int, end_row: int, start_col: int, end_col: int) -> str:
    """Clears all formatting (colors, bold, etc) from a specific range."""
    spreadsheet_id = spreadsheet_id.strip()
    try:
        sid = _sheet_id_by_name(spreadsheet_id, sheet_name)
        _sheets().spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{
                'updateCells': {
                    'range': {
                        'sheetId': sid,
                        'startRowIndex': start_row,
                        'endRowIndex': end_row + 1,
                        'startColumnIndex': start_col,
                        'endColumnIndex': end_col + 1,
                    },
                    'fields': 'userEnteredFormat'
                }
            }]}
        ).execute()
        return f"✅ Cleared formatting in range."
    except Exception as e:
        return f"❌ Error clearing formatting: {e}"

if __name__ == "__main__":
    mcp.run(transport='stdio')

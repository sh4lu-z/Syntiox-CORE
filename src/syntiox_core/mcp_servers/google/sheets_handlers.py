import json
from mcp.server.fastmcp import FastMCP
from google_common import get_service

mcp = FastMCP("Google-Sheets-Tools")


def _sheets():
    return get_service("sheets", "v4")


def _drive():
    return get_service("drive", "v3")


def _sheet_id_by_name(spreadsheet_id: str, sheet_name: str) -> int:
    meta = _sheets().spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for s in meta.get("sheets", []):
        p = s.get("properties", {})
        if p.get("title") == sheet_name:
            return p["sheetId"]
    raise ValueError(f"Sheet tab '{sheet_name}' not found")


@mcp.tool()
def sheets_data(
    action: str,
    spreadsheet_id: str = "",
    range_name: str = "Sheet1!A1:Z100",
    values_json: str = "",
    ranges_csv: str = "",
    find_text: str = "",
    replace_text: str = "",
    sheet_name: str = "Sheet1",
    column: str = "A",
) -> str:
    """Manage Google Sheet data cells: read, write, append, clear, batch_read, batch_write, find_replace, get_first_empty_row."""
    action_clean = (action or "").strip().lower()
    sid = spreadsheet_id.strip()

    try:
        svc = _sheets()

        if action_clean in ("read", "read_range"):
            if not sid:
                return "Error: 'spreadsheet_id' is required."
            res = svc.spreadsheets().values().get(spreadsheetId=sid, range=range_name).execute()
            values = res.get("values", [])
            if not values:
                return f"Range '{range_name}' contains no data."
            lines = [f"SHEET DATA: {range_name}", "-" * 40]
            for i, row in enumerate(values[:50], 1):
                lines.append(f"  Row {i:02}: {' | '.join(str(c) for c in row)}")
            if len(values) > 50:
                lines.append(f"  ... ({len(values)} rows total)")
            return "\n".join(lines)

        elif action_clean in ("write", "update"):
            if not sid or not values_json:
                return "Error: 'spreadsheet_id' and 'values_json' (e.g. '[[\"a\",\"b\"]]') are required."
            vals = json.loads(values_json)
            res = svc.spreadsheets().values().update(
                spreadsheetId=sid, range=range_name, valueInputOption="USER_ENTERED", body={"values": vals}
            ).execute()
            return f"Wrote to '{range_name}'. Updated {res.get('updatedCells', 0)} cells."

        elif action_clean == "append":
            if not sid or not values_json:
                return "Error: 'spreadsheet_id' and 'values_json' (e.g. '[\"a\", \"b\"]' or '[[\"a\", \"b\"]]') are required."
            parsed = json.loads(values_json)
            rows = [parsed] if isinstance(parsed, list) and (not parsed or not isinstance(parsed[0], list)) else parsed
            res = svc.spreadsheets().values().append(
                spreadsheetId=sid, range=sheet_name or range_name, valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS", body={"values": rows}
            ).execute()
            return f"Row(s) appended successfully. Updated range: {res.get('updates', {}).get('updatedRange', '')}"

        elif action_clean == "clear":
            if not sid:
                return "Error: 'spreadsheet_id' is required."
            svc.spreadsheets().values().clear(spreadsheetId=sid, range=range_name).execute()
            return f"Range '{range_name}' cleared."

        elif action_clean == "batch_read":
            if not sid or not ranges_csv:
                return "Error: 'spreadsheet_id' and 'ranges_csv' (e.g. 'Sheet1!A1:B5,Sheet1!C1:D5') are required."
            ranges = [r.strip() for r in ranges_csv.split(",") if r.strip()]
            res = svc.spreadsheets().values().batchGet(spreadsheetId=sid, ranges=ranges).execute()
            lines = [f"BATCH READ - {len(ranges)} ranges", "-" * 40]
            for vr in res.get("valueRanges", []):
                lines.append(f"\nRange: {vr.get('range', '?')}")
                for r in vr.get("values", [])[:20]:
                    lines.append(f"  {' | '.join(str(c) for c in r)}")
            return "\n".join(lines)

        elif action_clean == "batch_write":
            if not sid or not values_json:
                return "Error: 'spreadsheet_id' and 'values_json' (JSON dict of range -> values or list of ValueRanges) are required."
            data = json.loads(values_json)
            if isinstance(data, dict):
                value_ranges = [{"range": k, "values": [[v]] if not isinstance(v, list) else v} for k, v in data.items()]
            else:
                value_ranges = data
            res = svc.spreadsheets().values().batchUpdate(
                spreadsheetId=sid, body={"valueInputOption": "USER_ENTERED", "data": value_ranges}
            ).execute()
            return f"Batch update complete: {res.get('totalUpdatedCells', 0)} cells updated."

        elif action_clean == "find_replace":
            if not sid or not find_text:
                return "Error: 'spreadsheet_id' and 'find_text' are required."
            sh_id = _sheet_id_by_name(sid, sheet_name)
            res = svc.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={"requests": [{"findReplace": {"find": find_text, "replacement": replace_text or "", "sheetId": sh_id, "matchCase": False, "allSheets": False}}]}
            ).execute()
            repl = res.get("replies", [{}])[0].get("findReplace", {})
            return f"Find & replace complete. Occurrences changed: {repl.get('occurrencesChanged', 0)}."

        elif action_clean == "get_first_empty_row":
            if not sid:
                return "Error: 'spreadsheet_id' is required."
            res = svc.spreadsheets().values().get(spreadsheetId=sid, range=f"{sheet_name}!{column}:{column}").execute()
            vals = res.get("values", [])
            return f"First empty row in column {column}: {len(vals) + 1}"

        else:
            return f"Unknown sheet data action '{action}'. Valid actions: read, write, append, clear, batch_read, batch_write, find_replace, get_first_empty_row."

    except Exception as e:
        return f"Sheet data operation failed: {e}"


@mcp.tool()
def sheets_manage(
    action: str,
    spreadsheet_id: str = "",
    title: str = "",
    tab_name: str = "",
    old_name: str = "",
    new_name: str = "",
    start_row: int = 0,
    end_row: int = 0,
    start_col: int = 0,
    end_col: int = 0,
    bold: bool = False,
    bg_color_hex: str = "",
    text_color_hex: str = "",
    font_size: int = 10,
    sort_column_index: int = 0,
    ascending: bool = True,
    max_results: int = 10,
) -> str:
    """Manage spreadsheets structure: list_spreadsheets, create_spreadsheet, copy_spreadsheet, delete_spreadsheet, get_metadata, list_tabs, add_tab, delete_tab, rename_tab, duplicate_tab, format_cells, delete_rows, delete_columns, clear_formatting, sort_range, auto_resize_columns."""
    action_clean = (action or "").strip().lower()
    sid = spreadsheet_id.strip()

    try:
        svc = _sheets()
        drive_svc = _drive()

        if action_clean in ("list_spreadsheets", "list"):
            res = drive_svc.files().list(
                q="mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
                pageSize=max_results, fields="files(id, name, modifiedTime, webViewLink)"
            ).execute()
            files = res.get("files", [])
            if not files:
                return "No spreadsheets found."
            lines = [f"SPREADSHEETS - {len(files)} FOUND", "-" * 40]
            for f in files:
                lines.append(f"Title: {f['name']} | ID: {f['id']} | Link: {f.get('webViewLink')}")
            return "\n".join(lines)

        elif action_clean in ("create_spreadsheet", "create"):
            name = title or "Untitled Spreadsheet"
            res = svc.spreadsheets().create(body={"properties": {"title": name}}).execute()
            new_id = res["spreadsheetId"]
            return f"Spreadsheet created: '{name}'. ID: {new_id} Link: https://docs.google.com/spreadsheets/d/{new_id}/edit"

        elif action_clean == "copy_spreadsheet":
            if not sid:
                return "Error: 'spreadsheet_id' is required."
            res = drive_svc.files().copy(fileId=sid, body={"name": title or "Copy of Spreadsheet"}).execute()
            return f"Spreadsheet copied. New ID: {res['id']}"

        elif action_clean == "delete_spreadsheet":
            if not sid:
                return "Error: 'spreadsheet_id' is required."
            drive_svc.files().delete(fileId=sid).execute()
            return f"Spreadsheet {sid} permanently deleted."

        elif action_clean in ("get_metadata", "list_tabs", "tabs"):
            if not sid:
                return "Error: 'spreadsheet_id' is required."
            meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
            shs = meta.get("sheets", [])
            lines = [f"Spreadsheet: '{meta.get('properties', {}).get('title')}'", "-" * 35]
            for s in shs:
                p = s.get("properties", {})
                lines.append(f"  Tab: {p.get('title')} (ID: {p.get('sheetId')}, Index: {p.get('index')})")
            return "\n".join(lines)

        elif action_clean == "add_tab":
            if not sid or not tab_name:
                return "Error: 'spreadsheet_id' and 'tab_name' are required."
            res = svc.spreadsheets().batchUpdate(
                spreadsheetId=sid, body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
            ).execute()
            new_tab_id = res["replies"][0]["addSheet"]["properties"]["sheetId"]
            return f"Tab '{tab_name}' added. Sheet ID: {new_tab_id}"

        elif action_clean == "delete_tab":
            if not sid or not tab_name:
                return "Error: 'spreadsheet_id' and 'tab_name' are required."
            sh_id = _sheet_id_by_name(sid, tab_name)
            svc.spreadsheets().batchUpdate(
                spreadsheetId=sid, body={"requests": [{"deleteSheet": {"sheetId": sh_id}}]}
            ).execute()
            return f"Tab '{tab_name}' deleted."

        elif action_clean == "rename_tab":
            target_old = old_name or tab_name
            if not sid or not target_old or not new_name:
                return "Error: 'spreadsheet_id', 'old_name' (or 'tab_name'), and 'new_name' are required."
            sh_id = _sheet_id_by_name(sid, target_old)
            svc.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={"requests": [{"updateSheetProperties": {"properties": {"sheetId": sh_id, "title": new_name}, "fields": "title"}}]}
            ).execute()
            return f"Tab '{target_old}' renamed to '{new_name}'."

        elif action_clean == "duplicate_tab":
            target_tab = tab_name or old_name
            if not sid or not target_tab:
                return "Error: 'spreadsheet_id' and 'tab_name' are required."
            sh_id = _sheet_id_by_name(sid, target_tab)
            req = {"duplicateSheet": {"sourceSheetId": sh_id}}
            if new_name:
                req["duplicateSheet"]["newSheetName"] = new_name
            res = svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [req]}).execute()
            dup_id = res["replies"][0]["duplicateSheet"]["properties"]["sheetId"]
            return f"Tab '{target_tab}' duplicated. New Sheet ID: {dup_id}"

        elif action_clean == "delete_rows":
            if not sid or not tab_name:
                return "Error: 'spreadsheet_id' and 'tab_name' are required."
            sh_id = _sheet_id_by_name(sid, tab_name)
            svc.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={"requests": [{"deleteDimension": {"range": {"sheetId": sh_id, "dimension": "ROWS", "startIndex": start_row, "endIndex": end_row}}}]}
            ).execute()
            return f"Rows {start_row} to {end_row} deleted in '{tab_name}'."

        elif action_clean == "delete_columns":
            if not sid or not tab_name:
                return "Error: 'spreadsheet_id' and 'tab_name' are required."
            sh_id = _sheet_id_by_name(sid, tab_name)
            svc.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={"requests": [{"deleteDimension": {"range": {"sheetId": sh_id, "dimension": "COLUMNS", "startIndex": start_col, "endIndex": end_col}}}]}
            ).execute()
            return f"Columns {start_col} to {end_col} deleted in '{tab_name}'."

        elif action_clean == "auto_resize_columns":
            if not sid or not tab_name:
                return "Error: 'spreadsheet_id' and 'tab_name' are required."
            sh_id = _sheet_id_by_name(sid, tab_name)
            svc.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={"requests": [{"autoResizeDimensions": {"dimensions": {"sheetId": sh_id, "dimension": "COLUMNS", "startIndex": start_col, "endIndex": end_col}}}]}
            ).execute()
            return f"Columns {start_col} to {end_col} auto-resized in '{tab_name}'."

        else:
            return f"Unknown spreadsheet management action '{action}'. Valid actions: list_spreadsheets, create_spreadsheet, copy_spreadsheet, delete_spreadsheet, get_metadata, list_tabs, add_tab, delete_tab, rename_tab, duplicate_tab, delete_rows, delete_columns, auto_resize_columns."

    except Exception as e:
        return f"Spreadsheet management operation failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")

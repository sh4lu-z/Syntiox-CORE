from mcp.server.fastmcp import FastMCP
from google_common import get_service, escape_drive_query

mcp = FastMCP("Google-Docs-Tools")


def _docs():
    return get_service("docs", "v1")


def _drive():
    return get_service("drive", "v3")


def _doc_end_index(doc_id: str) -> int:
    doc = _docs().documents().get(documentId=doc_id).execute()
    return doc["body"]["content"][-1]["endIndex"] - 1


def _extract_doc_text(doc: dict) -> str:
    text = ""
    for element in doc.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if paragraph:
            for run in paragraph.get("elements", []):
                text_run = run.get("textRun")
                if text_run:
                    text += text_run.get("content", "")
    return text


@mcp.tool()
def docs_content(
    action: str,
    doc_id: str = "",
    text: str = "",
    index: int = 1,
    find_text: str = "",
    replace_text: str = "",
    start_index: int = 0,
    end_index: int = 0,
    level: int = 1,
    rows: int = 2,
    cols: int = 2,
) -> str:
    """Manage Google Doc content: read, structure, append_text, insert_text, replace_text, delete_range, add_heading, add_table."""
    action_clean = (action or "").strip().lower()
    did = doc_id.strip()

    try:
        svc = _docs()

        if action_clean in ("read", "get_content"):
            if not did:
                return "Error: 'doc_id' is required."
            doc = svc.documents().get(documentId=did).execute()
            title = doc.get("title", "Untitled")
            content = _extract_doc_text(doc)
            preview = content[:3000] + ("..." if len(content) > 3000 else "")
            lines = [
                f"DOCUMENT: {title}",
                "=" * 40,
                preview,
                "-" * 40,
                f"Total Characters: {len(content)} | Document ID: {did}",
            ]
            return "\n".join(lines)

        elif action_clean == "structure":
            if not did:
                return "Error: 'doc_id' is required."
            doc = svc.documents().get(documentId=did).execute()
            lines = [f"STRUCTURE: {doc.get('title', 'Untitled')}", "-" * 40]
            for element in doc.get("body", {}).get("content", []):
                start = element.get("startIndex", "?")
                end = element.get("endIndex", "?")
                if "paragraph" in element:
                    style = element["paragraph"].get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
                    snippet = "".join(r.get("textRun", {}).get("content", "") for r in element["paragraph"].get("elements", [])).strip()[:60]
                    lines.append(f"  [{start}-{end}] {style}: {snippet or '(empty)'}")
                elif "table" in element:
                    lines.append(f"  [{start}-{end}] TABLE")
            return "\n".join(lines)

        elif action_clean == "append_text":
            if not did or not text:
                return "Error: 'doc_id' and 'text' are required to append."
            end_idx = _doc_end_index(did)
            svc.documents().batchUpdate(
                documentId=did,
                body={"requests": [{"insertText": {"location": {"index": end_idx}, "text": "\n" + text}}]}
            ).execute()
            return f"Text appended to document {did}."

        elif action_clean == "insert_text":
            if not did or not text:
                return "Error: 'doc_id' and 'text' are required to insert."
            svc.documents().batchUpdate(
                documentId=did,
                body={"requests": [{"insertText": {"location": {"index": index}, "text": text}}]}
            ).execute()
            return f"Text inserted at index {index}."

        elif action_clean in ("replace_text", "find_replace"):
            if not did or not find_text:
                return "Error: 'doc_id' and 'find_text' are required."
            svc.documents().batchUpdate(
                documentId=did,
                body={"requests": [{"replaceAllText": {"containsText": {"text": find_text, "matchCase": False}, "replaceText": replace_text or ""}}]}
            ).execute()
            return f"Replaced all occurrences of '{find_text}' with '{replace_text}' in document {did}."

        elif action_clean == "delete_range":
            if not did or start_index < 0 or end_index <= start_index:
                return "Error: 'doc_id', 'start_index', and 'end_index' (end_index > start_index) are required."
            svc.documents().batchUpdate(
                documentId=did,
                body={"requests": [{"deleteContentRange": {"range": {"startIndex": start_index, "endIndex": end_index}}}]}
            ).execute()
            return f"Deleted content range [{start_index}, {end_index}) in document {did}."

        elif action_clean == "add_heading":
            if not did or not text:
                return "Error: 'doc_id' and 'text' are required."
            style = "HEADING_1" if level <= 1 else "HEADING_2"
            end_idx = _doc_end_index(did)
            ins_text = "\n" + text + "\n"
            svc.documents().batchUpdate(
                documentId=did,
                body={"requests": [
                    {"insertText": {"location": {"index": end_idx}, "text": ins_text}},
                    {"updateParagraphStyle": {"range": {"startIndex": end_idx + 1, "endIndex": end_idx + 1 + len(text)}, "paragraphStyle": {"namedStyleType": style}, "fields": "namedStyleType"}},
                ]}
            ).execute()
            return f"Heading ({style}) added: '{text}'."

        elif action_clean == "add_table":
            if not did:
                return "Error: 'doc_id' is required."
            if rows < 1 or cols < 1 or rows > 20 or cols > 10:
                return "Error: rows must be 1-20 and cols must be 1-10."
            end_idx = _doc_end_index(did)
            svc.documents().batchUpdate(
                documentId=did,
                body={"requests": [{"insertTable": {"rows": rows, "columns": cols, "location": {"index": end_idx}}}]}
            ).execute()
            return f"Table {rows}x{cols} added at end of document {did}."

        else:
            return f"Unknown doc content action '{action}'. Valid actions: read, structure, append_text, insert_text, replace_text, delete_range, add_heading, add_table."

    except Exception as e:
        return f"Doc content operation failed: {e}"


@mcp.tool()
def docs_manage(
    action: str,
    title: str = "",
    query: str = "",
    max_results: int = 10,
) -> str:
    """Manage Google Documents lifecycle: list_documents, create_document, search_documents."""
    action_clean = (action or "").strip().lower()

    try:
        if action_clean in ("list_documents", "list"):
            drive_svc = _drive()
            res = drive_svc.files().list(
                q="mimeType='application/vnd.google-apps.document' and trashed=false",
                pageSize=max_results, fields="files(id, name, modifiedTime, webViewLink)"
            ).execute()
            files = res.get("files", [])
            if not files:
                return "No Google Documents found."
            lines = [f"GOOGLE DOCS - {len(files)} DOCUMENTS", "-" * 40]
            for f in files:
                lines.append(f"Title: {f['name']} | ID: {f['id']} | Link: {f.get('webViewLink')}")
            return "\n".join(lines)

        elif action_clean in ("create_document", "create"):
            doc_title = title or "Untitled Document"
            doc = _docs().documents().create(body={"title": doc_title}).execute()
            new_id = doc["documentId"]
            return f"Document '{doc_title}' created. ID: {new_id} Link: https://docs.google.com/document/d/{new_id}/edit"

        elif action_clean in ("search_documents", "search"):
            if not query:
                return "Error: 'query' parameter is required for search."
            escaped = escape_drive_query(query)
            drive_svc = _drive()
            res = drive_svc.files().list(
                q=f"mimeType='application/vnd.google-apps.document' and name contains '{escaped}' and trashed=false",
                pageSize=max_results, fields="files(id, name, webViewLink)"
            ).execute()
            files = res.get("files", [])
            if not files:
                return f"No documents found matching '{query}'."
            lines = [f"DOCS SEARCH: '{query}' - {len(files)} MATCHES", "-" * 40]
            for f in files:
                lines.append(f"Title: {f['name']} | ID: {f['id']}")
            return "\n".join(lines)

        else:
            return f"Unknown document management action '{action}'. Valid actions: list_documents, create_document, search_documents."

    except Exception as e:
        return f"Doc management operation failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")

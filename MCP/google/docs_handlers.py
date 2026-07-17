"""
📄 Google Docs Handler Tools
"""
import io
import os
from mcp.server.fastmcp import FastMCP
from googleapiclient.http import MediaIoBaseDownload
from google_common import get_service, escape_drive_query, share_file

mcp = FastMCP("Google-Docs-Tools")


def _docs():
    return get_service('docs', 'v1')


def _drive():
    return get_service('drive', 'v3')


def _doc_end_index(doc_id: str) -> int:
    doc = _docs().documents().get(documentId=doc_id).execute()
    return doc['body']['content'][-1]['endIndex'] - 1


def _extract_doc_text(doc: dict) -> str:
    text = ""
    for element in doc.get('body', {}).get('content', []):
        paragraph = element.get('paragraph')
        if paragraph:
            for run in paragraph.get('elements', []):
                text_run = run.get('textRun')
                if text_run:
                    text += text_run.get('content', '')
    return text


@mcp.tool()
def list_documents(max_results: int = 10) -> str:
    """List Google Documents in Drive."""
    try:
        results = _drive().files().list(
            q="mimeType='application/vnd.google-apps.document' and trashed=false",
            pageSize=max_results,
            fields="files(id, name, modifiedTime, webViewLink)"
        ).execute()
        files = results.get('files', [])
        if not files:
            return "📄 No Google Documents found."
        output = f"📄 GOOGLE DOCS — {len(files)} DOCUMENTS\n{'─'*40}\n"
        for f in files:
            output += (
                f"📝 {f['name']}\n"
                f"   🔑 ID: {f['id']}\n"
                f"   🔗 {f.get('webViewLink','N/A')}\n"
                f"{'─'*40}\n"
            )
        return output
    except Exception as e:
        return f"❌ Error listing documents: {e}"


@mcp.tool()
def get_document_content(doc_id: str) -> str:
    """Read the text content of a Google Document."""
    try:
        doc = _docs().documents().get(documentId=doc_id).execute()
        title = doc.get('title', 'Untitled')
        text = _extract_doc_text(doc)
        preview = text[:2000] + ("..." if len(text) > 2000 else "")
        return f"📄 DOCUMENT: {title}\n{'═'*40}\n{preview}\n{'─'*40}\n📏 Chars: {len(text)} | ID: {doc_id}"
    except Exception as e:
        return f"❌ Error reading document: {e}"


@mcp.tool()
def get_document_structure(doc_id: str) -> str:
    """List the structure of a Google Document with start and end indices."""
    try:
        doc = _docs().documents().get(documentId=doc_id).execute()
        output = f"📄 STRUCTURE: {doc.get('title', 'Untitled')}\n{'─'*40}\n"
        for element in doc.get('body', {}).get('content', []):
            start = element.get('startIndex', '?')
            end = element.get('endIndex', '?')
            if 'paragraph' in element:
                style = element['paragraph'].get('paragraphStyle', {}).get('namedStyleType', 'NORMAL_TEXT')
                snippet = ""
                for run in element['paragraph'].get('elements', []):
                    tr = run.get('textRun', {})
                    snippet += tr.get('content', '')
                snippet = snippet.strip()[:60]
                output += f"  [{start}-{end}] {style}: {snippet or '(empty)'}\n"
            elif 'table' in element:
                output += f"  [{start}-{end}] TABLE\n"
        return output
    except Exception as e:
        return f"❌ Error getting document structure: {e}"


@mcp.tool()
def create_document(title: str) -> str:
    """Create a new Google Document."""
    try:
        doc = _docs().documents().create(body={'title': title}).execute()
        doc_id = doc['documentId']
        return (
            f"✅ Document '{title}' created!\n"
            f"   🔑 ID: {doc_id}\n"
            f"   🔗 https://docs.google.com/document/d/{doc_id}/edit\n"
            f"   💡 Use this ID for update/delete/share tools."
        )
    except Exception as e:
        return f"❌ Error creating document: {e}"


@mcp.tool()
def append_text_to_document(doc_id: str, text: str) -> str:
    """Append text to the end of a Google Document."""
    try:
        end_index = _doc_end_index(doc_id)
        _docs().documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [{'insertText': {'location': {'index': end_index}, 'text': '\n' + text}}]}
        ).execute()
        return f"✅ Text appended to document (ID: {doc_id})."
    except Exception as e:
        return f"❌ Error appending text: {e}"


@mcp.tool()
def insert_text_at_index(doc_id: str, index: int, text: str) -> str:
    """Insert text at a specific index in a Google Document."""
    try:
        _docs().documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [{'insertText': {'location': {'index': index}, 'text': text}}]}
        ).execute()
        return f"✅ Text inserted at index {index}."
    except Exception as e:
        return f"❌ Error inserting text: {e}"


@mcp.tool()
def replace_text_in_document(doc_id: str, find_text: str, replace_text: str) -> str:
    """Find and replace all occurrences of text in a Google Document."""
    try:
        _docs().documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [{
                'replaceAllText': {
                    'containsText': {'text': find_text, 'matchCase': False},
                    'replaceText': replace_text,
                }
            }]}
        ).execute()
        return f"✅ Replaced '{find_text}' → '{replace_text}' in document."
    except Exception as e:
        return f"❌ Error replacing text: {e}"


@mcp.tool()
def find_replace_in_document(doc_id: str, find_text: str, replace_text: str) -> str:
    """Find and replace text (alias)."""
    return replace_text_in_document(doc_id, find_text, replace_text)


@mcp.tool()
def delete_text_range(doc_id: str, start_index: int, end_index: int) -> str:
    """Delete a specific range of text by indices."""
    try:
        _docs().documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [{
                'deleteContentRange': {'range': {'startIndex': start_index, 'endIndex': end_index}}
            }]}
        ).execute()
        return f"✅ Deleted content [{start_index}, {end_index})."
    except Exception as e:
        return f"❌ Error deleting range: {e}"


@mcp.tool()
def add_heading_to_document(doc_id: str, text: str, level: int = 1) -> str:
    """Add a heading (level 1 or 2) to the end of a Document."""
    try:
        style = 'HEADING_1' if level <= 1 else 'HEADING_2'
        end_index = _doc_end_index(doc_id)
        insert_text = '\n' + text + '\n'
        _docs().documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [
                {'insertText': {'location': {'index': end_index}, 'text': insert_text}},
                {
                    'updateParagraphStyle': {
                        'range': {
                            'startIndex': end_index + 1,
                            'endIndex': end_index + 1 + len(text),
                        },
                        'paragraphStyle': {'namedStyleType': style},
                        'fields': 'namedStyleType',
                    }
                },
            ]}
        ).execute()
        return f"✅ Heading ({style}) added: '{text}'."
    except Exception as e:
        return f"❌ Error adding heading: {e}"


@mcp.tool()
def add_table_to_document(doc_id: str, rows: int, cols: int) -> str:
    """Add a simple empty table to the end of a Document."""
    try:
        if rows < 1 or cols < 1 or rows > 20 or cols > 10:
            return "❌ rows 1-20, cols 1-10."
        end_index = _doc_end_index(doc_id)
        _docs().documents().batchUpdate(
            documentId=doc_id,
            body={'requests': [{
                'insertTable': {
                    'rows': rows,
                    'columns': cols,
                    'location': {'index': end_index},
                }
            }]}
        ).execute()
        return f"✅ Table {rows}x{cols} added at end of document."
    except Exception as e:
        return f"❌ Error adding table: {e}"


@mcp.tool()
def search_documents(query: str) -> str:
    """Search for Google Documents by name."""
    try:
        q = escape_drive_query(query)
        results = _drive().files().list(
            q=f"mimeType='application/vnd.google-apps.document' and name contains '{q}' and trashed=false",
            pageSize=10,
            fields="files(id, name, webViewLink)"
        ).execute()
        files = results.get('files', [])
        if not files:
            return f"🔍 '{query}' Documents found."
        output = f"🔍 DOCS SEARCH: '{query}'\n{'─'*40}\n"
        for f in files:
            output += f"📝 {f['name']} | ID: {f['id']}\n"
        return output
    except Exception as e:
        return f"❌ Error searching documents: {e}"


@mcp.tool()
def share_document(doc_id: str, email: str, role: str = "reader") -> str:
    """Share a Google Document via email."""
    try:
        perm = share_file(doc_id, email, role)
        return f"✅ Shared with {perm.get('emailAddress', email)} as {perm.get('role', role)}."
    except Exception as e:
        return f"❌ Error sharing document: {e}"


@mcp.tool()
def rename_document(doc_id: str, new_title: str) -> str:
    """Rename a Google Document."""
    try:
        _drive().files().update(fileId=doc_id, body={'name': new_title}).execute()
        return f"✅ Renamed to '{new_title}'."
    except Exception as e:
        return f"❌ Error renaming document: {e}"


@mcp.tool()
def delete_document(doc_id: str, permanent: bool = False) -> str:
    """Delete or trash a Google Document."""
    try:
        if permanent:
            _drive().files().delete(fileId=doc_id).execute()
            return f"🗑️ Document permanently deleted (ID: {doc_id})."
        _drive().files().update(fileId=doc_id, body={'trashed': True}).execute()
        return f"🗑️ Document moved to trash (ID: {doc_id})."
    except Exception as e:
        return f"❌ Error deleting document: {e}"


@mcp.tool()
def export_document(doc_id: str, local_path: str, export_format: str = "pdf") -> str:
    """Export a Google Document to a local file (PDF or DOCX)."""
    try:
        mime_map = {'pdf': 'application/pdf', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        mime = mime_map.get(export_format.lower())
        if not mime:
            return "❌ export_format must be pdf or docx."
        parent = os.path.dirname(os.path.abspath(local_path))
        if parent and not os.path.isdir(parent):
            return f"❌ Directory not found: {parent}"
        request = _drive().files().export_media(fileId=doc_id, mimeType=mime)
        fh = io.FileIO(local_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.close()
        return f"✅ Exported to {local_path} ({export_format})."
    except Exception as e:
        return f"❌ Error exporting document: {e}"



@mcp.tool()
def read_text_range(doc_id: str, start_index: int, end_index: int) -> str:
    """Reads the text content within a specific index range in a Google Document."""
    doc_id = doc_id.strip()
    try:
        doc = _docs().documents().get(documentId=doc_id).execute()
        text = ""
        for element in doc.get('body', {}).get('content', []):
            start = element.get('startIndex', 0)
            end = element.get('endIndex', 0)
            # Check for overlap
            if start < end_index and end > start_index:
                paragraph = element.get('paragraph')
                if paragraph:
                    for run in paragraph.get('elements', []):
                        text_run = run.get('textRun')
                        if text_run:
                            text += text_run.get('content', '')
        return f"📄 Content [{start_index}-{end_index}]:\n{text}"
    except Exception as e:
        return f"❌ Error reading text range: {e}"

if __name__ == "__main__":
    mcp.run(transport='stdio')

"""
📁 Google Drive Handler Tools
"""
import io
import os
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from mcp.server.fastmcp import FastMCP
from google_common import get_service, escape_drive_query, share_file

mcp = FastMCP("Google-Drive-Tools")


def _drive():
    return get_service('drive', 'v3')


@mcp.tool()
def list_drive_files(max_results: int = 10, folder_name: str = "") -> str:
    """List Google Drive files, optionally within a specific folder."""
    try:
        query = "trashed = false"
        if folder_name:
            qname = escape_drive_query(folder_name)
            folder_res = _drive().files().list(
                q=f"name = '{qname}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                fields="files(id, name)"
            ).execute()
            folders = folder_res.get('files', [])
            if folders:
                query += f" and '{folders[0]['id']}' in parents"
        results = _drive().files().list(
            q=query, pageSize=max_results,
            fields="files(id, name, mimeType, size, modifiedTime, webViewLink)"
        ).execute()
        files = results.get('files', [])
        if not files:
            return "📁 No files found in Drive."
        output = f"📁 GOOGLE DRIVE — {len(files)} FILES\n{'─'*40}\n"
        for f in files:
            size = int(f.get('size', 0) or 0)
            size_str = f"{size/1024:.1f} KB" if size and size < 1024 * 1024 else (f"{size/1024/1024:.1f} MB" if size else 'N/A')
            mime = f.get('mimeType', '').replace('application/vnd.google-apps.', '[Google] ')
            output += f"📄 {f['name']}\n   Type: {mime} | Size: {size_str}\n   🔑 ID: {f['id']}\n{'─'*40}\n"
        return output
    except Exception as e:
        return f"❌ Error listing drive files: {e}"


@mcp.tool()
def search_drive_files(query: str, max_results: int = 10) -> str:
    """Search for files in Google Drive by name."""
    try:
        q = escape_drive_query(query)
        results = _drive().files().list(
            q=f"name contains '{q}' and trashed = false",
            pageSize=max_results,
            fields="files(id, name, mimeType, webViewLink)"
        ).execute()
        files = results.get('files', [])
        if not files:
            return f"🔍 No files found for '{query}'."
        output = f"🔍 DRIVE SEARCH: '{query}'\n{'─'*40}\n"
        for f in files:
            output += f"📄 {f['name']} | ID: {f['id']}\n"
        return output
    except Exception as e:
        return f"❌ Error searching drive: {e}"


@mcp.tool()
def get_drive_file_info(file_id: str) -> str:
    """Get detailed information about a Google Drive file."""
    file_id = file_id.strip()
    try:
        f = _drive().files().get(
            fileId=file_id,
            fields="id, name, mimeType, size, createdTime, modifiedTime, webViewLink, owners, shared, parents"
        ).execute()
        size = int(f.get('size', 0) or 0)
        owners = ', '.join(o.get('displayName', '') for o in f.get('owners', []))
        return (
            f"📄 FILE INFO\n{'═'*40}\n"
            f"Name: {f['name']}\nType: {f.get('mimeType')}\n"
            f"Size: {size} bytes\nOwner: {owners}\n"
            f"Shared: {'Yes' if f.get('shared') else 'No'}\n"
            f"Link: {f.get('webViewLink')}\nID: {f['id']}\n"
        )
    except Exception as e:
        return f"❌ Error getting file info: {e}"


@mcp.tool()
def create_drive_folder(folder_name: str, parent_folder_id: str = "") -> str:
    """Create a new Google Drive folder."""
    try:
        metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_folder_id:
            metadata['parents'] = [parent_folder_id]
        folder = _drive().files().create(body=metadata, fields='id, name, webViewLink').execute()
        return f"✅ Folder '{folder_name}' created.\n   🔑 ID: {folder['id']}\n   💡 Use ID for move/upload."
    except Exception as e:
        return f"❌ Error creating folder: {e}"


@mcp.tool()
def delete_drive_file(file_id: str) -> str:
    """Permanently delete a file from Google Drive."""
    file_id = file_id.strip()
    try:
        _drive().files().delete(fileId=file_id).execute()
        return f"🗑️ File (ID: {file_id}) permanently deleted."
    except Exception as e:
        return f"❌ Error deleting file: {e}"


@mcp.tool()
def upload_file_to_drive(local_file_path: str, drive_folder_id: str = "") -> str:
    """Upload a local file to Google Drive."""
    try:
        if not os.path.exists(local_file_path):
            return f"❌ File not found: {local_file_path}"
        filename = os.path.basename(local_file_path)
        metadata = {'name': filename}
        if drive_folder_id:
            metadata['parents'] = [drive_folder_id]
        media = MediaFileUpload(local_file_path, resumable=True)
        result = _drive().files().create(body=metadata, media_body=media, fields='id, name, webViewLink').execute()
        return f"✅ Uploaded '{filename}'.\n   🔑 ID: {result['id']}"
    except Exception as e:
        return f"❌ Error uploading file: {e}"


@mcp.tool()
def download_drive_file(file_id: str, local_path: str) -> str:
    """Download a Google Drive file to a local path (exports native Google docs to PDF)."""
    file_id = file_id.strip()
    try:
        meta = _drive().files().get(fileId=file_id, fields='mimeType, name').execute()
        mime = meta.get('mimeType', '')
        parent = os.path.dirname(os.path.abspath(local_path))
        if parent and not os.path.isdir(parent):
            return f"❌ Directory not found: {parent}"
        if mime.startswith('application/vnd.google-apps.'):
            return export_google_file(file_id, local_path, "pdf")
        request = _drive().files().get_media(fileId=file_id)
        fh = io.FileIO(local_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.close()
        return f"✅ Downloaded '{meta.get('name')}' to {local_path}."
    except Exception as e:
        return f"❌ Error downloading file: {e}"


@mcp.tool()
def export_google_file(file_id: str, local_path: str, export_format: str = "pdf") -> str:
    """Export Google Docs/Sheets/Slides to a local file (pdf, docx, xlsx, pptx)."""
    file_id = file_id.strip()
    try:
        fmt_map = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        }
        mime = fmt_map.get(export_format.lower())
        if not mime:
            return "❌ export_format: pdf, docx, xlsx, or pptx."
        request = _drive().files().export_media(fileId=file_id, mimeType=mime)
        fh = io.FileIO(local_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.close()
        return f"✅ Exported to {local_path} ({export_format})."
    except Exception as e:
        return f"❌ Error exporting file: {e}"


@mcp.tool()
def rename_drive_file(file_id: str, new_name: str) -> str:
    """Rename a Google Drive file."""
    file_id = file_id.strip()
    try:
        _drive().files().update(fileId=file_id, body={'name': new_name}).execute()
        return f"✅ Renamed to '{new_name}'."
    except Exception as e:
        return f"❌ Error renaming file: {e}"


@mcp.tool()
def move_drive_file(file_id: str, new_parent_folder_id: str) -> str:
    """Move a file to a different folder in Google Drive."""
    file_id = file_id.strip()
    try:
        f = _drive().files().get(fileId=file_id, fields='parents').execute()
        prev = ','.join(f.get('parents', []))
        _drive().files().update(
            fileId=file_id,
            addParents=new_parent_folder_id,
            removeParents=prev,
            fields='id, parents'
        ).execute()
        return f"✅ Moved to folder {new_parent_folder_id}."
    except Exception as e:
        return f"❌ Error moving file: {e}"


@mcp.tool()
def copy_drive_file(file_id: str, new_name: str = "") -> str:
    """Copy a Google Drive file."""
    file_id = file_id.strip()
    try:
        body = {'name': new_name} if new_name else {}
        result = _drive().files().copy(fileId=file_id, body=body).execute()
        return f"✅ Copied. New ID: {result['id']}"
    except Exception as e:
        return f"❌ Error copying file: {e}"


@mcp.tool()
def share_drive_file(file_id: str, email: str, role: str = "reader") -> str:
    """Share a Google Drive file with an email address."""
    file_id = file_id.strip()
    try:
        perm = share_file(file_id, email, role)
        return f"✅ Shared with {perm.get('emailAddress', email)} as {perm.get('role', role)}."
    except Exception as e:
        return f"❌ Error sharing file: {e}"


@mcp.tool()
def list_file_permissions(file_id: str) -> str:
    """List permissions for a Google Drive file."""
    file_id = file_id.strip()
    try:
        result = _drive().permissions().list(fileId=file_id, fields='permissions(emailAddress,role,type)').execute()
        perms = result.get('permissions', [])
        if not perms:
            return "No permissions listed."
        output = f"🔐 PERMISSIONS — {len(perms)}\n{'─'*30}\n"
        for p in perms:
            output += f"  {p.get('type')} | {p.get('role')} | {p.get('emailAddress', 'link')}\n"
        return output
    except Exception as e:
        return f"❌ Error listing permissions: {e}"


@mcp.tool()
def trash_drive_file(file_id: str) -> str:
    """Move a Google Drive file to the trash."""
    file_id = file_id.strip()
    try:
        _drive().files().update(fileId=file_id, body={'trashed': True}).execute()
        return f"🗑️ File moved to trash (ID: {file_id})."
    except Exception as e:
        return f"❌ Error trashing file: {e}"


@mcp.tool()
def restore_drive_file(file_id: str) -> str:
    """Restore a trashed Google Drive file."""
    file_id = file_id.strip()
    try:
        _drive().files().update(fileId=file_id, body={'trashed': False}).execute()
        return f"✅ File restored from trash (ID: {file_id})."
    except Exception as e:
        return f"❌ Error restoring file: {e}"


@mcp.tool()
def create_drive_shortcut(target_file_id: str, shortcut_name: str, parent_folder_id: str = "") -> str:
    """Create a shortcut to a file in Google Drive."""
    try:
        metadata = {
            'name': shortcut_name,
            'mimeType': 'application/vnd.google-apps.shortcut',
            'shortcutDetails': {'targetId': target_file_id},
        }
        if parent_folder_id:
            metadata['parents'] = [parent_folder_id]
        result = _drive().files().create(body=metadata, fields='id, name').execute()
        return f"✅ Shortcut '{shortcut_name}' created. ID: {result['id']}"
    except Exception as e:
        return f"❌ Error creating shortcut: {e}"


@mcp.tool()
def list_shared_with_me(max_results: int = 10) -> str:
    """List files shared with you in Google Drive."""
    try:
        results = _drive().files().list(
            q="sharedWithMe = true and trashed = false",
            pageSize=max_results,
            fields="files(id, name, mimeType, webViewLink)"
        ).execute()
        files = results.get('files', [])
        if not files:
            return "No shared files found."
        output = f"📂 SHARED WITH ME — {len(files)}\n{'─'*40}\n"
        for f in files:
            output += f"📄 {f['name']} | ID: {f['id']}\n"
        return output
    except Exception as e:
        return f"❌ Error listing shared files: {e}"


@mcp.tool()
def get_drive_storage_quota() -> str:
    """Get Google Drive storage quota and usage."""
    try:
        about = _drive().about().get(fields='storageQuota, user').execute()
        q = about.get('storageQuota', {})
        user = about.get('user', {}).get('emailAddress', 'N/A')
        limit = int(q.get('limit', 0) or 0)
        usage = int(q.get('usage', 0) or 0)
        def fmt(b):
            if b <= 0:
                return 'N/A'
            gb = b / (1024 ** 3)
            return f"{gb:.2f} GB"
        return (
            f"💾 DRIVE STORAGE ({user})\n"
            f"Used: {fmt(usage)}\n"
            f"Limit: {fmt(limit)}\n"
            f"Drive: {q.get('usageInDrive', 'N/A')} bytes\n"
        )
    except Exception as e:
        return f"❌ Error getting storage quota: {e}"


if __name__ == "__main__":
    mcp.run(transport='stdio')

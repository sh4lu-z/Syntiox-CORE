import io
import os
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from mcp.server.fastmcp import FastMCP
from google_common import get_service, escape_drive_query, share_file

mcp = FastMCP("Google-Drive-Tools")


def _drive():
    return get_service("drive", "v3")


@mcp.tool()
def drive_files(
    action: str,
    file_id: str = "",
    query: str = "",
    local_path: str = "",
    new_name: str = "",
    drive_folder_id: str = "",
    export_format: str = "pdf",
    max_results: int = 10,
) -> str:
    """Manage Google Drive files: list, search, get_info, upload, download, export, rename, copy, trash, restore, delete, list_shared, storage_quota."""
    action_clean = (action or "").strip().lower()

    try:
        svc = _drive()

        if action_clean in ("list", "list_files"):
            q_filter = "trashed = false"
            if drive_folder_id:
                q_filter += f" and '{drive_folder_id.strip()}' in parents"
            results = svc.files().list(
                q=q_filter, pageSize=max_results,
                fields="files(id, name, mimeType, size, modifiedTime, webViewLink)"
            ).execute()
            files = results.get("files", [])
            if not files:
                return "No files found in Drive."
            lines = [f"GOOGLE DRIVE - {len(files)} FILES", "-" * 40]
            for f in files:
                size = int(f.get("size", 0) or 0)
                size_str = f"{size/1024:.1f} KB" if size and size < 1024 * 1024 else (f"{size/1024/1024:.1f} MB" if size else "N/A")
                mime = f.get("mimeType", "").replace("application/vnd.google-apps.", "[Google] ")
                lines.append(f"Name: {f['name']} | Type: {mime} | Size: {size_str} | ID: {f['id']}")
            return "\n".join(lines)

        elif action_clean == "search":
            if not query:
                return "Error: 'query' parameter is required for search."
            escaped = escape_drive_query(query)
            results = svc.files().list(
                q=f"name contains '{escaped}' and trashed = false",
                pageSize=max_results,
                fields="files(id, name, mimeType, webViewLink)"
            ).execute()
            files = results.get("files", [])
            if not files:
                return f"No files found matching '{query}'."
            lines = [f"DRIVE SEARCH: '{query}' - {len(files)} RESULTS", "-" * 40]
            for f in files:
                lines.append(f"Name: {f['name']} | ID: {f['id']} | Link: {f.get('webViewLink', '')}")
            return "\n".join(lines)

        elif action_clean in ("get_info", "info"):
            if not file_id:
                return "Error: 'file_id' parameter is required."
            f = svc.files().get(
                fileId=file_id.strip(),
                fields="id, name, mimeType, size, createdTime, modifiedTime, webViewLink, owners, shared, parents"
            ).execute()
            owners = ", ".join(o.get("displayName", "") for o in f.get("owners", []))
            lines = [
                "FILE INFO",
                "=" * 40,
                f"Name     : {f.get('name')}",
                f"Type     : {f.get('mimeType')}",
                f"Size     : {f.get('size', 0)} bytes",
                f"Owner    : {owners}",
                f"Shared   : {'Yes' if f.get('shared') else 'No'}",
                f"Link     : {f.get('webViewLink')}",
                f"ID       : {f.get('id')}",
            ]
            return "\n".join(lines)

        elif action_clean == "upload":
            if not local_path or not os.path.exists(local_path):
                return f"Error: Local file not found at '{local_path}'."
            filename = os.path.basename(local_path)
            meta = {"name": filename}
            if drive_folder_id:
                meta["parents"] = [drive_folder_id.strip()]
            media = MediaFileUpload(local_path, resumable=True)
            res = svc.files().create(body=meta, media_body=media, fields="id, name, webViewLink").execute()
            return f"Uploaded '{filename}'. ID: {res['id']} Link: {res.get('webViewLink', '')}"

        elif action_clean == "download":
            if not file_id or not local_path:
                return "Error: 'file_id' and 'local_path' are required to download."
            meta = svc.files().get(fileId=file_id.strip(), fields="mimeType, name").execute()
            mime = meta.get("mimeType", "")
            parent_dir = os.path.dirname(os.path.abspath(local_path))
            if parent_dir and not os.path.isdir(parent_dir):
                return f"Error: Destination directory does not exist: {parent_dir}"

            if mime.startswith("application/vnd.google-apps."):
                return export_format_file(svc, file_id.strip(), local_path, export_format)

            req = svc.files().get_media(fileId=file_id.strip())
            with io.FileIO(local_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            return f"Downloaded '{meta.get('name')}' to {local_path}."

        elif action_clean == "export":
            if not file_id or not local_path:
                return "Error: 'file_id' and 'local_path' are required."
            return export_format_file(svc, file_id.strip(), local_path, export_format)

        elif action_clean == "rename":
            if not file_id or not new_name:
                return "Error: 'file_id' and 'new_name' are required to rename."
            svc.files().update(fileId=file_id.strip(), body={"name": new_name}).execute()
            return f"File {file_id} renamed to '{new_name}'."

        elif action_clean == "copy":
            if not file_id:
                return "Error: 'file_id' parameter is required to copy."
            body = {"name": new_name} if new_name else {}
            res = svc.files().copy(fileId=file_id.strip(), body=body).execute()
            return f"File copied. New ID: {res['id']}"

        elif action_clean == "trash":
            if not file_id:
                return "Error: 'file_id' parameter is required."
            svc.files().update(fileId=file_id.strip(), body={"trashed": True}).execute()
            return f"File {file_id} moved to trash."

        elif action_clean == "restore":
            if not file_id:
                return "Error: 'file_id' parameter is required."
            svc.files().update(fileId=file_id.strip(), body={"trashed": False}).execute()
            return f"File {file_id} restored from trash."

        elif action_clean == "delete":
            if not file_id:
                return "Error: 'file_id' parameter is required to delete."
            svc.files().delete(fileId=file_id.strip()).execute()
            return f"File {file_id} permanently deleted."

        elif action_clean == "list_shared":
            results = svc.files().list(
                q="sharedWithMe = true and trashed = false",
                pageSize=max_results,
                fields="files(id, name, mimeType, webViewLink)"
            ).execute()
            files = results.get("files", [])
            if not files:
                return "No shared files found."
            lines = [f"SHARED WITH ME - {len(files)} FILES", "-" * 40]
            for f in files:
                lines.append(f"Name: {f['name']} | ID: {f['id']}")
            return "\n".join(lines)

        elif action_clean == "storage_quota":
            about = svc.about().get(fields="storageQuota, user").execute()
            q = about.get("storageQuota", {})
            user = about.get("user", {}).get("emailAddress", "N/A")
            limit = int(q.get("limit", 0) or 0)
            usage = int(q.get("usage", 0) or 0)
            fmt_gb = lambda b: f"{b / (1024 ** 3):.2f} GB" if b > 0 else "N/A"
            return f"Drive Storage ({user}) - Used: {fmt_gb(usage)}, Limit: {fmt_gb(limit)}, UsageInDrive: {q.get('usageInDrive', 'N/A')} bytes"

        else:
            return f"Unknown file action '{action}'. Valid actions: list, search, get_info, upload, download, export, rename, copy, trash, restore, delete, list_shared, storage_quota."

    except Exception as e:
        return f"Drive file operation failed: {e}"


def export_format_file(svc, file_id: str, local_path: str, export_format: str) -> str:
    fmt_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    mime = fmt_map.get((export_format or "pdf").lower())
    if not mime:
        return "Error: export_format must be pdf, docx, xlsx, or pptx."
    req = svc.files().export_media(fileId=file_id, mimeType=mime)
    with io.FileIO(local_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return f"Exported file to {local_path} ({export_format})."


@mcp.tool()
def drive_folders(
    action: str,
    folder_name: str = "",
    folder_id: str = "",
    parent_folder_id: str = "",
    file_id: str = "",
    new_parent_folder_id: str = "",
    max_results: int = 20,
) -> str:
    """Manage Google Drive folders: create, list_contents, move."""
    action_clean = (action or "").strip().lower()

    try:
        svc = _drive()

        if action_clean == "create":
            if not folder_name:
                return "Error: 'folder_name' parameter is required."
            meta = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
            if parent_folder_id:
                meta["parents"] = [parent_folder_id.strip()]
            folder = svc.files().create(body=meta, fields="id, name, webViewLink").execute()
            return f"Folder '{folder_name}' created. ID: {folder['id']} Link: {folder.get('webViewLink', '')}"

        elif action_clean == "list_contents":
            target_id = folder_id.strip() if folder_id else "root"
            q = f"'{target_id}' in parents and trashed = false"
            results = svc.files().list(
                q=q, pageSize=max_results, fields="files(id, name, mimeType, size)"
            ).execute()
            files = results.get("files", [])
            if not files:
                return f"No items found inside folder {target_id}."
            lines = [f"FOLDER CONTENTS ({target_id}) - {len(files)} ITEMS", "-" * 40]
            for f in files:
                is_folder = f.get("mimeType") == "application/vnd.google-apps.folder"
                tag = "[DIR]" if is_folder else "[FILE]"
                lines.append(f"  {tag} {f['name']} (ID: {f['id']})")
            return "\n".join(lines)

        elif action_clean == "move":
            target_file = file_id.strip() if file_id else folder_id.strip()
            if not target_file or not new_parent_folder_id:
                return "Error: 'file_id' (or 'folder_id') and 'new_parent_folder_id' are required."
            f = svc.files().get(fileId=target_file, fields="parents").execute()
            prev = ",".join(f.get("parents", []))
            svc.files().update(
                fileId=target_file,
                addParents=new_parent_folder_id.strip(),
                removeParents=prev,
                fields="id, parents"
            ).execute()
            return f"Moved {target_file} to folder {new_parent_folder_id}."

        else:
            return f"Unknown folder action '{action}'. Valid actions: create, list_contents, move."

    except Exception as e:
        return f"Drive folder operation failed: {e}"


@mcp.tool()
def drive_sharing(
    action: str,
    file_id: str = "",
    email: str = "",
    role: str = "reader",
    permission_id: str = "",
) -> str:
    """Manage Drive sharing and permissions: share, list_permissions, unshare."""
    action_clean = (action or "").strip().lower()

    try:
        svc = _drive()

        if action_clean in ("list_permissions", "list"):
            if not file_id:
                return "Error: 'file_id' parameter is required."
            res = svc.permissions().list(fileId=file_id.strip(), fields="permissions(id, emailAddress, role, type)").execute()
            perms = res.get("permissions", [])
            if not perms:
                return "No permissions found."
            lines = [f"PERMISSIONS FOR {file_id}", "-" * 30]
            for p in perms:
                lines.append(f"  ID: {p.get('id')} | Type: {p.get('type')} | Role: {p.get('role')} | User: {p.get('emailAddress', 'anyone')}")
            return "\n".join(lines)

        elif action_clean == "share":
            if not file_id or not email:
                return "Error: 'file_id' and 'email' are required to share."
            perm = share_file(file_id.strip(), email.strip(), role)
            return f"Shared file {file_id} with {perm.get('emailAddress', email)} as {perm.get('role', role)}."

        elif action_clean in ("unshare", "delete"):
            if not file_id or not permission_id:
                return "Error: 'file_id' and 'permission_id' are required."
            svc.permissions().delete(fileId=file_id.strip(), permissionId=permission_id.strip()).execute()
            return f"Permission {permission_id} removed from file {file_id}."

        else:
            return f"Unknown sharing action '{action}'. Valid actions: share, list_permissions, unshare."

    except Exception as e:
        return f"Drive sharing operation failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")

import os
import base64
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from mcp.server.fastmcp import FastMCP
from google_common import get_service

mcp = FastMCP("Google-Gmail-Tools")


def _gmail():
    return get_service("gmail", "v1")


def _extract_body(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    for part in payload.get("parts", []):
        res = _extract_body(part)
        if res:
            return res
    return ""


@mcp.tool()
def manage_gmail(
    action: str,
    query: str = "",
    email_id: str = "",
    to_email: str = "",
    subject: str = "",
    email_body: str = "",
    file_path: str = "",
    label_name: str = "",
    label_id: str = "",
    max_results: int = 5,
) -> str:
    """Manage Gmail operations: list_latest, search, get_body, send, reply, send_attachment, delete, mark_read, mark_unread, archive, list_labels, create_label, delete_label, create_draft, send_draft, list_drafts, get_profile."""
    action_clean = (action or "").strip().lower()

    try:
        svc = _gmail()

        if action_clean in ("list_latest", "list_inbox", "inbox"):
            results = svc.users().messages().list(
                userId="me", labelIds=["INBOX"], maxResults=max_results
            ).execute()
            messages = results.get("messages", [])
            if not messages:
                return "No emails found in Inbox."

            lines = [f"INBOX - TOP {len(messages)} EMAILS", "-" * 40]
            for msg in messages:
                data = svc.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute()
                headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
                snippet = data.get("snippet", "")[:100]
                lines.append(f"Subject : {headers.get('Subject', 'No Subject')}")
                lines.append(f"From    : {headers.get('From', 'Unknown')}")
                lines.append(f"Date    : {headers.get('Date', '')}")
                lines.append(f"Preview : {snippet}...")
                lines.append(f"ID      : {msg['id']}")
                lines.append("-" * 40)
            return "\n".join(lines)

        elif action_clean == "search":
            if not query:
                return "Error: 'query' parameter is required for search action."
            results = svc.users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()
            messages = results.get("messages", [])
            if not messages:
                return f"No emails found matching query '{query}'."

            lines = [f"SEARCH: '{query}' - {len(messages)} RESULTS", "-" * 40]
            for msg in messages:
                data = svc.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute()
                headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
                lines.append(f"Subject : {headers.get('Subject', 'No Subject')}")
                lines.append(f"From    : {headers.get('From', 'Unknown')} | Date: {headers.get('Date', '')}")
                lines.append(f"ID      : {msg['id']}")
                lines.append("-" * 40)
            return "\n".join(lines)

        elif action_clean in ("get_body", "get_message", "read"):
            if not email_id:
                return "Error: 'email_id' parameter is required to read email body."
            msg = svc.users().messages().get(userId="me", id=email_id.strip(), format="full").execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            body = _extract_body(msg.get("payload", {})) or "(Body not found)"
            lines = [
                "EMAIL DETAILS",
                "=" * 40,
                f"From    : {headers.get('From', 'Unknown')}",
                f"To      : {headers.get('To', 'Unknown')}",
                f"Subject : {headers.get('Subject', 'No Subject')}",
                f"Date    : {headers.get('Date', '')}",
                "-" * 40,
                body,
            ]
            return "\n".join(lines)

        elif action_clean == "send":
            if not to_email:
                return "Error: 'to_email' parameter is required to send email."
            msg = MIMEText(email_body or "")
            msg["to"] = to_email
            msg["from"] = "me"
            msg["subject"] = subject or "No Subject"
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
            return f"Email successfully sent to {to_email}. ID: {sent['id']}"

        elif action_clean == "send_attachment":
            if not to_email:
                return "Error: 'to_email' parameter is required."
            if not file_path or not os.path.exists(file_path):
                return f"Error: File not found at '{file_path}'."
            msg = MIMEMultipart()
            msg["to"] = to_email
            msg["from"] = "me"
            msg["subject"] = subject or "No Subject"
            msg.attach(MIMEText(email_body or ""))

            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = "application/octet-stream"
            main_type, sub_type = mime_type.split("/", 1)

            with open(file_path, "rb") as f:
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(f.read())
            encoders.encode_base64(attachment)
            attachment.add_header(
                "Content-Disposition", "attachment", filename=os.path.basename(file_path)
            )
            msg.attach(attachment)

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
            return f"Email with attachment sent to {to_email}. ID: {sent['id']}"

        elif action_clean == "reply":
            if not email_id:
                return "Error: 'email_id' parameter is required to reply."
            original = svc.users().messages().get(
                userId="me", id=email_id.strip(), format="metadata",
                metadataHeaders=["From", "Subject", "Message-ID"]
            ).execute()
            headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}
            thread_id = original.get("threadId", "")
            reply_to = headers.get("From", "")
            orig_subject = headers.get("Subject", "")
            reply_subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"
            msg_id = headers.get("Message-ID", "")

            msg = MIMEText(email_body or "")
            msg["to"] = reply_to
            msg["from"] = "me"
            msg["subject"] = reply_subject
            if msg_id:
                msg["In-Reply-To"] = msg_id
                msg["References"] = msg_id

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            sent = svc.users().messages().send(
                userId="me", body={"raw": raw, "threadId": thread_id}
            ).execute()
            return f"Reply sent to {reply_to}. ID: {sent['id']}"

        elif action_clean in ("delete", "trash"):
            if not email_id:
                return "Error: 'email_id' parameter is required to delete email."
            svc.users().messages().trash(userId="me", id=email_id.strip()).execute()
            return f"Email {email_id} moved to Trash."

        elif action_clean == "mark_read":
            if not email_id:
                return "Error: 'email_id' parameter is required."
            svc.users().messages().modify(
                userId="me", id=email_id.strip(), body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return f"Email {email_id} marked as read."

        elif action_clean == "mark_unread":
            if not email_id:
                return "Error: 'email_id' parameter is required."
            svc.users().messages().modify(
                userId="me", id=email_id.strip(), body={"addLabelIds": ["UNREAD"]}
            ).execute()
            return f"Email {email_id} marked as unread."

        elif action_clean == "archive":
            if not email_id:
                return "Error: 'email_id' parameter is required."
            svc.users().messages().modify(
                userId="me", id=email_id.strip(), body={"removeLabelIds": ["INBOX"]}
            ).execute()
            return f"Email {email_id} archived."

        elif action_clean == "list_labels":
            result = svc.users().labels().list(userId="me").execute()
            labels = result.get("labels", [])
            if not labels:
                return "No labels found."
            lines = ["GMAIL LABELS", "-" * 30]
            for lbl in labels:
                lines.append(f"  {lbl['name']} (ID: {lbl['id']})")
            return "\n".join(lines)

        elif action_clean == "create_label":
            if not label_name:
                return "Error: 'label_name' parameter is required."
            body = {"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
            created = svc.users().labels().create(userId="me", body=body).execute()
            return f"Label '{label_name}' created. ID: {created['id']}"

        elif action_clean == "delete_label":
            if not label_id:
                return "Error: 'label_id' parameter is required."
            svc.users().labels().delete(userId="me", id=label_id.strip()).execute()
            return f"Label {label_id} deleted."

        elif action_clean == "create_draft":
            msg = MIMEText(email_body or "")
            msg["to"] = to_email
            msg["from"] = "me"
            msg["subject"] = subject or "No Subject"
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            draft = svc.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
            return f"Draft created successfully. ID: {draft['id']}"

        elif action_clean == "send_draft":
            if not email_id:
                return "Error: 'email_id' parameter is required (draft ID)."
            sent = svc.users().drafts().send(userId="me", body={"id": email_id.strip()}).execute()
            return f"Draft {email_id} sent successfully. Message ID: {sent['id']}"

        elif action_clean == "list_drafts":
            res = svc.users().drafts().list(userId="me", maxResults=max_results).execute()
            drafts = res.get("drafts", [])
            if not drafts:
                return "No drafts found."
            lines = [f"DRAFTS - {len(drafts)} FOUND", "-" * 30]
            for d in drafts:
                d_id = d.get("id")
                lines.append(f"Draft ID: {d_id}")
            return "\n".join(lines)

        elif action_clean == "get_profile":
            prof = svc.users().getProfile(userId="me").execute()
            return f"Email: {prof.get('emailAddress')}, Total Messages: {prof.get('messagesTotal')}, Total Threads: {prof.get('threadsTotal')}"

        else:
            return f"Unknown action '{action}'. Valid actions: list_latest, search, get_body, send, send_attachment, reply, delete, mark_read, mark_unread, archive, list_labels, create_label, delete_label, create_draft, send_draft, list_drafts, get_profile."

    except Exception as e:
        return f"Gmail operation failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")

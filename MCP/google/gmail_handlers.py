"""
📧 Gmail Handler Tools
"""
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
    return get_service('gmail', 'v1')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 1: Latest Emails
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def list_latest_emails(max_results: int = 5) -> str:
    """List the latest emails in the Inbox."""
    try:
        svc = _gmail()
        results = svc.users().messages().list(
            userId='me', labelIds=['INBOX'], maxResults=max_results
        ).execute()
        messages = results.get('messages', [])

        if not messages:
            return "📥 No emails found in the Inbox."

        output = f"📥 INBOX — TOP {len(messages)} EMAILS\n{'─'*40}\n"
        for msg in messages:
            data = svc.users().messages().get(
                userId='me', id=msg['id'], format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            headers = {h['name']: h['value'] for h in data.get('payload', {}).get('headers', [])}
            snippet = data.get('snippet', '')[:100]
            output += (
                f"📌 Subject : {headers.get('Subject', 'No Subject')}\n"
                f"   From    : {headers.get('From', 'Unknown')}\n"
                f"   Date    : {headers.get('Date', '')}\n"
                f"   Preview : {snippet}...\n"
                f"   ID      : {msg['id']}\n"
                f"{'─'*40}\n"
            )
        return output
    except Exception as e:
        return f"❌ Error fetching emails: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 2: Send Email
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def send_gmail_email(to_email: str, subject: str, email_body: str) -> str:
    """Send an email via Gmail."""
    try:
        svc = _gmail()
        msg = MIMEText(email_body)
        msg['to'] = to_email
        msg['from'] = 'me'
        msg['subject'] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = svc.users().messages().send(userId='me', body={'raw': raw}).execute()
        return f"✅ Email successfully sent to {to_email}! (ID: {sent['id']})"
    except Exception as e:
        return f"❌ Error sending email: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 3: Search Emails
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def search_emails(query: str, max_results: int = 5) -> str:
    """Search for emails in Gmail using queries (e.g. from:x, subject:y)."""
    try:
        svc = _gmail()
        results = svc.users().messages().list(
            userId='me', q=query, maxResults=max_results
        ).execute()
        messages = results.get('messages', [])

        if not messages:
            return f"🔍 No emails found for '{query}'."

        output = f"🔍 SEARCH: '{query}' — {len(messages)} RESULTS\n{'─'*40}\n"
        for msg in messages:
            data = svc.users().messages().get(
                userId='me', id=msg['id'], format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            headers = {h['name']: h['value'] for h in data.get('payload', {}).get('headers', [])}
            output += (
                f"📌 {headers.get('Subject', 'No Subject')}\n"
                f"   From: {headers.get('From', 'Unknown')} | Date: {headers.get('Date', '')}\n"
                f"   ID: {msg['id']}\n"
                f"{'─'*40}\n"
            )
        return output
    except Exception as e:
        return f"❌ Error searching emails: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 4: Get Full Email Body
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def get_email_body(email_id: str) -> str:
    """Get the full content (body) of an email by its ID."""
    email_id = email_id.strip()
    try:
        svc = _gmail()
        msg = svc.users().messages().get(userId='me', id=email_id, format='full').execute()
        headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}

        # Body decode
        body = ""
        payload = msg.get('payload', {})

        def extract_body(part):
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            for sub in part.get('parts', []):
                result = extract_body(sub)
                if result:
                    return result
            return ""

        body = extract_body(payload)
        if not body:
            body = "(Body not found)"

        return (
            f"📧 EMAIL DETAILS\n{'═'*40}\n"
            f"From    : {headers.get('From', 'Unknown')}\n"
            f"To      : {headers.get('To', 'Unknown')}\n"
            f"Subject : {headers.get('Subject', 'No Subject')}\n"
            f"Date    : {headers.get('Date', '')}\n"
            f"{'─'*40}\n"
            f"{body}\n"
        )
    except Exception as e:
        return f"❌ Error getting email body: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 5: Delete Email
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def delete_email(email_id: str) -> str:
    """Move an email to the Trash."""
    email_id = email_id.strip()
    try:
        svc = _gmail()
        svc.users().messages().trash(userId='me', id=email_id).execute()
        return f"🗑️ Email (ID: {email_id}) moved to Trash."
    except Exception as e:
        return f"❌ Error deleting email: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 6: Mark Email as Read
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def mark_email_as_read(email_id: str) -> str:
    """Mark an email as read."""
    email_id = email_id.strip()
    try:
        svc = _gmail()
        svc.users().messages().modify(
            userId='me', id=email_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        return f"✅ Email (ID: {email_id}) marked as Read."
    except Exception as e:
        return f"❌ Error marking as read: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 7: Reply to Email
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def reply_to_email(email_id: str, reply_body: str) -> str:
    """Reply to a specific email."""
    email_id = email_id.strip()
    try:
        svc = _gmail()
        original = svc.users().messages().get(userId='me', id=email_id, format='metadata',
                                               metadataHeaders=['From', 'Subject', 'Message-ID', 'To']).execute()
        headers = {h['name']: h['value'] for h in original.get('payload', {}).get('headers', [])}
        thread_id = original.get('threadId', '')

        reply_to = headers.get('From', '')
        subject  = headers.get('Subject', '')
        if not subject.startswith('Re:'):
            subject = f"Re: {subject}"
        msg_id   = headers.get('Message-ID', '')

        msg = MIMEText(reply_body)
        msg['to']          = reply_to
        msg['from']        = 'me'
        msg['subject']     = subject
        msg['In-Reply-To'] = msg_id
        msg['References']  = msg_id

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(
            userId='me', body={'raw': raw, 'threadId': thread_id}
        ).execute()
        return f"✅ Reply successfully sent to {reply_to}!"
    except Exception as e:
        return f"❌ Error sending reply: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 8: List Gmail Labels
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def list_email_labels() -> str:
    """List all Gmail labels/folders."""
    try:
        svc = _gmail()
        result = svc.users().labels().list(userId='me').execute()
        labels = result.get('labels', [])

        if not labels:
            return "📂 No labels found."

        output = "📂 GMAIL LABELS\n" + "─" * 30 + "\n"
        for lbl in labels:
            output += f"  🏷️  {lbl['name']}  (ID: {lbl['id']})\n"
        return output
    except Exception as e:
        return f"❌ Error getting labels: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 9: Send Email with Attachment
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def send_email_with_attachment(to_email: str, subject: str, email_body: str, file_path: str) -> str:
    """Send an email with a file attachment."""
    try:
        if not os.path.exists(file_path):
            return f"❌ File not found: {file_path}"

        svc = _gmail()
        msg = MIMEMultipart()
        msg['to']      = to_email
        msg['from']    = 'me'
        msg['subject'] = subject
        msg.attach(MIMEText(email_body))

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        main_type, sub_type = mime_type.split('/', 1)

        with open(file_path, 'rb') as f:
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(f.read())
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', 'attachment',
                              filename=os.path.basename(file_path))
        msg.attach(attachment)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = svc.users().messages().send(userId='me', body={'raw': raw}).execute()
        return f"✅ Email with attachment successfully sent to {to_email}! (ID: {sent['id']})"
    except Exception as e:
        return f"❌ Error sending email with attachment: {e}"

# ──────────────────────────────────────────────────────────────
# ▶️ Entry Point
# ──────────────────────────────────────────────────────────────

@mcp.tool()
def mark_email_as_unread(email_id: str) -> str:
    """Mark an email as unread."""
    email_id = email_id.strip()
    try:
        _gmail().users().messages().modify(
            userId='me', id=email_id,
            body={'addLabelIds': ['UNREAD']}
        ).execute()
        return f"✅ Email (ID: {email_id}) marked as Unread."
    except Exception as e:
        return f"❌ Error marking as unread: {e}"

@mcp.tool()
def archive_email(email_id: str) -> str:
    """Archive an email (removes it from INBOX)."""
    email_id = email_id.strip()
    try:
        _gmail().users().messages().modify(
            userId='me', id=email_id,
            body={'removeLabelIds': ['INBOX']}
        ).execute()
        return f"✅ Email (ID: {email_id}) archived."
    except Exception as e:
        return f"❌ Error archiving email: {e}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
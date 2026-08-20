"""
Shared Google API helpers for MCP handlers.
"""
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, '..', '..', 'config', 'token.json')

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/forms.body',
    'https://www.googleapis.com/auth/forms.responses.readonly',
]


def get_credentials() -> Credentials:
    if not os.path.exists(TOKEN_PATH):
        raise Exception(
            "❌ token.json file not found! Run python auth_setup.py first to authenticate."
        )
    # Use scopes stored in token.json (do not force invalid/extra scopes on refresh)
    creds = Credentials.from_authorized_user_file(TOKEN_PATH)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())
    return creds


def get_service(api_name: str, api_version: str):
    return build(api_name, api_version, credentials=get_credentials())


def escape_drive_query(text: str) -> str:
    """Escape user text for Drive API query strings."""
    return text.replace("\\", "\\\\").replace("'", "\\'")


def share_file(file_id: str, email: str, role: str = "reader") -> dict:
    """
    Share a Drive file. role: reader | writer | commenter
    """
    if role not in ("reader", "writer", "commenter"):
        role = "reader"
    drive = get_service('drive', 'v3')
    return drive.permissions().create(
        fileId=file_id,
        body={'type': 'user', 'role': role, 'emailAddress': email},
        fields='id, role, emailAddress',
        sendNotificationEmail=True,
    ).execute()

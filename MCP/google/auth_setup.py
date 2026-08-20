"""
Google OAuth First-Time Setup Script
Run this ONCE to generate token.json
After this, Syntiox CORE MCP server will work automatically.
"""

import os
import sys

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, '..', '..', 'config', 'credentials.json')
TOKEN_PATH       = os.path.join(BASE_DIR, '..', '..', 'config', 'token.json')

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

def main():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    print("-" * 50)
    print("Google OAuth Setup - One Time Login")
    print("-" * 50)

    if not os.path.exists(CREDENTIALS_PATH):
        print(f"❌ credentials.json not found: {CREDENTIALS_PATH}")
        print("Download it from Google Cloud Console → APIs & Services → Credentials")
        sys.exit(1)

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🌐 Opening browser for Google login...")
            print("   (If browser doesn't open, check the URL printed below)")
            flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)

        with open(TOKEN_PATH, 'w') as f:
            f.write(creds.to_json())

        print("-" * 50)
        print("[OK] Login successful!")
        print(f"[OK] Token saved -> {TOKEN_PATH}")
        print("-" * 50)
        print("[OK] Now restart Syntiox CORE - Google Suite MCP will work!")
        print("[NOTE] If new scopes were added, delete google/token.json first to force full re-login.")
    else:
        print("[OK] Token already valid - no login needed!")
        print(f"   Token: {TOKEN_PATH}")

if __name__ == "__main__":
    main()

"""One-time Gmail OAuth2 setup.

Usage:
    python scripts/gmail_auth.py [--account marwan|subscriptions]

Prerequisites:
    1. Go to https://console.cloud.google.com
    2. Create a project (or use an existing one)
    3. APIs & Services -> Library -> enable "Gmail API"
    4. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
    5. Application type: Desktop app
    6. Add the client_id and client_secret to .env:
         GMAIL_MARWAN_CLIENT_ID=...
         GMAIL_MARWAN_CLIENT_SECRET=...
    7. Run this script. It will open a browser for you to authorize.
       Tokens are stored locally and auto-refresh.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from app.config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def authorize(account: str = "marwan"):
    settings = get_settings()

    if account == "marwan":
        client_id = settings.gmail_marwan_client_id
        client_secret = settings.gmail_marwan_client_secret
        token_path = settings.gmail_marwan_token_path
        address = settings.gmail_marwan_address
    elif account == "subscriptions":
        client_id = settings.gmail_marwan_client_id  # same OAuth client
        client_secret = settings.gmail_marwan_client_secret
        token_path = settings.gmail_subscriptions_token_path
        address = settings.gmail_subscriptions_address
    else:
        print(f"Unknown account: {account}")
        sys.exit(1)

    if not client_id or not client_secret:
        print("ERROR: GMAIL_MARWAN_CLIENT_ID / GMAIL_MARWAN_CLIENT_SECRET not set in .env")
        print("See the docstring at the top of this file for setup steps.")
        sys.exit(1)

    token_path = Path(token_path)
    token_path.parent.mkdir(parents=True, exist_ok=True)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    print(f"\nAuthorizing {account} ({address})...")
    print("Your browser will open. Sign in with the correct Google account.\n")

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"\nTokens saved to: {token_path}")
    print("This account is now authorized. Tokens will auto-refresh.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default="marwan", choices=["marwan", "subscriptions"])
    args = parser.parse_args()
    authorize(args.account)

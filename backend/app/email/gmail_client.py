"""Gmail API wrapper — read inbox, send messages."""
import base64
import json
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Iterator, Optional
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings

settings = get_settings()


def _load_creds(token_path: str) -> Optional[Credentials]:
    p = Path(token_path)
    if not p.exists():
        return None
    creds = Credentials.from_authorized_user_info(
        json.loads(p.read_text(encoding="utf-8")),
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
        ],
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        p.write_text(creds.to_json(), encoding="utf-8")
    return creds


def get_service(account: str = "marwan"):
    """Returns an authenticated Gmail API client, or None if not authorized yet."""
    if account == "marwan":
        token_path = settings.gmail_marwan_token_path
    elif account == "subscriptions":
        token_path = settings.gmail_subscriptions_token_path
    else:
        raise ValueError(f"Unknown account: {account}")

    creds = _load_creds(token_path)
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def list_message_ids(
    service,
    query: str = "newer_than:7d",
    max_results: int = 200,
) -> list[str]:
    """List Gmail message IDs matching the query."""
    ids: list[str] = []
    page_token = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token, maxResults=min(max_results, 500))
            .execute()
        )
        for m in resp.get("messages", []):
            ids.append(m["id"])
            if len(ids) >= max_results:
                return ids
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


def get_message(service, message_id: str) -> dict:
    """Fetch a full message by ID."""
    return service.users().messages().get(userId="me", id=message_id, format="full").execute()


def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> tuple[str, str]:
    """Returns (text, html). Walks multipart structures."""
    text_body, html_body = "", ""

    def walk(part: dict):
        nonlocal text_body, html_body
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data:
            if mime == "text/plain" and not text_body:
                text_body = _decode_part(data)
            elif mime == "text/html" and not html_body:
                html_body = _decode_part(data)
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return text_body, html_body


def _header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _parse_addresses(field: str) -> list[str]:
    if not field:
        return []
    matches = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", field)
    return [m.lower() for m in matches]


def parse_message(raw: dict) -> dict:
    """Convert a raw Gmail API message into a flat dict suitable for our DB."""
    payload = raw.get("payload", {})
    headers = payload.get("headers", [])

    from_field = _header(headers, "From")
    from_addresses = _parse_addresses(from_field)
    from_address = from_addresses[0] if from_addresses else ""
    from_name_match = re.match(r'^"?([^"<]*?)"?\s*<', from_field)
    from_name = from_name_match.group(1).strip() if from_name_match else ""

    to_addresses = _parse_addresses(_header(headers, "To"))
    cc_addresses = _parse_addresses(_header(headers, "Cc"))

    subject = _header(headers, "Subject")
    message_id = _header(headers, "Message-ID") or raw["id"]
    in_reply_to = _header(headers, "In-Reply-To") or None
    date_header = _header(headers, "Date")

    text_body, html_body = _extract_body(payload)
    snippet = raw.get("snippet", "")

    sent_at = None
    if "internalDate" in raw:
        sent_at = datetime.fromtimestamp(int(raw["internalDate"]) / 1000, tz=timezone.utc)

    has_attachments = any(
        p.get("filename") for p in payload.get("parts", []) or []
    )

    return {
        "gmail_id": raw["id"],
        "thread_id": raw.get("threadId"),
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "from_address": from_address,
        "from_name": from_name or None,
        "to_addresses": to_addresses,
        "cc_addresses": cc_addresses,
        "subject": subject or None,
        "body_text": text_body or None,
        "body_html": html_body or None,
        "snippet": snippet,
        "sent_at": sent_at,
        "labels": raw.get("labelIds", []),
        "has_attachments": has_attachments,
        "is_read": "UNREAD" not in raw.get("labelIds", []),
    }


def send_message(
    service,
    to: list[str],
    subject: str,
    body_text: str,
    cc: Optional[list[str]] = None,
    in_reply_to: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> dict:
    """Send an email via the authenticated account. Returns Gmail's response."""
    msg = MIMEMultipart("alternative") if False else MIMEText(body_text, "plain", "utf-8")
    msg["to"] = ", ".join(to)
    if cc:
        msg["cc"] = ", ".join(cc)
    msg["subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    body: dict = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id

    return service.users().messages().send(userId="me", body=body).execute()

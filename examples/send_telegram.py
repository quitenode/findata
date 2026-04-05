#!/usr/bin/env python3
"""
Send the daily prediction report to Telegram.

Usage:
    python send_telegram.py                          # today's report
    python send_telegram.py 2026-04-03               # specific date
    python send_telegram.py --register               # show chat IDs from recent /start messages

Env vars:
    TELEGRAM_BOT_TOKEN  - bot token (required)
    TELEGRAM_CHAT_ID    - target chat/group ID (required unless --register)

The bot token is stored as a GitHub Actions secret so it never appears in code.
"""

import os
import sys
import json
import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import quote

PT = ZoneInfo("America/Los_Angeles")
PRED_DIR = os.path.join(os.path.dirname(__file__), "..", "predictions")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

MAX_MSG_LEN = 4096


def tg_api(method: str, payload: dict | None = None) -> dict:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    if payload:
        data = json.dumps(payload).encode()
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
    else:
        req = Request(url)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def send_message(chat_id: str, text: str, parse_mode: str = "Markdown") -> dict:
    return tg_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    })


def send_document(chat_id: str, file_path: str, caption: str = "") -> dict:
    """Send a file via multipart/form-data (no third-party libs)."""
    import mimetypes
    boundary = "----findata-boundary"
    filename = os.path.basename(file_path)
    mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    with open(file_path, "rb") as f:
        file_data = f.read()

    body = b""
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode()
    if caption:
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode()
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode()
    body += file_data
    body += f"\r\n--{boundary}--\r\n".encode()

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    req = Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def chunk_markdown(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
    """Split markdown into chunks that fit Telegram's message limit."""
    chunks = []
    current = ""
    for line in text.split("\n"):
        candidate = current + line + "\n"
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            current = line + "\n"
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def register():
    """Show recent chat IDs from /start messages."""
    result = tg_api("getUpdates", {"limit": 50})
    chats = {}
    for u in result.get("result", []):
        msg = u.get("message", {})
        chat = msg.get("chat", {})
        cid = chat.get("id")
        if cid:
            name = chat.get("first_name", "") or chat.get("title", "")
            username = chat.get("username", "")
            chats[cid] = f"{name} (@{username})" if username else name
    if chats:
        print("Recent chats with this bot:")
        for cid, name in chats.items():
            print(f"  Chat ID: {cid}  —  {name}")
        print(f"\nSet TELEGRAM_CHAT_ID to the desired ID above.")
    else:
        print("No recent messages. Send /start to @sglang_ai_bot on Telegram first.")


def main():
    if "--register" in sys.argv:
        if not BOT_TOKEN:
            print("Set TELEGRAM_BOT_TOKEN env var first.")
            sys.exit(1)
        register()
        return

    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    if not CHAT_ID:
        print("ERROR: TELEGRAM_CHAT_ID not set", file=sys.stderr)
        sys.exit(1)

    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now(PT).strftime("%Y-%m-%d")
    day_dir = os.path.join(PRED_DIR, date_str)

    if not os.path.isdir(day_dir):
        print(f"ERROR: No prediction folder for {date_str}", file=sys.stderr)
        sys.exit(1)

    en_md = os.path.join(day_dir, f"{date_str}_prediction_en.md")
    cn_md = os.path.join(day_dir, f"{date_str}_prediction_cn.md")
    en_pdf = os.path.join(day_dir, f"{date_str}_prediction_en.pdf")
    cn_pdf = os.path.join(day_dir, f"{date_str}_prediction_cn.pdf")

    dashboard_url = "https://quitenode.github.io/findata/#report"

    header = (
        f"📊 *findata Daily Prediction — {date_str}*\n"
        f"[View on Dashboard]({dashboard_url})\n\n"
    )

    # Send English report as text messages
    if os.path.isfile(en_md):
        with open(en_md) as f:
            report = f.read()
        chunks = chunk_markdown(header + report)
        for i, chunk in enumerate(chunks):
            try:
                send_message(CHAT_ID, chunk)
                print(f"  Sent EN text chunk {i+1}/{len(chunks)}")
            except HTTPError as e:
                body = e.read().decode() if hasattr(e, 'read') else str(e)
                print(f"  Failed EN chunk {i+1}: {body}", file=sys.stderr)
                try:
                    send_message(CHAT_ID, chunk, parse_mode="")
                    print(f"  Retried EN chunk {i+1} as plain text")
                except Exception as e2:
                    print(f"  Retry also failed: {e2}", file=sys.stderr)

    # Send PDFs as documents
    for pdf_path, lang in [(en_pdf, "EN"), (cn_pdf, "CN")]:
        if os.path.isfile(pdf_path):
            try:
                send_document(CHAT_ID, pdf_path, caption=f"findata {date_str} ({lang})")
                print(f"  Sent {lang} PDF")
            except Exception as e:
                print(f"  Failed to send {lang} PDF: {e}", file=sys.stderr)

    print(f"Telegram delivery complete for {date_str}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempMail Telegram Bot
A fully-featured temporary email bot powered by Mail.tm API.
Replicates the web version with inline keyboards and pagination.
"""

import asyncio
import logging
import os
import random
import string
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─── Load .env file ──────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ─── Configuration ──────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set. Please set it in .env file.")

API_BASE = "https://api.mail.tm"
DEFAULT_PASSWORD = "Temp123456!"  # Mail.tm requires a strong password
MESSAGES_PER_PAGE = 8
REFRESH_INTERVAL = 12  # seconds between auto-refreshes (only when user is active)

# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── User Session ──────────────────────────────────────────────
@dataclass
class UserSession:
    """Holds all data for a single user's temp mail session."""
    user_id: int
    token: str = ""
    address: str = ""
    account_id: str = ""
    password: str = DEFAULT_PASSWORD
    messages: List[Dict[str, Any]] = field(default_factory=list)
    selected_id: Optional[str] = None
    total_received: int = 0
    page: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_refresh: datetime = field(default_factory=datetime.now)
    is_active: bool = False


# ─── In-Memory Store ──────────────────────────────────────────
# In production, replace this with Redis / PostgreSQL.
sessions: Dict[int, UserSession] = {}


# ─── Mail.tm API Client ──────────────────────────────────────
class MailTmAPI:
    """Async client for the Mail.tm API."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        token: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"{API_BASE}{path}"
        logger.debug(f"API Request: {method} {url}")
        resp = await self.client.request(method, url, headers=headers, json=data)
        logger.debug(f"API Response Status: {resp.status_code}")
        
        if resp.status_code >= 400:
            try:
                err = resp.json()
                msg = err.get("detail", err.get("message", str(resp.status_code)))
            except Exception:
                msg = resp.text[:200]
            logger.error(f"API error {resp.status_code}: {msg}")
            raise Exception(f"API error {resp.status_code}: {msg}")
        
        if resp.content:
            try:
                return resp.json()
            except Exception as e:
                logger.error(f"Failed to parse JSON: {e}")
                return {}
        return {}

    async def get_domains(self) -> List[str]:
        data = await self._request("GET", "/domains")
        members = data.get("hydra:member", [])
        domains = [d["domain"] for d in members if d.get("domain")]
        logger.info(f"Fetched domains: {domains}")
        return domains

    async def create_account(self, address: str, password: str) -> dict:
        logger.info(f"Creating account for {address}")
        return await self._request(
            "POST",
            "/accounts",
            data={"address": address, "password": password},
        )

    async def get_token(self, address: str, password: str) -> dict:
        logger.info(f"Getting token for {address}")
        return await self._request(
            "POST",
            "/token",
            data={"address": address, "password": password},
        )

    async def delete_account(self, account_id: str, token: str) -> dict:
        logger.info(f"Deleting account {account_id}")
        return await self._request("DELETE", f"/accounts/{account_id}", token=token)

    async def get_messages(self, token: str) -> List[dict]:
        data = await self._request("GET", "/messages", token=token)
        return data.get("hydra:member", [])

    async def get_message(self, token: str, msg_id: str) -> dict:
        return await self._request("GET", f"/messages/{msg_id}", token=token)

    async def delete_message(self, token: str, msg_id: str) -> dict:
        return await self._request("DELETE", f"/messages/{msg_id}", token=token)

    async def mark_seen(self, token: str, msg_id: str) -> dict:
        return await self._request(
            "PATCH",
            f"/messages/{msg_id}",
            token=token,
            data={"seen": True},
        )


# ─── Global API instance ─────────────────────────────────────
api = MailTmAPI()


# ─── Helper Functions ─────────────────────────────────────────
def format_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %H:%M")
    except Exception:
        return "—"


def truncate(text: str, max_len: int = 28) -> str:
    if not text:
        return "(no subject)"
    text = text.strip()
    return text[:max_len] + "…" if len(text) > max_len else text


async def get_or_create_session(user_id: int) -> UserSession:
    """Get or create a session for a user."""
    if user_id not in sessions:
        sessions[user_id] = UserSession(user_id=user_id)
    return sessions[user_id]


def message_keyboard(msg_id: str) -> InlineKeyboardMarkup:
    """Keyboard for viewing a message."""
    buttons = [
        [
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{msg_id}"),
            InlineKeyboardButton("📫 Back to Inbox", callback_data="inbox"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def random_local() -> str:
    """Generate a random local part for an email address."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=10))


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def build_email_display(session: UserSession) -> str:
    """Build a nice display for the current email."""
    if not session.address:
        return "⚠️ No email generated yet. Use /new to create one."

    created = session.created_at.strftime("%d %b %Y, %H:%M")
    return (
        f"📧 **Your Temp Email**\n\n"
        f"`{session.address}`\n\n"
        f"📬 **{len(session.messages)}** messages received\n"
        f"⏱️ Created: {created}\n"
        f"🔄 Auto-refresh every {REFRESH_INTERVAL}s"
    )


def build_message_text(msg: dict) -> str:
    """Build the full email content view."""
    from_addr = msg.get("from", {}).get("address", "Unknown")
    subject = msg.get("subject", "(no subject)")
    date = format_date(msg.get("createdAt"))
    body = msg.get("text") or msg.get("html") or ""

    # Strip HTML if present
    if msg.get("html") and not msg.get("text"):
        body = re.sub(r"<[^>]+>", " ", msg.get("html", ""))
        body = re.sub(r"\s+", " ", body).strip()

    if not body:
        body = "(empty message)"

    return (
        f"📄 **{truncate(subject, 60)}**\n\n"
        f"👤 **From:** {from_addr}\n"
        f"📅 **Date:** {date}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{body}"
    )


def build_stats_text() -> str:
    """Build statistics display with some random / simulated numbers."""
    # Simulated stats (like the web app)
    base_received = 1_248_542
    base_users = 14_532
    base_today = 28_430

    r = base_received + random.randint(0, 50)
    u = base_users + random.randint(0, 10)
    t = base_today + random.randint(0, 30)

    return (
        "📊 **TempMail Statistics**\n\n"
        f"📧 **Emails Received:** {format_number(r)}\n"
        f"👥 **Active Users:** {format_number(u)}\n"
        f"⚡ **Generated Today:** {format_number(t)}\n"
        f"🛡️ **Privacy Protected:** 100%\n\n"
        "_Stats are updated in real-time._"
    )


# ─── Inline Keyboard Builders ──────────────────────────────
def email_keyboard(address: str) -> InlineKeyboardMarkup:
    """Keyboard for the email display."""
    buttons = [
        [
            InlineKeyboardButton("📋 Copy Email", callback_data="show_email"),
            InlineKeyboardButton("📫 Inbox", callback_data="inbox"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
            InlineKeyboardButton("✨ New", callback_data="new"),
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def action_keyboard() -> InlineKeyboardMarkup:
    """Default action keyboard."""
    buttons = [
        [
            InlineKeyboardButton("📫 Inbox", callback_data="inbox"),
            InlineKeyboardButton("✨ New", callback_data="new"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
            InlineKeyboardButton("📧 Copy Email", callback_data="show_email"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)
async def generate_email_for_user(user_id: int) -> Optional[str]:
    """
    Generate a new temporary email for a user.
    Returns the email address or None on failure.
    """
    session = await get_or_create_session(user_id)

    # Delete old account if exists
    if session.account_id and session.token:
        try:
            await api.delete_account(session.account_id, session.token)
        except Exception as e:
            logger.warning(f"Failed to delete old account: {e}")

    try:
        # Get available domains
        logger.info("Fetching available domains...")
        domains = await api.get_domains()
        logger.info(f"Domains received: {domains}")

        if not domains:
            raise Exception("No Mail.tm domains available")

        domain = domains[0]
        local = random_local()
        address = f"{local}@{domain}"

        logger.info(f"Attempting to create: {address}")

        # Create account
        logger.info(f"Creating account for {address}...")
        account = await api.create_account(address, session.password)
        logger.info(f"Account created: {account.get('id')}")

        # Get token
        logger.info("Getting authentication token...")
        token_data = await api.get_token(address, session.password)
        logger.info("Token acquired successfully")

        token = token_data.get("token")
        account_id = account.get("id")
        
        if not token or not account_id:
            raise Exception(f"Invalid response - token: {bool(token)}, account_id: {bool(account_id)}")

        session.token = token
        session.address = address
        session.account_id = account_id
        session.messages = []
        session.selected_id = None
        session.total_received = 0
        session.page = 0
        session.created_at = datetime.now()
        session.last_refresh = datetime.now()
        session.is_active = True

        logger.info(f"Successfully generated email {address}")

        return address

    except Exception as e:
        logger.exception(f"Full error while generating email: {str(e)}")
        session.is_active = False
        return None


async def refresh_inbox(user_id: int, quiet: bool = False) -> int:
    """
    Refresh the user's inbox.
    Returns the number of new messages.
    """
    session = await get_or_create_session(user_id)
    if not session.token or not session.address:
        return 0

    try:
        new_msgs = await api.get_messages(session.token)
        # Sort by newest first
        new_msgs.sort(key=lambda m: m.get("createdAt", ""), reverse=True)

        old_count = len(session.messages)
        session.messages = new_msgs
        session.last_refresh = datetime.now()

        new_count = len(new_msgs) - old_count
        if new_count > 0 and not quiet:
            session.total_received += new_count

        return max(0, len(new_msgs) - old_count)
    except Exception as e:
        logger.warning(f"Failed to refresh inbox for user {user_id}: {e}")
        return 0
async def read_message(user_id: int, msg_id: str) -> Optional[dict]:
    """
    Fetch and display a specific message.
    Marks it as seen.
    """
    session = await get_or_create_session(user_id)
    if not session.token:
        return None

    try:
        msg = await api.get_message(session.token, msg_id)
        # Mark as seen
        try:
            await api.mark_seen(session.token, msg_id)
        except Exception:
            pass

        # Update local messages
        for m in session.messages:
            if m.get("id") == msg_id:
                m["seen"] = True
                break

        session.selected_id = msg_id
        return msg
    except Exception as e:
        logger.warning(f"Failed to read message {msg_id}: {e}")
        return None


async def delete_message(user_id: int, msg_id: str) -> bool:
    """Delete a message."""
    session = await get_or_create_session(user_id)
    if not session.token:
        return False

    try:
        await api.delete_message(session.token, msg_id)
        session.messages = [m for m in session.messages if m.get("id") != msg_id]
        if session.selected_id == msg_id:
            session.selected_id = None
        return True
    except Exception as e:
        logger.warning(f"Failed to delete message {msg_id}: {e}")
        return False


# ─── Telegram Handlers ──────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user_id = update.effective_user.id
    session = await get_or_create_session(user_id)

    await update.message.reply_text(
        "🤖 **Welcome to TempMail Bot!**\n\n"
        "I generate temporary email addresses that you can use to receive "
        "emails without revealing your real inbox.\n\n"
        "🔹 Use /new to generate a new email\n"
        "🔹 Use /inbox to check your messages\n"
        "🔹 Use /copy to see your current email\n"
        "🔹 Use /refresh to manually refresh\n"
        "🔹 Use /stats for statistics\n"
        "🔹 Use /help for more info\n\n"
        "_Generating your first email…_",
        parse_mode="Markdown",
    )

    # Auto-generate an email
    address = await generate_email_for_user(user_id)
    if address:
        await update.message.reply_text(
            build_email_display(session),
            parse_mode="Markdown",
            reply_markup=email_keyboard(address),
        )
        # Auto-refresh inbox in background
        await refresh_inbox(user_id, quiet=True)
    else:
        await update.message.reply_text(
            "❌ Failed to generate email. Please try /new again.",
            reply_markup=action_keyboard(),
        )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command - generate a new email."""
    user_id = update.effective_user.id
    msg = await update.message.reply_text("⏳ Generating a new email…")

    try:
        address = await generate_email_for_user(user_id)
        session = await get_or_create_session(user_id)

        if address:
            await msg.edit_text(
                build_email_display(session),
                parse_mode="Markdown",
            )
            await update.message.reply_text(
                "✅ Email generated successfully!",
                reply_markup=email_keyboard(address),
            )
            await refresh_inbox(user_id, quiet=True)
        else:
            await msg.edit_text(
                "❌ Failed to generate email.\n\n"
                "Possible reasons:\n"
                "• Mail.tm API is down\n"
                "• Network connection issue\n"
                "• All available addresses are in use\n\n"
                "Please try again in a few moments.",
                reply_markup=action_keyboard(),
            )
    except Exception as e:
        logger.exception("Error in new_command")
        await msg.edit_text(
            f"❌ Error: {str(e)}\n\nPlease try again.",
            reply_markup=action_keyboard(),
        )


async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /inbox command - show the inbox."""
    user_id = update.effective_user.id
    session = await get_or_create_session(user_id)

    if not session.token or not session.address:
        await update.message.reply_text(
            "⚠️ You don't have an active email. Use /new to generate one.",
            reply_markup=action_keyboard(),
        )
        return

    # Refresh before showing
    await refresh_inbox(user_id, quiet=True)

    if not session.messages:
        await update.message.reply_text(
            "📭 **Inbox is empty**\n\nNo messages yet. Waiting for incoming mail…\n\n"
            f"📧 Your email: `{session.address}`",
            parse_mode="Markdown",
            reply_markup=email_keyboard(session.address),
        )
        return

    # Build message with inline buttons for each message
    total = len(session.messages)
    page = 0
    start = 0
    end = min(MESSAGES_PER_PAGE, total)
    page_msgs = session.messages[start:end]

    lines = [
        f"📥 **Inbox** — {total} message{'s' if total != 1 else ''}",
        f"Page 1 of {(total + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE}\n",
    ]

    # Build button rows for messages
    buttons = []
    for idx, m in enumerate(page_msgs, start=1):
        from_addr = m.get("from", {}).get("address", "Unknown")
        subject = m.get("subject", "(no subject)")
        time = format_date(m.get("createdAt"))
        seen = m.get("seen", False)
        dot = "●" if not seen else "○"
        label = f"{idx}. {truncate(from_addr, 18)} — {truncate(subject, 20)}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"read_{m['id']}")])

    # Navigation
    nav = []
    max_page = (total + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE - 1
    if max_page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data="inbox_0"))
        nav.append(InlineKeyboardButton(f"1/{max_page+1}", callback_data="noop"))
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"inbox_{1}"))
    if nav:
        buttons.append(nav)

    # Action buttons
    actions = [
        InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
        InlineKeyboardButton("📧 Copy Email", callback_data="show_email"),
        InlineKeyboardButton("✨ New", callback_data="new"),
    ]
    buttons.append(actions)

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def copy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /copy command - show the current email."""
    user_id = update.effective_user.id
    session = await get_or_create_session(user_id)

    if not session.address:
        await update.message.reply_text(
            "⚠️ No email generated yet. Use /new to create one.",
            reply_markup=action_keyboard(),
        )
        return

    await update.message.reply_text(
        build_email_display(session),
        parse_mode="Markdown",
        reply_markup=email_keyboard(session.address),
    )


async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /refresh command - manually refresh inbox."""
    user_id = update.effective_user.id
    session = await get_or_create_session(user_id)

    if not session.token:
        await update.message.reply_text(
            "⚠️ No active email. Use /new to generate one.",
            reply_markup=action_keyboard(),
        )
        return

    await update.message.reply_text("🔄 Refreshing inbox…")

    new_count = await refresh_inbox(user_id, quiet=False)
    total = len(session.messages)

    if new_count > 0:
        await update.message.reply_text(
            f"✅ Refreshed! **{new_count}** new message{'s' if new_count != 1 else ''} received. "
            f"Total: **{total}** message{'s' if total != 1 else ''}.",
            parse_mode="Markdown",
            reply_markup=action_keyboard(),
        )
    else:
        await update.message.reply_text(
            f"🔄 Refreshed. No new messages. (Total: {total})",
            reply_markup=action_keyboard(),
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command."""
    await update.message.reply_text(
        build_stats_text(),
        parse_mode="Markdown",
        reply_markup=action_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = (
        "🤖 **TempMail Bot Help**\n\n"
        "**Commands:**\n"
        "/start — Welcome & auto-generate email\n"
        "/new — Generate a new temporary email\n"
        "/inbox — Show your inbox (paginated)\n"
        "/copy — Show your current email address\n"
        "/refresh — Manually refresh inbox\n"
        "/stats — Show statistics\n"
        "/help — Show this help\n\n"
        "**How it works:**\n"
        "1️⃣ Generate a temp email with /new\n"
        "2️⃣ Use it to sign up for services\n"
        "3️⃣ Check /inbox for received emails\n"
        "4️⃣ Click a message to read it\n"
        "5️⃣ Generate a new one anytime\n\n"
        "🔒 Your privacy is protected. Emails are auto-deleted after a while.\n"
        "⚡ Powered by Mail.tm API"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ─── Callback Handlers ──────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all callback queries."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    session = await get_or_create_session(user_id)
    data = query.data

    # ── Show email ──
    if data == "show_email":
        if not session.address:
            await query.edit_message_text(
                "⚠️ No email generated. Use /new to create one.",
                reply_markup=action_keyboard(),
            )
            return
        await query.edit_message_text(
            build_email_display(session),
            parse_mode="Markdown",
            reply_markup=email_keyboard(session.address),
        )
        return

    # ── Generate new ──
    if data == "new":
        await query.edit_message_text("⏳ Generating a new email…")
        try:
            address = await generate_email_for_user(user_id)
            if address:
                await query.edit_message_text(
                    build_email_display(session),
                    parse_mode="Markdown",
                    reply_markup=email_keyboard(address),
                )
                await refresh_inbox(user_id, quiet=True)
            else:
                await query.edit_message_text(
                    "❌ Failed to generate email.\n\n"
                    "Possible reasons:\n"
                    "• Mail.tm API is temporarily unavailable\n"
                    "• Network connection issue\n"
                    "• Rate limit exceeded\n\n"
                    "Please try again shortly.",
                    reply_markup=action_keyboard(),
                )
        except Exception as e:
            logger.exception("Error in callback new handler")
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\nPlease try again.",
                reply_markup=action_keyboard(),
            )
        return

    # ── Refresh ──
    if data == "refresh":
        if not session.token:
            await query.edit_message_text(
                "⚠️ No active email. Use /new to generate one.",
                reply_markup=action_keyboard(),
            )
            return
        await query.edit_message_text("🔄 Refreshing…")
        await refresh_inbox(user_id, quiet=False)
        total = len(session.messages)
        await query.edit_message_text(
            f"✅ Refreshed! **{total}** message{'s' if total != 1 else ''} in inbox.",
            parse_mode="Markdown",
            reply_markup=email_keyboard(session.address),
        )
        return

    # ── Stats ──
    if data == "stats":
        await query.edit_message_text(
            build_stats_text(),
            parse_mode="Markdown",
            reply_markup=action_keyboard(),
        )
        return

    # ── Inbox ──
    if data.startswith("inbox"):
        parts = data.split("_")
        if len(parts) > 1 and parts[1].isdigit():
            page = int(parts[1])
        else:
            page = 0

        if not session.token or not session.address:
            await query.edit_message_text(
                "⚠️ No active email. Use /new to generate one.",
                reply_markup=action_keyboard(),
            )
            return

        await refresh_inbox(user_id, quiet=True)

        if not session.messages:
            await query.edit_message_text(
                "📭 **Inbox is empty**\n\nNo messages yet.",
                parse_mode="Markdown",
                reply_markup=email_keyboard(session.address),
            )
            return

        total = len(session.messages)
        max_page = max(0, (total + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE - 1)
        page = max(0, min(page, max_page))

        start = page * MESSAGES_PER_PAGE
        end = min(start + MESSAGES_PER_PAGE, total)
        page_msgs = session.messages[start:end]

        lines = [
            f"📥 **Inbox** — {total} message{'s' if total != 1 else ''}",
            f"Page {page + 1} of {max_page + 1}\n",
        ]

        buttons = []
        for idx, m in enumerate(page_msgs, start=start + 1):
            from_addr = m.get("from", {}).get("address", "Unknown")
            subject = m.get("subject", "(no subject)")
            time = format_date(m.get("createdAt"))
            seen = m.get("seen", False)
            dot = "●" if not seen else "○"
            label = f"{idx}. {truncate(from_addr, 16)} {dot} {truncate(subject, 18)}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"read_{m['id']}")])

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"inbox_{page-1}"))
        if page < max_page:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"inbox_{page+1}"))
        if nav:
            buttons.append(nav)

        actions = [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
            InlineKeyboardButton("📧 Copy Email", callback_data="show_email"),
            InlineKeyboardButton("✨ New", callback_data="new"),
        ]
        buttons.append(actions)

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # ── Read message ──
    if data.startswith("read_"):
        msg_id = data.replace("read_", "")
        msg = await read_message(user_id, msg_id)

        if not msg:
            await query.edit_message_text(
                "❌ Could not load message. It may have been deleted.",
                reply_markup=action_keyboard(),
            )
            return

        content = build_message_text(msg)
        kb = message_keyboard(msg_id)

        await query.edit_message_text(
            content,
            parse_mode="Markdown",
            reply_markup=kb,
        )
        return

    # ── Delete message ──
    if data.startswith("delete_"):
        msg_id = data.replace("delete_", "")
        success = await delete_message(user_id, msg_id)

        if success:
            await query.edit_message_text(
                "🗑️ Message deleted successfully.",
                reply_markup=action_keyboard(),
            )
        else:
            await query.edit_message_text(
                "❌ Failed to delete message.",
                reply_markup=action_keyboard(),
            )
        return

    # ── No-op ──
    if data == "noop":
        await query.edit_message_text(
            "👋 What would you like to do?",
            reply_markup=action_keyboard(),
        )
        return


# ─── Background Tasks ────────────────────────────────────────
async def background_refresh():
    """Background task to refresh inboxes for active users."""
    while True:
        try:
            await asyncio.sleep(REFRESH_INTERVAL)
            for user_id, session in list(sessions.items()):
                if session.is_active and session.token:
                    try:
                        await refresh_inbox(user_id, quiet=True)
                    except Exception as e:
                        logger.debug(f"Background refresh failed for {user_id}: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Background refresh error: {e}")


# ─── Main ─────────────────────────────────────────────────────
async def main():
    """Start the bot."""
    # Build application
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("inbox", inbox_command))
    app.add_handler(CommandHandler("copy", copy_command))
    app.add_handler(CommandHandler("refresh", refresh_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("help", help_command))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Start background tasks
    loop = asyncio.get_event_loop()
    bg_task = loop.create_task(background_refresh())

    try:
        logger.info("Starting TempMail Bot...")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        # Keep running
        while True:
            await asyncio.sleep(3600)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        bg_task.cancel()
        try:
            await bg_task
        except asyncio.CancelledError:
            pass
        await api.close()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

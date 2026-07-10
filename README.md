# 📧 TempMail Telegram Bot

**Instant Disposable Email – Right in Your Telegram**

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue)](https://core.telegram.org/bots)

A fully-featured Telegram bot that generates temporary email addresses using the [Mail.tm](https://mail.tm) API. Protect your privacy, avoid spam, and receive OTPs or verification codes – all from your favourite messenger.

---

## ✨ Features

- 🚀 **Instant Generation** – Create a new disposable email with `/new` in seconds.
- 📬 **Live Inbox** – Automatically refreshes every 12 seconds; see new messages as they arrive.
- 📖 **Read Messages** – Tap any email to view sender, date, and full content (HTML stripped).
- 📋 **One‑tap Copy** – Copy your email address directly to your clipboard via inline buttons.
- 🔄 **Manual Refresh** – Use `/refresh` or the refresh button to check for new mail anytime.
- 🗑️ **Delete Messages** – Remove individual messages or generate a new email to start fresh.
- 📊 **Statistics** – View global usage stats (simulated) with `/stats`.
- 🌙 **Always On** – The bot runs 24/7; you keep your session alive as long as you use it.

---

## 🤖 Commands

| Command     | Description |
|-------------|-------------|
| `/start`    | Welcome message and auto‑generates your first email. |
| `/new`      | Generates a brand new temporary email (old one is discarded). |
| `/inbox`    | Shows your paginated message list. |
| `/copy`     | Displays your current email address with a copy button. |
| `/refresh`  | Manually refreshes the inbox. |
| `/stats`    | Shows global usage statistics. |
| `/help`     | Displays this help text. |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- A [Telegram Bot Token](https://core.telegram.org/bots#6-botfather) from @BotFather
- (Optional) `pip` and a virtual environment

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/xsazedul/tempmail-telegram-bot.git
   cd tempmail-telegram-bot

# 📧 TempMail Telegram Bot

**Instant Disposable Email – Right in Your Telegram**

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue)](https://core.telegram.org/bots)

A fully-featured Telegram bot that generates temporary email addresses using the [Mail.tm](https://mail.tm) API. Protect your privacy, avoid spam, and receive OTPs or verification codes – all from your favourite messenger.

---
### Prerequisites

- Python 3.8 or higher
- Visual Studio Code
- Git
- A Telegram Bot Token from @BotFather

---

## 📥 Clone Repository

```bash
git clone https://github.com/xsazedul/tempmail-telegram-bot.git
cd tempmail-telegram-bot
```

---

## 📂 Open in VS Code

Open the project with VS Code:

```bash
code .
```

Or open VS Code manually and select the project folder.

---

## 🐍 Create Virtual Environment

### Windows

```bash
python -m venv venv
```

Activate:

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 📦 Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🤖 Configure Bot Token

Open **bot.py** and replace:

```python
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
```

with

```python
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
```

Or use an environment variable.

### Windows CMD

```cmd
set BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
python bot.py
```

### Windows PowerShell

```powershell
$env:BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
python bot.py
```

### Linux / macOS

```bash
export BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
python3 bot.py
```

---

## ▶️ Run the Bot

If you're using the token directly in **bot.py**:

```bash
python bot.py
```

or

```bash
python3 bot.py
```

If everything is configured correctly, you'll see:

```text
Starting TempMail Bot...
```

---

## 💬 Test Your Bot

Open Telegram and send:

```text
/start
```

Generate a new email:

```text
/new
```

View inbox:

```text
/inbox
```

Refresh inbox:

```text
/refresh
```

View statistics:

```text
/stats
```

---

## 📁 Project Structure

```text
tempmail-telegram-bot/
│── bot.py
│── requirements.txt
│── README.md
│── LICENSE
```

---

## 🛠 Built With

- Python
- python-telegram-bot
- Mail.tm API
- httpx
- asyncio

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

## ⭐ Support

If you found this project useful, please consider giving it a ⭐ on GitHub.

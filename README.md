# MultiRoom Chatbot

A lightweight desktop group-chat app for **KoboldAI / KoboldCpp**. Create bots with a picture and a personality, put up to 10 of them in a chat room, and talk to them all at once. Each reply from the model is split into separate messages, one per character, that arrive one after another like a real group chat.

Built with Python 3.11 and PySide6 (Qt).

---

## Requirements

- **Windows** (the launcher is a `.bat`; the Python code itself is cross-platform)
- **Python 3.11** with the `py` launcher
- **KoboldCpp** (or KoboldAI) running locally with a model loaded. The default address is `http://localhost:5001`.

## Installation

```bat
cd "MultiRoom Chatbot"
py -3.11 -m pip install -r requirements.txt
```

This installs `PySide6` and `requests`.

## Running

Double-click **`run.bat`**. The app starts without a console window.

To see logs and errors in a console, edit the top of `run.bat`:

```bat
set DEBUG=1
```

With `DEBUG=0`, any errors are written to `data\error.log`.

You can also run it directly:

```bat
py -3.11 main.py
```

---

## Using the app

### Bots tab
- Click **+ New bot**, or the **Add bot** card.
- Fill in:
  - **Name**: what the bot is called in chat. It can't contain `[`, `]` or `:`.
  - **Description**: a short line shown under the bot's card.
  - **Context**: the personality, background and speech quirks sent to the AI. This is what shapes how the bot talks.
  - **Image**: choose one with **Browse…**, then crop it to a square. **Crop…** lets you re-crop later.
- Click a card to edit or delete a bot.
- Images are copied into `data/avatars/`, so moving or deleting the original file won't break anything.

### Chat tab
- **+ New chat** opens the chat setup:
  - Pick **1–10 bots**.
  - **Roles in this chat** (optional): a role for each bot in this chat only, e.g. *"Alex's mom"* or *"Alex's rival"*. The same bot can be a different person in each chat.
  - **Complete Response**: every bot must reply each turn and is encouraged to talk to the others.
  - **Chat context**: scenario or setting text, e.g. *"Everyone is at a beach party."*
- Type a message. **Enter** sends it and **Shift+Enter** adds a new line.
- While the model is working, a typing animation shows. Replies then arrive one at a time, 3–5 seconds apart.
- Click a bot's **picture** in the chat, or in the header, to see its profile and its role in that chat.
- **⟳ New session** stops any reply in progress and starts the chat fresh. The old conversation is kept under Saved chats.

### Saved chats
- Chats save automatically after every message.
- **SAVED CHATS** in the left column lists chats from earlier runs. Click one to read it.
- **Continue this chat** starts a new session with the same bots and settings. The most recent ~4,000 characters of the old chat are given to the AI as "earlier conversation", so the bots remember what happened.
- Right-click a chat to delete it.

### Settings (⚙)
| Setting | What it does |
|---|---|
| KoboldAI URL | Where KoboldCpp is running. **Test connection** checks it. |
| Your name | How you appear in the chat and in the prompt. |
| Your image | Optional avatar for your messages. With none set, no picture is shown. |
| Max output tokens | Longest reply the model may write. Default **220**. |
| Chat image size | Size of the avatars in chat, 32–128 px. |
| Sampler preset | **Godlike** (default), **Liminal Drift**, or **Custom** (set your own temperature). |
| Instruct format | Wrapping for instruct models: **Mistral** (default), ChatML, Llama 3, Alpaca, None, or Custom tags. Pick the one that matches your model. |
| Clear all data… | Deletes bots and images, saved chats and/or settings. This can't be undone. |

The **☀ / ☾** button in the top bar switches between light and dark mode.

The dot next to the model name shows the connection: green means connected, red means it can't reach Kobold.

---

## How it talks to the model

The app builds one prompt per turn and sends it to KoboldCpp's `/api/v1/generate` endpoint. It doesn't use Kobold Lite's memory or world info.

```
### Characters

[Ashley]
<context>
In this chat, Ashley's role: <role, if set>

[Victor]
<context>

### Chat Context              (if set)
### Earlier conversation      (if continuing a saved chat)

### Instructions
Format rules: every line is "[Name]: dialogue", actions go in *asterisks*,
never speak for the user, ...

### Chat

[You]: hey guys
[Ashley]: ...
```

The whole prompt is wrapped in the instruct tags you picked. The reply is split on `[Name]:` tags into one message per character. Lines from your name, or from names not in the chat, are dropped. When the chat gets long, the oldest messages are trimmed so the prompt fits the model's context.

---

## Project layout

```
main.py                 entry point (theme, error log)
run.bat                 launcher (DEBUG flag at the top)
app/
  models.py             Bot, Chat, Message data classes
  prompt.py             prompt building + reply parsing
  kobold.py             KoboldCpp API client, sampler/instruct presets
  session.py            per-chat sending, delays, auto-save
  storage.py            JSON files, image copies, saved chats
  ui/                   all windows and widgets (PySide6)
tests/                  unit tests
data/                   created on first run (your bots, chats, settings, avatars)
```

## Your data

Everything is stored locally in the `data/` folder:

- `settings.json`: your settings
- `bots.json`: your bots
- `avatars/`: bot images (cropped copies and originals) and your own image
- `chats/`: saved chats, one JSON file each
- `error.log`: only created if something goes wrong

To back up your data, copy the `data/` folder. To reset everything, use **Settings → Clear all data…** or delete the folder.

## Running the tests

```bat
py -3.11 -m unittest discover -s tests
```

---

## Troubleshooting

- **"Can't reach KoboldAI"**
  - Make sure KoboldCpp is running and has a model loaded.
  - Check the URL in Settings and use **Test connection**.
- **Bots speak for you or ramble**
  - Pick the **Instruct format** that matches your model.
  - Lower **Max output tokens**.
- **Replies feel slow.** Check the KoboldCpp console:
  - A large *"Processing Prompt"* count on every message means the prompt cache is being missed. Switching between chats causes this.
  - Otherwise, most of the wait is the 3–5 second gap between each bot's message.
- **A bot ignores its role**
  - Write the role naming you, e.g. *"Alex's overprotective mom"* instead of *"mom"*.
  - Roles far from the bot's usual personality slip more often. Small local models will sometimes drift.
- **Something crashed with no window.** Look in `data\error.log`, or set `DEBUG=1` in `run.bat` to see errors live.

# ping-me-when

[![tests](https://github.com/runkunl-emr/ping-me-when/actions/workflows/ci.yml/badge.svg)](https://github.com/runkunl-emr/ping-me-when/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Get a desktop notification any time a specific person posts in a specific Discord channel.

No coding needed. Double-click to start. Configure everything in your browser.

> [中文快速入门 / Chinese quickstart](#中文快速入门)

```
                ┌─────────────────────────┐
                │  Discord                 │
                │  • #market-calls         │
                │  • Alice posts: "BUY..." │
                └────────────┬────────────┘
                             ▼
                ┌─────────────────────────┐
                │ ping-me-when (running   │
                │ on your computer)       │
                │                          │
                │  matches subscription:   │
                │  channel + username      │
                └────────────┬────────────┘
                             ▼
              ┌──────────────────────────────┐
              │  📨 Alice's market calls      │
              │  "BUY..."                     │
              └──────────────────────────────┘
                  macOS / Discord webhook
```

## Quick start (Mac)

1. **Download** this folder (Code → Download ZIP, then unzip).
2. Pick how you want it to run:
   - **`start-menubar.command`** *(recommended)* — runs as a small 📨 icon in the macOS menu bar. No visible terminal window. Click → Start / Stop / Open settings. Auto-starts the listener next time you launch if a config is saved.
   - **`start.command`** — runs in a Terminal window. Closing the window stops the app.

   First run sets up Python dependencies (~30 seconds).
3. Your browser opens at `http://127.0.0.1:8765/`. Configure:
   - Paste your **Discord token** (instructions below)
   - Add a subscription: **channel ID** + one or more **usernames** (comma- or space-separated)
   - Pick how to get notified (macOS notification by default; you can also forward to a Discord webhook)
4. Click **Start listening**. That's it — leave the terminal window open.
5. To stop, double-click `stop.command` (or close the terminal window).

> First run: macOS may say *"start.command can't be opened because Apple cannot check it for malicious software."* Right-click → **Open** → **Open**. You only need to do this once.

## Quick start (Windows)

Double-click `start.bat`. Same setup, in `cmd.exe`. Requires Python 3 from <https://www.python.org/downloads/> with the *"Add Python to PATH"* option checked during install.

## Quick start (Linux)

```bash
chmod +x start.command  # works as a regular bash script
./start.command
```

## How to get your Discord token

> Treat your token like a password. Anyone with it can read every channel you can see and act as you. **Never paste it into a public chat.**

1. Open Discord in a **browser** (the desktop app makes this trickier).
2. Press <kbd>Cmd</kbd>+<kbd>Option</kbd>+<kbd>I</kbd> (Mac) or <kbd>F12</kbd> (Win/Linux) to open DevTools.
3. Click the **Network** tab.
4. Click any channel — requests appear in the panel.
5. Click any request to `discord.com/api/...` → **Headers** → scroll to **Request Headers** → find `Authorization:`.
6. Copy the long string after `Authorization:` and paste it into ping-me-when's setup page.

## How to get a channel ID

1. Discord → Settings → Advanced → enable **Developer Mode**.
2. Right-click any channel in the sidebar → **Copy Channel ID**.

## How to add a Discord webhook (optional)

If you want the alert to also appear in a private Discord channel (e.g. for use on your phone via the Discord app):

1. In your private server, channel settings → **Integrations** → **Webhooks** → **New Webhook**.
2. Copy the webhook URL.
3. Paste it into ping-me-when's "Discord webhook URL" field.

## Privacy & safety

- Your token and subscriptions are stored in `config.json` next to the app on your own computer. Nothing is uploaded anywhere.
- The web UI listens on `127.0.0.1` only — not reachable from other machines on your network.
- The listener is **read-only**. It cannot post messages or change anything in Discord.

## Self-bot caveat

This tool uses your **user token** (the same one your Discord client uses), which technically means you're running a "self-bot" while the listener is connected. Discord's official terms of service discourage self-bots. The risk is low for a passive read-only listener, but in theory your account could be flagged. If you'd rather avoid that, the ground-up alternative is to register a real Discord bot application and use a bot token — that requires server-admin permission to invite the bot, so it's not always practical.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest

pytest -q                       # run unit tests
PING_NO_BROWSER=1 python -m src.server  # run server without auto-opening browser
```

Tests cover the storage layer and the message-filter logic. They don't connect to a real Discord socket.

## Limitations / non-goals

- Only "channel + username" matching. No keywords, regex, mentions, embeds — keep it simple.
- One running instance per machine.
- macOS notifications only on macOS (obviously). Windows/Linux users can use the webhook channel instead.
- Stops when the terminal window closes.
- DMs and private threads aren't supported.

## Click-to-jump notifications

If `terminal-notifier` is installed (`brew install terminal-notifier`), clicking a notification opens the Discord message in your browser. Without it, notifications still appear, but aren't clickable. Webhook forwards always include the message link.

## 中文快速入门

任何指定的 Discord 用户在指定频道一发言，你立刻收到桌面通知。

### 安装

1. 下载这个文件夹（点 Code → Download ZIP，解压到任意位置）
2. **双击 `start.command`**。第一次运行会安装 Python 依赖，约 30 秒
3. 浏览器自动打开 `http://127.0.0.1:8765/`，右上角语言切换为「中文」
4. 填入：
   - **Discord 令牌**（教程在页面里）
   - **频道 ID**（Discord → 设置 → 高级 → 启用开发者模式；右键频道 → 复制频道 ID）
   - **用户名**（要监听的人，多个用逗号或空格分隔）
   - **备注**（可选，自定义通知标题）
5. 点 **保存** → **开始监听**
6. 关掉浏览器没关系，但留着 Terminal 窗口
7. 想停就双击 `stop.command`

### 通知里能看到什么？

- 标题：用你设置的备注，或者 "用户名 in #频道名"
- 内容：消息的前 500 字
- 装了 `brew install terminal-notifier` 的话，**点通知直接跳到 Discord 那条消息**

### 隐私

- 令牌只存本地 `config.json`（权限 0600，只你自己能读），不上传任何地方
- 服务器只监听 `127.0.0.1`，外部网络无法访问
- 程序只读不写：Discord 那边它发不出消息

## Roadmap / TODO

- **Signed `.app` / `.dmg` bundle** — currently the menu-bar app runs from source via `start-menubar.command`. Wrapping it with `py2app` and Apple-signing it would make distribution truly drag-to-Applications.
- **Auto-start on login** — install a `launchd` LaunchAgent so the listener boots with the machine.
- **Mention / keyword filters** — optional regex on top of channel+user.
- **"Find user by display name"** helper — paste display name, get the matching `username` so users don't have to dig through Discord settings.

## License

MIT — see [LICENSE](LICENSE). Free to fork, modify, and redistribute. No warranty.

## Security model

- Server binds to `127.0.0.1` only, never to `0.0.0.0`. The host-pinning middleware refuses requests whose `Host:` header isn't `127.0.0.1` or `localhost`.
- Mutating endpoints require `Content-Type: application/json` (small CSRF defense; cross-origin `<form>` POSTs use `application/x-www-form-urlencoded`).
- The webhook URL is validated to `https://*.discord.com` only, so it can't be used as an SSRF gadget.
- `config.json` is written with 0600 permissions (owner-only).
- The token is never echoed back over the API; clients only learn whether one is set.
- The Discord WebSocket is closed on `SIGTERM`/`SIGINT`/server shutdown, so the listener doesn't leave a dangling session.

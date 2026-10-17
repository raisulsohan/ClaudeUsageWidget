# Claude Usage Widget — Windows

A Windows desktop widget that shows your [claude.ai](https://claude.ai) plan limits at a glance, so you see a limit coming before you hit it.

- **Session**: the rolling 5-hour limit
- **Weekly**: the 7-day limit across all models
- **Fable**: the separate weekly Fable limit (shown only if your plan has one)
- **Extra usage**: credits spent against your monthly cap

Bars turn **amber at 75%** and **red at 90%**. A pixel-art mascot reacts to your session usage: calm when you're idle, sweating at 75%, panicking at 90%, asleep once you hit the limit.

> **Unofficial.** Not affiliated with Anthropic. It reads the same internal endpoint the claude.ai settings page uses, which can change without notice.

This is a Windows port of [sdezubiria's macOS widget](https://github.com/sdezubiria/claude-usage-widget). The macOS parts (Keychain, launchd, Übersicht) are replaced with Windows equivalents: DPAPI / Credential Manager, Task Scheduler, and a tkinter window that now carries the mascot itself.

---

## How it works

There are two ways to get usage data, depending on your browser. Both end with the same `usage_data.json` that `widget.py` draws, refreshing itself whenever the file changes.

**A. Chrome extension (recommended for Chrome / Edge / Brave)** — a tiny extension fetches usage from inside the browser using your live login, so no cookie file is ever read:

```
Chrome extension ──▶ claude.ai usage API
       │
       ▼ (POST)
  receiver.py ──▶ usage_data.json ──▶ widget.py
```

**B. Cookie / paste (good for Firefox-family, or any browser via a pasted key)**:

```
Browser cookies (Firefox, Zen, …)  ──┐
                                      ├─▶ fetch_usage.py ──▶ claude.ai usage API ──▶ usage_data.json ──▶ widget.py
Saved key (Credential Manager/DPAPI) ─┘
```

`fetch_usage.py` and `receiver.py` share the same parsing code, so the widget schema is defined once. Your login never leaves your machine except to talk to claude.ai. Requests use [`curl_cffi`](https://github.com/lexiforest/curl_cffi) so Cloudflare lets them through.

> **Which should I use?** On Chrome/Edge, use **A** — Windows keeps the Chrome cookie file exclusively locked while the browser runs, and Chrome 127+ encrypts cookies so an outside program can't read them. The extension sidesteps both. On Firefox/Zen/LibreWolf/Floorp, **B** works silently with zero extra setup.

---

## Requirements

| | |
|---|---|
| **Windows 10/11** | Uses DPAPI and Task Scheduler |
| **Python 3.10+** | Check with `py --version`. tkinter ships with the python.org installer |
| **A browser logged in to claude.ai** | See [Supported browsers](#supported-browsers) |

---

## Install with the setup file (no Python needed)

`installer\ClaudeUsageWidget-Setup.exe` installs the widget for your Windows user (no admin prompt) to `%LOCALAPPDATA%\Programs\Claude Usage Widget`. It is the extension method in one program: the receiver and the widget run together in `ClaudeUsageWidget.exe`.

1. Run `ClaudeUsageWidget-Setup.exe`. Keep **Start the widget when I sign in to Windows** ticked if you want it at logon.
2. Load the extension once: open `chrome://extensions` (or `edge://extensions`), turn on **Developer mode**, click **Load unpacked**, and select the `extension` folder in the install folder. The Start Menu has a **Chrome extension folder** shortcut to it.
3. Start **Claude Usage Widget** from the Start Menu. Right-click the widget to quit; that also stops the receiver.

Uninstall from **Settings → Apps → Installed apps**.

**Build the setup file yourself:** install [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install -e --id JRSoftware.InnoSetup`), then run `build_installer.bat`. It bundles `app.py` with PyInstaller and packs it with `installer.iss`.

---

## Quick start

Install the Python dependencies once, for either method:

```bash
pip install -r requirements.txt
```

### One-click start (Windows, extension method)

Once the one-time setup is done (Python, `pip install`, and the extension loaded as in Method A below), these two files are all you need:

| File | What it does |
|---|---|
| **`Start Widget.cmd`** | Starts `receiver.py` and `widget.py` in the background. A small window shows for a few seconds, then closes. Safe to double-click again: it skips whatever is already running. |
| **`Stop Widget.cmd`** | Stops both. (Right-clicking the widget closes just the widget.) |

**Start at logon:** press **Win+R**, type `shell:startup`, Enter. In the folder that opens, right-click → **New → Shortcut**, point it at `Start Widget.cmd`, then open the shortcut's **Properties** and set **Run** to **Minimized** so no window flashes at sign-in.

### Method A — Chrome extension (recommended for Chrome/Edge/Brave)

1. **Load the extension.** Open `chrome://extensions`, turn on **Developer mode** (top-right), click **Load unpacked**, and select this project's `extension` folder. (In Edge use `edge://extensions`; in Brave `brave://extensions`.)
2. **Start the receiver** — it writes `usage_data.json` whenever the extension pushes data:
   ```bash
   py receiver.py
   ```
   Or run it in the background with `start_receiver.bat`, or at logon with
   `powershell -ExecutionPolicy Bypass -File install_task.ps1 -Receiver`.
3. **Show the widget:**
   ```bash
   py widget.py
   ```

Steps 2 and 3 are exactly what `Start Widget.cmd` does for you, so after loading the extension once you can just double-click that.

Make sure you're logged in to claude.ai in that browser. The extension refreshes every 5 minutes on its own. To push immediately, open `chrome://extensions`, find the widget, and click the service-worker **reload**. Check its logs via the extension's **service worker** link.

### Method B — cookie / paste (Firefox-family, or any browser)

1. **Connect your account.** Log in to claude.ai, then:
   ```bash
   py fetch_usage.py --setup
   ```
   It finds and tests a login, or asks you to paste your `sessionKey` (see [Paste your key](#paste-your-key-the-universal-method)).
2. **Keep it fresh** — a Scheduled Task that runs at logon, every 5 minutes:
   ```bash
   powershell -ExecutionPolicy Bypass -File install_task.ps1
   ```
   Or run `start.bat` to fetch in the background without a task.
3. **Show the widget:** `py widget.py`

### The widget

Drag to move, double-click to refresh, right-click to quit. Leave it running — it picks up new data on its own. To start it at logon with the extension method, use the `Start Widget.cmd` Startup shortcut described under [One-click start](#one-click-start-windows-extension-method). With the cookie/paste method, put a shortcut to `widget.py` (opened with `pythonw.exe`) in the same Startup folder instead: press **Win+R**, type `shell:startup`, and drop the shortcut there.

---

## Supported browsers

Windows handles browser cookies very differently from macOS, so read this.

| Family | Browsers | On Windows |
|---|---|---|
| **Firefox** | Firefox, Zen, LibreWolf, Floorp | **Works silently.** Cookies are plain text and not locked; expired logins renew on the next run. Recommended. |
| **Chromium** | Chrome, Edge, Brave, Vivaldi, Chromium | **Only while the browser is closed**, and only on older versions. Chrome/Edge keep the cookie file **exclusively locked while running**, and version 127+ add *app-bound encryption* that an ordinary program can't decrypt. When that happens, use Firefox-family or paste your key. |
| **Other** | Safari (N/A), Arc, anything else | Paste your key once (below). |

The key takeaway: on a typical Chrome/Edge setup the widget **cannot** read your cookie automatically. That's a Windows + Chrome security limitation, not a bug. For Chrome/Edge/Brave, use the **[browser extension](#method-a--chrome-extension-recommended-for-chromeedgebrave)** (fully automatic). Otherwise use a **Firefox-family browser** or **paste your key once**.

To limit the search to one browser: `py fetch_usage.py --setup --browser firefox` (names: `firefox zen librewolf floorp chrome edge brave vivaldi chromium`). For the background fetcher, set the environment variable `CLAUDE_BROWSER` instead. To see what was detected without using it: `py fetch_usage.py --browsers`.

### Paste your key (the universal method)

1. Open claude.ai and open DevTools (**F12**).
2. Go to **Application → Storage → Cookies → https://claude.ai**.
3. Copy the value of `sessionKey`.
4. Run `py fetch_usage.py --setup` and paste it when asked.

The key is saved for your Windows user (see [Where your key is stored](#where-your-key-is-stored)) and reused every run. Pasted keys can't renew themselves — when the widget says your session expired, repeat these steps.

---

## Where your key is stored

The `sessionKey` is never written to disk in plain text:

- If the optional [`keyring`](https://pypi.org/project/keyring/) package is installed (`pip install keyring`), it goes into **Windows Credential Manager** (Control Panel → Credential Manager → Windows Credentials, under `claude.ai`).
- Otherwise it's saved to `%LOCALAPPDATA%\claude-usage-widget\session.bin`, **encrypted with DPAPI** so only your Windows account can read it back.

Either way, another user account on the PC can't read it.

---

## The mascot

The pixel robot's mood follows your **session** usage:

| Session | Mood |
|---|---|
| under 25% | idle — slow breathing, blinking |
| 25–74% | working — walks in place |
| 75–89% | hustling — faster, sweat drop |
| 90–99% | panicking — shaking, sweating |
| 100% | resting — eyes shut, floating z's |

To change the thresholds, edit `mood_for()` in `widget.py`. Colors live in the `C` dict at the top of the same file.

---

## Configuration

| What | How |
|---|---|
| **Widget layout** | `LAYOUT` at the top of `widget.py`: `"compact"` (small strip above the taskbar, default), `"horizontal"` (wide strip), or `"vertical"` (corner card) |
| **Compact size / text** | `COMPACT_W` (width), `COMPACT_H` (height) at the top of `widget.py`. Text sizes are the `size=` values in `_redraw_compact` |
| **Keep clear of the clock** | `TRAY_MARGIN` (px reserved on the right for the system tray) — the widget can't be dragged past it |
| **Remembered position** | The widget reopens where you last dragged it (`%LOCALAPPDATA%\claude-usage-widget\widget_pos.json`), clamped so it can't hide behind the taskbar or slide into the tray. Delete that file to reset to the default spot |
| **Use one browser only** | `--browser NAME`, or set `CLAUDE_BROWSER=NAME` |
| **Fetch interval** | `py fetch_usage.py --loop 120` (seconds). Default is 300 |
| **Manual values** | `py set_usage.py` asks for each value — handy for testing the UI |

### `usage_data.json`

The widget reads this file:

```json
{
  "plan": "Max",
  "session": { "percent": 55, "resets_in": "1h 18m" },
  "weekly":  { "percent": 54, "resets_in": "2d 7h" },
  "fable":   { "percent": 92, "resets_in": "7h", "available": true },
  "extra":   { "enabled": true, "spent": 0.0, "percent": 0, "limit": 12.0, "resets": "1st of month" },
  "updated": "2026-10-01T11:41:48"
}
```

---

## Troubleshooting

**The widget shows old numbers / "updated Xh ago" keeps growing** — check the log:

```bash
Get-Content fetch.log -Tail 20
```

**Using the extension and nothing updates** — check, in order:

- Is `receiver.py` running? Its window prints a line each time the extension pushes. If the extension logs `is receiver.py running?`, start it (`Start Widget.cmd` does this).
- Open `chrome://extensions` → the widget's **service worker** link → Console. `logged in to claude.ai?` means log in; a receiver error means the receiver isn't reachable on `127.0.0.1:8765`.
- Click the service worker **reload** to push immediately instead of waiting 5 minutes.

Cookie/paste method:

- `cookies are locked`: Chrome/Edge is running. Use the extension instead, switch to a Firefox-family browser, or paste your key.
- `app-bound encryption`: your Chromium browser is version 127+. Use Firefox-family or paste your key.
- `Session expired`: log in to claude.ai again (Firefox-family renews automatically), or re-run `--setup` and paste a fresh key.
- `Blocked by Cloudflare`: usually temporary; clears on a later run.

**`py` isn't recognized** — install Python from [python.org](https://www.python.org/downloads/windows/) (not the Microsoft Store stub) and tick *Add python.exe to PATH*. Then use `py` or `python`.

**Restart the background fetcher**

```bash
Start-ScheduledTask -TaskName ClaudeUsageWidget
```

---

## Project layout

```
widget.py           floating tkinter widget, with the mascot
usage_data.json     written by either method, read by the widget

Method A (Chrome extension)
  extension/         unpacked MV3 extension — load this folder in chrome://extensions
  receiver.py        local endpoint that the extension POSTs usage to
  Start Widget.cmd   one click: start receiver.py + widget.py (skips what's already running)
  Stop Widget.cmd    stop both
  start_receiver.bat run only the receiver in the background

Method B (cookie / paste)
  fetch_usage.py     fetches usage and writes usage_data.json
  browser_cookies.py finds claude.ai logins (Firefox plaintext, Chromium DPAPI+AES-GCM)
  credential_store.py saves the sessionKey (Credential Manager or DPAPI file)
  windpapi.py        thin ctypes wrapper around Windows DPAPI
  start.bat          run the fetcher without Task Scheduler

Installer
  app.py             receiver + widget in one process (the .exe entry point)
  build_installer.bat  PyInstaller + Inno Setup → installer\ClaudeUsageWidget-Setup.exe
  installer.iss      Inno Setup script

Shared
  set_usage.py       enter values by hand (UI testing)
  install_task.ps1   register the background component as a Scheduled Task
                     (fetch_usage by default; -Receiver for the extension method)
  uninstall_task.ps1 remove it
```

---

## License

[MIT](LICENSE) — same as the upstream project.

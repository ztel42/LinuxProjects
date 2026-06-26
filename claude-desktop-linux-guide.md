# Installing Claude Desktop on Linux (Pop!_OS / Ubuntu / Debian)

> **Heads up:** Anthropic does not officially ship Claude Desktop for Linux.
> This guide uses the best community-maintained package —
> [aaddrick/claude-desktop-debian](https://github.com/aaddrick/claude-desktop-debian) —
> which repackages the official Windows app to run natively on Linux.
> It is not affiliated with or supported by Anthropic.

---

## What You'll End Up With

- A fully functional Claude Desktop GUI app on your Linux machine
- System tray icon, global hotkeys, and MCP server support
- Automatic updates via `apt upgrade` (no manual reinstalls)

---

## Prerequisites

- A Debian/Ubuntu-based distro (Pop!\_OS, Ubuntu, Linux Mint, etc.)
- A terminal
- `sudo` access

---

## Step 1 — Add the Claude Desktop Repository

This tells your system where to download Claude Desktop from and verifies it's legitimate.

```bash
# Download and save the security key
curl -fsSL https://pkg.claude-desktop-debian.dev/KEY.gpg | sudo gpg --dearmor -o /usr/share/keyrings/claude-desktop.gpg

# Add the repository to your system
echo "deb [signed-by=/usr/share/keyrings/claude-desktop.gpg arch=amd64,arm64] https://pkg.claude-desktop-debian.dev stable main" | sudo tee /etc/apt/sources.list.d/claude-desktop.list
```

---

## Step 2 — Install Claude Desktop

```bash
sudo apt update && sudo apt install claude-desktop
```

---

## Step 3 — Run the Health Check

Before launching the app, run the built-in diagnostic tool to make sure everything installed correctly.

```bash
claude-desktop --doctor
```

### What to look for

- `[PASS]` next to every line = you're good to go
- `[WARN] Node.js: not found` = harmless unless you plan to use MCP servers (see Step 4)
- `[FAIL]` on anything = copy the output and check the [troubleshooting docs](https://github.com/aaddrick/claude-desktop-debian/blob/main/docs/troubleshooting.md)

### Example of a healthy output

```
Claude Desktop Diagnostics
================================
[PASS] Installed version: 1.15200.0-2.0.22
[PASS] Display server: Wayland
[PASS] Electron: v41.5.0
[PASS] Chrome sandbox: permissions OK
[PASS] MCP config: valid JSON
[PASS] Desktop entry: /usr/share/applications/claude-desktop.desktop
[PASS] Disk space: 785652MB free

Cowork Mode
----------------
[PASS] bubblewrap: found
[PASS] bubblewrap: sandbox probe succeeded
```

---

## Step 4 — Install Node.js v20+ (Optional, for MCP Servers)

MCP servers let Claude access your filesystem, run commands, or connect to tools like GitHub and Slack.
You only need this if you plan to use those features.

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify
node --version   # should show v20.x.x or higher
```

---

## Step 5 — Launch Claude Desktop

Find it in your app launcher by searching **Claude**, or run it from the terminal:

```bash
claude-desktop
```

Sign in with your Anthropic account and you're done.

---

## Useful Tips

| Thing you want | How to do it |
|---|---|
| Global hotkey popup | `Ctrl + Alt + Space` |
| Keep hotkeys working on Wayland | Leave `CLAUDE_USE_WAYLAND` unset (default) |
| Update Claude Desktop | `sudo apt upgrade` |
| MCP config file location | `~/.config/Claude/claude_desktop_config.json` |
| App logs | `~/.cache/claude-desktop-debian/launcher.log` |

---

## Troubleshooting

If something goes wrong, always start with:

```bash
claude-desktop --doctor
```

The output will usually tell you exactly what's wrong and how to fix it.
For anything else, check the official project docs:
[github.com/aaddrick/claude-desktop-debian](https://github.com/aaddrick/claude-desktop-debian)

import os
import re
import subprocess
import webbrowser
import urllib.parse
import ctypes
import datetime
import threading
import difflib
from pathlib import Path


# ---------- Static command maps (always available, instant) ----------

APP_PATHS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "wordpad": "write.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
    "device manager": "devmgmt.msc",
    "disk management": "diskmgmt.msc",
    "services": "services.msc",
    "registry": "regedit.exe",
    "registry editor": "regedit.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "settings": "ms-settings:",
    "snipping tool": "snippingtool.exe",
    "snip": "snippingtool.exe",
    "character map": "charmap.exe",
    "on-screen keyboard": "osk.exe",
    "magnifier": "magnify.exe",
    "narrator": "narrator.exe",
    "xbox game bar": "ms-gamebar:",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
}

SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "translate": "https://translate.google.com",
    "github": "https://www.github.com",
    "stack overflow": "https://stackoverflow.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
    "linkedin": "https://www.linkedin.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "twitch": "https://www.twitch.tv",
    "whatsapp": "https://web.whatsapp.com",
    "amazon": "https://www.amazon.com",
    "ebay": "https://www.ebay.com",
    "wikipedia": "https://www.wikipedia.org",
    "roblox": "https://www.roblox.com",
    "steam": "https://store.steampowered.com",
    "epic games": "https://store.epicgames.com",
    "discord web": "https://discord.com/app",
}

FOLDERS = {
    "desktop": Path.home() / "Desktop",
    "downloads": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "pictures": Path.home() / "Pictures",
    "videos": Path.home() / "Videos",
    "music": Path.home() / "Music",
    "home": Path.home(),
    "user folder": Path.home(),
    "onedrive": Path.home() / "OneDrive",
    "recycle bin": None,  # special shell folder
    "this pc": None,
    "my computer": None,
}

SHELL_LOCATIONS = {
    "recycle bin": "shell:RecycleBinFolder",
    "this pc": "shell:MyComputerFolder",
    "my computer": "shell:MyComputerFolder",
}


# ---------- Dynamic app index (Start Menu + Desktop + UWP) ----------

_app_index: list[tuple[str, str]] = []  # (lowercase_name, launch_target)
_index_lock = threading.Lock()
_index_built = False


def _scan_shortcuts(root: Path):
    results = []
    if not root.exists():
        return results
    for p in root.rglob("*.lnk"):
        name = p.stem.strip()
        if not name:
            continue
        # Skip uninstallers, readmes, license docs
        low = name.lower()
        if any(s in low for s in ("uninstall", "readme", "license", "help ", "eula")):
            continue
        results.append((low, str(p)))
    # also .url files (internet shortcuts)
    for p in root.rglob("*.url"):
        results.append((p.stem.strip().lower(), str(p)))
    return results


def _scan_uwp():
    """Use PowerShell Get-StartApps to list UWP / Store apps."""
    try:
        ps = r'Get-StartApps | ForEach-Object { $_.Name + "|" + $_.AppID }'
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        results = []
        for line in out.stdout.splitlines():
            if "|" not in line:
                continue
            name, aid = line.split("|", 1)
            name = name.strip().lower()
            aid = aid.strip()
            if name and aid:
                results.append((name, f"shell:AppsFolder\\{aid}"))
        return results
    except Exception:
        return []


def build_app_index():
    """Build the app index in a background thread; idempotent."""
    global _index_built
    with _index_lock:
        if _index_built:
            return
        _index_built = True
    t = threading.Thread(target=_do_build, daemon=True)
    t.start()


def _do_build():
    items = []
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path.home() / "Desktop",
        Path.home() / "OneDrive/Desktop",
        Path(os.environ.get("PUBLIC", "")) / "Desktop",
    ]
    for r in roots:
        items.extend(_scan_shortcuts(r))
    items.extend(_scan_uwp())

    # Dedup by (name, target)
    seen = set(); unique = []
    for n, tgt in items:
        key = (n, tgt)
        if key in seen: continue
        seen.add(key); unique.append((n, tgt))

    with _index_lock:
        _app_index[:] = unique


def _find_app(query: str) -> str | None:
    """Fuzzy-find best matching launch target from the index."""
    if not _app_index:
        return None
    q = query.strip().lower()
    if not q:
        return None
    names = [n for n, _ in _app_index]

    # 1) exact
    for n, tgt in _app_index:
        if n == q:
            return tgt
    # 2) startswith
    starts = [(n, tgt) for n, tgt in _app_index if n.startswith(q)]
    if starts:
        starts.sort(key=lambda x: len(x[0]))
        return starts[0][1]
    # 3) substring
    subs = [(n, tgt) for n, tgt in _app_index if q in n]
    if subs:
        subs.sort(key=lambda x: len(x[0]))
        return subs[0][1]
    # 4) token overlap — every query word appears as a token
    q_tokens = set(re.findall(r"\w+", q))
    if q_tokens:
        best = None; best_score = 0
        for n, tgt in _app_index:
            n_tokens = set(re.findall(r"\w+", n))
            if q_tokens.issubset(n_tokens):
                score = 100 - len(n)  # prefer shorter matches
                if score > best_score:
                    best_score = score; best = tgt
        if best:
            return best
    # 5) difflib fallback
    match = difflib.get_close_matches(q, names, n=1, cutoff=0.75)
    if match:
        for n, tgt in _app_index:
            if n == match[0]:
                return tgt
    return None


# ---------- Launchers ----------

def _press_key(vk: int):
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


def _send_hotkey(vks: list[int]):
    for v in vks: ctypes.windll.user32.keybd_event(v, 0, 0, 0)
    for v in reversed(vks): ctypes.windll.user32.keybd_event(v, 0, 2, 0)


def open_url(target: str) -> str:
    t = (target or "").strip().lower()
    url = SITES.get(t)
    if not url:
        if "." in t and " " not in t:
            url = t if t.startswith("http") else f"https://{t}"
        else:
            for k in sorted(SITES.keys(), key=len, reverse=True):
                if k in t:
                    url = SITES[k]; break
    if not url:
        return f"I couldn't find {target}."
    webbrowser.open(url)
    return f"Opening {target}."


def open_app(name: str) -> str:
    key = (name or "").strip().lower()
    if not key:
        return "Open what?"

    # Built-in folders
    if key in FOLDERS and FOLDERS[key] is not None:
        try:
            os.startfile(str(FOLDERS[key])); return f"Opening {key}."
        except Exception as e:
            return f"Couldn't open {key}: {e}"
    if key in SHELL_LOCATIONS:
        try:
            subprocess.Popen(["explorer.exe", SHELL_LOCATIONS[key]])
            return f"Opening {key}."
        except Exception as e:
            return f"Couldn't open {key}: {e}"

    # Built-in apps
    path = APP_PATHS.get(key)
    if path:
        try:
            if path.startswith("ms-"):
                os.startfile(path)
            elif path.endswith(".msc"):
                subprocess.Popen(["mmc", path])
            else:
                subprocess.Popen(path, shell=False)
            return f"Opening {name}."
        except Exception as e:
            return f"Couldn't open {name}: {e}"

    # Dynamic index (Start Menu / Desktop / UWP)
    target = _find_app(key)
    if target:
        try:
            if target.startswith("shell:"):
                subprocess.Popen(["explorer.exe", target])
            else:
                os.startfile(target)
            return f"Opening {name}."
        except Exception as e:
            return f"Couldn't launch {name}: {e}"

    # Final fallback — let Windows try to interpret it
    try:
        subprocess.Popen(["cmd", "/c", "start", "", key], shell=False)
        return f"Trying to open {name}."
    except Exception as e:
        return f"I couldn't open {name}. {e}"


def search_web(query: str) -> str:
    if not query:
        return "What should I search for?"
    webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(query))
    return f"Searching the web for {query}."


def youtube_search(query: str) -> str:
    if not query:
        return "What should I play?"
    webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query))
    return f"Searching YouTube for {query}."


def system_action(action: str) -> str:
    a = (action or "").lower()
    try:
        if a in ("volume up", "vol up"):
            for _ in range(5): _press_key(0xAF)
            return "Volume up."
        if a in ("volume down", "vol down"):
            for _ in range(5): _press_key(0xAE)
            return "Volume down."
        if a == "max volume":
            for _ in range(50): _press_key(0xAF)
            return "Maximum volume."
        if a == "min volume":
            for _ in range(50): _press_key(0xAE)
            return "Minimum volume."
        if a in ("mute", "unmute"):
            _press_key(0xAD); return "Toggling mute."
        if a == "play" or a == "pause":
            _press_key(0xB3); return f"{a.title()}."
        if a == "next":
            _press_key(0xB0); return "Next track."
        if a == "previous":
            _press_key(0xB1); return "Previous track."
        if a == "brightness up":
            subprocess.Popen(["powershell", "-NoProfile", "-Command",
                "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, [Math]::Min(100,(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness + 15))"],
                creationflags=0x08000000)
            return "Brightness up."
        if a == "brightness down":
            subprocess.Popen(["powershell", "-NoProfile", "-Command",
                "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, [Math]::Max(0,(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness - 15))"],
                creationflags=0x08000000)
            return "Brightness down."
        if a == "screenshot":
            _send_hotkey([0x5B, 0x10, 0x53])  # Win+Shift+S
            return "Opening snipping tool."
        if a == "show desktop":
            _send_hotkey([0x5B, 0x44])  # Win+D
            return "Showing desktop."
        if a == "task view":
            _send_hotkey([0x5B, 0x09])  # Win+Tab
            return "Task view."
        if a == "minimize all":
            _send_hotkey([0x5B, 0x4D])  # Win+M
            return "Minimizing all windows."
        if a == "new desktop":
            _send_hotkey([0x5B, 0x11, 0x44])  # Win+Ctrl+D
            return "New virtual desktop."
        if a == "switch desktop":
            _send_hotkey([0x5B, 0x11, 0x27])  # Win+Ctrl+Right
            return "Switching desktop."
        if a == "close window":
            _send_hotkey([0x12, 0x73])  # Alt+F4
            return "Closing window."
        if a == "copy":
            _send_hotkey([0x11, 0x43]); return "Copied."
        if a == "paste":
            _send_hotkey([0x11, 0x56]); return "Pasted."
        if a == "cut":
            _send_hotkey([0x11, 0x58]); return "Cut."
        if a == "undo":
            _send_hotkey([0x11, 0x5A]); return "Undone."
        if a == "redo":
            _send_hotkey([0x11, 0x59]); return "Redone."
        if a == "select all":
            _send_hotkey([0x11, 0x41]); return "Selected all."
        if a == "empty recycle bin":
            SHERB_NOCONFIRMATION = 0x1
            SHERB_NOPROGRESSUI = 0x2
            SHERB_NOSOUND = 0x4
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None,
                SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND)
            return "Recycle bin emptied."
        if a == "lock":
            ctypes.windll.user32.LockWorkStation(); return "Locking the workstation."
        if a == "sleep":
            subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return "Going to sleep."
        if a == "shutdown":
            subprocess.Popen("shutdown /s /t 10", shell=True)
            return "Shutting down in 10 seconds. Say cancel to abort."
        if a == "restart":
            subprocess.Popen("shutdown /r /t 10", shell=True)
            return "Restarting in 10 seconds."
        if a == "sign out":
            subprocess.Popen("shutdown /l", shell=True)
            return "Signing out."
        if a == "cancel":
            subprocess.Popen("shutdown /a", shell=True)
            return "Cancelled."
        if a == "time":
            return "It is " + datetime.datetime.now().strftime("%I:%M %p")
        if a == "date":
            return "Today is " + datetime.datetime.now().strftime("%A, %B %d, %Y")
        if a == "battery":
            try:
                import psutil  # optional
                b = psutil.sensors_battery()
                if b: return f"Battery at {int(b.percent)} percent."
            except Exception:
                pass
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                "(Get-WmiObject -Class Win32_Battery).EstimatedChargeRemaining"],
                capture_output=True, text=True, timeout=5, creationflags=0x08000000)
            pct = (out.stdout or "").strip().splitlines()[0] if out.stdout else ""
            return f"Battery at {pct} percent." if pct.isdigit() else "No battery detected."
    except Exception as e:
        return f"System error. {e}"
    return f"I don't know how to {action}."


def execute(action: str, value: str) -> str:
    a = (action or "").lower()
    v = value or ""
    if a == "open_url": return open_url(v)
    if a == "open_app": return open_app(v)
    if a == "search_web": return search_web(v)
    if a == "youtube": return youtube_search(v)
    if a == "system": return system_action(v)
    return ""

import os
import re
import shlex
import shutil
import subprocess
import sys
import webbrowser
import urllib.parse
import urllib.request
import json
import ctypes
import configparser
import datetime
import threading
import difflib
import random
from pathlib import Path

try:
    import pyperclip
except Exception:
    pyperclip = None

IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")


# ---------- Static command maps (always available, instant) ----------

_APP_PATHS_WINDOWS = {
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

_APP_PATHS_LINUX = {
    "notepad": ["gedit", "gnome-text-editor", "kate", "xed", "mousepad", "leafpad"],
    "text editor": ["gedit", "gnome-text-editor", "kate", "xed", "mousepad"],
    "wordpad": ["gedit", "gnome-text-editor", "kate", "xed", "mousepad"],
    "calculator": ["gnome-calculator", "kcalc", "galculator"],
    "calc": ["gnome-calculator", "kcalc", "galculator"],
    "paint": ["gimp", "kolourpaint", "pinta"],
    "explorer": ["nautilus", "dolphin", "nemo", "pcmanfm", "thunar"],
    "file explorer": ["nautilus", "dolphin", "nemo", "pcmanfm", "thunar"],
    "files": ["nautilus", "dolphin", "nemo", "pcmanfm", "thunar"],
    "task manager": ["gnome-system-monitor", "ksysguard", "xfce4-taskmanager"],
    "system monitor": ["gnome-system-monitor", "ksysguard", "xfce4-taskmanager"],
    "control panel": ["gnome-control-center", "systemsettings5", "xfce4-settings-manager"],
    "settings": ["gnome-control-center", "systemsettings5", "xfce4-settings-manager"],
    "device manager": ["gnome-control-center", "systemsettings5"],
    "disk management": ["gnome-disks", "kde-partitionmanager"],
    "services": ["gnome-system-monitor"],
    "registry": ["dconf-editor"],
    "registry editor": ["dconf-editor"],
    "cmd": ["gnome-terminal", "konsole", "xfce4-terminal", "x-terminal-emulator", "xterm"],
    "command prompt": ["gnome-terminal", "konsole", "xfce4-terminal", "x-terminal-emulator", "xterm"],
    "powershell": ["pwsh", "gnome-terminal", "konsole", "xterm"],
    "terminal": ["gnome-terminal", "konsole", "xfce4-terminal", "x-terminal-emulator", "xterm"],
    "snipping tool": ["gnome-screenshot", "flameshot", "spectacle"],
    "snip": ["gnome-screenshot", "flameshot", "spectacle"],
    "character map": ["gucharmap", "kcharselect"],
    "on-screen keyboard": ["onboard", "florence"],
    "magnifier": ["kmag"],
    "narrator": ["orca"],
    "archive manager": ["file-roller", "ark", "xarchiver"],
    "software": ["gnome-software", "plasma-discover", "software-center"],
    "software center": ["gnome-software", "plasma-discover", "software-center"],
    "firefox": ["firefox"],
    "chrome": ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"],
    "chromium": ["chromium-browser", "chromium"],
    "edge": ["microsoft-edge", "microsoft-edge-stable"],
    "microsoft edge": ["microsoft-edge", "microsoft-edge-stable"],
}

APP_PATHS = _APP_PATHS_LINUX if IS_LINUX else _APP_PATHS_WINDOWS

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
    # --- search / reference ---
    "bing": "https://www.bing.com", "duckduckgo": "https://duckduckgo.com",
    "yahoo": "https://www.yahoo.com", "yandex": "https://yandex.com",
    "wolfram": "https://www.wolframalpha.com", "wolfram alpha": "https://www.wolframalpha.com",
    "archive": "https://archive.org", "wayback machine": "https://web.archive.org",
    "scholar": "https://scholar.google.com", "google scholar": "https://scholar.google.com",
    "arxiv": "https://arxiv.org", "pubmed": "https://pubmed.ncbi.nlm.nih.gov",
    "merriam webster": "https://www.merriam-webster.com", "dictionary": "https://www.dictionary.com",
    "thesaurus": "https://www.thesaurus.com", "urban dictionary": "https://www.urbandictionary.com",
    "wiktionary": "https://en.wiktionary.org", "britannica": "https://www.britannica.com",
    # --- coding / dev ---
    "gitlab": "https://gitlab.com", "bitbucket": "https://bitbucket.org",
    "codepen": "https://codepen.io", "codesandbox": "https://codesandbox.io",
    "replit": "https://replit.com", "jsfiddle": "https://jsfiddle.net",
    "leetcode": "https://leetcode.com", "hackerrank": "https://www.hackerrank.com",
    "codewars": "https://www.codewars.com", "stack exchange": "https://stackexchange.com",
    "mdn": "https://developer.mozilla.org", "w3schools": "https://www.w3schools.com",
    "devdocs": "https://devdocs.io", "npm": "https://www.npmjs.com",
    "pypi": "https://pypi.org", "rubygems": "https://rubygems.org",
    "crates": "https://crates.io", "docker hub": "https://hub.docker.com",
    "vercel": "https://vercel.com", "netlify": "https://www.netlify.com",
    "render": "https://render.com", "railway": "https://railway.app",
    "cloudflare": "https://dash.cloudflare.com", "aws": "https://aws.amazon.com/console",
    "azure": "https://portal.azure.com", "gcp": "https://console.cloud.google.com",
    "google cloud": "https://console.cloud.google.com", "digitalocean": "https://cloud.digitalocean.com",
    # --- AI ---
    "anthropic": "https://www.anthropic.com", "openai": "https://openai.com",
    "huggingface": "https://huggingface.co", "perplexity": "https://www.perplexity.ai",
    "midjourney": "https://www.midjourney.com", "stable diffusion": "https://stablediffusionweb.com",
    "dalle": "https://labs.openai.com", "copilot": "https://copilot.microsoft.com",
    "groq": "https://groq.com", "mistral": "https://mistral.ai",
    "cohere": "https://cohere.com", "replicate": "https://replicate.com",
    "elevenlabs": "https://elevenlabs.io", "runway": "https://runwayml.com",
    "suno": "https://suno.com", "civitai": "https://civitai.com",
    "leonardo": "https://leonardo.ai", "ideogram": "https://ideogram.ai",
    # --- entertainment / video ---
    "disney plus": "https://www.disneyplus.com", "disney+": "https://www.disneyplus.com",
    "hbo max": "https://www.max.com", "max": "https://www.max.com",
    "hulu": "https://www.hulu.com", "prime video": "https://www.primevideo.com",
    "apple tv": "https://tv.apple.com", "paramount plus": "https://www.paramountplus.com",
    "peacock": "https://www.peacocktv.com", "crunchyroll": "https://www.crunchyroll.com",
    "youtube music": "https://music.youtube.com", "soundcloud": "https://soundcloud.com",
    "bandcamp": "https://bandcamp.com", "deezer": "https://www.deezer.com",
    "tidal": "https://tidal.com", "apple music": "https://music.apple.com",
    "vimeo": "https://vimeo.com", "dailymotion": "https://www.dailymotion.com",
    "kick": "https://kick.com", "rumble": "https://rumble.com",
    "imdb": "https://www.imdb.com", "rotten tomatoes": "https://www.rottentomatoes.com",
    "metacritic": "https://www.metacritic.com", "letterboxd": "https://letterboxd.com",
    "myanimelist": "https://myanimelist.net", "anilist": "https://anilist.co",
    # --- social ---
    "threads": "https://www.threads.net", "mastodon": "https://mastodon.social",
    "bluesky": "https://bsky.app", "snapchat": "https://web.snapchat.com",
    "pinterest": "https://www.pinterest.com", "tumblr": "https://www.tumblr.com",
    "telegram": "https://web.telegram.org", "signal": "https://signal.org",
    "messenger": "https://www.messenger.com", "slack": "https://slack.com",
    "teams": "https://teams.microsoft.com", "microsoft teams": "https://teams.microsoft.com",
    "zoom": "https://zoom.us", "google meet": "https://meet.google.com",
    "skype": "https://web.skype.com", "quora": "https://www.quora.com",
    "medium": "https://medium.com", "substack": "https://substack.com",
    "patreon": "https://www.patreon.com", "kofi": "https://ko-fi.com",
    # --- shopping ---
    "etsy": "https://www.etsy.com", "walmart": "https://www.walmart.com",
    "target": "https://www.target.com", "best buy": "https://www.bestbuy.com",
    "newegg": "https://www.newegg.com", "ikea": "https://www.ikea.com",
    "alibaba": "https://www.alibaba.com", "aliexpress": "https://www.aliexpress.com",
    "shein": "https://www.shein.com", "temu": "https://www.temu.com",
    "wayfair": "https://www.wayfair.com", "home depot": "https://www.homedepot.com",
    "costco": "https://www.costco.com", "shopify": "https://www.shopify.com",
    # --- gaming ---
    "playstation": "https://www.playstation.com", "xbox": "https://www.xbox.com",
    "nintendo": "https://www.nintendo.com", "ea": "https://www.ea.com",
    "ubisoft": "https://www.ubisoft.com", "blizzard": "https://www.blizzard.com",
    "battle net": "https://www.battle.net", "gog": "https://www.gog.com",
    "itch": "https://itch.io", "minecraft": "https://www.minecraft.net",
    "fortnite": "https://www.fortnite.com", "valorant": "https://playvalorant.com",
    "league": "https://leagueoflegends.com", "league of legends": "https://leagueoflegends.com",
    "riot": "https://www.riotgames.com", "ign": "https://www.ign.com",
    "gamespot": "https://www.gamespot.com", "speedrun": "https://www.speedrun.com",
    # --- news / info ---
    "bbc": "https://www.bbc.com", "cnn": "https://www.cnn.com",
    "nyt": "https://www.nytimes.com", "new york times": "https://www.nytimes.com",
    "guardian": "https://www.theguardian.com", "reuters": "https://www.reuters.com",
    "ap news": "https://apnews.com", "bloomberg": "https://www.bloomberg.com",
    "wsj": "https://www.wsj.com", "wall street journal": "https://www.wsj.com",
    "ft": "https://www.ft.com", "economist": "https://www.economist.com",
    "verge": "https://www.theverge.com", "ars technica": "https://arstechnica.com",
    "techcrunch": "https://techcrunch.com", "wired": "https://www.wired.com",
    "engadget": "https://www.engadget.com", "9to5mac": "https://9to5mac.com",
    "hacker news": "https://news.ycombinator.com", "lobsters": "https://lobste.rs",
    # --- finance ---
    "coinbase": "https://www.coinbase.com", "binance": "https://www.binance.com",
    "kraken": "https://www.kraken.com", "robinhood": "https://robinhood.com",
    "etoro": "https://www.etoro.com", "fidelity": "https://www.fidelity.com",
    "vanguard": "https://www.vanguard.com", "schwab": "https://www.schwab.com",
    "tradingview": "https://www.tradingview.com", "yahoo finance": "https://finance.yahoo.com",
    "google finance": "https://www.google.com/finance", "coinmarketcap": "https://coinmarketcap.com",
    "coingecko": "https://www.coingecko.com", "etherscan": "https://etherscan.io",
    "paypal": "https://www.paypal.com", "venmo": "https://venmo.com",
    "wise": "https://wise.com", "stripe": "https://stripe.com",
    # --- productivity / docs ---
    "notion": "https://www.notion.so", "obsidian": "https://obsidian.md",
    "evernote": "https://evernote.com", "trello": "https://trello.com",
    "asana": "https://app.asana.com", "monday": "https://monday.com",
    "linear": "https://linear.app", "jira": "https://atlassian.com/software/jira",
    "confluence": "https://atlassian.com/software/confluence", "airtable": "https://airtable.com",
    "figma": "https://www.figma.com", "miro": "https://miro.com",
    "canva": "https://www.canva.com", "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com", "google slides": "https://slides.google.com",
    "office": "https://www.office.com", "outlook": "https://outlook.live.com",
    "calendar": "https://calendar.google.com", "google calendar": "https://calendar.google.com",
    "icloud": "https://www.icloud.com", "dropbox": "https://www.dropbox.com",
    "box": "https://www.box.com", "wetransfer": "https://wetransfer.com",
    # --- learning ---
    "coursera": "https://www.coursera.org", "edx": "https://www.edx.org",
    "udemy": "https://www.udemy.com", "udacity": "https://www.udacity.com",
    "khan academy": "https://www.khanacademy.org", "duolingo": "https://www.duolingo.com",
    "skillshare": "https://www.skillshare.com", "pluralsight": "https://www.pluralsight.com",
    "codecademy": "https://www.codecademy.com", "freecodecamp": "https://www.freecodecamp.org",
    "brilliant": "https://brilliant.org", "ted": "https://www.ted.com",
    # --- travel ---
    "google flights": "https://www.google.com/travel/flights", "skyscanner": "https://www.skyscanner.net",
    "kayak": "https://www.kayak.com", "expedia": "https://www.expedia.com",
    "booking": "https://www.booking.com", "airbnb": "https://www.airbnb.com",
    "tripadvisor": "https://www.tripadvisor.com", "uber": "https://www.uber.com",
    "lyft": "https://www.lyft.com", "doordash": "https://www.doordash.com",
    "ubereats": "https://www.ubereats.com", "grubhub": "https://www.grubhub.com",
    # --- weather / utilities ---
    "weather": "https://weather.com", "weather underground": "https://www.wunderground.com",
    "speedtest": "https://www.speedtest.net", "fast": "https://fast.com",
    "downdetector": "https://downdetector.com", "ifttt": "https://ifttt.com",
    "zapier": "https://zapier.com", "make": "https://www.make.com",
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
}

if IS_LINUX:
    FOLDERS["recycle bin"] = Path.home() / ".local/share/Trash/files"
    FOLDERS["trash"] = Path.home() / ".local/share/Trash/files"
    FOLDERS["this pc"] = Path("/")
    FOLDERS["my computer"] = Path("/")
    SHELL_LOCATIONS = {}
else:
    FOLDERS["onedrive"] = Path.home() / "OneDrive"
    FOLDERS["recycle bin"] = None  # special shell folder
    FOLDERS["this pc"] = None
    FOLDERS["my computer"] = None
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


_FIELD_CODE_RE = re.compile(r"%[fFuUdDnNickvm]")


def _scan_desktop_files(root: Path):
    """Parse .desktop launcher files (freedesktop.org spec)."""
    results = []
    if not root.exists():
        return results
    for p in root.glob("*.desktop"):
        try:
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.read(p, encoding="utf-8")
            if "Desktop Entry" not in cp:
                continue
            entry = cp["Desktop Entry"]
            if entry.get("Type", "Application") != "Application":
                continue
            if entry.get("NoDisplay", "false").strip().lower() == "true":
                continue
            if entry.get("Hidden", "false").strip().lower() == "true":
                continue
            name = entry.get("Name", "").strip()
            exec_cmd = entry.get("Exec", "").strip()
            if name and exec_cmd:
                results.append((name.lower(), exec_cmd))
        except Exception:
            continue
    return results


def _launch_desktop_exec(exec_cmd: str):
    """Launch a .desktop Exec= line, stripping %f/%U/etc field codes."""
    cmd = _FIELD_CODE_RE.sub("", exec_cmd).strip()
    parts = shlex.split(cmd)
    if not parts:
        raise RuntimeError("empty launch command")
    subprocess.Popen(parts)


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
    if IS_LINUX:
        roots = [
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
            Path("/var/lib/snapd/desktop/applications"),
            Path.home() / ".local/share/applications",
            Path.home() / ".local/share/flatpak/exports/share/applications",
            Path("/var/lib/flatpak/exports/share/applications"),
        ]
        for r in roots:
            items.extend(_scan_desktop_files(r))
    else:
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


def _xdotool_key(keys: str):
    """Send a key combo (e.g. 'ctrl+c') via xdotool — X11/XWayland only."""
    if not shutil.which("xdotool"):
        raise RuntimeError("xdotool isn't installed (sudo apt install xdotool).")
    subprocess.run(["xdotool", "key", "--clearmodifiers", keys], timeout=3)


def _first_available(cmds) -> str | None:
    for c in cmds:
        if shutil.which(c):
            return c
    return None


def _open_path(path: str):
    if IS_LINUX:
        subprocess.Popen(["xdg-open", path])
    else:
        os.startfile(path)


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
            _open_path(str(FOLDERS[key])); return f"Opening {key}."
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
        if IS_LINUX:
            cmd = _first_available(path) if isinstance(path, (list, tuple)) else path
            if not cmd or not shutil.which(cmd):
                return f"{name.title()} isn't installed."
            try:
                subprocess.Popen([cmd])
                return f"Opening {name}."
            except Exception as e:
                return f"Couldn't open {name}: {e}"
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

    # Dynamic index (Start Menu / Desktop / UWP, or Linux .desktop entries)
    target = _find_app(key)
    if target:
        try:
            if IS_LINUX:
                _launch_desktop_exec(target)
            elif target.startswith("shell:"):
                subprocess.Popen(["explorer.exe", target])
            else:
                os.startfile(target)
            return f"Opening {name}."
        except Exception as e:
            return f"Couldn't launch {name}: {e}"

    # Final fallback — try to find it directly on PATH (Linux) or let the
    # shell interpret it (Windows)
    if IS_LINUX:
        exe = (shutil.which(key) or shutil.which(key.replace(" ", "-"))
               or shutil.which(key.replace(" ", "")))
        if exe:
            try:
                subprocess.Popen([exe])
                return f"Opening {name}."
            except Exception as e:
                return f"Couldn't open {name}: {e}"
        return f"I couldn't find {name}."
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


_pending_power_timer = None


def _schedule_power(cmd: list, seconds: float = 10.0):
    global _pending_power_timer
    if _pending_power_timer is not None:
        _pending_power_timer.cancel()
    t = threading.Timer(seconds, lambda: subprocess.Popen(cmd))
    t.daemon = True
    _pending_power_timer = t
    t.start()


def _cancel_power() -> bool:
    global _pending_power_timer
    if _pending_power_timer is not None:
        _pending_power_timer.cancel()
        _pending_power_timer = None
        return True
    return False


def _linux_system_action(a: str):
    """Returns a response string, or None if `a` isn't handled here."""
    if a in ("volume up", "vol up"):
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"]); return "Volume up."
    if a in ("volume down", "vol down"):
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"]); return "Volume down."
    if a == "max volume":
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "100%"]); return "Maximum volume."
    if a == "min volume":
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "0%"]); return "Minimum volume."
    if a in ("mute", "unmute"):
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]); return "Toggling mute."
    if a in ("play", "pause"):
        subprocess.run(["playerctl", "play-pause"]); return f"{a.title()}."
    if a == "next":
        subprocess.run(["playerctl", "next"]); return "Next track."
    if a == "previous":
        subprocess.run(["playerctl", "previous"]); return "Previous track."
    if a == "brightness up":
        subprocess.run(["brightnessctl", "set", "+10%"]); return "Brightness up."
    if a == "brightness down":
        subprocess.run(["brightnessctl", "set", "10%-"]); return "Brightness down."
    if a == "screenshot":
        cmd = _first_available(["gnome-screenshot", "flameshot", "spectacle"])
        if cmd == "gnome-screenshot": subprocess.Popen([cmd, "-i"])
        elif cmd == "flameshot": subprocess.Popen([cmd, "gui"])
        elif cmd: subprocess.Popen([cmd])
        else: return "No screenshot tool installed (try: sudo apt install gnome-screenshot)."
        return "Opening the screenshot tool."
    if a in ("show desktop", "minimize all"):
        subprocess.run(["wmctrl", "-k", "on"]); return "Showing desktop."
    if a == "task view":
        _xdotool_key("super"); return "Task view."
    if a in ("new desktop", "switch desktop"):
        return "Virtual desktop switching isn't supported on Linux yet."
    if a == "close window":
        subprocess.run(["wmctrl", "-c", ":ACTIVE:"]); return "Closing window."
    if a == "copy": _xdotool_key("ctrl+c"); return "Copied."
    if a == "paste": _xdotool_key("ctrl+v"); return "Pasted."
    if a == "cut": _xdotool_key("ctrl+x"); return "Cut."
    if a == "undo": _xdotool_key("ctrl+z"); return "Undone."
    if a == "redo": _xdotool_key("ctrl+y"); return "Redone."
    if a == "select all": _xdotool_key("ctrl+a"); return "Selected all."
    if a == "empty recycle bin":
        trash = Path.home() / ".local/share/Trash"
        shutil.rmtree(trash / "files", ignore_errors=True)
        shutil.rmtree(trash / "info", ignore_errors=True)
        (trash / "files").mkdir(parents=True, exist_ok=True)
        (trash / "info").mkdir(parents=True, exist_ok=True)
        return "Trash emptied."
    if a == "lock":
        cmd = _first_available(["loginctl", "gnome-screensaver-command", "xdg-screensaver"])
        if cmd == "loginctl":
            subprocess.Popen(["loginctl", "lock-session"])
        elif cmd == "gnome-screensaver-command":
            subprocess.Popen(["gnome-screensaver-command", "-l"])
        elif cmd == "xdg-screensaver":
            subprocess.Popen(["xdg-screensaver", "lock"])
        else:
            return "No screen locker found."
        return "Locking the screen."
    if a == "sleep":
        subprocess.Popen(["systemctl", "suspend"]); return "Going to sleep."
    if a == "shutdown":
        _schedule_power(["systemctl", "poweroff"])
        return "Shutting down in 10 seconds. Say cancel to abort."
    if a == "restart":
        _schedule_power(["systemctl", "reboot"])
        return "Restarting in 10 seconds."
    if a == "sign out":
        cmd = _first_available(["gnome-session-quit"])
        if cmd:
            subprocess.Popen([cmd, "--logout", "--no-prompt"])
        else:
            subprocess.Popen(["loginctl", "terminate-user", os.environ.get("USER", "")])
        return "Signing out."
    if a == "cancel":
        return "Cancelled." if _cancel_power() else "Nothing pending to cancel."
    if a == "battery":
        try:
            import psutil
            b = psutil.sensors_battery()
            if b: return f"Battery at {int(b.percent)} percent."
        except Exception:
            pass
        return "No battery detected."
    return None


def system_action(action: str) -> str:
    a = (action or "").lower()
    if a == "time":
        return "It is " + datetime.datetime.now().strftime("%I:%M %p")
    if a == "date":
        return "Today is " + datetime.datetime.now().strftime("%A, %B %d, %Y")
    if IS_LINUX:
        try:
            r = _linux_system_action(a)
        except Exception as e:
            return f"System error. {e}"
        return r if r is not None else f"I don't know how to {action}."
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


# ---------- New cool commands ----------

def weather(location: str) -> str:
    loc = (location or "").strip() or ""
    try:
        url = f"https://wttr.in/{urllib.parse.quote(loc)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        cur = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]
        place = area.get("areaName", [{"value": loc or "your location"}])[0]["value"]
        desc = cur["weatherDesc"][0]["value"]
        temp_c = cur["temp_C"]
        feels = cur["FeelsLikeC"]
        wind = cur["windspeedKmph"]
        return f"In {place} it's {temp_c} degrees Celsius and {desc.lower()}. Feels like {feels}. Wind {wind} kilometres per hour."
    except Exception as e:
        return f"Couldn't fetch the weather. {e}"


def timer(value: str) -> str:
    """value like '5 minutes' or '30 seconds'."""
    v = (value or "").strip().lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|[smh])\b", v)
    if not m:
        return "How long? Try 'set a timer for 5 minutes'."
    n = float(m.group(1))
    unit = m.group(2)
    secs = n * (1 if unit.startswith(("s", "sec")) else 60 if unit.startswith(("m", "min")) else 3600)
    label = f"{int(n)} {unit}" + ("s" if n != 1 and not unit.endswith("s") else "")

    def _fire():
        try:
            if IS_LINUX:
                if shutil.which("notify-send"):
                    subprocess.run(["notify-send", "-u", "critical", "Jarvis Timer",
                                     f"Your timer for {label} is up."])
                sound = Path("/usr/share/sounds/freedesktop/stereo/complete.oga")
                if shutil.which("paplay") and sound.exists():
                    subprocess.Popen(["paplay", str(sound)])
            else:
                ctypes.windll.user32.MessageBeep(0xFFFFFFFF)
                ctypes.windll.user32.MessageBoxW(0, f"⏰ Your timer for {label} is up.", "Jarvis Timer", 0x40 | 0x40000)
        except Exception:
            pass

    threading.Timer(secs, _fire).start()
    return f"Timer set for {label}."


def calculator(expr: str) -> str:
    """Safe arithmetic evaluator: + - * / ** % () and float/int."""
    e = (expr or "").lower()
    e = (e.replace("plus", "+").replace("minus", "-")
           .replace("times", "*").replace("multiplied by", "*")
           .replace("divided by", "/").replace("over", "/")
           .replace("squared", "**2").replace("cubed", "**3")
           .replace("to the power of", "**").replace("power of", "**")
           .replace("modulo", "%").replace("mod", "%")
           .replace("x", "*"))
    e = re.sub(r"[^0-9+\-*/().% ]", "", e).strip()
    if not e:
        return "Calculate what?"
    try:
        result = eval(e, {"__builtins__": {}}, {})
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"{expr.strip()} equals {result}."
    except Exception:
        return f"I couldn't compute {expr}."


def joke() -> str:
    try:
        req = urllib.request.Request(
            "https://official-joke-api.appspot.com/random_joke",
            headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.loads(r.read().decode("utf-8", "ignore"))
        return f"{j['setup']} ... {j['punchline']}"
    except Exception:
        return random.choice([
            "I told my computer I needed a break. It said 'no problem, I'll go to sleep'.",
            "Why did the developer go broke? Because he used up all his cache.",
            "There are 10 types of people in the world: those who understand binary, and those who don't.",
        ])


def news() -> str:
    """Top headline from Hacker News (no key)."""
    try:
        req = urllib.request.Request(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            ids = json.loads(r.read().decode("utf-8"))
        titles = []
        for sid in ids[:3]:
            req = urllib.request.Request(
                f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                headers={"User-Agent": "Jarvis/2.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                item = json.loads(r.read().decode("utf-8"))
                if item and item.get("title"):
                    titles.append(item["title"])
        if titles:
            return "Top headlines: " + ". ".join(titles[:3]) + "."
    except Exception:
        pass
    return "I couldn't reach the news."


def translate(value: str) -> str:
    """value like 'hello to spanish' or 'good morning to french'."""
    m = re.search(r"^(.*)\s+(?:to|in|into)\s+(\w+)$", (value or "").strip(), re.I)
    if not m:
        return "Try 'translate hello to Spanish'."
    text, lang = m.group(1).strip(), m.group(2).strip().lower()
    code_map = {
        "spanish": "es", "french": "fr", "german": "de", "italian": "it",
        "portuguese": "pt", "japanese": "ja", "chinese": "zh-CN", "korean": "ko",
        "russian": "ru", "arabic": "ar", "hebrew": "he", "dutch": "nl",
        "polish": "pl", "turkish": "tr", "hindi": "hi", "english": "en",
    }
    code = code_map.get(lang, lang)
    try:
        url = ("https://api.mymemory.translated.net/get?q="
               + urllib.parse.quote(text) + f"&langpair=en|{code}")
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        out = data.get("responseData", {}).get("translatedText")
        if out:
            return f"In {lang}: {out}"
    except Exception:
        pass
    return "Translation service unreachable."


def system_stats() -> str:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.4)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        return f"CPU at {cpu:.0f} percent. Memory {mem:.0f} percent. Disk {disk:.0f} percent."
    except Exception:
        return "System stats unavailable."


def type_text(text: str) -> str:
    """Type text into the currently focused window after a short delay."""
    if not text:
        return "Type what?"

    def _do():
        import time
        time.sleep(1.5)
        if IS_LINUX:
            if shutil.which("xdotool"):
                subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "12", text])
            return
        for ch in text:
            vk = ctypes.windll.user32.VkKeyScanW(ord(ch))
            if vk == -1: continue
            shift = (vk >> 8) & 1
            key = vk & 0xFF
            if shift: ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)
            if shift: ctypes.windll.user32.keybd_event(0x10, 0, 2, 0)
            time.sleep(0.012)

    threading.Thread(target=_do, daemon=True).start()
    if IS_LINUX and not shutil.which("xdotool"):
        return "Typing needs xdotool — install it with 'sudo apt install xdotool'."
    return f"Typing in 1.5 seconds — focus the target window now."


def flip_coin() -> str:
    return "Heads." if random.random() < 0.5 else "Tails."


def roll_dice(value: str) -> str:
    m = re.match(r"(\d*)d(\d+)", (value or "").lower().strip())
    if m:
        n = int(m.group(1) or "1")
        sides = int(m.group(2))
    else:
        n, sides = 1, 6
    if n > 20 or sides > 1000: return "Too many dice."
    rolls = [random.randint(1, sides) for _ in range(n)]
    if n == 1: return f"You rolled a {rolls[0]}."
    return f"You rolled {sum(rolls)} ({', '.join(map(str, rolls))})."


# ---------- Bulk new commands ----------

# Unit conversions: factor relative to a canonical unit per dimension
_UNITS = {
    "length": {"mm": 0.001, "cm": 0.01, "m": 1, "km": 1000,
               "in": 0.0254, "ft": 0.3048, "yard": 0.9144, "mile": 1609.344},
    "mass":   {"mg": 1e-6, "g": 0.001, "kg": 1, "ton": 1000,
               "oz": 0.0283495, "lb": 0.453592, "stone": 6.35029},
    "volume": {"ml": 0.001, "l": 1, "cup": 0.2366, "pint": 0.4732,
               "quart": 0.9464, "gallon": 3.7854},
    "speed":  {"kmh": 1, "mph": 1.60934, "mps": 3.6, "knot": 1.852},
    "time":   {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800},
    "data":   {"byte": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4},
}
_UNIT_ALIASES = {
    "millimeter": "mm", "millimeters": "mm", "centimeter": "cm", "centimeters": "cm",
    "meter": "m", "meters": "m", "kilometer": "km", "kilometers": "km",
    "inch": "in", "inches": "in", "foot": "ft", "feet": "ft",
    "yards": "yard", "miles": "mile",
    "milligram": "mg", "milligrams": "mg", "gram": "g", "grams": "g",
    "kilogram": "kg", "kilograms": "kg", "tons": "ton",
    "ounce": "oz", "ounces": "oz", "pound": "lb", "pounds": "lb",
    "milliliter": "ml", "milliliters": "ml", "liter": "l", "liters": "l", "litre": "l",
    "cups": "cup", "pints": "pint", "quarts": "quart", "gallons": "gallon",
    "kph": "kmh", "kilometers per hour": "kmh", "miles per hour": "mph",
    "meters per second": "mps", "knots": "knot",
    "seconds": "second", "minutes": "minute", "hours": "hour", "days": "day", "weeks": "week",
    "bytes": "byte", "kilobyte": "kb", "kilobytes": "kb", "megabyte": "mb",
    "megabytes": "mb", "gigabyte": "gb", "gigabytes": "gb", "terabyte": "tb", "terabytes": "tb",
}

def _canonical_unit(u: str):
    u = u.lower().strip()
    u = _UNIT_ALIASES.get(u, u)
    for dim, table in _UNITS.items():
        if u in table:
            return dim, u
    return None, None

def convert(value: str) -> str:
    """value like '5 km to miles' or '212 fahrenheit to celsius'."""
    v = (value or "").lower().strip()
    # Temperature
    m = re.match(r"(-?\d+(?:\.\d+)?)\s*(?:degrees?\s*)?(c|celsius|f|fahrenheit|k|kelvin)\s+(?:to|in)\s+(c|celsius|f|fahrenheit|k|kelvin)", v)
    if m:
        n = float(m.group(1))
        src = m.group(2)[0]; dst = m.group(3)[0]
        # to celsius first
        if src == "f": c = (n - 32) * 5/9
        elif src == "k": c = n - 273.15
        else: c = n
        if dst == "f": out = c * 9/5 + 32
        elif dst == "k": out = c + 273.15
        else: out = c
        return f"{n}°{src.upper()} is {out:.2f}°{dst.upper()}."
    # Generic
    m = re.match(r"(-?\d+(?:\.\d+)?)\s*([\w ]+?)\s+(?:to|in)\s+([\w ]+)", v)
    if not m:
        return "Try '5 km to miles' or '212 F to C'."
    n = float(m.group(1)); src = m.group(2).strip(); dst = m.group(3).strip()
    sd, su = _canonical_unit(src); dd, du = _canonical_unit(dst)
    if not su or not du or sd != dd:
        return f"I can't convert {src} to {dst}."
    base = n * _UNITS[sd][su]
    out = base / _UNITS[dd][du]
    return f"{n} {src} equals {out:.4g} {dst}."


def define(word: str) -> str:
    w = (word or "").strip().split()[0:3]
    if not w: return "Define what?"
    q = " ".join(w)
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(q)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        if isinstance(data, list) and data:
            for entry in data:
                for meaning in entry.get("meanings", []):
                    pos = meaning.get("partOfSpeech", "")
                    defs = meaning.get("definitions", [])
                    if defs and defs[0].get("definition"):
                        return f"{q} ({pos}): {defs[0]['definition']}"
    except Exception:
        pass
    return f"No definition found for {q}."


def synonym(word: str) -> str:
    w = (word or "").strip()
    if not w: return "Synonyms for what?"
    try:
        req = urllib.request.Request(
            f"https://api.datamuse.com/words?rel_syn={urllib.parse.quote(w)}&max=5",
            headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        words = [d["word"] for d in data][:5]
        if words:
            return f"Synonyms for {w}: " + ", ".join(words) + "."
    except Exception:
        pass
    return f"No synonyms found for {w}."


def rhyme(word: str) -> str:
    w = (word or "").strip()
    if not w: return "Rhymes with what?"
    try:
        req = urllib.request.Request(
            f"https://api.datamuse.com/words?rel_rhy={urllib.parse.quote(w)}&max=8",
            headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        words = [d["word"] for d in data][:8]
        if words:
            return f"Rhymes with {w}: " + ", ".join(words) + "."
    except Exception:
        pass
    return f"No rhymes for {w}."


def crypto_price(symbol: str) -> str:
    s = (symbol or "bitcoin").lower().strip()
    aliases = {"btc": "bitcoin", "eth": "ethereum", "doge": "dogecoin",
               "sol": "solana", "ada": "cardano", "xrp": "ripple",
               "ltc": "litecoin", "matic": "polygon", "dot": "polkadot",
               "shib": "shiba-inu", "avax": "avalanche-2", "link": "chainlink"}
    coin = aliases.get(s, s)
    try:
        req = urllib.request.Request(
            f"https://api.coingecko.com/api/v3/simple/price?ids={urllib.parse.quote(coin)}&vs_currencies=usd",
            headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8"))
        price = data.get(coin, {}).get("usd")
        if price is not None:
            return f"{coin.title()} is at ${price:,.2f}."
    except Exception:
        pass
    return f"Couldn't fetch {coin} price."


def stock_price(symbol: str) -> str:
    s = (symbol or "").upper().strip()
    if not s: return "Which stock?"
    try:
        req = urllib.request.Request(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?interval=1d",
            headers={"User-Agent": "Mozilla/5.0 Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8"))
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("previousClose") or price
        cur = meta.get("currency", "USD")
        if price is not None:
            change = (price - prev) / prev * 100 if prev else 0
            arrow = "up" if change >= 0 else "down"
            return f"{s} is {price:.2f} {cur}, {arrow} {abs(change):.2f}% today."
    except Exception:
        pass
    return f"Couldn't fetch {s}."


def _clipboard_copy(text: str) -> bool:
    if pyperclip is not None:
        try:
            pyperclip.copy(text); return True
        except Exception:
            pass
    if IS_LINUX:
        for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, input=text, text=True, timeout=2); return True
                except Exception:
                    continue
        return False
    try:
        subprocess.run("clip", input=text, text=True, timeout=2); return True
    except Exception:
        return False


def _clipboard_read() -> str | None:
    if pyperclip is not None:
        try:
            return pyperclip.paste()
        except Exception:
            pass
    if IS_LINUX:
        for cmd in (["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]):
            if shutil.which(cmd[0]):
                try:
                    out = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                    return out.stdout
                except Exception:
                    continue
        return None
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                             capture_output=True, text=True, timeout=3,
                             creationflags=0x08000000)
        return out.stdout
    except Exception:
        return None


def password_gen(value: str = "") -> str:
    import string
    m = re.search(r"\d+", value or "")
    n = int(m.group(0)) if m else 16
    n = max(6, min(64, n))
    chars = string.ascii_letters + string.digits + "!@#$%&*?-_+="
    pw = "".join(random.choice(chars) for _ in range(n))
    if _clipboard_copy(pw):
        return f"Password generated and copied: {pw}"
    return f"Password: {pw}"


def random_color() -> str:
    h = "%06X" % random.randint(0, 0xFFFFFF)
    r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
    copied = _clipboard_copy(f"#{h}")
    return f"Random color: #{h}, RGB {r}, {g}, {b}." + (" Copied." if copied else "")


def random_number(value: str) -> str:
    m = re.findall(r"\d+", value or "")
    if len(m) >= 2:
        a, b = int(m[0]), int(m[1])
    else:
        a, b = 1, 100
    if a > b: a, b = b, a
    return f"Random number between {a} and {b}: {random.randint(a, b)}."


def quote() -> str:
    """Inspirational quote — falls back to local list if API down."""
    try:
        req = urllib.request.Request("https://api.quotable.io/random",
                                     headers={"User-Agent": "Jarvis/2.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            j = json.loads(r.read().decode("utf-8"))
        return f'"{j["content"]}" — {j["author"]}'
    except Exception:
        return random.choice([
            '"The best way out is always through." — Robert Frost',
            '"Sometimes you win, sometimes you learn." — John Maxwell',
            '"Stay hungry. Stay foolish." — Steve Jobs',
        ])


def word_count(text: str) -> str:
    t = (text or "").strip()
    if not t: return "Count what?"
    return f"{len(t.split())} words, {len(t)} characters."


def reverse_text(text: str) -> str:
    return (text or "")[::-1] or "Reverse what?"


def upper_text(text: str) -> str:
    return (text or "").upper() or "Uppercase what?"


def lower_text(text: str) -> str:
    return (text or "").lower() or "Lowercase what?"


def clipboard_get() -> str:
    out = _clipboard_read()
    v = (out or "").strip()
    if v:
        return f"Clipboard: {v[:200]}"
    return "Clipboard is empty." if out is not None else "Couldn't read clipboard."


def clipboard_set(text: str) -> str:
    if not text: return "Set clipboard to what?"
    return "Copied." if _clipboard_copy(text) else "Couldn't write clipboard."


def _linux_window(a: str) -> str:
    try:
        if a in ("snap left", "left half"): _xdotool_key("super+Left"); return "Snapped left."
        if a in ("snap right", "right half"): _xdotool_key("super+Right"); return "Snapped right."
        if a in ("maximize", "maximise", "full screen"):
            subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-b", "add,maximized_vert,maximized_horz"])
            return "Maximized."
        if a in ("restore", "restore down", "minimize"):
            subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-b", "remove,maximized_vert,maximized_horz"])
            return "Restored." if a != "minimize" else "Minimized."
        if a == "alt tab": _xdotool_key("alt+Tab"); return "Switching window."
        if a == "switch tab": _xdotool_key("ctrl+Tab"); return "Next tab."
        if a == "previous tab": _xdotool_key("ctrl+shift+Tab"); return "Previous tab."
        if a == "new tab": _xdotool_key("ctrl+t"); return "New tab."
        if a == "close tab": _xdotool_key("ctrl+w"); return "Closed tab."
        if a == "reopen tab": _xdotool_key("ctrl+shift+t"); return "Reopened tab."
        if a == "refresh": _xdotool_key("F5"); return "Refreshing."
        if a == "find": _xdotool_key("ctrl+f"); return "Find."
        if a == "save": _xdotool_key("ctrl+s"); return "Saved."
        if a == "print": _xdotool_key("ctrl+p"); return "Print dialog."
        if a == "zoom in": _xdotool_key("ctrl+plus"); return "Zoom in."
        if a == "zoom out": _xdotool_key("ctrl+minus"); return "Zoom out."
        if a == "reset zoom": _xdotool_key("ctrl+0"); return "Zoom reset."
        if a == "back": _xdotool_key("alt+Left"); return "Back."
        if a == "forward": _xdotool_key("alt+Right"); return "Forward."
        if a == "scroll up": _xdotool_key("Page_Up"); return "Page up."
        if a == "scroll down": _xdotool_key("Page_Down"); return "Page down."
        if a == "top": _xdotool_key("ctrl+Home"); return "Top."
        if a == "bottom": _xdotool_key("ctrl+End"); return "Bottom."
        if a == "address bar": _xdotool_key("ctrl+l"); return "Address bar."
        if a == "downloads": _xdotool_key("ctrl+j"); return "Downloads."
        if a == "history": _xdotool_key("ctrl+h"); return "History."
        if a == "bookmarks": _xdotool_key("ctrl+shift+o"); return "Bookmarks."
        if a == "dev tools": _xdotool_key("F12"); return "Dev tools."
    except Exception as e:
        return f"Window error: {e}"
    return f"Don't know how to do that."


def window(action: str) -> str:
    """Snap / move / arrange windows."""
    a = (action or "").lower().strip()
    if IS_LINUX:
        return _linux_window(a)
    try:
        if a in ("snap left", "left half"): _send_hotkey([0x5B, 0x25]); return "Snapped left."
        if a in ("snap right", "right half"): _send_hotkey([0x5B, 0x27]); return "Snapped right."
        if a in ("maximize", "maximise", "full screen"): _send_hotkey([0x5B, 0x26]); return "Maximized."
        if a in ("restore", "restore down"): _send_hotkey([0x5B, 0x28]); return "Restored."
        if a == "minimize": _send_hotkey([0x5B, 0x28]); return "Minimized."
        if a == "alt tab": _send_hotkey([0x12, 0x09]); return "Switching window."
        if a == "switch tab": _send_hotkey([0x11, 0x09]); return "Next tab."
        if a == "previous tab": _send_hotkey([0x11, 0x10, 0x09]); return "Previous tab."
        if a == "new tab": _send_hotkey([0x11, 0x54]); return "New tab."
        if a == "close tab": _send_hotkey([0x11, 0x57]); return "Closed tab."
        if a == "reopen tab": _send_hotkey([0x11, 0x10, 0x54]); return "Reopened tab."
        if a == "refresh": _press_key(0x74); return "Refreshing."
        if a == "find": _send_hotkey([0x11, 0x46]); return "Find."
        if a == "save": _send_hotkey([0x11, 0x53]); return "Saved."
        if a == "print": _send_hotkey([0x11, 0x50]); return "Print dialog."
        if a == "zoom in": _send_hotkey([0x11, 0xBB]); return "Zoom in."
        if a == "zoom out": _send_hotkey([0x11, 0xBD]); return "Zoom out."
        if a == "reset zoom": _send_hotkey([0x11, 0x30]); return "Zoom reset."
        if a == "back": _press_key(0x08); return "Back."
        if a == "forward": _send_hotkey([0x12, 0x27]); return "Forward."
        if a == "scroll up": _press_key(0x21); return "Page up."
        if a == "scroll down": _press_key(0x22); return "Page down."
        if a == "top": _send_hotkey([0x11, 0x24]); return "Top."
        if a == "bottom": _send_hotkey([0x11, 0x23]); return "Bottom."
        if a == "address bar": _send_hotkey([0x11, 0x4C]); return "Address bar."
        if a == "downloads": _send_hotkey([0x11, 0x4A]); return "Downloads."
        if a == "history": _send_hotkey([0x11, 0x48]); return "History."
        if a == "bookmarks": _send_hotkey([0x11, 0x10, 0x4F]); return "Bookmarks."
        if a == "dev tools": _press_key(0x7B); return "Dev tools."
    except Exception as e:
        return f"Window error: {e}"
    return f"Don't know how to {action}."


def kill_process(name: str) -> str:
    """Kill all processes matching a name (e.g. 'chrome', 'notepad')."""
    n = (name or "").strip().lower()
    if not n: return "Kill what?"
    if IS_LINUX:
        base = n[:-4] if n.endswith(".exe") else n
        blocked = {"systemd", "init", "gnome-shell", "xorg", "wayland", "dbus-daemon", "kwin"}
        if base in blocked: return f"I won't kill {base} — it's a system process."
        try:
            out = subprocess.run(["pkill", "-f", "-i", base],
                                 capture_output=True, text=True, timeout=4)
            if out.returncode == 0:
                return f"Closed {base}."
            return f"No running {base}."
        except Exception as e:
            return f"Couldn't kill {base}: {e}"
    if not n.endswith(".exe"): n += ".exe"
    blocked = {"explorer.exe", "winlogon.exe", "csrss.exe", "wininit.exe", "system.exe"}
    if n in blocked: return f"I won't kill {n} — it's a system process."
    try:
        out = subprocess.run(["taskkill", "/F", "/IM", n],
                             capture_output=True, text=True, timeout=4)
        if out.returncode == 0:
            return f"Closed {n}."
        return f"No running {n}."
    except Exception as e:
        return f"Couldn't kill {n}: {e}"


_ROBOT_HUB = None


def set_robot_hub(hub):
    global _ROBOT_HUB
    _ROBOT_HUB = hub


def _robot():
    if _ROBOT_HUB is None or not _ROBOT_HUB.is_connected():
        return None
    return _ROBOT_HUB


def robot_forward(value: str = "") -> str:
    hub = _robot()
    return hub.drive("forward") if hub else "The rover isn't connected."


def robot_backward(value: str = "") -> str:
    hub = _robot()
    return hub.drive("backward") if hub else "The rover isn't connected."


def robot_turn(direction: str) -> str:
    hub = _robot()
    return hub.turn(direction) if hub else "The rover isn't connected."


def robot_stop(value: str = "") -> str:
    hub = _robot()
    return hub.stop_all() if hub else "The rover isn't connected."


def robot_head(direction: str) -> str:
    hub = _robot()
    return hub.turn_head(direction) if hub else "The rover isn't connected."


def robot_claw(action: str) -> str:
    hub = _robot()
    return hub.claw(action) if hub else "The rover isn't connected."


def execute(action: str, value: str) -> str:
    a = (action or "").lower()
    v = value or ""
    if a == "open_url": return open_url(v)
    if a == "open_app": return open_app(v)
    if a == "search_web": return search_web(v)
    if a == "youtube": return youtube_search(v)
    if a == "system": return system_action(v)
    if a == "weather": return weather(v)
    if a == "timer": return timer(v)
    if a == "calc": return calculator(v)
    if a == "joke": return joke()
    if a == "news": return news()
    if a == "translate": return translate(v)
    if a == "stats": return system_stats()
    if a == "type": return type_text(v)
    if a == "coin": return flip_coin()
    if a == "dice": return roll_dice(v)
    if a == "convert": return convert(v)
    if a == "define": return define(v)
    if a == "synonym": return synonym(v)
    if a == "rhyme": return rhyme(v)
    if a == "crypto": return crypto_price(v)
    if a == "stock": return stock_price(v)
    if a == "password": return password_gen(v)
    if a == "color": return random_color()
    if a == "rand": return random_number(v)
    if a == "quote": return quote()
    if a == "wordcount": return word_count(v)
    if a == "reverse": return reverse_text(v)
    if a == "upper": return upper_text(v)
    if a == "lower": return lower_text(v)
    if a == "clip_get": return clipboard_get()
    if a == "clip_set": return clipboard_set(v)
    if a == "window": return window(v)
    if a == "kill": return kill_process(v)
    if a == "robot_forward": return robot_forward(v)
    if a == "robot_backward": return robot_backward(v)
    if a == "robot_turn": return robot_turn(v)
    if a == "robot_stop": return robot_stop(v)
    if a == "robot_head": return robot_head(v)
    if a == "robot_claw": return robot_claw(v)
    return ""

"""Jarvis brain — rule-based intent parser with optional LLM + free web Q&A.

Works great with NO API key. If ANTHROPIC_API_KEY is set, it's used for the
hardest chat/reasoning fallback. Otherwise, chat questions hit DuckDuckGo's
Instant Answer API and Wikipedia REST — both free, no auth.
"""
import json
import re
import urllib.parse
import urllib.request

from config import ANTHROPIC_API_KEY, MODEL, ASSISTANT_NAME, USER_NAME
from commands import SITES, APP_PATHS, FOLDERS


WAKE_PREFIXES = ("jarvis", "hey jarvis", "ok jarvis", "okay jarvis")
FILLER_PREFIXES = (
    "can you", "could you", "please", "i want you to", "i need you to",
    "would you", "will you", "just", "now",
)

SYSTEM_MAP = {
    "volume up": ["volume up", "louder", "turn it up", "increase volume", "raise volume"],
    "volume down": ["volume down", "quieter", "turn it down", "lower volume", "decrease volume"],
    "mute": ["mute", "unmute", "silence"],
    "play": ["resume", "play music", "continue music"],
    "pause": ["pause", "pause music", "stop music"],
    "next": ["next", "next track", "next song", "skip"],
    "previous": ["previous", "previous track", "previous song", "go back"],
    "lock": ["lock", "lock the computer", "lock pc", "lock screen", "lock workstation"],
    "sleep": ["sleep", "go to sleep", "suspend"],
    "shutdown": ["shutdown", "shut down", "turn off the computer", "power off"],
    "restart": ["restart", "reboot", "restart the computer"],
    "cancel": ["cancel", "abort", "nevermind", "never mind", "cancel shutdown"],
    "time": ["time", "what time is it", "current time", "tell me the time"],
    "date": ["date", "what is the date", "today's date", "what day is it"],
    "max volume": ["max volume", "maximum volume", "full volume"],
    "min volume": ["min volume", "minimum volume", "zero volume"],
    "brightness up": ["brightness up", "brighter", "increase brightness"],
    "brightness down": ["brightness down", "darker", "decrease brightness", "dim the screen"],
    "screenshot": ["screenshot", "take a screenshot", "snip", "snip screen", "capture screen"],
    "show desktop": ["show desktop", "minimize everything", "show the desktop"],
    "task view": ["task view", "show tasks", "show windows"],
    "minimize all": ["minimize all", "minimize everything", "minimize all windows"],
    "new desktop": ["new desktop", "new virtual desktop"],
    "switch desktop": ["switch desktop", "next desktop"],
    "close window": ["close window", "close this window", "close the window"],
    "copy": ["copy", "copy that"],
    "paste": ["paste", "paste that"],
    "cut": ["cut"],
    "undo": ["undo"],
    "redo": ["redo"],
    "select all": ["select all"],
    "empty recycle bin": ["empty recycle bin", "empty the recycle bin", "empty trash"],
    "sign out": ["sign out", "log out", "log off"],
    "battery": ["battery", "battery level", "how much battery", "battery status"],
}

OPEN_VERBS = ("open", "launch", "start", "run", "bring up", "pull up", "show me")
SEARCH_VERBS = ("search for", "search", "google", "look up", "find")
PLAY_VERBS = ("play", "watch", "put on", "queue up")


def _strip_prefixes(text: str) -> str:
    t = text.strip().lower().rstrip("?.!")
    for w in WAKE_PREFIXES:
        if t.startswith(w):
            t = t[len(w):].lstrip(" ,")
            break
    changed = True
    while changed:
        changed = False
        for f in FILLER_PREFIXES:
            if t.startswith(f + " "):
                t = t[len(f) + 1:]
                changed = True
    return t.strip()


def _match_system(t: str):
    for action, phrases in SYSTEM_MAP.items():
        for p in phrases:
            if re.search(rf"\b{re.escape(p)}\b", t):
                return action
    return None


def _known_target(t: str):
    for k in sorted(SITES.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", t):
            return "url", k
    for k in sorted(APP_PATHS.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", t):
            return "app", k
    for k in sorted(FOLDERS.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", t):
            return "app", k
    return None, None


def _after_verb(t: str, verbs) -> str:
    for v in sorted(verbs, key=len, reverse=True):
        m = re.match(rf"^{re.escape(v)}\b\s*(.*)$", t)
        if m:
            return m.group(1).strip()
    return ""


def _duckduckgo(query: str) -> str:
    try:
        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_redirect": "1", "no_html": "1", "skip_disambig": "1"}
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        for key in ("AbstractText", "Answer", "Definition"):
            v = data.get(key)
            if v:
                return v if len(v) < 400 else v[:380].rsplit(". ", 1)[0] + "."
        topics = data.get("RelatedTopics") or []
        for topic in topics:
            if isinstance(topic, dict) and topic.get("Text"):
                txt = topic["Text"]
                return txt if len(txt) < 400 else txt[:380] + "…"
    except Exception:
        pass
    return ""


def _pollinations(prompt: str, history=None) -> str:
    """Free LLM via pollinations.ai — no API key needed."""
    try:
        sys_msg = (
            f"You are {ASSISTANT_NAME}, a witty, concise AI assistant for {USER_NAME}. "
            "Reply in 1-3 short sentences, like a butler. No markdown, no lists."
        )
        convo = ""
        if history:
            for turn in history[-6:]:
                role = "User" if turn["role"] == "user" else "Jarvis"
                convo += f"{role}: {turn['content']}\n"
        full = f"{sys_msg}\n{convo}User: {prompt}\nJarvis:"
        url = "https://text.pollinations.ai/" + urllib.parse.quote(full)
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/4.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            txt = r.read().decode("utf-8", "ignore").strip()
        # strip any leading "Jarvis:" the model echoed
        txt = re.sub(r"^(Jarvis|Assistant)\s*:\s*", "", txt, flags=re.I)
        if len(txt) > 600:
            txt = txt[:560].rsplit(". ", 1)[0] + "."
        return txt
    except Exception:
        return ""


def _wikipedia(query: str) -> str:
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(query.replace(" ", "_"))
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        extract = data.get("extract")
        if extract:
            parts = re.split(r"(?<=[.!?])\s+", extract)
            return " ".join(parts[:2])[:450]
    except Exception:
        pass
    return ""


class Brain:
    def __init__(self):
        self._llm = None
        if ANTHROPIC_API_KEY:
            try:
                from anthropic import Anthropic
                self._llm = Anthropic(api_key=ANTHROPIC_API_KEY)
            except Exception:
                self._llm = None
        self.history = []

    def think(self, raw: str) -> dict:
        t = _strip_prefixes(raw)

        # ----- New cool commands first (more specific patterns) -----

        # Weather
        m = re.match(r"(?:what's |what is |how is )?(?:the )?weather(?: like)?(?: in (.+))?$", t)
        if m:
            loc = (m.group(1) or "").strip()
            return {"action": "weather", "value": loc, "speak": ""}
        if t.startswith("weather "):
            return {"action": "weather", "value": t[8:].strip(), "speak": ""}

        # Timer
        m = re.match(r"(?:set (?:a )?|start (?:a )?)?timer (?:for |of )?(.+)$", t)
        if m:
            return {"action": "timer", "value": m.group(1).strip(), "speak": ""}
        m = re.match(r"remind me in (.+)", t)
        if m:
            return {"action": "timer", "value": m.group(1).strip(), "speak": ""}

        # Calculator
        m = re.match(r"(?:calculate|compute|what(?:'s| is)) (.+)$", t)
        if m and re.search(r"[\d+\-*/x%]|plus|minus|times|divided|squared|cubed|power", m.group(1)):
            return {"action": "calc", "value": m.group(1).strip("?. "), "speak": ""}
        # bare arithmetic like "5 plus 3" or "12 times 4"
        if re.fullmatch(r"[\d\s+\-*/x%().]+", t) and re.search(r"\d", t) and re.search(r"[+\-*/x%]", t):
            return {"action": "calc", "value": t, "speak": ""}

        # Joke
        if re.search(r"\b(tell me a joke|joke|make me laugh|something funny)\b", t):
            return {"action": "joke", "value": "", "speak": ""}

        # News
        if re.search(r"\b(news|headlines|what's happening|what is happening)\b", t):
            return {"action": "news", "value": "", "speak": ""}

        # Translate
        m = re.match(r"(?:translate )(.+?)(?:\s+(?:to|in|into)\s+(\w+))$", t)
        if m:
            return {"action": "translate", "value": f"{m.group(1)} to {m.group(2)}", "speak": ""}

        # System stats
        if re.search(r"\b(system stats|system status|cpu|memory usage|how is the system)\b", t):
            return {"action": "stats", "value": "", "speak": ""}

        # Type text
        m = re.match(r"(?:type|write) (.+)$", t)
        if m:
            return {"action": "type", "value": m.group(1).strip("\"' "), "speak": ""}

        # Coin / dice
        if re.search(r"\b(flip a coin|coin flip|toss a coin)\b", t):
            return {"action": "coin", "value": "", "speak": ""}
        m = re.match(r"roll (?:a )?(?:die|dice|d(\d+)|(\d+) ?d ?(\d+))$", t)
        if m:
            spec = "1d6"
            if m.group(1): spec = f"1d{m.group(1)}"
            elif m.group(2) and m.group(3): spec = f"{m.group(2)}d{m.group(3)}"
            return {"action": "dice", "value": spec, "speak": ""}
        if "roll the dice" in t or "roll dice" in t:
            return {"action": "dice", "value": "1d6", "speak": ""}

        # Unit conversion (5 km to miles, 100 f to c, 2 kg to pounds)
        if re.search(r"\d.*\s+(?:to|in)\s+\w", t) and re.search(r"(km|mi|miles?|kg|pound|lb|oz|gram|ounce|inch|foot|feet|yard|meter|cm|mm|liter|gallon|cup|fahrenheit|celsius|kelvin|mph|kmh|kph|byte|kb|mb|gb|tb|second|minute|hour|day|week)\b", t):
            return {"action": "convert", "value": t, "speak": ""}
        m = re.match(r"convert (.+)$", t)
        if m: return {"action": "convert", "value": m.group(1), "speak": ""}

        # Definition / spelling / synonyms / rhymes
        m = re.match(r"(?:define|definition of|meaning of|what does (.+) mean) (.+)$", t)
        if m:
            w = m.group(2) or m.group(1)
            return {"action": "define", "value": w.strip("?. "), "speak": ""}
        m = re.match(r"^define (.+)$", t)
        if m: return {"action": "define", "value": m.group(1).strip("?. "), "speak": ""}
        m = re.match(r"(?:synonyms? (?:for|of)|another word for) (.+)$", t)
        if m: return {"action": "synonym", "value": m.group(1).strip("?. "), "speak": ""}
        m = re.match(r"(?:what )?rhymes? with (.+)$", t)
        if m: return {"action": "rhyme", "value": m.group(1).strip("?. "), "speak": ""}

        # Crypto / stock prices
        m = re.match(r"(?:price of |what's the price of |what is the price of )?(?:bitcoin|btc|ethereum|eth|dogecoin|doge|solana|sol|cardano|ada|ripple|xrp|litecoin|ltc|polygon|matic|polkadot|dot|avalanche|avax|chainlink|link|shiba|shib)\s*(?:price)?$", t)
        if m:
            sym = re.sub(r"^(price of |what's the price of |what is the price of )", "", t)
            sym = re.sub(r"\s*price$", "", sym).strip()
            return {"action": "crypto", "value": sym, "speak": ""}
        m = re.match(r"(?:stock price (?:of|for)|price of stock|how is) (\w+)(?: stock)?$", t)
        if m: return {"action": "stock", "value": m.group(1), "speak": ""}
        m = re.match(r"(\w{1,5}) stock(?: price)?$", t)
        if m: return {"action": "stock", "value": m.group(1), "speak": ""}

        # Password / random / color / quote
        if re.search(r"\b(generate (?:a )?password|new password|random password|create (?:a )?password)\b", t):
            return {"action": "password", "value": t, "speak": ""}
        if re.search(r"\b(random color|give me a color|pick a color)\b", t):
            return {"action": "color", "value": "", "speak": ""}
        m = re.match(r"random number(?: between (\d+) (?:and|to) (\d+))?", t)
        if m:
            v = f"{m.group(1)} {m.group(2)}" if m.group(1) else ""
            return {"action": "rand", "value": v, "speak": ""}
        if re.search(r"\b(inspire me|motivate me|quote|inspirational quote|wise words)\b", t):
            return {"action": "quote", "value": "", "speak": ""}

        # Text utilities
        m = re.match(r"(?:word count|count words in|how many words in) (.+)$", t)
        if m: return {"action": "wordcount", "value": m.group(1), "speak": ""}
        m = re.match(r"reverse (?:the text |this )?(.+)$", t)
        if m: return {"action": "reverse", "value": m.group(1), "speak": ""}
        m = re.match(r"(?:uppercase|capitalize) (.+)$", t)
        if m: return {"action": "upper", "value": m.group(1), "speak": ""}
        m = re.match(r"lowercase (.+)$", t)
        if m: return {"action": "lower", "value": m.group(1), "speak": ""}

        # Clipboard
        if re.search(r"\b(read clipboard|what's (?:in|on) (?:the )?clipboard|clipboard contents)\b", t):
            return {"action": "clip_get", "value": "", "speak": ""}
        m = re.match(r"copy (?:to clipboard )?(.+?)(?: to clipboard)?$", t)
        if m and "tab" not in t and "that" not in t:
            return {"action": "clip_set", "value": m.group(1).strip("\"'"), "speak": ""}

        # Window / browser shortcuts
        WINDOW_PHRASES = {
            "snap left": "snap left", "snap right": "snap right",
            "left half": "snap left", "right half": "snap right",
            "maximize": "maximize", "maximise": "maximize", "full screen": "maximize",
            "restore": "restore", "minimize this window": "minimize",
            "alt tab": "alt tab", "switch window": "alt tab",
            "next tab": "switch tab", "switch tab": "switch tab",
            "previous tab": "previous tab", "new tab": "new tab",
            "close tab": "close tab", "reopen tab": "reopen tab",
            "refresh": "refresh", "reload": "refresh",
            "find on page": "find", "find in page": "find",
            "save": "save", "print": "print",
            "zoom in": "zoom in", "zoom out": "zoom out", "reset zoom": "reset zoom",
            "go back": "back", "go forward": "forward",
            "scroll up": "scroll up", "page up": "scroll up",
            "scroll down": "scroll down", "page down": "scroll down",
            "go to top": "top", "go to bottom": "bottom",
            "address bar": "address bar", "downloads": "downloads",
            "history": "history", "bookmarks": "bookmarks",
            "developer tools": "dev tools", "dev tools": "dev tools",
        }
        for phrase, w in WINDOW_PHRASES.items():
            if re.search(rf"\b{re.escape(phrase)}\b", t):
                return {"action": "window", "value": w, "speak": ""}

        # Kill process
        m = re.match(r"(?:kill|close|quit|terminate|end) (?:process )?(\w[\w ]*?)(?: process)?$", t)
        if m and m.group(1) not in ("window", "this window", "tab", "current window"):
            return {"action": "kill", "value": m.group(1).strip(), "speak": ""}

        sys_action = _match_system(t)
        if sys_action:
            return {"action": "system", "value": sys_action, "speak": self._sys_speak(sys_action)}

        play_q = _after_verb(t, PLAY_VERBS)
        if play_q:
            play_q = re.sub(r"\s+on\s+youtube$", "", play_q).strip()
            if play_q:
                return {"action": "youtube", "value": play_q, "speak": f"Queuing up {play_q}."}

        open_q = _after_verb(t, OPEN_VERBS)
        if open_q:
            return self._resolve_open(open_q)

        search_q = _after_verb(t, SEARCH_VERBS)
        if search_q:
            return {"action": "search_web", "value": search_q, "speak": f"Searching the web for {search_q}."}

        kind, key = _known_target(t)
        if kind == "url" and len(t.split()) <= 3:
            return {"action": "open_url", "value": key, "speak": f"Opening {key}."}
        if kind == "app" and len(t.split()) <= 3:
            return {"action": "open_app", "value": key, "speak": f"Opening {key}."}
        if re.fullmatch(r"[\w\-]+\.(com|org|net|io|ai|dev|co|gg|uk|gov|edu)[\w\-/.?=&%]*", t):
            return {"action": "open_url", "value": t, "speak": f"Opening {t}."}

        st = self._smalltalk(t)
        if st:
            return {"action": "chat", "value": "", "speak": st}

        if self._llm:
            try:
                return self._llm_think(raw)
            except Exception:
                pass

        # Free LLM (no key) — pollinations.ai
        poll = _pollinations(raw, self.history)
        if poll:
            self.history.append({"role": "user", "content": raw})
            self.history.append({"role": "assistant", "content": poll})
            self.history = self.history[-12:]
            return {"action": "chat", "value": "", "speak": poll}

        ans = _duckduckgo(t) or _wikipedia(t)
        if ans:
            return {"action": "chat", "value": "", "speak": ans}

        return {"action": "search_web", "value": raw,
                "speak": f"Let me search the web for that, {USER_NAME}."}

    def _sys_speak(self, action: str) -> str:
        return {
            "time": "Checking the clock.",
            "date": "Checking the calendar.",
            "volume up": "Volume up.", "volume down": "Volume down.",
            "mute": "Toggling mute.", "play": "Playing.", "pause": "Paused.",
            "next": "Next track.", "previous": "Previous track.",
            "lock": f"Locking the workstation, {USER_NAME}.",
            "sleep": "Going to sleep.",
            "shutdown": "Shutting down in 10 seconds. Say cancel to abort.",
            "restart": "Restarting in 10 seconds.",
            "cancel": "Cancelled.",
        }.get(action, "Acknowledged.")

    def _resolve_open(self, q: str) -> dict:
        q = q.strip()
        if not q:
            return {"action": "chat", "value": "", "speak": "Open what, exactly?"}
        if re.fullmatch(r"[\w\-]+\.(com|org|net|io|ai|dev|co|gg|uk|gov|edu)[\w\-/.?=&%]*", q):
            return {"action": "open_url", "value": q, "speak": f"Opening {q}."}
        for k in sorted(SITES.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(k)}\b", q):
                return {"action": "open_url", "value": k, "speak": f"Opening {k}."}
        for k in sorted(APP_PATHS.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(k)}\b", q):
                return {"action": "open_app", "value": k, "speak": f"Opening {k}."}
        return {"action": "open_app", "value": q, "speak": f"Opening {q}."}

    def _smalltalk(self, t: str) -> str:
        if re.fullmatch(r"(hi|hello|hey|yo|sup|hiya)[!. ]*", t):
            return f"Hello, {USER_NAME}. At your service."
        if "how are you" in t:
            return "All systems nominal. And yourself?"
        if "thank you" in t or t == "thanks":
            return "My pleasure."
        if "your name" in t:
            return f"{ASSISTANT_NAME}. Just A Rather Very Intelligent System."
        if re.fullmatch(r"(goodbye|bye|see you|exit|quit)", t):
            return "Goodbye."
        if "who made you" in t or "who created you" in t:
            return "I was assembled for your PC."
        return ""

    def _llm_think(self, raw: str) -> dict:
        SYSTEM = (
            f"You are {ASSISTANT_NAME}, a concise, witty AI assistant for {USER_NAME}'s PC. "
            "Reply with a single JSON object: "
            '{"action":"open_url|open_app|search_web|youtube|system|chat",'
            '"value":"...","speak":"..."}. No markdown.'
        )
        self.history.append({"role": "user", "content": raw})
        resp = self._llm.messages.create(
            model=MODEL, max_tokens=300, system=SYSTEM, messages=self.history[-10:]
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        self.history.append({"role": "assistant", "content": text})
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return {"action": "chat", "value": "", "speak": text}
        try:
            d = json.loads(m.group(0))
            return {"action": d.get("action", "chat"),
                    "value": d.get("value", ""),
                    "speak": d.get("speak", "")}
        except Exception:
            return {"action": "chat", "value": "", "speak": text}

"""Control Cozmo from a web page in Safari -- tap buttons for manual driving,
or flip on "Autonomous AI mode" and let Claude decide what he does next
using his real camera, with a live camera feed either way. Runs a small
local web server directly on your iPhone (via Pythonista/Pyto/a-Shell) on
top of cozmo_control.py's CozmoLink and cozmo_autonomous.py's Claude-vision
loop, using ONLY the Python standard library (http.server, socketserver,
json) -- same zero-dependency approach as every other script in this
folder, nothing to `pip install`.

=====================================================================
SETUP (same as cozmo_control.py, plus two extra files)
=====================================================================
1. Everything from cozmo_control.py's setup: a Python app (Pythonista 3,
   Pyto, or a-Shell), Cozmo awake on his charger, your iPhone's Wi-Fi
   joined to Cozmo's own network.
2. cozmo_control.py AND cozmo_autonomous.py must both be saved as their
   own files in the same folder -- this file imports both.
3. If you want to use "Autonomous AI mode" (the manual buttons and offline
   chat work without it): open cozmo_autonomous.py and paste your
   Anthropic API key into its API_KEY line near the top, or set the
   ANTHROPIC_API_KEY environment variable. See cozmo_autonomous.py's own
   docstring for why this needs a real (paid, pay-as-you-go) API key and
   your iPhone's cellular data turned on.
4. Run this file instead of the others.
5. It prints a URL like http://172.31.1.2:8080/ -- open that in Safari
   (on the same iPhone, or any other device joined to Cozmo's Wi-Fi) to
   get the control page.

No internet is needed for the page itself, or for manual driving/offline
chat -- those are served entirely from your iPhone (Cozmo's Wi-Fi has no
internet access anyway). Autonomous AI mode is the one exception: each
decision it makes is a real call to Claude, which needs cellular data on
(same as cozmo_autonomous.py run standalone).

Keep the Python app open and your screen on while this runs -- iOS
suspends backgrounded apps, which stops the keep-alive ping Cozmo expects
and disconnects him, same as every other script in this folder.
=====================================================================
"""
import base64
import json
import os
import socket
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler

try:
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _THIS_DIR = os.getcwd()
sys.path.insert(0, _THIS_DIR)
from cozmo_control import CozmoLink, ROBOT_ADDR, think
import cozmo_autonomous as ca

HOST = "0.0.0.0"
PORT = 8080

link = None
_camera_stop = False
_latest_jpeg = None
_latest_jpeg_lock = threading.Lock()

# ---- Autonomous AI mode -- same Claude-vision loop as cozmo_autonomous.py,
# started/stopped from the web page instead of running as its own script.
_ai_thread = None
_ai_stop_event = threading.Event()
_ai_running = False
_ai_log = []
_ai_log_lock = threading.Lock()


def _ai_log_line(text):
    with _ai_log_lock:
        _ai_log.append(text)
        del _ai_log[:-40]


def _local_ip():
    """The iPhone's own IP on Cozmo's Wi-Fi, so the printed URL is one you
    can actually open -- found by asking the OS which local address it'd
    use to reach Cozmo (no packets sent, just a routing-table lookup, so
    this works with no internet access)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(ROBOT_ADDR)
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def _camera_loop():
    global _latest_jpeg
    while not _camera_stop:
        jpeg = link.capture_image(timeout=2.0)
        if jpeg:
            with _latest_jpeg_lock:
                _latest_jpeg = jpeg


def _ai_loop():
    global _ai_running
    _ai_running = True
    _ai_log_line("Autonomous AI mode started -- Cozmo is now deciding for himself.")
    while not _ai_stop_event.is_set():
        try:
            jpeg = link.capture_image(timeout=3.0)
            content = []
            if jpeg:
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg",
                               "data": base64.b64encode(jpeg).decode("ascii")},
                })
                content.append({"type": "text", "text": "This is what you see right now. What do you do?"})
            else:
                content.append({"type": "text", "text":
                                 "Your camera frame didn't arrive in time this turn. What do you do?"})

            response = ca.call_claude([{"role": "user", "content": content}])
            thought = None
            action_desc = None
            for block in response.get("content", []):
                if block.get("type") == "text" and block["text"].strip():
                    thought = block["text"].strip()
                elif block.get("type") == "tool_use":
                    action_desc = ca.run_tool(link, block["name"], block.get("input", {}))
            _ai_log_line(" -- ".join(x for x in (action_desc, thought) if x) or "(no action)")
        except RuntimeError as e:
            _ai_log_line(str(e))
        _ai_stop_event.wait(ca.TICK_SECONDS)
    _ai_running = False
    _ai_log_line("Autonomous AI mode stopped.")


def _ai_start():
    global _ai_thread
    if _ai_running:
        return "Autonomous AI mode is already running."
    if not ca.API_KEY or ca.API_KEY == "PASTE_YOUR_KEY_HERE":
        raise ValueError(
            "No Anthropic API key set -- edit cozmo_autonomous.py's API_KEY "
            "near the top (get one at https://console.anthropic.com), or set "
            "the ANTHROPIC_API_KEY environment variable.")
    _ai_stop_event.clear()
    _ai_thread = threading.Thread(target=_ai_loop, daemon=True)
    _ai_thread.start()
    return "Starting autonomous AI mode..."


def _ai_stop():
    if not _ai_running:
        return "Autonomous AI mode isn't running."
    _ai_stop_event.set()
    return "Stopping autonomous AI mode..."


def _dispatch(path, data):
    """Runs one API action against the connected Cozmo and returns a reply
    string. Raises KeyError/ValueError on bad input -- the handler below
    turns that into a 400 response."""
    if path == "/api/ai/start":
        return _ai_start()
    if path == "/api/ai/stop":
        return _ai_stop()
    if path == "/api/drive":
        link.drive(data["direction"])
        return f"Driving {data['direction']}."
    if path == "/api/turn":
        link.turn(data["direction"])
        return f"Turning {data['direction']}."
    if path == "/api/stop":
        link.stop()
        return "Stopped."
    if path == "/api/head":
        link.head(data["direction"])
        return f"Looking {data['direction']}."
    if path == "/api/lift":
        link.lift(data["direction"])
        return f"Lift {data['direction']}."
    if path == "/api/lights":
        link.lights(data["color"])
        return f"Lights -> {data['color']}."
    if path == "/api/chat":
        return think(link, data.get("text", "")) or "..."
    raise ValueError("Unknown endpoint: " + path)


class Handler(BaseHTTPRequestHandler):
    def _send_bytes(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, status=200):
        self._send_bytes(json.dumps(obj).encode("utf-8"), "application/json", status)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_bytes(PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/ai/log":
            with _ai_log_lock:
                lines = list(_ai_log)
            self._send_json({"ok": True, "running": _ai_running, "lines": lines})
        elif path == "/api/camera":
            with _latest_jpeg_lock:
                jpeg = _latest_jpeg
            if jpeg:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg)
            else:
                self._send_json({"ok": False, "error": "no frame yet"}, status=503)
        else:
            self._send_json({"ok": False, "error": "not found"}, status=404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if not path.startswith("/api/"):
            self._send_json({"ok": False, "error": "not found"}, status=404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"ok": False, "error": "bad JSON"}, status=400)
            return
        try:
            reply = _dispatch(path, data)
        except (KeyError, ValueError) as e:
            self._send_json({"ok": False, "error": str(e)}, status=400)
            return
        self._send_json({"ok": True, "reply": reply})

    def log_message(self, fmt, *args):
        pass  # keep the on-device console readable -- comment out to debug


class _Server(socketserver.ThreadingTCPServer):
    # Must be a class attribute, not set on the instance after construction
    # -- ThreadingTCPServer.__init__ binds the socket immediately, so
    # setting this afterward is too late to have any effect. Without it, a
    # restart right after stopping the script fails with "Address already
    # in use" until the OS lets go of the port on its own (can take a
    # minute or two).
    allow_reuse_address = True


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cozmo</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 16px; padding-bottom: 40px;
    background: #14161a; color: #e8e8ea;
    font: 16px -apple-system, system-ui, sans-serif;
  }
  h1 { font-size: 20px; margin: 0 0 12px; text-align: center; }
  #cam {
    display: block; width: 100%; max-width: 480px; aspect-ratio: 4/3;
    margin: 0 auto 14px; border-radius: 12px; background: #000;
    object-fit: contain; border: 1px solid #333;
  }
  #status {
    text-align: center; min-height: 20px; margin-bottom: 16px;
    color: #9fd6a0; font-size: 14px;
  }
  .panel {
    max-width: 480px; margin: 0 auto 18px;
    display: grid; gap: 8px;
  }
  .row { display: grid; gap: 8px; grid-auto-flow: column; grid-auto-columns: 1fr; }
  button {
    padding: 14px 8px; font-size: 15px; font-weight: 600;
    border: none; border-radius: 10px; background: #2a2d34; color: #e8e8ea;
    -webkit-tap-highlight-color: transparent;
  }
  button:active { background: #3a3f48; }
  #stopBtn { background: #7a2020; }
  #stopBtn:active { background: #9a2828; }
  .swatch { color: #14161a; }
  .swatch[data-color="green"] { background: #3ecf5e; }
  .swatch[data-color="red"] { background: #e8574a; }
  .swatch[data-color="blue"] { background: #4a90e8; }
  .swatch[data-color="white"] { background: #e8e8ea; }
  .swatch[data-color="off"] { background: #555; color: #e8e8ea; }
  .chat { display: flex; gap: 8px; }
  .chat input {
    flex: 1; padding: 12px; border-radius: 10px; border: 1px solid #444;
    background: #1c1f24; color: #e8e8ea; font-size: 15px;
  }
  .chat button { flex: 0 0 auto; padding: 12px 18px; background: #2a5a8a; }
  .label { font-size: 12px; color: #999; text-align: center; margin: -4px 0 2px; }
  #aiBtn { background: #2a5a2a; }
  #aiBtn.running { background: #7a2020; }
  .log {
    height: 90px; overflow-y: auto; padding: 8px 10px; border-radius: 10px;
    background: #1c1f24; border: 1px solid #333; color: #aab; font-size: 12px;
    font-family: ui-monospace, monospace; white-space: pre-wrap;
  }
</style>
</head>
<body>
<h1>Cozmo Control</h1>
<img id="cam" src="/api/camera" alt="Cozmo's camera feed">
<div id="status">Connecting...</div>

<div class="panel">
  <div class="label">Autonomous AI -- Cozmo decides for himself, using his camera and Claude</div>
  <div class="row"><button id="aiBtn" onclick="toggleAi()">Start AI Mode</button></div>
  <div id="aiLog" class="log"></div>
</div>

<div class="panel">
  <div class="label">Drive</div>
  <div class="row"><button onclick="send('/api/drive',{direction:'forward'})">Forward</button></div>
  <div class="row">
    <button onclick="send('/api/turn',{direction:'left'})">Left</button>
    <button id="stopBtn" onclick="send('/api/stop')">STOP</button>
    <button onclick="send('/api/turn',{direction:'right'})">Right</button>
  </div>
  <div class="row"><button onclick="send('/api/drive',{direction:'backward'})">Backward</button></div>
</div>

<div class="panel">
  <div class="label">Head / Lift</div>
  <div class="row">
    <button onclick="send('/api/head',{direction:'up'})">Head Up</button>
    <button onclick="send('/api/head',{direction:'center'})">Head Center</button>
    <button onclick="send('/api/head',{direction:'down'})">Head Down</button>
  </div>
  <div class="row">
    <button onclick="send('/api/lift',{direction:'up'})">Lift Up</button>
    <button onclick="send('/api/lift',{direction:'down'})">Lift Down</button>
  </div>
</div>

<div class="panel">
  <div class="label">Lights</div>
  <div class="row">
    <button class="swatch" data-color="green" onclick="send('/api/lights',{color:'green'})">Green</button>
    <button class="swatch" data-color="red" onclick="send('/api/lights',{color:'red'})">Red</button>
    <button class="swatch" data-color="blue" onclick="send('/api/lights',{color:'blue'})">Blue</button>
    <button class="swatch" data-color="white" onclick="send('/api/lights',{color:'white'})">White</button>
    <button class="swatch" data-color="off" onclick="send('/api/lights',{color:'off'})">Off</button>
  </div>
</div>

<div class="panel">
  <div class="label">Talk to Cozmo (offline chat + free-form move commands)</div>
  <div class="chat">
    <input id="chatInput" type="text" placeholder="e.g. spin, tell me a joke..."
           onkeydown="if(event.key==='Enter')sendChat()">
    <button onclick="sendChat()">Send</button>
  </div>
</div>

<script>
function setStatus(text) { document.getElementById('status').textContent = text; }

async function send(path, body) {
  setStatus('...');
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {})
    });
    const data = await res.json();
    setStatus(data.ok ? data.reply : ('Error: ' + data.error));
  } catch (e) {
    setStatus('Connection error -- is the server still running?');
  }
}

function sendChat() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  send('/api/chat', {text: text});
}

// Poll the camera feed -- simpler and more compatible than an MJPEG stream,
// plenty smooth enough for "see what he sees" at a robot's speed.
setInterval(() => {
  document.getElementById('cam').src = '/api/camera?t=' + Date.now();
}, 1200);

let aiRunning = false;

async function toggleAi() {
  const path = aiRunning ? '/api/ai/stop' : '/api/ai/start';
  try {
    const res = await fetch(path, {method: 'POST'});
    const data = await res.json();
    setStatus(data.ok ? data.reply : ('Error: ' + data.error));
  } catch (e) {
    setStatus('Connection error -- is the server still running?');
  }
  pollAiLog();
}

async function pollAiLog() {
  try {
    const res = await fetch('/api/ai/log');
    const data = await res.json();
    aiRunning = data.running;
    const btn = document.getElementById('aiBtn');
    btn.textContent = aiRunning ? 'Stop AI Mode' : 'Start AI Mode';
    btn.classList.toggle('running', aiRunning);
    const box = document.getElementById('aiLog');
    box.textContent = data.lines.join('\n');
    box.scrollTop = box.scrollHeight;
  } catch (e) {
    // server not reachable this tick -- next poll will retry
  }
}

setInterval(pollAiLog, 3000);
pollAiLog();

setStatus('Ready.');
</script>
</body>
</html>
"""


def main():
    global link, _camera_stop

    print("Connecting to Cozmo...")
    link = CozmoLink()
    if not link.connect(timeout=8.0):
        print("Couldn't connect within 8 seconds.")
        print("Check: is your iPhone's Wi-Fi joined to Cozmo's own network "
              "(not your home Wi-Fi)? Is Cozmo awake (on his charger, lift "
              "raised and lowered once)?")
        return

    threading.Thread(target=_camera_loop, daemon=True).start()

    server = _Server((HOST, PORT), Handler)

    print()
    print("Cozmo is ready! Open this page in Safari:")
    print(f"  http://{_local_ip()}:{PORT}/")
    print("(Works from any device joined to Cozmo's own Wi-Fi, not just this "
          "iPhone -- but keep THIS app open and its screen on, since it's the "
          "one holding the Wi-Fi connection to Cozmo.)")
    print("Press Ctrl+C (or however your Python app stops a running script) "
          "to end this.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _camera_stop = True
        _ai_stop_event.set()
        server.shutdown()
        server.server_close()
        link.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()

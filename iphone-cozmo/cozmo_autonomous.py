"""Autonomous AI-controlled Cozmo -- he acts entirely on his own, on a
timer, using real camera vision. You don't type commands and you don't
chat with him each turn -- you just watch. This is the "AI controls him,
not me talking to him" version.

=====================================================================
REQUIREMENTS (same as cozmo_ai.py)
=====================================================================
1. An Anthropic API key -- https://console.anthropic.com (real,
   pay-as-you-go billing, not free).
2. Your iPhone's cellular data turned on (Cozmo's own Wi-Fi has no
   internet; Claude is reached over cellular while Wi-Fi talks to Cozmo).
3. cozmo_control.py must be in the same folder -- this file imports it.
4. Everything else from cozmo_control.py's setup: Pythonista/Pyto/a-Shell,
   waking Cozmo, joining his Wi-Fi network.

=====================================================================
HOW IT'S DIFFERENT FROM cozmo_ai.py
=====================================================================
cozmo_ai.py waits for you to type something, then Claude responds.
This file never waits for you. Once running, it repeats, forever, on its
own:
  1. Capture a frame from Cozmo's camera.
  2. Send that image to Claude along with what's happened recently.
  3. Claude decides on ONE thing to do (move, turn, look around, change
     his lights) and does it -- or just sits and "thinks" if nothing
     seems worth doing.
  4. Wait a few seconds, then repeat.

Uses raw HTTPS to Claude's Messages API (stdlib `urllib` only), not the
official `anthropic` Python package -- see cozmo_ai.py's docstring for
why (that package needs compiled dependencies no on-device iOS Python
app can install).

Camera images come back as grayscale (not color) -- this keeps frames
small and fast to send over Wi-Fi/cellular. The reconstruction from
Cozmo's on-wire image format to a normal JPEG (in cozmo_control.py) was
checked byte-for-byte against pycozmo's own camera module before being
written -- see tests/test_cozmo_camera.py in this project.

Press Ctrl+C (or however your Python app stops a running script) to end
it -- there's no 'quit' prompt since there's no prompt to type into.
=====================================================================
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # No __file__ -- running inside a notebook-style cell (Jupyter,
    # Carnets, etc.) rather than as a plain script. Fall back to the
    # current working directory, which is where cozmo_control.py should
    # be if it's been saved alongside this file.
    _THIS_DIR = os.getcwd()
sys.path.insert(0, _THIS_DIR)
from cozmo_control import CozmoLink

# ===================================================================
# PASTE YOUR ANTHROPIC API KEY HERE
# ===================================================================
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "PASTE_YOUR_KEY_HERE")

MODEL = "claude-opus-5"
API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# How long to wait between autonomous decisions. Shorter feels livelier,
# but costs more (one Claude call, with an image, per tick).
TICK_SECONDS = 8

SYSTEM_PROMPT = (
    "You are Cozmo, a small, curious, playful robot with a camera for eyes. "
    "Nobody is chatting with you right now -- you decide entirely on your "
    "own what to do next, once every few seconds, based on what you "
    "actually see through your camera. Always call exactly one tool each "
    "turn. Be curious: react to what's in front of you, explore, don't "
    "repeat the same action over and over. You may add one short sentence "
    "about what you're thinking, for a log nobody reads live, so keep it "
    "brief. If the image is blank, dark, or you're facing a wall, that's a "
    "good reason to turn or move rather than staying put."
)

TOOLS = [
    {
        "name": "drive",
        "description": "Drive forward or backward for about 1.5 seconds.",
        "input_schema": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["forward", "backward"]}},
            "required": ["direction"],
        },
    },
    {
        "name": "turn",
        "description": "Turn in place left or right for about 0.8 seconds.",
        "input_schema": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["left", "right"]}},
            "required": ["direction"],
        },
    },
    {
        "name": "look",
        "description": "Tilt your head up, down, or back to center -- changes what your camera sees.",
        "input_schema": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["up", "down", "center"]}},
            "required": ["direction"],
        },
    },
    {
        "name": "lights",
        "description": "Change your backpack light color -- a way to express how you feel about what you see.",
        "input_schema": {
            "type": "object",
            "properties": {"color": {"type": "string", "enum": ["green", "red", "blue", "white", "off"]}},
            "required": ["color"],
        },
    },
    {
        "name": "wait",
        "description": "Do nothing this turn -- stay put and keep watching.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def call_claude(messages):
    payload = {
        "model": MODEL,
        "max_tokens": 512,
        "system": SYSTEM_PROMPT,
        "tools": TOOLS,
        "messages": messages,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, method="POST", headers={
        "content-type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Claude API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Couldn't reach Claude's servers -- is cellular data on? ({e.reason})"
        ) from e


def run_tool(link, name, tool_input):
    if name == "drive":
        link.drive(tool_input["direction"])
        return f"Driving {tool_input['direction']}."
    if name == "turn":
        link.turn(tool_input["direction"])
        return f"Turning {tool_input['direction']}."
    if name == "look":
        link.head(tool_input["direction"])
        return f"Looking {tool_input['direction']}."
    if name == "lights":
        link.lights(tool_input["color"])
        return f"Lights -> {tool_input['color']}."
    if name == "wait":
        return "Just watching."
    return f"Unknown tool: {name}"


def one_tick(link, recent_actions):
    jpeg = link.capture_image(timeout=3.0)
    content = []
    if jpeg:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(jpeg).decode("ascii")},
        })
        content.append({"type": "text", "text": "This is what you see right now. What do you do?"})
    else:
        content.append({"type": "text", "text":
                         "Your camera frame didn't arrive in time this turn. What do you do?"})

    messages = [{"role": "user", "content": content}]
    response = call_claude(messages)
    blocks = response.get("content", [])

    thought = None
    action_desc = None
    for block in blocks:
        if block.get("type") == "text" and block["text"].strip():
            thought = block["text"].strip()
        elif block.get("type") == "tool_use":
            action_desc = run_tool(link, block["name"], block.get("input", {}))

    line = " -- ".join(x for x in (action_desc, thought) if x) or "(no action)"
    print(line)
    recent_actions.append(action_desc or "wait")
    del recent_actions[:-5]


def main():
    if not API_KEY or API_KEY == "PASTE_YOUR_KEY_HERE":
        print("No Anthropic API key set. Edit this file and paste your key "
              "into API_KEY near the top (get one at "
              "https://console.anthropic.com), or set the "
              "ANTHROPIC_API_KEY environment variable.")
        return

    print("Connecting to Cozmo...")
    link = CozmoLink()
    if not link.connect(timeout=8.0):
        print("Couldn't connect within 8 seconds.")
        print("Check: is your iPhone's Wi-Fi joined to Cozmo's own network? "
              "Is Cozmo awake (on his charger, lift raised and lowered once)?")
        return

    print()
    print(f"Cozmo is ready and acting on his own now, checking in every {TICK_SECONDS}s.")
    print("(Needs cellular data ON. Keep this app open and your screen on, "
          "or Cozmo disconnects. Stop the script to end this.)")

    recent_actions = []
    try:
        while True:
            try:
                one_tick(link, recent_actions)
            except RuntimeError as e:
                print(str(e))
            time.sleep(TICK_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        link.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()

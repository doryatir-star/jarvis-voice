"""AI-controlled Cozmo -- Claude itself decides what Cozmo does, instead of
the fixed offline command-matcher in cozmo_control.py. Talk to it naturally;
it decides when to actually move Cozmo (by calling tools) versus just reply.

=====================================================================
REQUIREMENTS
=====================================================================
1. An Anthropic API key -- https://console.anthropic.com
   This is a real account with real pay-as-you-go billing (not a
   subscription) -- typically a fraction of a cent per exchange with the
   default model here, but it is not free. Paste your key into API_KEY
   below, or set it as the ANTHROPIC_API_KEY environment variable.

2. Your iPhone's CELLULAR DATA turned on. Cozmo's own Wi-Fi hotspot (which
   you must be joined to for the robot commands to work) has no internet.
   As long as cellular data is on, iOS automatically sends internet-bound
   traffic (this script's calls to Claude) over cellular while Wi-Fi keeps
   carrying the Cozmo commands -- you don't need to do anything special,
   just make sure cellular data isn't turned off.

3. Everything from cozmo_control.py's setup still applies (Pythonista/Pyto/
   a-Shell, waking Cozmo, joining his Wi-Fi network) -- see that file and
   iphone-cozmo/README.md. This file imports cozmo_control.py, so both
   files need to be in the same folder.

=====================================================================
WHY RAW HTTPS INSTEAD OF THE OFFICIAL `anthropic` PYTHON PACKAGE
=====================================================================
The official SDK depends on compiled (non-pure-Python) packages. On-device
iOS Python apps restrict pip to pure-Python packages only, and iOS itself
forbids apps from loading unsigned native code -- so no on-device Python
interpreter (a-Shell, Pythonista, Pyto) can install the SDK's dependencies,
full stop. This calls the same documented Messages API
(https://docs.claude.com/en/api/messages) directly over `urllib.request`
-- stdlib only, consistent with cozmo_control.py's zero-dependency design.
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cozmo_control import CozmoLink

# ===================================================================
# PASTE YOUR ANTHROPIC API KEY HERE
# ===================================================================
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "PASTE_YOUR_KEY_HERE")

# Anthropic's recommended default. Costs more per exchange than
# "claude-haiku-4-5" -- change it here if you'd rather pay less per turn.
MODEL = "claude-opus-5"

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

SYSTEM_PROMPT = (
    "You are Cozmo, a small, curious, playful robot. You are having a real "
    "spoken conversation with your owner and you can actually move your "
    "physical body using the tools available to you. Use a tool whenever "
    "the user's message calls for movement, looking around, lifting your "
    "arm, or changing your lights -- don't just describe it in words, "
    "actually call the tool. Otherwise, just reply in short, warm, "
    "personality-filled sentences, like a friendly small robot would. You "
    "have no internet access of your own and don't know about anything "
    "that happened after your training -- if asked something you'd need to "
    "look up, say so playfully instead of guessing."
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
        "name": "stop",
        "description": "Immediately stop all movement.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "head",
        "description": "Tilt your head up, down, or back to center.",
        "input_schema": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["up", "down", "center"]}},
            "required": ["direction"],
        },
    },
    {
        "name": "lift",
        "description": "Raise or lower your lift arm.",
        "input_schema": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["up", "down"]}},
            "required": ["direction"],
        },
    },
    {
        "name": "lights",
        "description": "Change your backpack light color.",
        "input_schema": {
            "type": "object",
            "properties": {"color": {"type": "string", "enum": ["green", "red", "blue", "white", "off"]}},
            "required": ["color"],
        },
    },
]


def call_claude(messages):
    """One raw HTTPS call to POST /v1/messages. Returns the parsed JSON body."""
    payload = {
        "model": MODEL,
        "max_tokens": 1024,
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
            "Couldn't reach Claude's servers -- is your iPhone's cellular "
            f"data turned on? ({e.reason})"
        ) from e


def run_tool(link, name, tool_input):
    if name == "drive":
        link.drive(tool_input["direction"])
        return f"Driving {tool_input['direction']}."
    if name == "turn":
        link.turn(tool_input["direction"])
        return f"Turning {tool_input['direction']}."
    if name == "stop":
        link.stop()
        return "Stopped."
    if name == "head":
        link.head(tool_input["direction"])
        return f"Head -> {tool_input['direction']}."
    if name == "lift":
        link.lift(tool_input["direction"])
        return f"Lift -> {tool_input['direction']}."
    if name == "lights":
        link.lights(tool_input["color"])
        return f"Lights -> {tool_input['color']}."
    return f"Unknown tool: {name}"


def think(link, messages, user_text):
    """Appends the user's message, then loops calling Claude and executing
    any tools it asks for, until it replies with plain text (no more tool
    calls). Mutates `messages` in place so the conversation has memory."""
    messages.append({"role": "user", "content": user_text})
    while True:
        response = call_claude(messages)
        content = response.get("content", [])
        messages.append({"role": "assistant", "content": content})

        for block in content:
            if block.get("type") == "text" and block["text"].strip():
                print(block["text"])

        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if not tool_uses:
            return

        tool_results = []
        for tu in tool_uses:
            result_text = run_tool(link, tu["name"], tu.get("input", {}))
            print(f"[{tu['name']}] {result_text}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu["id"],
                "content": result_text,
            })
        messages.append({"role": "user", "content": tool_results})


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
    print("Cozmo is ready, and Claude is his brain now -- just talk naturally.")
    print("(Needs cellular data ON -- Cozmo's Wi-Fi has no internet, so "
          "Claude is reached over cellular instead. Keep this app open and "
          "your screen on, or Cozmo disconnects.)")
    print("Type 'quit' to exit.")

    messages = []
    try:
        while True:
            try:
                text = input("> ")
            except EOFError:
                break
            if text.strip().lower() in ("quit", "exit"):
                break
            try:
                think(link, messages, text)
            except RuntimeError as e:
                print(str(e))
    finally:
        link.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()

"""Tests for Cozmo's brain -- the Ollama path especially, since that's the
one that works with no API key and no internet. A stand-in Ollama runs on
a spare port, so these need neither Ollama installed nor a network."""
import json
import os
import socketserver
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "iphone-cozmo"))

import cozmo_all_in_one as app


class FakeLink:
    def __init__(self):
        self.did = []

    def drive(self, d): self.did.append(("drive", d))
    def turn(self, d): self.did.append(("turn", d))
    def head(self, d): self.did.append(("head", d))
    def lift(self, d): self.did.append(("lift", d))
    def lights(self, c): self.did.append(("lights", c))
    def show_face(self, **kwargs): pass
    def capture_image(self, timeout=3.0): return None


class _FakeOllama(BaseHTTPRequestHandler):
    installed = [{"name": "llama3.2:latest"}]
    reply = {"say": "Hello!", "mood": "happy", "move": "none"}
    last_request = None

    def log_message(self, *args):
        pass

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            self._json({"models": _FakeOllama.installed})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        _FakeOllama.last_request = json.loads(self.rfile.read(length))
        self._json({"message": {"role": "assistant",
                                "content": json.dumps(_FakeOllama.reply)}})


class OllamaTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _FakeOllama)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.link = FakeLink()
        app.link = self.link
        app.OLLAMA_URL = f"http://127.0.0.1:{self.port}"
        app.OLLAMA_MODEL = ""
        app.API_KEY = ""                      # the whole point: no key
        _FakeOllama.installed = [{"name": "llama3.2:latest"}]
        _FakeOllama.reply = {"say": "Hello!", "mood": "happy", "move": "none"}
        _FakeOllama.last_request = None
        app._conversation.clear()
        app.set_mood("neutral")


class TestModelDiscovery(OllamaTestCase):
    def test_lists_installed_models(self):
        self.assertEqual(app.ollama_models(), ["llama3.2:latest"])

    def test_prefers_a_model_that_can_see(self):
        # A camera is useless to a text-only model, so when both are
        # installed the one that understands pictures should win.
        _FakeOllama.installed = [{"name": "llama3.2:latest"}, {"name": "llava:7b"}]
        self.assertEqual(app.pick_ollama_model(), "llava:7b")

    def test_falls_back_to_whatever_is_installed(self):
        self.assertEqual(app.pick_ollama_model(), "llama3.2:latest")

    def test_an_explicit_model_choice_wins(self):
        app.OLLAMA_MODEL = "mistral"
        self.assertEqual(app.pick_ollama_model(), "mistral")

    def test_no_models_means_no_brain(self):
        _FakeOllama.installed = []
        self.assertEqual(app.pick_ollama_model(), "")
        self.assertEqual(app.brain_name(), "")

    def test_reports_ollama_as_the_brain_when_no_api_key_is_set(self):
        self.assertEqual(app.brain_name(), "ollama:llama3.2:latest")

    def test_vision_models_are_recognised(self):
        for name in ("llava:7b", "moondream", "llama3.2-vision:11b", "gemma3:4b"):
            self.assertTrue(app.model_can_see(name), name)
        for name in ("llama3.2:latest", "mistral", "phi3"):
            self.assertFalse(app.model_can_see(name), name)


class TestThinking(OllamaTestCase):
    def test_reply_drives_speech_face_and_body_together(self):
        _FakeOllama.reply = {"say": "Ooh!", "mood": "excited", "move": "lights_green"}
        say, action = app.talk_to_cozmo("Hi!")
        self.assertEqual(say, "Ooh!")
        self.assertEqual(app.current_mood(), "excited")
        self.assertEqual(self.link.did, [("lights", "green")])
        self.assertIn("green", action)

    def test_asks_ollama_to_enforce_json(self):
        app.talk_to_cozmo("Hi!")
        self.assertEqual(_FakeOllama.last_request.get("format"), "json")

    def test_sends_the_camera_frame_to_a_model_that_can_see(self):
        _FakeOllama.installed = [{"name": "llava:7b"}]
        app._latest_jpeg = b"\xff\xd8frame\xff\xd9"
        try:
            app.talk_to_cozmo("What is this?")
        finally:
            app._latest_jpeg = None
        self.assertIn("images", _FakeOllama.last_request["messages"][-1])

    def test_does_not_send_pictures_to_a_text_only_model(self):
        # llama3.2 can't read images, and sending them anyway just bloats
        # the request for nothing.
        app._latest_jpeg = b"\xff\xd8frame\xff\xd9"
        try:
            app.talk_to_cozmo("What is this?")
        finally:
            app._latest_jpeg = None
        self.assertNotIn("images", _FakeOllama.last_request["messages"][-1])

    def test_remembers_the_conversation_across_turns(self):
        app.talk_to_cozmo("My name is Sam.")
        app.talk_to_cozmo("What is my name?")
        roles = [m["role"] for m in _FakeOllama.last_request["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        self.assertIn("Sam", _FakeOllama.last_request["messages"][1]["content"])

    def test_memory_is_capped_so_requests_cannot_grow_forever(self):
        for i in range(20):
            app.talk_to_cozmo(f"message {i}")
        self.assertLessEqual(len(app._conversation), app.MEMORY_TURNS)

    def test_a_nonsense_mood_falls_back_instead_of_crashing(self):
        _FakeOllama.reply = {"say": "Hi", "mood": "bananas", "move": "none"}
        app.talk_to_cozmo("Hi")
        self.assertEqual(app.current_mood(), "neutral")

    def test_a_nonsense_move_is_ignored_instead_of_crashing(self):
        _FakeOllama.reply = {"say": "Hi", "mood": "happy", "move": "backflip"}
        say, action = app.talk_to_cozmo("Hi")
        self.assertEqual(say, "Hi")
        self.assertIsNone(action)
        self.assertEqual(self.link.did, [])

    def test_an_empty_reply_still_says_something(self):
        _FakeOllama.reply = {"say": "", "mood": "happy", "move": "none"}
        say, _ = app.talk_to_cozmo("Hi")
        self.assertTrue(say)

    def test_ollama_being_down_explains_how_to_fix_it(self):
        app.OLLAMA_URL = "http://127.0.0.1:1"      # nothing listening
        with self.assertRaises(RuntimeError) as caught:
            app.talk_to_cozmo("Hi")
        self.assertIn("ollama.com", str(caught.exception).lower())

    def test_no_brain_at_all_explains_how_to_get_one(self):
        _FakeOllama.installed = []
        with self.assertRaises(RuntimeError) as caught:
            app.talk_to_cozmo("Hi")
        self.assertIn("ollama", str(caught.exception).lower())


class TestMoves(OllamaTestCase):
    def test_every_advertised_move_actually_does_something(self):
        # The move names are listed to the model in JSON_RULES, so any one
        # of them that quietly did nothing would be a promise unkept.
        for move in app.MOVES:
            self.link.did.clear()
            result = app.apply_move(self.link, move)
            if move == "none":
                self.assertIsNone(result)
                self.assertEqual(self.link.did, [])
            else:
                self.assertTrue(result, f"{move} returned nothing")
                self.assertEqual(len(self.link.did), 1, f"{move} moved nothing")

    def test_the_moves_offered_to_the_model_match_the_ones_implemented(self):
        for move in app.MOVES:
            self.assertIn(move, app.JSON_RULES)


if __name__ == "__main__":
    unittest.main()

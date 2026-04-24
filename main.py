import re
import sys
from PyQt5 import QtCore, QtWidgets

from config import ASSISTANT_NAME, USER_NAME
from ui import JarvisWindow
from voice import Voice, list_input_devices
from brain import Brain
import commands
commands.build_app_index()


# Wake words (including common mishearings from Google's speech API)
WAKE_WORDS = (
    "jarvis", "hey jarvis", "ok jarvis", "okay jarvis",
    "service", "travis", "charles", "jervis", "jarvice", "jarvi",
    "parvis", "garvis", "harvey", "carvis", "jar is", "drive us",
)
# Only use the longer phrases first so "hey jarvis" strips both words
WAKE_WORDS = tuple(sorted(set(WAKE_WORDS), key=len, reverse=True))


def _strip_wake(text: str):
    """Return (command_text, wake_matched)."""
    t = text.strip().lower().lstrip(",. ")
    for w in WAKE_WORDS:
        if t == w:
            return "", True
        if t.startswith(w + " ") or t.startswith(w + ",") or t.startswith(w + "."):
            return t[len(w):].lstrip(" ,.!?"), True
    return text, False


class JarvisSignals(QtCore.QObject):
    user_said = QtCore.pyqtSignal(str)
    jarvis_said = QtCore.pyqtSignal(str)
    status = QtCore.pyqtSignal(str)
    level = QtCore.pyqtSignal(float)


class Jarvis:
    """Voice-only, always-listening assistant."""

    def __init__(self, win: JarvisWindow):
        self.win = win
        self.sig = JarvisSignals()
        self.brain = Brain()
        self.voice = Voice(
            on_heard=self._heard,
            on_status=lambda s: self.sig.status.emit(s),
            on_error=lambda m: self.sig.jarvis_said.emit(m),
            on_level=lambda v: self.sig.level.emit(v),
        )

        self.sig.user_said.connect(self.win.append_user)
        self.sig.jarvis_said.connect(self.win.append_jarvis)
        self.sig.status.connect(self.win.set_status)
        self.sig.level.connect(self.win.set_mic_level)
        self.win.mic_btn.toggled.connect(self._mic_toggled)
        self.win.device_changed.connect(self._on_device_change)

        # Populate device picker
        devices = list_input_devices()
        self.win.populate_devices(devices, self.voice._device_index)

        self.sig.status.emit("listening")
        self.voice.start()
        greeting = (f"Online, {USER_NAME}. Start any command with 'Jarvis' and I'll respond.")
        self.sig.jarvis_said.emit(greeting)
        self.voice.say(greeting)

    def _mic_toggled(self, on):
        self.voice.enabled = on
        self.sig.status.emit("listening" if on else "idle")
        self.sig.jarvis_said.emit("Microphone active." if on else "Microphone muted.")

    def _on_device_change(self, idx: int):
        self.sig.jarvis_said.emit(f"Switching to microphone #{idx}.")
        self.voice.set_device(idx)

    def _heard(self, text: str):
        text = (text or "").strip()
        if not text or len(text) < 3:
            return
        command, matched = _strip_wake(text)
        if not matched:
            # Mic is working, just not addressed to Jarvis — show dimmed.
            self.sig.user_said.emit(f"[ignored] {text}")
            return
        if not command:
            self.sig.user_said.emit(text)
            self.voice.say("Yes?")
            return
        self._process(command)

    def _process(self, text: str):
        self.sig.user_said.emit(text)
        self.sig.status.emit("thinking")
        try:
            decision = self.brain.think(text)
        except Exception as e:
            decision = {"action": "chat", "value": "", "speak": f"Processing error: {e}"}
        action = decision.get("action", "chat")
        value = decision.get("value", "")
        speak = decision.get("speak", "")

        if action and action != "chat":
            r = commands.execute(action, value)
            if r and not speak:
                speak = r

        if not speak:
            speak = "Done."

        self.sig.jarvis_said.emit(speak)
        self.sig.status.emit("speaking")
        self.voice.say(speak)
        QtCore.QTimer.singleShot(1500, lambda: self.sig.status.emit(
            "listening" if self.voice.enabled else "idle"))


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = JarvisWindow()
    win.show()
    _ = Jarvis(win)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

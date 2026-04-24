import os
import audioop
import queue
import tempfile
import threading
import time
import traceback

import pyttsx3
import speech_recognition as sr


LOG_PATH = os.path.join(tempfile.gettempdir(), "jarvis_voice.log")


def _log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except Exception:
        pass


# Words we never want to treat as devices (virtual / output / duplicates)
_BLOCKLIST_HINTS = (
    "sound mapper", "stereo mix", "speakers", "output", "digital output",
    "line out", "spdif", "hdmi", "display audio",
    # virtual / routing devices that often have no real audio
    "steam streaming", "steam virtual", "nvidia high", "nvidia broadcast",
    "obs virtual", "voicemeeter", "vb-audio", "vb cable", "discord virtual",
)


def list_input_devices() -> list[tuple[int, str]]:
    """Return [(device_index, name)] of real input devices."""
    names = sr.Microphone.list_microphone_names()
    result = []
    for i, n in enumerate(names):
        nl = n.lower()
        if any(b in nl for b in _BLOCKLIST_HINTS):
            continue
        if not n.strip():
            continue
        result.append((i, n))
    return result


def pick_default_device() -> int | None:
    """Pick the most likely real microphone (letting PortAudio default win is best)."""
    # Returning None lets speech_recognition use the Windows default input,
    # which respects the user's Windows → Sound settings. Most reliable.
    return None


class Voice:
    def __init__(self, on_heard, on_status=None, on_error=None, on_level=None):
        self.on_heard = on_heard
        self.on_status = on_status or (lambda s: None)
        self.on_error = on_error or (lambda s: None)
        self.on_level = on_level or (lambda v: None)  # 0.0..1.0 audio level
        self.enabled = True
        self._stop = False
        self._speaking = False
        self._mute_until = 0.0
        self._tts_queue: "queue.Queue[str]" = queue.Queue()
        self._device_index = None
        self._last_heard_at = 0.0
        self._warned_silent = False

        try:
            self.recognizer = sr.Recognizer()
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.7
            self.recognizer.energy_threshold = 200
            _log("recognizer ok")
        except Exception:
            _log("recognizer init failed:\n" + traceback.format_exc())
            raise

        self.mic = None
        self._mic_lock = threading.Lock()
        self._device_changed = threading.Event()
        self._init_mic(pick_default_device())
        self._init_tts()

    def _init_mic(self, device_index):
        try:
            with self._mic_lock:
                self._device_index = device_index
                self.mic = sr.Microphone(device_index=device_index)
            names = sr.Microphone.list_microphone_names()
            nm = names[device_index] if device_index is not None and device_index < len(names) else "default"
            _log(f"mic index={device_index} name={nm!r}")
        except Exception:
            _log("mic init failed:\n" + traceback.format_exc())
            with self._mic_lock:
                self.mic = None
            self.on_error("Microphone init failed. Check Windows mic settings.")

    def set_device(self, device_index):
        """Swap the mic device safely — just signal the listener to reload."""
        if device_index == self._device_index:
            return
        self._init_mic(device_index)
        self._device_changed.set()  # listen loop will exit any `with` block and rebind

    def _init_tts(self):
        try:
            self.engine = pyttsx3.init("sapi5")
            self.engine.setProperty("rate", 185)
            self.engine.setProperty("volume", 1.0)
            for v in self.engine.getProperty("voices"):
                nm = (v.name or "").lower()
                if "david" in nm or "mark" in nm or "male" in nm:
                    self.engine.setProperty("voice", v.id); break
            _log("tts ok")
        except Exception:
            _log("tts init failed:\n" + traceback.format_exc())
            self.engine = None

    def start(self):
        if self.mic is not None:
            self._calibrate()
        threading.Thread(target=self._listen_loop, daemon=True).start()
        threading.Thread(target=self._silence_watchdog, daemon=True).start()
        threading.Thread(target=self._speak_loop, daemon=True).start()

    def _calibrate(self):
        try:
            with self._mic_lock:
                mic = self.mic
            if mic is None:
                return
            with mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
            _log(f"ambient energy_threshold={self.recognizer.energy_threshold:.0f}")
        except Exception:
            _log("ambient calibration failed:\n" + traceback.format_exc())

    def stop(self):
        self._stop = True
        self._tts_queue.put(None)

    def say(self, text: str):
        if text:
            self._tts_queue.put(text)

    def _speak_loop(self):
        while not self._stop:
            text = self._tts_queue.get()
            if text is None: break
            self._speaking = True
            try:
                if self.engine is not None:
                    self.engine.say(text)
                    self.engine.runAndWait()
            except Exception:
                _log("speak failed:\n" + traceback.format_exc())
            finally:
                self._speaking = False
                self._mute_until = time.monotonic() + 1.5

    def _silence_watchdog(self):
        """If the listener never captures a phrase in 30s, tell the user."""
        start = time.monotonic()
        while not self._stop and not self._warned_silent:
            time.sleep(2)
            if self._last_heard_at > 0:
                return
            if time.monotonic() - start > 30:
                self._warned_silent = True
                _log("silence watchdog tripped — no audio in 15s")
                self.on_error(
                    "I can't hear anything from the microphone. "
                    "Open Windows Settings → Privacy & security → Microphone, "
                    "turn ON 'Let desktop apps access your microphone', "
                    "then use the dropdown in my window to pick a different mic."
                )
                return

    def _listen_loop(self):
        while not self._stop:
            if self._device_changed.is_set():
                self._device_changed.clear()
                self._calibrate()
            if not self.enabled or self._speaking:
                self.on_level(0.0); time.sleep(0.1); continue
            with self._mic_lock:
                mic = self.mic
            if mic is None:
                time.sleep(0.3); continue
            try:
                with mic as source:
                    self.on_level(0.15)
                    audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=6)
            except AssertionError:
                time.sleep(0.1); continue
            except OSError as e:
                _log(f"mic OS error: {e}")
                self.on_error("Microphone error.")
                time.sleep(1); continue
            except Exception:
                _log("listen loop error:\n" + traceback.format_exc())
                time.sleep(0.5); continue

            try:
                rms = audioop.rms(audio.frame_data, audio.sample_width)
                self.on_level(min(1.0, rms / 3000.0))
                self._last_heard_at = time.monotonic()
            except Exception:
                pass

            try:
                text = self.recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                text = ""
            except sr.RequestError as e:
                _log(f"google api error: {e}")
                self.on_error("Speech service unreachable. Check internet.")
                text = ""; time.sleep(2)
            except Exception:
                _log("recognize error:\n" + traceback.format_exc())
                text = ""

            if text:
                if self._speaking or time.monotonic() < self._mute_until:
                    _log(f"(ignored echo) {text}")
                else:
                    _log(f"heard: {text}")
                    self.on_heard(text)

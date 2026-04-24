import math
import sys
from PyQt5 import QtCore, QtGui, QtWidgets


ACCENT = QtGui.QColor(0, 225, 255)
ACCENT_DIM = QtGui.QColor(0, 140, 170)
WARN = QtGui.QColor(255, 140, 0)
BG = QtGui.QColor(5, 10, 18)
TEXT = QtGui.QColor(200, 240, 255)


class ReactorCore(QtWidgets.QWidget):
    """Animated arc-reactor HUD core. Pulses when speaking or listening."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 420)
        self._phase = 0.0
        self._level = 0.0
        self._target_level = 0.0
        self._mode = "idle"  # idle | listening | thinking | speaking
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_mode(self, mode: str):
        self._mode = mode
        self._target_level = {"idle": 0.25, "listening": 0.75, "thinking": 0.55, "speaking": 1.0}.get(mode, 0.3)

    def _tick(self):
        self._phase += 0.05
        self._level += (self._target_level - self._level) * 0.08
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.42

        color = ACCENT if self._mode != "thinking" else WARN

        # Outer rotating rings
        for i, (rf, width, speed, dash) in enumerate([
            (1.00, 2, 0.6, [2, 8]),
            (0.88, 1, -0.9, [1, 4]),
            (0.74, 3, 0.4, [10, 6]),
        ]):
            pen = QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 180))
            pen.setWidth(width)
            pen.setDashPattern(dash)
            pen.setDashOffset(self._phase * 20 * speed)
            p.setPen(pen)
            p.setBrush(QtCore.Qt.NoBrush)
            rr = r * rf
            p.drawEllipse(QtCore.QPointF(cx, cy), rr, rr)

        # Tick marks
        p.setPen(QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 120), 1))
        for a in range(0, 360, 6):
            rad = math.radians(a + self._phase * 10)
            r1 = r * 0.95
            r2 = r * (1.02 if a % 30 == 0 else 0.99)
            p.drawLine(
                QtCore.QPointF(cx + math.cos(rad) * r1, cy + math.sin(rad) * r1),
                QtCore.QPointF(cx + math.cos(rad) * r2, cy + math.sin(rad) * r2),
            )

        # Pulsing glow
        glow_r = r * (0.42 + 0.08 * math.sin(self._phase * 2))
        grad = QtGui.QRadialGradient(cx, cy, glow_r * 2.2)
        grad.setColorAt(0.0, QtGui.QColor(color.red(), color.green(), color.blue(), int(200 * self._level)))
        grad.setColorAt(0.4, QtGui.QColor(color.red(), color.green(), color.blue(), int(80 * self._level)))
        grad.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        p.setBrush(QtGui.QBrush(grad))
        p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(QtCore.QPointF(cx, cy), glow_r * 2.2, glow_r * 2.2)

        # Inner core
        core_r = r * (0.20 + 0.04 * math.sin(self._phase * 3))
        core_grad = QtGui.QRadialGradient(cx, cy, core_r)
        core_grad.setColorAt(0.0, QtGui.QColor(240, 255, 255))
        core_grad.setColorAt(0.5, QtGui.QColor(color.red(), color.green(), color.blue(), 220))
        core_grad.setColorAt(1.0, QtGui.QColor(color.red(), color.green(), color.blue(), 40))
        p.setBrush(QtGui.QBrush(core_grad))
        p.drawEllipse(QtCore.QPointF(cx, cy), core_r, core_r)

        # Triangular reactor blades
        p.setPen(QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 230), 2))
        for k in range(6):
            a = math.radians(k * 60 + self._phase * 5)
            r_in, r_out = r * 0.28, r * 0.55
            p1 = QtCore.QPointF(cx + math.cos(a) * r_in, cy + math.sin(a) * r_in)
            p2 = QtCore.QPointF(cx + math.cos(a + 0.35) * r_out, cy + math.sin(a + 0.35) * r_out)
            p3 = QtCore.QPointF(cx + math.cos(a - 0.35) * r_out, cy + math.sin(a - 0.35) * r_out)
            path = QtGui.QPainterPath(p1)
            path.lineTo(p2); path.lineTo(p3); path.closeSubpath()
            p.fillPath(path, QtGui.QColor(color.red(), color.green(), color.blue(), 60))
            p.drawPath(path)


class Waveform(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._phase = 0.0
        self._amp = 0.1
        self._target = 0.1
        t = QtCore.QTimer(self); t.timeout.connect(self._tick); t.start(30)

    def set_amp(self, a):
        self._target = a

    def _tick(self):
        self._phase += 0.2
        self._amp += (self._target - self._amp) * 0.1
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height(); mid = h / 2
        pen = QtGui.QPen(ACCENT, 2); p.setPen(pen)
        pts = []
        for x in range(0, w, 3):
            y = mid + math.sin(x * 0.04 + self._phase) * mid * 0.9 * self._amp \
                    + math.sin(x * 0.11 + self._phase * 1.4) * mid * 0.4 * self._amp
            pts.append(QtCore.QPointF(x, y))
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])


class LevelBar(QtWidgets.QWidget):
    """Horizontal audio level meter — shows if the mic is actually picking up sound."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self._level = 0.0; self._peak = 0.0
        t = QtCore.QTimer(self); t.timeout.connect(self._tick); t.start(40)

    def set_level(self, v: float):
        self._level = max(0.0, min(1.0, v))
        if self._level > self._peak:
            self._peak = self._level

    def _tick(self):
        self._peak *= 0.92
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QtGui.QColor(0, 20, 32))
        p.setPen(QtGui.QPen(QtGui.QColor(0, 81, 106), 1))
        p.drawRect(0, 0, w - 1, h - 1)
        lw = int(w * self._level)
        grad = QtGui.QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QtGui.QColor(0, 225, 255))
        grad.setColorAt(0.7, QtGui.QColor(0, 225, 180))
        grad.setColorAt(1.0, QtGui.QColor(255, 140, 0))
        p.fillRect(1, 1, lw - 2, h - 2, QtGui.QBrush(grad))
        px = int(w * self._peak)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 200), 2))
        p.drawLine(px, 1, px, h - 2)


class JarvisWindow(QtWidgets.QWidget):
    user_input = QtCore.pyqtSignal(str)
    device_changed = QtCore.pyqtSignal(int)  # mic device index
    mic_test_requested = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S.")
        self.setMinimumSize(980, 680)
        self.setStyleSheet(self._qss())

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24); root.setSpacing(20)

        left = QtWidgets.QVBoxLayout(); left.setSpacing(10)
        self.reactor = ReactorCore()
        self.status = QtWidgets.QLabel("STANDBY")
        self.status.setAlignment(QtCore.Qt.AlignCenter)
        self.status.setObjectName("status")
        self.wave = Waveform()
        left.addWidget(self.reactor, 1)
        left.addWidget(self.status)
        left.addWidget(self.wave)
        root.addLayout(left, 1)

        right = QtWidgets.QVBoxLayout(); right.setSpacing(8)
        title = QtWidgets.QLabel("J · A · R · V · I · S")
        title.setObjectName("title")
        subtitle = QtWidgets.QLabel("Voice command interface — always listening")
        subtitle.setObjectName("subtitle")

        # Device picker row
        dev_row = QtWidgets.QHBoxLayout()
        dev_label = QtWidgets.QLabel("MIC:"); dev_label.setObjectName("devlabel")
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setObjectName("device")
        self.device_combo.currentIndexChanged.connect(self._on_device_change)
        dev_row.addWidget(dev_label); dev_row.addWidget(self.device_combo, 1)

        # Level meter
        meter_row = QtWidgets.QHBoxLayout()
        meter_label = QtWidgets.QLabel("LVL:"); meter_label.setObjectName("devlabel")
        self.level = LevelBar()
        meter_row.addWidget(meter_label); meter_row.addWidget(self.level, 1)

        self.transcript = QtWidgets.QTextEdit(); self.transcript.setReadOnly(True)
        self.transcript.setObjectName("transcript")

        btn_row = QtWidgets.QHBoxLayout()
        self.mic_btn = QtWidgets.QPushButton("🎙  MIC ON")
        self.mic_btn.setCheckable(True); self.mic_btn.setChecked(True)
        self.mic_btn.toggled.connect(
            lambda on: self.mic_btn.setText("🎙  MIC ON" if on else "🔇  MIC OFF"))
        btn_row.addStretch(1); btn_row.addWidget(self.mic_btn); btn_row.addStretch(1)

        right.addWidget(title); right.addWidget(subtitle)
        right.addLayout(dev_row)
        right.addLayout(meter_row)
        right.addWidget(self.transcript, 1)
        right.addLayout(btn_row)
        root.addLayout(right, 1)

    def populate_devices(self, devices: list, current_index: int | None):
        """devices: list of (index, name)"""
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for idx, name in devices:
            self.device_combo.addItem(f"{idx}: {name}", idx)
        if current_index is not None:
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == current_index:
                    self.device_combo.setCurrentIndex(i); break
        self.device_combo.blockSignals(False)

    def _on_device_change(self, row: int):
        idx = self.device_combo.itemData(row)
        if idx is not None:
            self.device_changed.emit(int(idx))

    def set_mic_level(self, v: float):
        self.level.set_level(v)
        # also modulate the waveform so users see activity
        self.wave.set_amp(max(0.12, v))

    # user_input signal kept for backward-compat; no longer fired from UI
    def _submit(self):
        pass

    # user_input signal kept for backward-compat; no longer fired from UI
    def _submit(self):
        pass

    # Slots called from worker thread via signals
    def append_user(self, text):
        if text.startswith("[ignored]"):
            body = text[len("[ignored]"):].strip()
            self.transcript.append(f'<span style="color:#456674">· {body}</span>')
        else:
            self.transcript.append(f'<span style="color:#7fe7ff">&gt; {text}</span>')

    def append_jarvis(self, text):
        self.transcript.append(f'<span style="color:#c8f0ff"><b>JARVIS:</b> {text}</span><br>')

    def set_status(self, mode: str):
        self.reactor.set_mode(mode)
        labels = {"idle": "STANDBY", "listening": "LISTENING…",
                  "thinking": "COGITATING…", "speaking": "SPEAKING…"}
        self.status.setText(labels.get(mode, mode.upper()))
        self.wave.set_amp({"idle": 0.08, "listening": 0.9, "thinking": 0.4, "speaking": 1.0}.get(mode, 0.1))

    def _qss(self):
        return """
        QWidget { background: #05090f; color: #c8f0ff; font-family: 'Consolas','Segoe UI',monospace; }
        QLabel#title { font-size: 34px; font-weight: 700; letter-spacing: 8px; color: #00e1ff; }
        QLabel#subtitle { font-size: 11px; letter-spacing: 4px; color: #5bb6c8; margin-bottom: 8px; }
        QLabel#status { font-size: 14px; letter-spacing: 6px; color: #00e1ff; padding: 6px; border: 1px solid #00516a; border-radius: 4px; background: rgba(0,40,60,120); }
        QTextEdit#transcript { background: rgba(0,20,32,180); border: 1px solid #00516a; border-radius: 6px; padding: 10px; font-size: 13px; selection-background-color: #00516a; }
        QLineEdit { background: rgba(0,20,32,220); border: 1px solid #00516a; border-radius: 4px; padding: 8px 12px; font-size: 13px; color: #c8f0ff; }
        QLineEdit:focus { border: 1px solid #00e1ff; }
        QPushButton { background: rgba(0,40,60,200); border: 1px solid #00a8c8; color: #00e1ff; padding: 8px 18px; border-radius: 3px; font-weight: 600; letter-spacing: 2px; }
        QPushButton:hover { background: #003848; border-color: #00e1ff; }
        QPushButton:checked { background: #004a60; border-color: #00e1ff; }
        QLabel#devlabel { font-size: 11px; letter-spacing: 3px; color: #5bb6c8; }
        QComboBox#device { background: rgba(0,20,32,220); border: 1px solid #00516a; color: #c8f0ff; padding: 4px 8px; border-radius: 3px; font-size: 12px; }
        QComboBox#device::drop-down { border: none; }
        QComboBox#device QAbstractItemView { background: #05141e; color: #c8f0ff; selection-background-color: #00516a; border: 1px solid #00516a; }
        QScrollBar:vertical { background: transparent; width: 8px; }
        QScrollBar::handle:vertical { background: #00516a; border-radius: 3px; }
        """

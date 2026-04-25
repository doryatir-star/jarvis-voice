import math
import random
import datetime
from PyQt5 import QtCore, QtGui, QtWidgets


ACCENT = QtGui.QColor(0, 225, 255)
ACCENT_DIM = QtGui.QColor(0, 140, 170)
WARN = QtGui.QColor(255, 140, 0)
OK = QtGui.QColor(60, 255, 180)
BG = QtGui.QColor(3, 7, 14)
TEXT = QtGui.QColor(200, 240, 255)


# ---------- Background: starfield + hex grid + shooting stars + scanlines ----------
class Starfield(QtWidgets.QWidget):
    """Animated starfield, hex grid, scan lines, and shooting stars."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self._stars = [(random.random(), random.random(), random.random())
                       for _ in range(180)]
        self._phase = 0.0
        self._scan_y = 0.0
        self._shoot = []  # (x0, y0, vx, vy, life)
        t = QtCore.QTimer(self); t.timeout.connect(self._tick); t.start(33)

    def _tick(self):
        self._phase += 0.04
        self._scan_y = (self._scan_y + 0.8) % 100
        new = []
        for x, y, z in self._stars:
            x = (x + 0.0005 * (z + 0.3)) % 1.0
            new.append((x, y, z))
        self._stars = new
        # spawn shooting star occasionally
        if random.random() < 0.012 and len(self._shoot) < 3:
            sx = random.random()
            sy = random.random() * 0.6
            self._shoot.append([sx, sy, 0.012, 0.005, 1.0])
        # advance shooting stars
        new_shoot = []
        for s in self._shoot:
            s[0] += s[2]; s[1] += s[3]; s[4] -= 0.018
            if s[4] > 0 and s[0] < 1.1 and s[1] < 1.1:
                new_shoot.append(s)
        self._shoot = new_shoot
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # Deep gradient bg
        grad = QtGui.QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QtGui.QColor(2, 5, 12))
        grad.setColorAt(0.5, QtGui.QColor(5, 12, 24))
        grad.setColorAt(1.0, QtGui.QColor(1, 3, 8))
        p.fillRect(0, 0, w, h, grad)

        # Hex grid pattern (low alpha)
        p.setPen(QtGui.QPen(QtGui.QColor(0, 100, 130, 28), 1))
        hex_r = 28
        hex_w = hex_r * math.sqrt(3)
        hex_h = hex_r * 1.5
        rows = int(h / hex_h) + 2
        cols = int(w / hex_w) + 2
        for row in range(rows):
            for col in range(cols):
                cx = col * hex_w + (hex_w / 2 if row % 2 else 0)
                cy = row * hex_h
                pts = [QtCore.QPointF(cx + math.cos(math.pi/3 * i + math.pi/2) * hex_r,
                                       cy + math.sin(math.pi/3 * i + math.pi/2) * hex_r)
                       for i in range(6)]
                poly = QtGui.QPolygonF(pts)
                p.drawPolygon(poly)

        # Stars (with twinkle)
        for sx, sy, sz in self._stars:
            x = sx * w; y = sy * h
            r = 0.4 + sz * 1.8
            twinkle = 0.7 + 0.3 * math.sin(self._phase * 3 + sx * 50)
            alpha = int((70 + sz * 180) * twinkle)
            p.fillRect(QtCore.QRectF(x, y, r, r),
                       QtGui.QColor(180, 230, 255, alpha))

        # Shooting stars
        for sx, sy, vx, vy, life in self._shoot:
            x = sx * w; y = sy * h
            tx = x - vx * w * 8; ty = y - vy * h * 8
            grad_l = QtGui.QLinearGradient(tx, ty, x, y)
            grad_l.setColorAt(0.0, QtGui.QColor(0, 225, 255, 0))
            grad_l.setColorAt(1.0, QtGui.QColor(180, 240, 255, int(220 * life)))
            pen = QtGui.QPen(QtGui.QBrush(grad_l), 1.8)
            p.setPen(pen); p.drawLine(QtCore.QPointF(tx, ty), QtCore.QPointF(x, y))
            p.fillRect(QtCore.QRectF(x - 1, y - 1, 2.5, 2.5),
                       QtGui.QColor(255, 255, 255, int(255 * life)))

        # Subtle radial vignette
        rg = QtGui.QRadialGradient(w / 2, h / 2, max(w, h) * 0.75)
        rg.setColorAt(0.0, QtGui.QColor(0, 0, 0, 0))
        rg.setColorAt(1.0, QtGui.QColor(0, 0, 0, 200))
        p.fillRect(0, 0, w, h, rg)

        # Moving scan line
        sy = int((self._scan_y / 100) * h)
        line_grad = QtGui.QLinearGradient(0, sy - 40, 0, sy + 40)
        line_grad.setColorAt(0.0, QtGui.QColor(0, 225, 255, 0))
        line_grad.setColorAt(0.5, QtGui.QColor(0, 225, 255, 30))
        line_grad.setColorAt(1.0, QtGui.QColor(0, 225, 255, 0))
        p.fillRect(0, sy - 40, w, 80, line_grad)


# ---------- Reactor ----------
class ReactorCore(QtWidgets.QWidget):
    """Animated arc-reactor HUD core. Pulses when speaking or listening."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(440, 440)
        self._phase = 0.0
        self._level = 0.3
        self._target_level = 0.3
        self._mode = "idle"
        self._spectrum = [0.0] * 64
        t = QtCore.QTimer(self); t.timeout.connect(self._tick); t.start(28)

    def set_mode(self, mode: str):
        self._mode = mode
        self._target_level = {"idle": 0.3, "listening": 0.8,
                              "thinking": 0.55, "speaking": 1.0}.get(mode, 0.3)

    def feed_spectrum(self, vals):
        # vals: 0..1 list, length flexible
        n = len(self._spectrum)
        if not vals: return
        for i in range(n):
            j = int(i / n * len(vals))
            target = vals[j]
            self._spectrum[i] += (target - self._spectrum[i]) * 0.35

    def _tick(self):
        self._phase += 0.045
        self._level += (self._target_level - self._level) * 0.08
        # decay spectrum
        for i in range(len(self._spectrum)):
            self._spectrum[i] *= 0.86
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.42
        color = ACCENT if self._mode != "thinking" else WARN

        # Outer rotating rings
        for rf, width, speed, dash in [
            (1.05, 1, 0.3, [4, 12]),
            (1.00, 2, 0.6, [2, 8]),
            (0.88, 1, -0.9, [1, 4]),
            (0.74, 3, 0.4, [10, 6]),
        ]:
            pen = QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 180))
            pen.setWidth(width)
            pen.setDashPattern(dash)
            pen.setDashOffset(self._phase * 20 * speed)
            p.setPen(pen); p.setBrush(QtCore.Qt.NoBrush)
            rr = r * rf
            p.drawEllipse(QtCore.QPointF(cx, cy), rr, rr)

        # Spectrum bars around the reactor (between r*1.06 and r*1.22)
        n = len(self._spectrum)
        for i, v in enumerate(self._spectrum):
            a = i / n * math.tau - math.pi / 2
            r1 = r * 1.07
            r2 = r * (1.10 + v * 0.18)
            p1 = QtCore.QPointF(cx + math.cos(a) * r1, cy + math.sin(a) * r1)
            p2 = QtCore.QPointF(cx + math.cos(a) * r2, cy + math.sin(a) * r2)
            alpha = int(60 + v * 195)
            pen = QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), alpha), 2)
            p.setPen(pen); p.drawLine(p1, p2)

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
        grad = QtGui.QRadialGradient(cx, cy, glow_r * 2.4)
        grad.setColorAt(0.0, QtGui.QColor(color.red(), color.green(), color.blue(), int(220 * self._level)))
        grad.setColorAt(0.4, QtGui.QColor(color.red(), color.green(), color.blue(), int(80 * self._level)))
        grad.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        p.setBrush(QtGui.QBrush(grad)); p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(QtCore.QPointF(cx, cy), glow_r * 2.4, glow_r * 2.4)

        # Reactor blades
        p.setPen(QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 230), 2))
        for k in range(8):
            a = math.radians(k * 45 + self._phase * 8)
            r_in, r_out = r * 0.30, r * 0.58
            p1 = QtCore.QPointF(cx + math.cos(a) * r_in, cy + math.sin(a) * r_in)
            p2 = QtCore.QPointF(cx + math.cos(a + 0.25) * r_out, cy + math.sin(a + 0.25) * r_out)
            p3 = QtCore.QPointF(cx + math.cos(a - 0.25) * r_out, cy + math.sin(a - 0.25) * r_out)
            path = QtGui.QPainterPath(p1)
            path.lineTo(p2); path.lineTo(p3); path.closeSubpath()
            p.fillPath(path, QtGui.QColor(color.red(), color.green(), color.blue(), 70))
            p.drawPath(path)

        # Inner core
        core_r = r * (0.20 + 0.04 * math.sin(self._phase * 3))
        core_grad = QtGui.QRadialGradient(cx, cy, core_r)
        core_grad.setColorAt(0.0, QtGui.QColor(245, 255, 255))
        core_grad.setColorAt(0.5, QtGui.QColor(color.red(), color.green(), color.blue(), 230))
        core_grad.setColorAt(1.0, QtGui.QColor(color.red(), color.green(), color.blue(), 40))
        p.setBrush(QtGui.QBrush(core_grad)); p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(QtCore.QPointF(cx, cy), core_r, core_r)


# ---------- Spectrum waveform ----------
class Spectrum(QtWidgets.QWidget):
    """Bar-style spectrum analyzer driven by mic level + simulated sub-bands."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        self._n = 48
        self._bars = [0.05] * self._n
        self._target = [0.05] * self._n
        self._phase = 0.0
        t = QtCore.QTimer(self); t.timeout.connect(self._tick); t.start(30)

    def set_amp(self, a):
        # Spread amplitude across bars with random jitter for that "FFT" feel
        a = max(0.04, min(1.0, a))
        for i in range(self._n):
            base = a * (0.6 + 0.4 * math.sin(self._phase * 1.7 + i * 0.4))
            jitter = a * random.random() * 0.6
            self._target[i] = max(0.04, min(1.0, base + jitter))

    def _tick(self):
        self._phase += 0.07
        for i in range(self._n):
            self._bars[i] += (self._target[i] - self._bars[i]) * 0.25
            self._target[i] *= 0.93
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bar_w = w / self._n
        for i, v in enumerate(self._bars):
            bh = v * (h - 8)
            x = i * bar_w + 1
            y = h - bh
            grad = QtGui.QLinearGradient(0, y, 0, h)
            grad.setColorAt(0.0, QtGui.QColor(0, 225, 255))
            grad.setColorAt(0.6, QtGui.QColor(0, 180, 200))
            grad.setColorAt(1.0, QtGui.QColor(0, 60, 90))
            p.fillRect(QtCore.QRectF(x, y, bar_w - 2, bh), QtGui.QBrush(grad))


class LevelBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(16)
        self._level = 0.0; self._peak = 0.0
        t = QtCore.QTimer(self); t.timeout.connect(self._tick); t.start(40)

    def set_level(self, v):
        self._level = max(0.0, min(1.0, v))
        if self._level > self._peak: self._peak = self._level

    def _tick(self):
        self._peak *= 0.92
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QtGui.QColor(0, 18, 28))
        p.setPen(QtGui.QPen(QtGui.QColor(0, 81, 106), 1))
        p.drawRect(0, 0, w - 1, h - 1)
        lw = int(w * self._level)
        grad = QtGui.QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QtGui.QColor(0, 225, 255))
        grad.setColorAt(0.7, QtGui.QColor(0, 225, 180))
        grad.setColorAt(1.0, QtGui.QColor(255, 140, 0))
        p.fillRect(1, 1, max(0, lw - 2), h - 2, QtGui.QBrush(grad))
        px = int(w * self._peak)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 200), 2))
        p.drawLine(px, 1, px, h - 2)


# ---------- L-shaped corner brackets that frame the reactor ----------
class CornerBrackets(QtWidgets.QWidget):
    """Animated L-brackets in the four corners around the reactor."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self._phase = 0.0
        t = QtCore.QTimer(self); t.timeout.connect(self._tick); t.start(40)

    def _tick(self):
        self._phase += 0.05
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        c = ACCENT
        pulse = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(self._phase * 1.5))
        col = QtGui.QColor(c.red(), c.green(), c.blue(), int(220 * pulse))
        pen = QtGui.QPen(col, 2); pen.setCapStyle(QtCore.Qt.FlatCap)
        p.setPen(pen)
        L = 36; pad = 6
        # 4 corners
        # top-left
        p.drawLine(pad, pad, pad + L, pad)
        p.drawLine(pad, pad, pad, pad + L)
        # top-right
        p.drawLine(w - pad, pad, w - pad - L, pad)
        p.drawLine(w - pad, pad, w - pad, pad + L)
        # bottom-left
        p.drawLine(pad, h - pad, pad + L, h - pad)
        p.drawLine(pad, h - pad, pad, h - pad - L)
        # bottom-right
        p.drawLine(w - pad, h - pad, w - pad - L, h - pad)
        p.drawLine(w - pad, h - pad, w - pad, h - pad - L)
        # tiny pip squares inside each corner
        p.setBrush(QtGui.QColor(c.red(), c.green(), c.blue(), 200))
        p.setPen(QtCore.Qt.NoPen)
        s = 3
        for cx, cy in [(pad + 8, pad + 8), (w - pad - 8 - s, pad + 8),
                        (pad + 8, h - pad - 8 - s), (w - pad - 8 - s, h - pad - 8 - s)]:
            p.fillRect(QtCore.QRectF(cx, cy, s, s),
                       QtGui.QColor(c.red(), c.green(), c.blue(), 220))


# ---------- Voiceprint vertical bars (flank the reactor) ----------
class VoicePrint(QtWidgets.QWidget):
    """Two columns of vertical bars that pulse with mic level."""
    def __init__(self, parent=None, mirror=False):
        super().__init__(parent)
        self.setFixedWidth(36)
        self._n = 22
        self._bars = [0.05] * self._n
        self._target = [0.05] * self._n
        self._phase = 0.0
        self._mirror = mirror
        t = QtCore.QTimer(self); t.timeout.connect(self._tick); t.start(34)

    def set_amp(self, a):
        a = max(0.04, min(1.0, a))
        for i in range(self._n):
            base = a * (0.5 + 0.5 * math.sin(self._phase * 1.3 + i * 0.55 + (1 if self._mirror else 0)))
            self._target[i] = max(0.05, min(1.0, base + a * random.random() * 0.4))

    def _tick(self):
        self._phase += 0.06
        for i in range(self._n):
            self._bars[i] += (self._target[i] - self._bars[i]) * 0.25
            self._target[i] *= 0.93
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bar_h = h / self._n
        c = ACCENT
        for i, v in enumerate(self._bars):
            bw = v * (w - 6)
            x = (w - bw) if self._mirror else 3
            y = i * bar_h + 1
            grad = QtGui.QLinearGradient(x, 0, x + bw, 0)
            if self._mirror:
                grad.setColorAt(0.0, QtGui.QColor(c.red(), c.green(), c.blue(), 30))
                grad.setColorAt(1.0, QtGui.QColor(c.red(), c.green(), c.blue(), 220))
            else:
                grad.setColorAt(0.0, QtGui.QColor(c.red(), c.green(), c.blue(), 220))
                grad.setColorAt(1.0, QtGui.QColor(c.red(), c.green(), c.blue(), 30))
            p.fillRect(QtCore.QRectF(x, y, bw, bar_h - 2), QtGui.QBrush(grad))


# ---------- Telemetry ticker strip ----------
class TelemetryStrip(QtWidgets.QWidget):
    """Scrolling fake-telemetry ticker shown across the bottom."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)
        self._offset = 0.0
        self._messages = self._gen()
        self._text = "  ◆  ".join(self._messages)
        t = QtCore.QTimer(self); t.timeout.connect(self._tick); t.start(40)
        # refresh telemetry strings periodically
        t2 = QtCore.QTimer(self); t2.timeout.connect(self._refresh); t2.start(7000)

    def _gen(self):
        msgs = [
            f"SYS {random.choice(['NOMINAL','GREEN','READY','ONLINE'])}",
            f"REACTOR {random.randint(82, 99)}%",
            f"COGNITION {random.uniform(2.1, 5.7):.2f} TFLOPS",
            f"COMMS {random.choice(['LINK STABLE','HANDSHAKE OK','ENCRYPTED'])}",
            f"UPTIME {random.randint(1,72)}h{random.randint(0,59):02d}m",
            f"MEM POOL {random.randint(1, 16)}.{random.randint(0,9)} GB",
            f"GPS LOCK {random.randint(8, 14)} SAT",
            f"CORE TEMP {random.randint(38, 56)}°C",
            f"NET LATENCY {random.randint(7, 42)} ms",
            f"AI LAYERS {random.randint(96, 256)}",
            f"VOICE BIOMETRIC {random.randint(95,99)}%",
            f"AUDIO IN -{random.randint(8, 36)} dB",
            f"SCAN PASS #{random.randint(1000,9999)}",
            f"AGENT {random.choice(['ACTIVE','LISTENING','IDLE'])}",
        ]
        random.shuffle(msgs)
        return msgs

    def _refresh(self):
        self._messages = self._gen()
        self._text = "  ◆  ".join(self._messages)

    def _tick(self):
        self._offset = (self._offset + 1.2) % 10000
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.TextAntialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QtGui.QColor(0, 14, 22, 180))
        c = ACCENT
        p.setPen(QtGui.QPen(QtGui.QColor(c.red(), c.green(), c.blue(), 80), 1))
        p.drawLine(0, 0, w, 0); p.drawLine(0, h - 1, w, h - 1)
        f = QtGui.QFont("Consolas", 9); p.setFont(f)
        fm = QtGui.QFontMetricsF(f)
        tw = fm.horizontalAdvance(self._text) + 80
        x = -(self._offset % tw)
        p.setPen(QtGui.QColor(c.red(), c.green(), c.blue(), 220))
        # draw twice for seamless scrolling
        p.drawText(QtCore.QPointF(x, h - 6), self._text)
        p.drawText(QtCore.QPointF(x + tw, h - 6), self._text)


# ---------- HUD info panels ----------
class InfoPanel(QtWidgets.QFrame):
    """Holographic-style info panel with title + value, used for clock/CPU/etc."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("infopanel")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10); v.setSpacing(2)
        self.title = QtWidgets.QLabel(title); self.title.setObjectName("paneltitle")
        self.value = QtWidgets.QLabel("—"); self.value.setObjectName("panelvalue")
        v.addWidget(self.title); v.addWidget(self.value)

    def set_value(self, text: str):
        self.value.setText(text)


class JarvisWindow(QtWidgets.QWidget):
    user_input = QtCore.pyqtSignal(str)
    device_changed = QtCore.pyqtSignal(int)
    mic_test_requested = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S.")
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(self._qss())

        # Background under everything
        self.bg = Starfield(self)
        self.bg.lower()

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20); root.setSpacing(18)

        # ===== LEFT: HUD info panels =====
        left = QtWidgets.QVBoxLayout(); left.setSpacing(10)
        title_l = QtWidgets.QLabel("S Y S T E M"); title_l.setObjectName("hudtitle")
        left.addWidget(title_l)
        self.clock_panel = InfoPanel("LOCAL TIME"); left.addWidget(self.clock_panel)
        self.date_panel = InfoPanel("DATE"); left.addWidget(self.date_panel)
        self.cpu_panel = InfoPanel("CPU LOAD"); left.addWidget(self.cpu_panel)
        self.ram_panel = InfoPanel("MEMORY"); left.addWidget(self.ram_panel)
        self.battery_panel = InfoPanel("POWER"); left.addWidget(self.battery_panel)
        self.net_panel = InfoPanel("NETWORK"); left.addWidget(self.net_panel)
        left.addStretch(1)
        left_w = QtWidgets.QWidget(); left_w.setLayout(left); left_w.setFixedWidth(220)
        root.addWidget(left_w)

        # ===== CENTER: reactor + status =====
        center = QtWidgets.QVBoxLayout(); center.setSpacing(10)
        # reactor row: voiceprint | reactor (with corner brackets) | voiceprint
        reactor_row = QtWidgets.QHBoxLayout(); reactor_row.setSpacing(6)
        self.vp_left = VoicePrint(mirror=True)
        self.reactor = ReactorCore()
        self.vp_right = VoicePrint(mirror=False)
        # wrap reactor in a stack so brackets overlay it
        reactor_wrap = QtWidgets.QWidget()
        wrap_layout = QtWidgets.QGridLayout(reactor_wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addWidget(self.reactor, 0, 0)
        self.brackets = CornerBrackets(reactor_wrap)
        self.brackets.setGeometry(0, 0, 10, 10)
        reactor_wrap.installEventFilter(self)
        self._reactor_wrap = reactor_wrap
        reactor_row.addWidget(self.vp_left)
        reactor_row.addWidget(reactor_wrap, 1)
        reactor_row.addWidget(self.vp_right)
        self.status = QtWidgets.QLabel("STANDBY")
        self.status.setAlignment(QtCore.Qt.AlignCenter); self.status.setObjectName("status")
        self.spectrum = Spectrum()
        self.telemetry = TelemetryStrip()
        center.addLayout(reactor_row, 1)
        center.addWidget(self.status)
        center.addWidget(self.spectrum)
        center.addWidget(self.telemetry)
        root.addLayout(center, 2)

        # ===== RIGHT: title, transcript, controls =====
        right = QtWidgets.QVBoxLayout(); right.setSpacing(8)
        title = QtWidgets.QLabel("J · A · R · V · I · S"); title.setObjectName("title")
        subtitle = QtWidgets.QLabel("Just A Rather Very Intelligent System")
        subtitle.setObjectName("subtitle")

        dev_row = QtWidgets.QHBoxLayout()
        dev_label = QtWidgets.QLabel("MIC:"); dev_label.setObjectName("devlabel")
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setObjectName("device")
        self.device_combo.currentIndexChanged.connect(self._on_device_change)
        dev_row.addWidget(dev_label); dev_row.addWidget(self.device_combo, 1)

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
        self.theme_btn = QtWidgets.QPushButton("CYAN")
        self.theme_btn.clicked.connect(self._cycle_theme)
        btn_row.addWidget(self.theme_btn); btn_row.addStretch(1); btn_row.addWidget(self.mic_btn)

        right.addWidget(title); right.addWidget(subtitle)
        right.addLayout(dev_row); right.addLayout(meter_row)
        right.addWidget(self.transcript, 1)
        right.addLayout(btn_row)
        right_w = QtWidgets.QWidget(); right_w.setLayout(right)
        root.addWidget(right_w, 2)

        # update HUD info every 2s
        self._info_timer = QtCore.QTimer(self)
        self._info_timer.timeout.connect(self._refresh_info)
        self._info_timer.start(2000)
        QtCore.QTimer.singleShot(100, self._refresh_info)

        # color theme cycle
        self._themes = [
            ("CYAN",   QtGui.QColor(0, 225, 255), "#00e1ff"),
            ("GOLD",   QtGui.QColor(255, 200, 60), "#ffc83c"),
            ("EMBER",  QtGui.QColor(255, 110, 60), "#ff6e3c"),
            ("MATRIX", QtGui.QColor(80, 255, 140), "#50ff8c"),
        ]
        self._theme_idx = 0

    def resizeEvent(self, e):
        self.bg.setGeometry(self.rect())
        super().resizeEvent(e)

    def eventFilter(self, obj, ev):
        if obj is getattr(self, "_reactor_wrap", None) and ev.type() == QtCore.QEvent.Resize:
            self.brackets.setGeometry(0, 0, obj.width(), obj.height())
            self.brackets.raise_()
        return super().eventFilter(obj, ev)

    def _on_device_change(self, row):
        idx = self.device_combo.itemData(row)
        if idx is not None:
            self.device_changed.emit(int(idx))

    def populate_devices(self, devices, current_index):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for idx, name in devices:
            self.device_combo.addItem(f"{idx}: {name}", idx)
        if current_index is not None:
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == current_index:
                    self.device_combo.setCurrentIndex(i); break
        self.device_combo.blockSignals(False)

    def set_mic_level(self, v):
        self.level.set_level(v)
        self.spectrum.set_amp(max(0.05, v))
        self.vp_left.set_amp(max(0.05, v))
        self.vp_right.set_amp(max(0.05, v))

    def _refresh_info(self):
        now = datetime.datetime.now()
        self.clock_panel.set_value(now.strftime("%H:%M:%S"))
        self.date_panel.set_value(now.strftime("%a · %b %d"))
        try:
            import psutil
            self.cpu_panel.set_value(f"{psutil.cpu_percent():.0f} %")
            m = psutil.virtual_memory()
            self.ram_panel.set_value(f"{m.percent:.0f} %  ·  {m.used/2**30:.1f} GB")
            b = psutil.sensors_battery()
            if b:
                charging = "⚡" if b.power_plugged else "🔋"
                self.battery_panel.set_value(f"{charging} {int(b.percent)} %")
            else:
                self.battery_panel.set_value("— DC link —")
            try:
                io = psutil.net_io_counters()
                if not hasattr(self, "_last_net"):
                    self._last_net = (io.bytes_sent, io.bytes_recv, now)
                last_s, last_r, last_t = self._last_net
                dt = max(0.5, (now - last_t).total_seconds())
                up = (io.bytes_sent - last_s) / dt / 1024
                dn = (io.bytes_recv - last_r) / dt / 1024
                self._last_net = (io.bytes_sent, io.bytes_recv, now)
                self.net_panel.set_value(f"↑{up:5.0f}  ↓{dn:5.0f} KB/s")
            except Exception:
                self.net_panel.set_value("— online —")
        except Exception:
            self.cpu_panel.set_value("psutil n/a")
            self.ram_panel.set_value("—")
            self.battery_panel.set_value("—")
            self.net_panel.set_value("—")

    def _cycle_theme(self):
        self._theme_idx = (self._theme_idx + 1) % len(self._themes)
        name, color, hex_ = self._themes[self._theme_idx]
        self.theme_btn.setText(name)
        # Repaint accent
        global ACCENT
        ACCENT = color
        self.setStyleSheet(self._qss(hex_))

    def append_user(self, text):
        if text.startswith("[ignored]"):
            body = text[len("[ignored]"):].strip()
            self.transcript.append(f'<span style="color:#456674">· {body}</span>')
        else:
            self.transcript.append(f'<span style="color:#7fe7ff">&gt; {text}</span>')

    def append_jarvis(self, text):
        self.transcript.append(f'<span style="color:#c8f0ff"><b>JARVIS:</b> {text}</span><br>')

    def set_status(self, mode):
        self.reactor.set_mode(mode)
        labels = {"idle": "STANDBY", "listening": "LISTENING…",
                  "thinking": "COGITATING…", "speaking": "SPEAKING…"}
        self.status.setText(labels.get(mode, mode.upper()))
        amp = {"idle": 0.06, "listening": 0.55,
               "thinking": 0.4, "speaking": 0.85}.get(mode, 0.1)
        self.spectrum.set_amp(amp)
        self.vp_left.set_amp(amp)
        self.vp_right.set_amp(amp)

    def _qss(self, accent="#00e1ff"):
        return f"""
        QWidget {{ background: transparent; color: #c8f0ff; font-family: 'Consolas','Segoe UI',monospace; }}
        QLabel#title {{ font-size: 30px; font-weight: 700; letter-spacing: 7px; color: {accent}; }}
        QLabel#subtitle {{ font-size: 10px; letter-spacing: 4px; color: #5bb6c8; margin-bottom: 6px; }}
        QLabel#hudtitle {{ font-size: 11px; letter-spacing: 6px; color: {accent}; padding: 4px 0; }}
        QLabel#status {{ font-size: 14px; letter-spacing: 6px; color: {accent}; padding: 6px;
                         border: 1px solid #00516a; border-radius: 4px; background: rgba(0,40,60,120); }}
        QFrame#infopanel {{
            background: rgba(0,18,30,180);
            border: 1px solid rgba(0,160,200,90);
            border-radius: 4px;
        }}
        QLabel#paneltitle {{ font-size: 9px; letter-spacing: 3px; color: #5bb6c8; }}
        QLabel#panelvalue {{ font-size: 16px; color: {accent}; font-weight: 600; }}
        QTextEdit#transcript {{ background: rgba(0,20,32,200); border: 1px solid #00516a;
                                border-radius: 6px; padding: 10px; font-size: 13px;
                                selection-background-color: #00516a; }}
        QPushButton {{ background: rgba(0,40,60,200); border: 1px solid #00a8c8; color: {accent};
                       padding: 8px 18px; border-radius: 3px; font-weight: 600; letter-spacing: 2px; }}
        QPushButton:hover {{ background: #003848; border-color: {accent}; }}
        QPushButton:checked {{ background: #004a60; border-color: {accent}; }}
        QLabel#devlabel {{ font-size: 11px; letter-spacing: 3px; color: #5bb6c8; }}
        QComboBox#device {{ background: rgba(0,20,32,220); border: 1px solid #00516a;
                            color: #c8f0ff; padding: 4px 8px; border-radius: 3px; font-size: 12px; }}
        QComboBox#device::drop-down {{ border: none; }}
        QComboBox#device QAbstractItemView {{ background: #05141e; color: #c8f0ff;
                                              selection-background-color: #00516a; border: 1px solid #00516a; }}
        QScrollBar:vertical {{ background: transparent; width: 8px; }}
        QScrollBar::handle:vertical {{ background: #00516a; border-radius: 3px; }}
        """

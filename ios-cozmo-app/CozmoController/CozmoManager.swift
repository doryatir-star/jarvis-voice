// Owns the UDP connection to a real Cozmo robot and exposes plain
// high-level methods (drive/turn/stopAll/turnHead/lift/lights) for the
// SwiftUI views to call — mirrors the shape of the LEGO app's HubManager
// and the Python desktop app's cozmo_hub.py, adapted to Apple's
// Network.framework.
//
// Handshake sequence (reverse-engineered from pycozmo, see the comment at
// the top of CozmoProtocol.swift):
//   1. Send a RESET frame.
//   2. Robot replies with a Connect packet — start the 0.5s ping keepalive.
//   3. Robot spontaneously sends FirmwareSignature — reply with Enable,
//      twice ("this repetition seems to trigger BodyInfo" per pycozmo).
//   4. Robot sends BodyInfo — reply with SetOrigin then SyncTime. Cozmo is
//      now ready for drive/head/lift/light commands.
//
// This implementation intentionally skips pycozmo's full sliding-window
// ack/retransmit machinery (SendWindow/ReceiveWindow) — on a direct,
// single-hop Wi-Fi link to the robot's own access point, plain fire-and-hope
// UDP delivery is reliable enough for manual joystick-style control, and a
// dropped "stop" is no worse than a dropped Bluetooth write would be on the
// LEGO app. What's kept is the part that actually matters for the
// connection surviving at all: correct frame/packet byte layout, the
// handshake, and the periodic keepalive ping (Cozmo's firmware appears to
// expect one — see conn.py's PING_INTERVAL).
import Foundation
import Network

enum Direction: Equatable { case forward, backward }
enum TurnDirection: Equatable { case left, right }
enum HeadDirection: String { case up, down, center }
enum LiftDirection: String { case up, down }

final class CozmoManager: NSObject, ObservableObject {
    enum ConnectionState: Equatable {
        case disconnected, connecting, handshaking, ready
    }

    @Published var connectionState: ConnectionState = .disconnected
    @Published var log: [String] = []

    @Published var driveSpeed: Float = 100 {
        didSet { UserDefaults.standard.set(driveSpeed, forKey: "driveSpeed") }
    }
    @Published var turnSpeed: Float = 80 {
        didSet { UserDefaults.standard.set(turnSpeed, forKey: "turnSpeed") }
    }
    @Published var driveSeconds: Double = 1.5
    @Published var turnSeconds: Double = 0.8

    private var connection: NWConnection?
    private var outgoingSeq: UInt16 = 0
    private var lastReceivedSeq: UInt16 = CozmoWire.oobSeq
    private var gotFirmwareSignature = false
    private var gotBodyInfo = false
    private var pingTimer: Timer?
    private var pingCounter: UInt32 = 0
    private var stopWorkItem: DispatchWorkItem?

    override init() {
        let savedDrive = UserDefaults.standard.object(forKey: "driveSpeed") as? Float
        let savedTurn = UserDefaults.standard.object(forKey: "turnSpeed") as? Float
        driveSpeed = savedDrive ?? 100
        turnSpeed = savedTurn ?? 80
        super.init()
    }

    // MARK: - Connect / disconnect

    func connect() {
        guard connection == nil else { return }
        addLog("Connecting to Cozmo at \(CozmoWire.robotHost):\(CozmoWire.robotPort)...")
        connectionState = .connecting
        outgoingSeq = 0
        lastReceivedSeq = CozmoWire.oobSeq
        gotFirmwareSignature = false
        gotBodyInfo = false

        let host = NWEndpoint.Host(CozmoWire.robotHost)
        let port = NWEndpoint.Port(rawValue: CozmoWire.robotPort)!
        let conn = NWConnection(host: host, port: port, using: .udp)
        connection = conn
        conn.stateUpdateHandler = { [weak self] state in
            guard let self else { return }
            switch state {
            case .ready:
                self.addLog("Socket ready — sending RESET.")
                self.sendReset()
                self.receiveLoop()
            case .failed(let error):
                self.addLog("Connection failed: \(error.localizedDescription)")
                self.teardown()
            case .cancelled:
                break
            default:
                break
            }
        }
        conn.start(queue: .main)
    }

    func disconnect() {
        guard let conn = connection else { return }
        let pkt = OutPacket(type: .disconnect, id: nil, payload: [])
        sendEngineFrame([pkt])
        pingTimer?.invalidate()
        pingTimer = nil
        stopWorkItem?.cancel()
        conn.cancel()
        teardown()
        addLog("Disconnected.")
    }

    private func teardown() {
        connection = nil
        connectionState = .disconnected
        pingTimer?.invalidate()
        pingTimer = nil
    }

    func addLog(_ line: String) {
        DispatchQueue.main.async {
            self.log.append(line)
            if self.log.count > 300 {
                self.log.removeFirst(self.log.count - 300)
            }
        }
    }

    // MARK: - Low-level send/receive

    private func sendRaw(_ data: Data) {
        guard let conn = connection else { return }
        conn.send(content: data, completion: .contentProcessed { [weak self] error in
            if let error {
                self?.addLog("Send failed: \(error.localizedDescription)")
            }
        })
        addLog("-> " + data.hexString)
    }

    private func sendReset() {
        let frame = CozmoFrame.encode(type: .reset, firstSeq: 0, seq: 0, ack: CozmoWire.oobSeq, packets: [])
        sendRaw(frame)
    }

    /// Wraps one or more packets in a single ENGINE frame, consuming one
    /// outgoing sequence number per non-OOB (command/disconnect) packet.
    private func sendEngineFrame(_ packets: [OutPacket]) {
        let seq = outgoingSeq
        outgoingSeq = outgoingSeq &+ 1
        let frame = CozmoFrame.encode(type: .engine, firstSeq: seq, seq: seq, ack: lastReceivedSeq, packets: packets)
        sendRaw(frame)
    }

    private func sendPing() {
        let pkt = CozmoCommand.ping(timeSentMs: Date().timeIntervalSince1970 * 1000, counter: pingCounter)
        pingCounter += 1
        let frame = CozmoFrame.encode(type: .ping, firstSeq: CozmoWire.oobSeq, seq: CozmoWire.oobSeq,
                                       ack: lastReceivedSeq, packets: [pkt])
        sendRaw(frame)
    }

    private func startPingTimer() {
        guard pingTimer == nil else { return }
        let timer = Timer(timeInterval: 0.5, repeats: true) { [weak self] _ in self?.sendPing() }
        RunLoop.main.add(timer, forMode: .common)
        pingTimer = timer
    }

    private func receiveLoop() {
        connection?.receiveMessage { [weak self] data, _, _, error in
            guard let self else { return }
            if let error {
                self.addLog("Receive error: \(error.localizedDescription)")
            }
            if let data, !data.isEmpty {
                self.handleIncoming(data)
            }
            if self.connection != nil {
                self.receiveLoop()
            }
        }
    }

    private func handleIncoming(_ data: Data) {
        addLog("<- " + data.hexString)
        guard let frame = CozmoFrame.decode(data) else {
            addLog("(failed to decode frame)")
            return
        }
        switch frame.type {
        case .engine, .robot:
            lastReceivedSeq = frame.seq
            for pkt in frame.packets {
                handlePacket(pkt)
            }
        case .ping:
            break
        default:
            break
        }
    }

    private func handlePacket(_ pkt: InPacket) {
        if pkt.typeByte == CozmoWire.PacketType.connect.rawValue {
            if connectionState == .connecting {
                addLog("Connected. Waiting for firmware/body info...")
                connectionState = .handshaking
                startPingTimer()
            }
            return
        }
        guard let id = pkt.id else { return }
        if id == CozmoWire.firmwareSignatureID, !gotFirmwareSignature {
            gotFirmwareSignature = true
            addLog("Got firmware signature — enabling motors.")
            sendEngineFrame([CozmoCommand.enable()])
            sendEngineFrame([CozmoCommand.enable()])
        } else if id == CozmoWire.bodyInfoID, !gotBodyInfo {
            gotBodyInfo = true
            addLog("Got body info — initializing.")
            sendEngineFrame([CozmoCommand.setOrigin()])
            sendEngineFrame([CozmoCommand.syncTime()])
            connectionState = .ready
            addLog("Cozmo ready.")
        }
    }

    // MARK: - High-level commands

    func drive(_ direction: Direction) {
        let speed = min(max(driveSpeed, 0), CozmoWire.maxWheelSpeedMMPS)
        let s = direction == .forward ? speed : -speed
        sendEngineFrame([CozmoCommand.driveWheels(l: s, r: s)])
        scheduleAutoStop(after: driveSeconds)
        addLog(direction == .forward ? "Moving forward." : "Moving backward.")
    }

    func turn(_ direction: TurnDirection) {
        let speed = min(max(turnSpeed, 0), CozmoWire.maxWheelSpeedMMPS)
        let l: Float = direction == .left ? -speed : speed
        let r: Float = direction == .left ? speed : -speed
        sendEngineFrame([CozmoCommand.driveWheels(l: l, r: r)])
        scheduleAutoStop(after: turnSeconds)
        addLog(direction == .left ? "Turning left." : "Turning right.")
    }

    func stopAll() {
        stopWorkItem?.cancel()
        sendEngineFrame([CozmoCommand.stopAllMotors()])
        addLog("Stopping.")
    }

    func turnHead(_ direction: HeadDirection) {
        let deg: Float
        switch direction {
        case .up: deg = CozmoWire.maxHeadAngleDeg - 5
        case .down: deg = CozmoWire.minHeadAngleDeg + 5
        case .center: deg = 0
        }
        let rad = deg * .pi / 180
        sendEngineFrame([CozmoCommand.setHeadAngle(angleRad: rad)])
        addLog("Head -> \(direction.rawValue)")
    }

    func lift(_ direction: LiftDirection) {
        let mm: Float = direction == .up ? CozmoWire.maxLiftHeightMM : CozmoWire.minLiftHeightMM
        sendEngineFrame([CozmoCommand.setLiftHeight(heightMM: mm)])
        addLog("Lift -> \(direction.rawValue)")
    }

    func lights(_ colorName: String) {
        guard let color = CozmoLightColor.byName(colorName) else {
            addLog("Unknown light color: \(colorName)")
            return
        }
        sendEngineFrame([CozmoCommand.lightStateCenter(color: color)])
        sendEngineFrame([CozmoCommand.lightStateSide(color: color)])
        addLog("Lights -> \(colorName)")
    }

    func sendRaw(hex: String) {
        guard let data = Data(hexString: hex) else {
            addLog("Bad hex: \(hex)")
            return
        }
        sendRaw(data)
    }

    // MARK: - Internals

    private func scheduleAutoStop(after seconds: Double) {
        stopWorkItem?.cancel()
        let item = DispatchWorkItem { [weak self] in self?.stopAll() }
        stopWorkItem = item
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: item)
    }
}

extension Data {
    /// Parses a plain hex string (no spaces, no "0x") into bytes.
    init?(hexString: String) {
        let chars = Array(hexString)
        guard chars.count % 2 == 0 else { return nil }
        var bytes = [UInt8]()
        bytes.reserveCapacity(chars.count / 2)
        var i = 0
        while i < chars.count {
            guard let hi = chars[i].hexDigitValue, let lo = chars[i + 1].hexDigitValue else { return nil }
            bytes.append(UInt8(hi << 4 | lo))
            i += 2
        }
        self = Data(bytes)
    }
}

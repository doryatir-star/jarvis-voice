// Cozmo's Wi-Fi wire protocol — a reliable-ish framing layer over plain UDP,
// reimplemented from the (unofficial, reverse-engineered) pycozmo project
// <https://github.com/zayfod/pycozmo>, the same reference the Python desktop
// app's cozmo_hub.py is built on. There is no official Apple or Anki
// documentation for any of this; every constant below was read out of
// pycozmo's source (frame.py, protocol_declaration.py, protocol_encoder.py,
// conn.py, lights.py) rather than guessed.
//
// Frame layout (little-endian throughout, no CRC/checksum of any kind):
//   7 bytes  magic "COZ\x03RE\x01"
//   1 byte   frame type
//   2 bytes  (first_seq + 1) mod 0x10000
//   2 bytes  (seq + 1) mod 0x10000
//   2 bytes  (ack + 1) mod 0x10000
//   ...      packets (for ENGINE/ROBOT frames), or a single Ping payload
//            (for PING frames), or nothing (RESET/FIN)
//
// Each packet inside an ENGINE/ROBOT frame is: 1 byte packet-type, then
// either [2-byte length-including-id][1-byte id][payload] for COMMAND/EVENT
// packets, or [2-byte length][payload] for CONNECT/DISCONNECT (which have no
// id byte and, for both, an empty payload).
import Foundation

enum CozmoWire {
    /// "COZ\x03RE\x01"
    static let frameID: [UInt8] = [0x43, 0x4F, 0x5A, 0x03, 0x52, 0x45, 0x01]
    static let robotHost = "172.31.1.1"
    static let robotPort: UInt16 = 5551
    static let oobSeq: UInt16 = 0xffff
    /// magic(7) + type(1) + firstSeq(2) + seq(2) + ack(2)
    static let headerSize = 14

    enum FrameType: UInt8 {
        case reset = 1
        case resetAck = 2
        case fin = 3
        case engineAct = 4
        case engine = 7
        case robot = 9
        case ping = 0x0b
    }

    enum PacketType: UInt8 {
        case connect = 2
        case disconnect = 3
        case command = 4
        case event = 5
        case keyframe = 0x0a
        case ping = 0x0b
    }

    // Packet IDs the robot sends us during the connect handshake.
    static let firmwareSignatureID: UInt8 = 0xee
    static let bodyInfoID: UInt8 = 0xed

    // Packet IDs we send.
    static let enableID: UInt8 = 0x25
    static let driveWheelsID: UInt8 = 0x32
    static let setLiftHeightID: UInt8 = 0x36
    static let setHeadAngleID: UInt8 = 0x37
    static let stopAllMotorsID: UInt8 = 0x3b
    static let setOriginID: UInt8 = 0x45
    static let syncTimeID: UInt8 = 0x4b
    static let lightStateCenterID: UInt8 = 0x03
    static let lightStateSideID: UInt8 = 0x11

    // Cozmo's own hardware limits (see pycozmo.robot / the Python desktop
    // app's cozmo_hub.py, which uses the same numbers).
    static let maxWheelSpeedMMPS: Float = 200.0
    static let minHeadAngleDeg: Float = -25.0
    static let maxHeadAngleDeg: Float = 44.5
    static let minLiftHeightMM: Float = 32.0
    static let maxLiftHeightMM: Float = 92.0
}

// MARK: - Binary reader/writer (little-endian, matches Python's "<" struct prefix)

struct ByteWriter {
    private(set) var bytes: [UInt8] = []

    mutating func u8(_ v: UInt8) { bytes.append(v) }

    mutating func u16(_ v: UInt16) {
        bytes.append(UInt8(v & 0xff))
        bytes.append(UInt8((v >> 8) & 0xff))
    }

    mutating func i16(_ v: Int16) { u16(UInt16(bitPattern: v)) }

    mutating func u32(_ v: UInt32) {
        for i in 0..<4 { bytes.append(UInt8((v >> (8 * i)) & 0xff)) }
    }

    mutating func f32(_ v: Float) { u32(v.bitPattern) }

    mutating func f64(_ v: Double) {
        let bits = v.bitPattern
        for i in 0..<8 { bytes.append(UInt8((bits >> (UInt64(8 * i))) & 0xff)) }
    }

    mutating func raw(_ b: [UInt8]) { bytes.append(contentsOf: b) }
}

struct ByteReader {
    let bytes: [UInt8]
    private(set) var offset: Int = 0

    init(_ data: Data) { bytes = [UInt8](data) }

    var remaining: Int { bytes.count - offset }

    mutating func u8() -> UInt8? {
        guard offset < bytes.count else { return nil }
        defer { offset += 1 }
        return bytes[offset]
    }

    mutating func u16() -> UInt16? {
        guard offset + 2 <= bytes.count else { return nil }
        let v = UInt16(bytes[offset]) | (UInt16(bytes[offset + 1]) << 8)
        offset += 2
        return v
    }

    mutating func take(_ n: Int) -> [UInt8]? {
        guard n >= 0, offset + n <= bytes.count else { return nil }
        defer { offset += n }
        return Array(bytes[offset..<offset + n])
    }
}

// MARK: - Packets

struct OutPacket {
    let type: CozmoWire.PacketType
    /// Present for .command / .event packets only.
    let id: UInt8?
    let payload: [UInt8]
}

struct InPacket {
    let typeByte: UInt8
    /// Present for .command / .event packets only.
    let id: UInt8?
    let payload: [UInt8]
}

struct DecodedFrame {
    let type: CozmoWire.FrameType
    let firstSeq: UInt16
    let seq: UInt16
    let ack: UInt16
    let packets: [InPacket]
}

enum CozmoFrame {
    static func encode(type: CozmoWire.FrameType, firstSeq: UInt16, seq: UInt16, ack: UInt16,
                        packets: [OutPacket]) -> Data {
        var w = ByteWriter()
        w.raw(CozmoWire.frameID)
        w.u8(type.rawValue)
        w.u16(firstSeq &+ 1)
        w.u16(seq &+ 1)
        w.u16(ack &+ 1)
        switch type {
        case .engine, .robot:
            for p in packets {
                w.u8(p.type.rawValue)
                if p.type == .command || p.type == .event {
                    w.u16(UInt16(p.payload.count + 1))
                    w.u8(p.id ?? 0)
                } else {
                    w.u16(UInt16(p.payload.count))
                }
                w.raw(p.payload)
            }
        case .ping:
            if let p = packets.first { w.raw(p.payload) }
        case .reset, .fin, .resetAck, .engineAct:
            break
        }
        return Data(w.bytes)
    }

    static func decode(_ data: Data) -> DecodedFrame? {
        var r = ByteReader(data)
        guard let magic = r.take(7), magic == CozmoWire.frameID else { return nil }
        guard let typeRaw = r.u8(), let type = CozmoWire.FrameType(rawValue: typeRaw) else { return nil }
        guard let rawFirst = r.u16(), let rawSeq = r.u16(), let rawAck = r.u16() else { return nil }
        let firstSeq = rawFirst &- 1
        let seq = rawSeq &- 1
        let ack = rawAck &- 1

        var packets: [InPacket] = []
        switch type {
        case .engine, .robot:
            while r.remaining > 0 {
                guard let typeByte = r.u8(), let lenField = r.u16() else { break }
                if typeByte == CozmoWire.PacketType.command.rawValue ||
                    typeByte == CozmoWire.PacketType.event.rawValue {
                    guard lenField >= 1, let id = r.u8() else { break }
                    let payload = r.take(Int(lenField) - 1) ?? []
                    packets.append(InPacket(typeByte: typeByte, id: id, payload: payload))
                } else {
                    let payload = r.take(Int(lenField)) ?? []
                    packets.append(InPacket(typeByte: typeByte, id: nil, payload: payload))
                }
            }
        case .ping:
            let payload = r.take(r.remaining) ?? []
            packets.append(InPacket(typeByte: CozmoWire.PacketType.ping.rawValue, id: nil, payload: payload))
        case .reset, .fin, .resetAck, .engineAct:
            break
        }
        return DecodedFrame(type: type, firstSeq: firstSeq, seq: seq, ack: ack, packets: packets)
    }
}

// MARK: - Command payload builders

enum CozmoCommand {
    static func driveWheels(l: Float, r: Float, lAccel: Float = 0, rAccel: Float = 0) -> OutPacket {
        var w = ByteWriter()
        w.f32(l); w.f32(r); w.f32(lAccel); w.f32(rAccel)
        return OutPacket(type: .command, id: CozmoWire.driveWheelsID, payload: w.bytes)
    }

    static func stopAllMotors() -> OutPacket {
        OutPacket(type: .command, id: CozmoWire.stopAllMotorsID, payload: [])
    }

    static func setHeadAngle(angleRad: Float, maxSpeed: Float = 10, accel: Float = 10,
                              duration: Float = 0, actionID: UInt8 = 0) -> OutPacket {
        var w = ByteWriter()
        w.f32(angleRad); w.f32(maxSpeed); w.f32(accel); w.f32(duration); w.u8(actionID)
        return OutPacket(type: .command, id: CozmoWire.setHeadAngleID, payload: w.bytes)
    }

    static func setLiftHeight(heightMM: Float, maxSpeed: Float = 10, accel: Float = 10,
                               duration: Float = 0, actionID: UInt8 = 0) -> OutPacket {
        var w = ByteWriter()
        w.f32(heightMM); w.f32(maxSpeed); w.f32(accel); w.f32(duration); w.u8(actionID)
        return OutPacket(type: .command, id: CozmoWire.setLiftHeightID, payload: w.bytes)
    }

    static func enable() -> OutPacket {
        OutPacket(type: .command, id: CozmoWire.enableID, payload: [])
    }

    /// Sets world-frame origin to (0,0,0). Sent once, right after the robot
    /// reports BodyInfo — mirrors pycozmo's _initialize_robot().
    static func setOrigin() -> OutPacket {
        var w = ByteWriter()
        w.u32(0); w.u32(0); w.u32(1); w.f32(0); w.f32(0); w.u32(0x8000_0000)
        return OutPacket(type: .command, id: CozmoWire.setOriginID, payload: w.bytes)
    }

    /// Also enables RobotState / ObjectAvailable events on the robot side.
    static func syncTime() -> OutPacket {
        var w = ByteWriter()
        w.u32(0); w.u32(0)
        return OutPacket(type: .command, id: CozmoWire.syncTimeID, payload: w.bytes)
    }

    private static func lightState(color: UInt16) -> [UInt8] {
        var w = ByteWriter()
        w.u16(color)   // on_color
        w.u16(color)   // off_color
        w.u8(0); w.u8(0); w.u8(0); w.u8(0)   // on/off/transition frame counts
        w.i16(0)       // offset
        return w.bytes
    }

    /// Front, middle and back backpack LEDs (all the same color).
    static func lightStateCenter(color: UInt16) -> OutPacket {
        var w = ByteWriter()
        let one = lightState(color: color)
        w.raw(one); w.raw(one); w.raw(one)
        w.u8(0)
        return OutPacket(type: .command, id: CozmoWire.lightStateCenterID, payload: w.bytes)
    }

    /// Left and right backpack LEDs (all the same color).
    static func lightStateSide(color: UInt16) -> OutPacket {
        var w = ByteWriter()
        let one = lightState(color: color)
        w.raw(one); w.raw(one)
        w.u8(0)
        return OutPacket(type: .command, id: CozmoWire.lightStateSideID, payload: w.bytes)
    }

    static func ping(timeSentMs: Double, counter: UInt32) -> OutPacket {
        var w = ByteWriter()
        w.f64(timeSentMs); w.u32(counter); w.u32(0); w.u8(0)
        return OutPacket(type: .ping, id: nil, payload: w.bytes)
    }
}

/// Backpack LED colors, pre-converted to Cozmo's on-wire 5-5-5 RGB packing
/// (see pycozmo/lights.py: Color.to_int16(), component*31/255, R<<10|G<<5|B).
enum CozmoLightColor {
    static let green: UInt16 = 0x03E0
    static let red: UInt16 = 0x7C00
    static let blue: UInt16 = 0x001F
    static let white: UInt16 = 0x7FFF
    static let off: UInt16 = 0x0000

    static func byName(_ name: String) -> UInt16? {
        switch name.lowercased() {
        case "green": return green
        case "red": return red
        case "blue": return blue
        case "white": return white
        case "off": return off
        default: return nil
        }
    }
}

extension Data {
    var hexString: String { map { String(format: "%02x", $0) }.joined() }
}

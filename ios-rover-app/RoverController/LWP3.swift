// LEGO Wireless Protocol 3.0 (LWP3) — the protocol LEGO's stock Powered
// Up/BOOST hub firmware speaks natively over Bluetooth LE. No Pybricks or
// custom firmware needed; this is the same protocol the official LEGO apps
// use.
//
// Byte layouts below were checked against LEGO's official protocol docs
// (github.com/LEGO/lego-ble-wireless-protocol-docs) and node-poweredup's
// real, shipped implementation (github.com/nathankellenicki/node-poweredup)
// — but this file has never been compiled or run against real hardware.
// If a motor doesn't respond, log the raw bytes in the Console tab and
// compare against those references.
import Foundation
import CoreBluetooth

enum LWP3 {
    static let hubServiceUUID = CBUUID(string: "00001623-1212-EFDE-1623-785FEABCD123")
    static let hubCharacteristicUUID = CBUUID(string: "00001624-1212-EFDE-1623-785FEABCD123")

    enum Port {
        static let a: UInt8 = 0x00 // Move Hub's internal tread motor A
        static let b: UInt8 = 0x01 // Move Hub's internal tread motor B
        static let c: UInt8 = 0x02 // external port C
        static let d: UInt8 = 0x03 // external port D
    }

    static func portName(_ port: UInt8) -> String {
        switch port {
        case Port.a: return "A"
        case Port.b: return "B"
        case Port.c: return "C"
        case Port.d: return "D"
        default: return "0x" + String(format: "%02x", port)
        }
    }

    enum EndState: UInt8 {
        case float = 0
        case hold = 126
        case brake = 127
    }

    private static let messageTypePortOutputCommand: UInt8 = 0x81
    private static let messageTypeHubAttachedIO: UInt8 = 0x04
    // Startup/completion byte: high nibble = startup info (0x10 = execute
    // immediately instead of queuing), low nibble = completion info
    // (0x01 = send a feedback message back). 0x11 combines both.
    private static let startupAndCompletion: UInt8 = 0x11
    private static let subCommandWriteDirectModeData: UInt8 = 0x51
    private static let subCommandGotoAbsolutePosition: UInt8 = 0x0D

    /// Continuous drive power for a single motor, -100...100 (0 = stop).
    /// Mode 0 is the "power" mode that basic motors — including the Move
    /// Hub's built-in tread motors — expose via WriteDirectModeData.
    static func writeDirectModeDataPower(port: UInt8, power: Int8) -> Data {
        var body: [UInt8] = [port, startupAndCompletion, subCommandWriteDirectModeData, 0x00]
        body.append(UInt8(bitPattern: power))
        return withHeader(messageType: messageTypePortOutputCommand, body: body)
    }

    /// Move a motor to an absolute angle in degrees. "Absolute" is relative
    /// to wherever the motor's internal zero position was when the hub
    /// powered on — for predictable head/claw centering, power the hub on
    /// with the head/claw already roughly centered.
    static func gotoAbsolutePosition(port: UInt8, angle: Int32, speed: Int8, maxPower: UInt8, endState: EndState) -> Data {
        var body: [UInt8] = [port, startupAndCompletion, subCommandGotoAbsolutePosition]
        withUnsafeBytes(of: angle.littleEndian) { body.append(contentsOf: $0) }
        body.append(UInt8(bitPattern: speed))
        body.append(maxPower)
        body.append(endState.rawValue)
        body.append(0x00) // use profile: none
        return withHeader(messageType: messageTypePortOutputCommand, body: body)
    }

    private static func withHeader(messageType: UInt8, body: [UInt8]) -> Data {
        // Header is [length, hubID(0x00), messageType] + body. Only the
        // single-byte length form is implemented — fine here since every
        // message we send is well under the 127-byte escape threshold.
        let total = 3 + body.count
        var bytes: [UInt8] = [UInt8(total), 0x00, messageType]
        bytes.append(contentsOf: body)
        return Data(bytes)
    }

    struct AttachedIOEvent {
        let port: UInt8
        let attached: Bool
        let ioTypeID: UInt16?
    }

    /// Parses a "Hub Attached I/O" notification (sent whenever a motor is
    /// plugged into or unplugged from an external port) so the app can show
    /// what's on port C/D without needing the calibrate_ports.py script.
    static func parseHubAttachedIO(_ data: Data) -> AttachedIOEvent? {
        guard data.count >= 5, data[2] == messageTypeHubAttachedIO else { return nil }
        let port = data[3]
        let event = data[4]
        if event == 0x00 {
            return AttachedIOEvent(port: port, attached: false, ioTypeID: nil)
        }
        guard data.count >= 7 else {
            return AttachedIOEvent(port: port, attached: true, ioTypeID: nil)
        }
        let ioType = UInt16(data[5]) | (UInt16(data[6]) << 8)
        return AttachedIOEvent(port: port, attached: true, ioTypeID: ioType)
    }
}

extension Data {
    /// Parses a hex string like "0a0081020111010064" (no spaces or 0x
    /// prefix) into raw bytes, for the Console tab's "raw" command.
    init?(hexString: String) {
        let clean = hexString.replacingOccurrences(of: " ", with: "")
        guard !clean.isEmpty, clean.count % 2 == 0 else { return nil }
        var bytes: [UInt8] = []
        var idx = clean.startIndex
        while idx < clean.endIndex {
            let next = clean.index(idx, offsetBy: 2)
            guard let b = UInt8(clean[idx..<next], radix: 16) else { return nil }
            bytes.append(b)
            idx = next
        }
        self = Data(bytes)
    }

    var hexString: String {
        map { String(format: "%02x", $0) }.joined()
    }
}

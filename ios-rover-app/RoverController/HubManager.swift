// Owns the CoreBluetooth connection to the LEGO Move Hub and exposes plain
// high-level methods (drive/turn/stopAll/turnHead/claw) for the SwiftUI
// views to call — mirrors the shape of the Python desktop app's LegoHub
// class, adapted to CoreBluetooth's delegate-callback style.
import Foundation
import CoreBluetooth

enum Direction: Equatable { case forward, backward }
enum TurnDirection: Equatable { case left, right }
enum HeadDirection: String { case left, right, center }
enum ClawAction: String { case open, close }

final class HubManager: NSObject, ObservableObject {
    enum ConnectionState: Equatable {
        case disconnected, scanning, connecting
        case connected(name: String)
    }

    struct DiscoveredHub: Identifiable {
        let id: UUID
        let peripheral: CBPeripheral
        let name: String
        let rssi: Int
    }

    @Published var isBluetoothReady = false
    @Published var discovered: [DiscoveredHub] = []
    @Published var connectionState: ConnectionState = .disconnected
    @Published var log: [String] = []

    @Published var clawPort: UInt8 {
        didSet { UserDefaults.standard.set(Int(clawPort), forKey: "clawPort") }
    }
    @Published var headPort: UInt8 {
        didSet { UserDefaults.standard.set(Int(headPort), forKey: "headPort") }
    }
    @Published var driveSpeed: Int8 = 60
    @Published var driveSeconds: Double = 1.5
    @Published var turnSeconds: Double = 0.8

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var characteristic: CBCharacteristic?
    private var stopWorkItem: DispatchWorkItem?

    override init() {
        let savedClaw = UserDefaults.standard.object(forKey: "clawPort") as? Int
        let savedHead = UserDefaults.standard.object(forKey: "headPort") as? Int
        clawPort = UInt8(savedClaw ?? Int(LWP3.Port.d))
        headPort = UInt8(savedHead ?? Int(LWP3.Port.c))
        super.init()
        central = CBCentralManager(delegate: self, queue: nil)
    }

    // MARK: - Scanning / connection

    func startScan() {
        guard isBluetoothReady else {
            addLog("Bluetooth isn't ready yet — check Settings > Bluetooth is on and permission is granted.")
            return
        }
        discovered.removeAll()
        connectionState = .scanning
        central.scanForPeripherals(withServices: [LWP3.hubServiceUUID], options: nil)
        addLog("Scanning for LEGO hubs...")
    }

    func stopScan() {
        central.stopScan()
    }

    func connect(to hub: DiscoveredHub) {
        stopScan()
        connectionState = .connecting
        peripheral = hub.peripheral
        peripheral?.delegate = self
        central.connect(hub.peripheral, options: nil)
        addLog("Connecting to \(hub.name)...")
    }

    func disconnect() {
        if let p = peripheral {
            central.cancelPeripheralConnection(p)
        }
    }

    func addLog(_ line: String) {
        DispatchQueue.main.async {
            self.log.append(line)
            if self.log.count > 300 {
                self.log.removeFirst(self.log.count - 300)
            }
        }
    }

    // MARK: - High-level rover commands

    func drive(_ direction: Direction) {
        let sign: Int8 = direction == .forward ? 1 : -1
        sendPower(driveSpeed * sign, port: LWP3.Port.a)
        sendPower(driveSpeed * sign, port: LWP3.Port.b)
        scheduleAutoStop(after: driveSeconds)
        addLog(direction == .forward ? "Moving forward." : "Moving backward.")
    }

    func turn(_ direction: TurnDirection) {
        let left: Int8 = direction == .left ? -driveSpeed : driveSpeed
        let right: Int8 = direction == .left ? driveSpeed : -driveSpeed
        sendPower(left, port: LWP3.Port.a)
        sendPower(right, port: LWP3.Port.b)
        scheduleAutoStop(after: turnSeconds)
        addLog(direction == .left ? "Turning left." : "Turning right.")
    }

    func stopAll() {
        stopWorkItem?.cancel()
        sendPower(0, port: LWP3.Port.a)
        sendPower(0, port: LWP3.Port.b)
        addLog("Stopping.")
    }

    func turnHead(_ direction: HeadDirection) {
        let angle: Int32 = direction == .left ? -90 : (direction == .right ? 90 : 0)
        write(LWP3.gotoAbsolutePosition(port: headPort, angle: angle, speed: 40, maxPower: 60, endState: .hold))
        addLog("Head -> \(direction.rawValue)")
    }

    func claw(_ action: ClawAction) {
        let angle: Int32 = action == .open ? -60 : 60
        write(LWP3.gotoAbsolutePosition(port: clawPort, angle: angle, speed: 40, maxPower: 60, endState: .hold))
        addLog("Claw -> \(action.rawValue)")
    }

    /// Nudges an external port a small amount so the user can see which
    /// physical motor (claw or head) it corresponds to.
    func nudge(port: UInt8) {
        write(LWP3.gotoAbsolutePosition(port: port, angle: 30, speed: 30, maxPower: 50, endState: .hold))
        addLog("Nudged port \(LWP3.portName(port)).")
    }

    func sendRaw(hex: String) {
        guard let data = Data(hexString: hex) else {
            addLog("Bad hex: \(hex)")
            return
        }
        write(data)
    }

    // MARK: - Internals

    private func scheduleAutoStop(after seconds: Double) {
        stopWorkItem?.cancel()
        let item = DispatchWorkItem { [weak self] in self?.stopAll() }
        stopWorkItem = item
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: item)
    }

    private func sendPower(_ power: Int8, port: UInt8) {
        write(LWP3.writeDirectModeDataPower(port: port, power: power))
    }

    private func write(_ data: Data) {
        guard let p = peripheral, let c = characteristic else {
            addLog("Not connected — can't send.")
            return
        }
        p.writeValue(data, for: c, type: .withoutResponse)
        addLog("-> " + data.hexString)
    }
}

// MARK: - CBCentralManagerDelegate

extension HubManager: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        isBluetoothReady = (central.state == .poweredOn)
        addLog(isBluetoothReady ? "Bluetooth ready." : "Bluetooth not ready (state \(central.state.rawValue)).")
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                         advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = peripheral.name ?? "Unknown hub"
        if !discovered.contains(where: { $0.id == peripheral.identifier }) {
            discovered.append(DiscoveredHub(id: peripheral.identifier, peripheral: peripheral, name: name, rssi: RSSI.intValue))
        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        addLog("Connected. Discovering services...")
        peripheral.discoverServices([LWP3.hubServiceUUID])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        connectionState = .disconnected
        addLog("Failed to connect: \(error?.localizedDescription ?? "unknown error")")
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        connectionState = .disconnected
        characteristic = nil
        addLog("Disconnected.")
    }
}

// MARK: - CBPeripheralDelegate

extension HubManager: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let service = peripheral.services?.first(where: { $0.uuid == LWP3.hubServiceUUID }) else {
            addLog("Hub service not found.")
            return
        }
        peripheral.discoverCharacteristics([LWP3.hubCharacteristicUUID], for: service)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard let char = service.characteristics?.first(where: { $0.uuid == LWP3.hubCharacteristicUUID }) else {
            addLog("Hub characteristic not found.")
            return
        }
        characteristic = char
        peripheral.setNotifyValue(true, for: char)
        connectionState = .connected(name: peripheral.name ?? "LEGO Hub")
        addLog("Ready.")
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard let data = characteristic.value else { return }
        addLog("<- " + data.hexString)
        if let event = LWP3.parseHubAttachedIO(data) {
            if event.attached {
                let typeHex = String(format: "%04x", event.ioTypeID ?? 0)
                addLog("Port \(LWP3.portName(event.port)): attached (IO type 0x\(typeHex))")
            } else {
                addLog("Port \(LWP3.portName(event.port)): detached")
            }
        }
    }
}

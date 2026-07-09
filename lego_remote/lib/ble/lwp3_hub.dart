import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_blue_plus/flutter_blue_plus.dart';

/// LEGO Wireless Protocol v3 (LWP3), used by SPIKE Prime/Essential,
/// Powered Up and Control+ hubs. Spec: https://lego.github.io/lego-ble-wireless-protocol-docs/
///
/// If the physical hub turns out to be an older WeDo 2.0 Smart Hub, only
/// this file needs to change: WeDo 2.0 uses a different GATT service
/// (0000f00e-...) and a simpler binary layout, not LWP3.
class Lwp3Hub {
  static final Guid serviceUuid =
      Guid('00001623-1212-efde-1623-785feabcd123');
  static final Guid characteristicUuid =
      Guid('00001624-1212-efde-1623-785feabcd123');

  static const int _msgHubProperty = 0x01;
  static const int _msgPortOutputCommand = 0x81;
  static const int _msgHubAttachedIO = 0x04;

  static const int _propertyBattery = 0x06;

  static const int _subcommandEnableUpdates = 0x02;

  final BluetoothDevice device;
  BluetoothCharacteristic? _characteristic;
  StreamSubscription<List<int>>? _notifySub;

  final Map<int, String> _attachedPorts = {};
  final _batteryController = StreamController<int>.broadcast();
  final _connectionStateController =
      StreamController<BluetoothConnectionState>.broadcast();

  Stream<int> get batteryLevel => _batteryController.stream;
  Stream<BluetoothConnectionState> get connectionState =>
      _connectionStateController.stream;
  Map<int, String> get attachedPorts => Map.unmodifiable(_attachedPorts);

  Lwp3Hub(this.device) {
    device.connectionState.listen((state) {
      _connectionStateController.add(state);
      if (state == BluetoothConnectionState.disconnected) {
        _notifySub?.cancel();
      }
    });
  }

  Future<void> connect() async {
    await device.connect(
      license: License.nonprofit,
      timeout: const Duration(seconds: 10),
    );
    final services = await device.discoverServices();
    final service = services.firstWhere(
      (s) => s.uuid == serviceUuid,
      orElse: () => throw StateError(
          'LEGO hub service not found on this device — it may not be an LWP3 hub.'),
    );
    _characteristic = service.characteristics.firstWhere(
      (c) => c.uuid == characteristicUuid,
    );
    await _characteristic!.setNotifyValue(true);
    _notifySub = _characteristic!.onValueReceived.listen(_handleNotification);
    await requestBatteryUpdates();
  }

  Future<void> disconnect() async {
    try {
      await setMotorPower(0, 0);
    } catch (_) {
      // Best-effort stop; device may already be gone.
    }
    await device.disconnect();
  }

  /// Sets power for the left/right drive motors, each in range -100..100.
  /// Port numbers 0 and 1 are the common default for a two-motor drive
  /// base; adjust if the hub attaches motors on different ports.
  Future<void> setMotorPower(int leftPower, int rightPower,
      {int leftPort = 0, int rightPort = 1}) async {
    await _sendPortOutputPower(leftPort, leftPower);
    await _sendPortOutputPower(rightPort, rightPower);
  }

  Future<void> stopAll() => setMotorPower(0, 0);

  Future<void> requestBatteryUpdates() async {
    final payload = Uint8List.fromList([
      _msgHubProperty,
      _propertyBattery,
      _subcommandEnableUpdates,
    ]);
    await _write(payload);
  }

  Future<void> _sendPortOutputPower(int port, int power) async {
    final clamped = power.clamp(-100, 100);
    final payload = Uint8List.fromList([
      _msgPortOutputCommand,
      port,
      0x11, // startup: immediate execution, no completion feedback
      0x51, // subcommand: WriteDirectModeData
      0x00, // mode 0 (power)
      clamped & 0xFF,
    ]);
    await _write(payload);
  }

  Future<void> _write(Uint8List payload) async {
    final characteristic = _characteristic;
    if (characteristic == null) {
      throw StateError('Not connected to a hub yet.');
    }
    final message = Uint8List(payload.length + 2);
    message[0] = message.length;
    message[1] = 0x00; // hub id, always 0
    message.setRange(2, message.length, payload);
    await characteristic.write(message, withoutResponse: true);
  }

  void _handleNotification(List<int> data) {
    if (data.length < 3) return;
    final messageType = data[2];
    switch (messageType) {
      case _msgHubAttachedIO:
        if (data.length >= 5) {
          final port = data[3];
          final event = data[4];
          if (event == 0x00) {
            _attachedPorts.remove(port);
          } else {
            _attachedPorts[port] = 'device 0x${data.length > 5 ? data[5].toRadixString(16) : '?'}';
          }
        }
        break;
      case _msgHubProperty:
        if (data.length >= 5 && data[3] == _propertyBattery) {
          _batteryController.add(data[5]);
        }
        break;
    }
  }

  Future<void> dispose() async {
    await _notifySub?.cancel();
    await _batteryController.close();
    await _connectionStateController.close();
  }
}

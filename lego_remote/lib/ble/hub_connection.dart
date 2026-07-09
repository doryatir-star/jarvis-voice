import 'dart:async';

import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';

import 'lwp3_hub.dart';

/// Owns the BLE scan lifecycle and the current hub connection so screens
/// don't talk to flutter_blue_plus directly.
class HubConnectionManager {
  Lwp3Hub? _hub;
  Lwp3Hub? get hub => _hub;

  Future<bool> requestPermissions() async {
    final statuses = await [
      Permission.bluetoothScan,
      Permission.bluetoothConnect,
      Permission.locationWhenInUse,
    ].request();
    return statuses.values.every((s) => s.isGranted || s.isLimited);
  }

  Stream<List<ScanResult>> startScan() {
    FlutterBluePlus.startScan(
      withServices: [Lwp3Hub.serviceUuid],
      timeout: const Duration(seconds: 15),
    );
    return FlutterBluePlus.scanResults;
  }

  Future<void> stopScan() => FlutterBluePlus.stopScan();

  Future<Lwp3Hub> connectTo(BluetoothDevice device) async {
    await stopScan();
    final hub = Lwp3Hub(device);
    await hub.connect();
    _hub = hub;
    return hub;
  }

  Future<void> disconnect() async {
    await _hub?.disconnect();
    await _hub?.dispose();
    _hub = null;
  }
}

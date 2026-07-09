import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import '../ble/hub_connection.dart';
import '../ble/lwp3_hub.dart';
import '../widgets/dpad_controls.dart';
import '../widgets/joystick.dart';
import '../widgets/status_bar.dart';

class RemoteScreen extends StatefulWidget {
  final Lwp3Hub hub;
  final String deviceName;
  final HubConnectionManager connection;

  const RemoteScreen({
    super.key,
    required this.hub,
    required this.deviceName,
    required this.connection,
  });

  @override
  State<RemoteScreen> createState() => _RemoteScreenState();
}

class _RemoteScreenState extends State<RemoteScreen> with WidgetsBindingObserver {
  bool _useJoystick = true;
  int? _batteryPercent;
  Timer? _sendTimer;
  int _pendingLeft = 0;
  int _pendingRight = 0;
  StreamSubscription<int>? _batterySub;
  StreamSubscription<BluetoothConnectionState>? _connectionSub;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _batterySub = widget.hub.batteryLevel.listen((level) {
      if (mounted) setState(() => _batteryPercent = level);
    });
    _connectionSub = widget.hub.connectionState.listen((state) {
      if (state == BluetoothConnectionState.disconnected && mounted) {
        Navigator.of(context).popUntil((route) => route.isFirst);
      }
    });
    _sendTimer = Timer.periodic(const Duration(milliseconds: 120), (_) {
      widget.hub.setMotorPower(_pendingLeft, _pendingRight);
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      _drive(0, 0);
    }
  }

  void _drive(int left, int right) {
    _pendingLeft = left;
    _pendingRight = right;
  }

  Future<void> _disconnect() async {
    await widget.connection.disconnect();
    if (mounted) Navigator.of(context).pop();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _sendTimer?.cancel();
    _batterySub?.cancel();
    _connectionSub?.cancel();
    widget.hub.stopAll();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Drive'),
        actions: [
          IconButton(
            icon: Icon(_useJoystick ? Icons.gamepad : Icons.control_camera),
            tooltip: 'Switch control mode',
            onPressed: () => setState(() => _useJoystick = !_useJoystick),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              StatusBar(
                deviceName: widget.deviceName,
                batteryPercent: _batteryPercent,
                onDisconnect: _disconnect,
              ),
              const Spacer(),
              Center(
                child: _useJoystick
                    ? Joystick(
                        onChanged: (offset) {
                          final (left, right) = tankMix(offset);
                          _drive(left, right);
                        },
                      )
                    : DpadControls(onDrive: _drive),
              ),
              const Spacer(),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red.withOpacity(0.25),
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                  icon: const Icon(Icons.stop_circle, color: Colors.white),
                  label: const Text('STOP', style: TextStyle(color: Colors.white)),
                  onPressed: () => _drive(0, 0),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import '../ble/hub_connection.dart';
import 'remote_screen.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _connection = HubConnectionManager();
  List<ScanResult> _results = [];
  String? _error;
  bool _connecting = false;

  @override
  void initState() {
    super.initState();
    _startScan();
  }

  Future<void> _startScan() async {
    setState(() => _error = null);
    final granted = await _connection.requestPermissions();
    if (!granted) {
      setState(() => _error =
          'Bluetooth/location permission was denied. Enable it in system settings to scan for the hub.');
      return;
    }
    if (!await FlutterBluePlus.isSupported) {
      setState(() => _error = 'This device does not support Bluetooth LE.');
      return;
    }
    _connection.startScan().listen(
      (results) => setState(() => _results = results),
      onError: (e) => setState(() => _error = e.toString()),
    );
  }

  Future<void> _connect(ScanResult result) async {
    setState(() => _connecting = true);
    try {
      final hub = await _connection.connectTo(result.device);
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => RemoteScreen(
            hub: hub,
            deviceName: result.device.platformName.isNotEmpty
                ? result.device.platformName
                : 'LEGO Hub',
            connection: _connection,
          ),
        ),
      );
      _startScan();
    } catch (e) {
      setState(() => _error = 'Could not connect: $e');
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  @override
  void dispose() {
    _connection.stopScan();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Find your LEGO robot')),
      body: Column(
        children: [
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(_error!, style: const TextStyle(color: Colors.redAccent)),
            ),
          const Padding(
            padding: EdgeInsets.all(16),
            child: Row(
              children: [
                SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Scanning for hubs (power it on so it is advertising)...',
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: _results.isEmpty
                ? const Center(child: Text('No hubs found yet.'))
                : ListView.builder(
                    itemCount: _results.length,
                    itemBuilder: (context, index) {
                      final result = _results[index];
                      final name = result.device.platformName.isNotEmpty
                          ? result.device.platformName
                          : 'Unknown LEGO hub';
                      return ListTile(
                        leading: const Icon(Icons.bluetooth),
                        title: Text(name),
                        subtitle: Text(result.device.remoteId.toString()),
                        trailing: _connecting
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.chevron_right),
                        onTap: _connecting ? null : () => _connect(result),
                      );
                    },
                  ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _startScan,
        child: const Icon(Icons.refresh),
      ),
    );
  }
}

import 'package:flutter/material.dart';

class StatusBar extends StatelessWidget {
  final String deviceName;
  final int? batteryPercent;
  final VoidCallback onDisconnect;

  const StatusBar({
    super.key,
    required this.deviceName,
    required this.batteryPercent,
    required this.onDisconnect,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.bluetooth_connected, color: Colors.lightBlueAccent),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              deviceName,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: Colors.white, fontSize: 14),
            ),
          ),
          if (batteryPercent != null) ...[
            Icon(
              batteryPercent! > 20
                  ? Icons.battery_std
                  : Icons.battery_alert,
              color: batteryPercent! > 20 ? Colors.greenAccent : Colors.redAccent,
              size: 18,
            ),
            const SizedBox(width: 4),
            Text('$batteryPercent%',
                style: const TextStyle(color: Colors.white70, fontSize: 13)),
            const SizedBox(width: 12),
          ],
          IconButton(
            icon: const Icon(Icons.link_off, color: Colors.white70),
            tooltip: 'Disconnect',
            onPressed: onDisconnect,
          ),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';

import 'screens/scan_screen.dart';

void main() {
  runApp(const LegoRemoteApp());
}

class LegoRemoteApp extends StatelessWidget {
  const LegoRemoteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'LEGO Remote',
      theme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.orange,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFF0E0E12),
      ),
      home: const ScanScreen(),
    );
  }
}

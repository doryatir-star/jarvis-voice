import 'package:flutter/material.dart';

enum DpadDirection { forward, backward, left, right, stop }

/// Simple press-and-hold direction buttons, as an alternative to the
/// joystick. Reports motor power (-100..100) via [onDrive] on press,
/// and (0, 0) on release.
class DpadControls extends StatelessWidget {
  final void Function(int left, int right) onDrive;
  final int power;

  const DpadControls({super.key, required this.onDrive, this.power = 70});

  void _press(DpadDirection direction) {
    switch (direction) {
      case DpadDirection.forward:
        onDrive(power, power);
        break;
      case DpadDirection.backward:
        onDrive(-power, -power);
        break;
      case DpadDirection.left:
        onDrive(-power, power);
        break;
      case DpadDirection.right:
        onDrive(power, -power);
        break;
      case DpadDirection.stop:
        onDrive(0, 0);
        break;
    }
  }

  Widget _button(BuildContext context, IconData icon, DpadDirection direction,
      {Color? color}) {
    return GestureDetector(
      onTapDown: (_) => _press(direction),
      onTapUp: (_) => onDrive(0, 0),
      onTapCancel: () => onDrive(0, 0),
      child: Container(
        width: 72,
        height: 72,
        decoration: BoxDecoration(
          color: color ?? Colors.white.withOpacity(0.08),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white24),
        ),
        child: Icon(icon, size: 32, color: Colors.white),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _button(context, Icons.keyboard_arrow_up, DpadDirection.forward),
        const SizedBox(height: 8),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _button(context, Icons.keyboard_arrow_left, DpadDirection.left),
            const SizedBox(width: 8),
            _button(
              context,
              Icons.stop_rounded,
              DpadDirection.stop,
              color: Colors.red.withOpacity(0.3),
            ),
            const SizedBox(width: 8),
            _button(context, Icons.keyboard_arrow_right, DpadDirection.right),
          ],
        ),
        const SizedBox(height: 8),
        _button(context, Icons.keyboard_arrow_down, DpadDirection.backward),
      ],
    );
  }
}

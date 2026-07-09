import 'dart:math';

import 'package:flutter/material.dart';

/// A draggable joystick. Reports normalized (x, y) in -1.0..1.0, where
/// y = -1 is fully forward and x = -1 is fully left, via [onChanged].
/// Snaps back to center and calls [onChanged](0, 0) on release.
class Joystick extends StatefulWidget {
  final ValueChanged<Offset> onChanged;
  final double size;

  const Joystick({super.key, required this.onChanged, this.size = 220});

  @override
  State<Joystick> createState() => _JoystickState();
}

class _JoystickState extends State<Joystick> {
  Offset _knobPosition = Offset.zero;

  void _updateFromLocal(Offset localPosition) {
    final center = Offset(widget.size / 2, widget.size / 2);
    final radius = widget.size / 2;
    var delta = localPosition - center;
    if (delta.distance > radius) {
      delta = Offset.fromDirection(delta.direction, radius);
    }
    setState(() => _knobPosition = delta);
    widget.onChanged(Offset(
      (delta.dx / radius).clamp(-1.0, 1.0),
      (delta.dy / radius).clamp(-1.0, 1.0),
    ));
  }

  void _reset() {
    setState(() => _knobPosition = Offset.zero);
    widget.onChanged(Offset.zero);
  }

  @override
  Widget build(BuildContext context) {
    final knobRadius = widget.size * 0.18;
    return GestureDetector(
      onPanStart: (details) => _updateFromLocal(details.localPosition),
      onPanUpdate: (details) => _updateFromLocal(details.localPosition),
      onPanEnd: (_) => _reset(),
      onPanCancel: _reset,
      child: Container(
        width: widget.size,
        height: widget.size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: Colors.white.withOpacity(0.06),
          border: Border.all(color: Colors.white24, width: 2),
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            const Icon(Icons.circle, size: 4, color: Colors.white24),
            Transform.translate(
              offset: _knobPosition,
              child: Container(
                width: knobRadius * 2,
                height: knobRadius * 2,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Theme.of(context).colorScheme.primary,
                  boxShadow: [
                    BoxShadow(
                      color: Theme.of(context)
                          .colorScheme
                          .primary
                          .withOpacity(0.5),
                      blurRadius: 12,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Mixes a normalized joystick (x, y) into left/right tank-drive motor
/// power values in -100..100. y = -1 (up) is full forward.
(int left, int right) tankMix(Offset joystick) {
  final throttle = -joystick.dy;
  final steer = joystick.dx;
  var left = throttle + steer;
  var right = throttle - steer;
  final maxMag = max(left.abs(), right.abs());
  if (maxMag > 1.0) {
    left /= maxMag;
    right /= maxMag;
  }
  return (
    (left * 100).round().clamp(-100, 100),
    (right * 100).round().clamp(-100, 100),
  );
}

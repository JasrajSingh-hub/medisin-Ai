import 'package:flutter/material.dart';

class AvatarPosePainter extends CustomPainter {
  final Map<String, dynamic> joints;

  AvatarPosePainter({required this.joints});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF68F5B8)
      ..strokeWidth = 3.0
      ..strokeCap = StrokeCap.round;

    joints.forEach((key, val) {
      if (val is Map && val.containsKey('x') && val.containsKey('y')) {
        final x = (val['x'] as num).toDouble() * size.width;
        final y = (val['y'] as num).toDouble() * size.height;
        canvas.drawCircle(Offset(x, y), 5.0, paint);
      }
    });
  }

  @override
  bool shouldRepaint(covariant AvatarPosePainter oldDelegate) {
    return oldDelegate.joints != joints;
  }
}

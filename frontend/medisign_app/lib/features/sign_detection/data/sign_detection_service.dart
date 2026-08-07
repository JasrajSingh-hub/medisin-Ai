import 'dart:convert';
import 'dart:math' as math;

import 'package:http/http.dart' as http;

import '../../../core/config/backend_endpoints.dart';

class SignPrediction {
  const SignPrediction({
    required this.letter,
    required this.confidence,
    required this.landmarks,
  });

  final String letter;
  final String confidence;
  final List<List<Map<String, double>>> landmarks;

  bool get isUnknown => letter.trim().toLowerCase() == 'unknown';

  String get displayText => isUnknown
      ? 'Detected Sign: Unknown ($confidence)'
      : 'Detected Sign: $letter ($confidence)';

  bool get hasLandmarks => landmarks.isNotEmpty;

  factory SignPrediction.fromJson(Map<String, dynamic> json) {
    final rawLandmarks = List<dynamic>.from(json['landmarks'] ?? const []);
    return SignPrediction(
      letter: json['letter']?.toString() ?? '',
      confidence: json['confidence']?.toString() ?? '',
      landmarks: rawLandmarks
          .map((hand) => List<dynamic>.from(hand as List)
              .map((point) => Map<String, double>.from(
                    (point as Map).map(
                      (key, value) => MapEntry(key.toString(), (value as num).toDouble()),
                    ),
                  ))
              .toList())
          .toList(),
    );
  }
}

class SignDetectionService {
  const SignDetectionService();

  Future<SignPrediction?> predictFromImageBytes(List<int> imageBytes) async {
    final imageDataUri = 'data:image/jpeg;base64,${base64Encode(imageBytes)}';
    final response = await http.post(
      Uri.parse(BackendEndpoints.signPrediction),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'image': imageDataUri}),
    );

    if (response.statusCode != 200) {
      String backendDetail = response.body;
      try {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        backendDetail = body['detail']?.toString() ?? backendDetail;
      } catch (_) {}
      throw Exception(
        'Image prediction failed (${response.statusCode}): $backendDetail',
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return SignPrediction.fromJson(data);
  }

  Future<SignPrediction?> predictFromLandmarks(List<double> landmarks126) async {
    final response = await http.post(
      Uri.parse(BackendEndpoints.signPredictionLandmarks),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'landmarks': landmarks126}),
    );

    if (response.statusCode != 200) {
      String backendDetail = response.body;
      try {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        backendDetail = body['detail']?.toString() ?? backendDetail;
      } catch (_) {}
      throw Exception(
        'Landmark prediction failed (${response.statusCode}): $backendDetail',
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return SignPrediction.fromJson(data);
  }

  List<double> build126Vector(List<List<Map<String, double>>> hands) {
    final vector126 = List<double>.filled(126, 0.0);
    if (hands.isEmpty) return vector126;

    final handCount = math.min(2, hands.length);
    for (var handIndex = 0; handIndex < handCount; handIndex++) {
      final keypoints = hands[handIndex];
      if (keypoints.length < 21) continue;

      final wristX = keypoints[0]['x'] ?? 0.0;
      final wristY = keypoints[0]['y'] ?? 0.0;
      final wristZ = keypoints[0]['z'] ?? 0.0;

      final centered = <List<double>>[];
      var maxDist = 0.00001;
      for (final point in keypoints) {
        final dx = (point['x'] ?? 0.0) - wristX;
        final dy = (point['y'] ?? 0.0) - wristY;
        final dz = (point['z'] ?? 0.0) - wristZ;
        final dist = dx * dx + dy * dy + dz * dz;
        if (dist > maxDist) maxDist = dist;
        centered.add([dx, dy, dz]);
      }

      final offset = handIndex * 63;
      for (var i = 0; i < 21; i++) {
        vector126[offset + i * 3] = centered[i][0] / maxDist;
        vector126[offset + i * 3 + 1] = centered[i][1] / maxDist;
        vector126[offset + i * 3 + 2] = centered[i][2] / maxDist;
      }
    }

    return vector126;
  }
}

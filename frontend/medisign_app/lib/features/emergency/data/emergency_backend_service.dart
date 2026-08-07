import 'dart:convert';
import 'dart:typed_data';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../../../core/config/backend_endpoints.dart';

class EmergencyPrediction {
  const EmergencyPrediction({
    required this.label,
    required this.confidence,
    required this.isEmergency,
    required this.probabilities,
  });

  final String label;
  final double confidence;
  final bool isEmergency;
  final Map<String, double> probabilities;

  factory EmergencyPrediction.fromJson(Map<String, dynamic> json) {
    final probabilities = <String, double>{};
    final rawProbabilities = json['probabilities'];
    if (rawProbabilities is Map) {
      rawProbabilities.forEach((key, value) {
        probabilities[key.toString()] = (value as num?)?.toDouble() ?? 0.0;
      });
    }

    return EmergencyPrediction(
      label: json['label']?.toString() ?? 'Unknown',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      isEmergency: json['is_emergency'] as bool? ?? false,
      probabilities: probabilities,
    );
  }
}

class NearbyHospital {
  const NearbyHospital({
    required this.name,
    required this.latitude,
    required this.longitude,
    required this.distanceMeters,
  });

  final String name;
  final double latitude;
  final double longitude;
  final double distanceMeters;
}

class EmergencyBackendService {
  const EmergencyBackendService();

  static const List<Map<String, Object>> _fallbackHospitals = [
    {'name': 'AIIMS Hospital', 'lat': 28.5672, 'lng': 77.2100, 'distance_m': 0.0},
    {'name': 'Safdarjung Hospital', 'lat': 28.5680, 'lng': 77.2070, 'distance_m': 0.0},
    {'name': 'Apollo Hospital', 'lat': 28.5665, 'lng': 77.2200, 'distance_m': 0.0},
    {'name': 'Max Super Speciality Hospital', 'lat': 28.5400, 'lng': 77.2500, 'distance_m': 0.0},
    {'name': 'Fortis Hospital', 'lat': 28.5425, 'lng': 77.1539, 'distance_m': 0.0},
  ];

  Future<bool> checkHealth() async {
    final response = await http.get(Uri.parse(BackendEndpoints.emergencyHealth));
    debugPrint('Emergency backend health status: ${response.statusCode}');
    return response.statusCode == 200;
  }

  Future<EmergencyPrediction> predictFromBytes(Uint8List imageBytes) async {
    final request = http.MultipartRequest('POST', Uri.parse(BackendEndpoints.emergencyPredict));
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        imageBytes,
        filename: 'emergency.jpg',
        contentType: MediaType('image', 'jpeg'),
      ),
    );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);
    debugPrint('Emergency backend predict response: ${response.statusCode}');
    if (response.statusCode != 200) {
      String errorMessage = 'Failed to predict emergency gesture';
      try {
        final errorBody = jsonDecode(response.body) as Map<String, dynamic>;
        errorMessage = errorBody['detail']?.toString() ?? errorMessage;
      } catch (_) {
        errorMessage = response.body;
      }
      throw Exception(errorMessage);
    }

    return EmergencyPrediction.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<List<NearbyHospital>> fetchNearbyHospitals({
    required double latitude,
    required double longitude,
  }) async {
    final url = '${BackendEndpoints.emergencyHealth.replaceAll('/health', '')}/nearby-hospitals?lat=$latitude&lng=$longitude';
    try {
      final response = await http.get(Uri.parse(url));
      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        final hospitals = data.map((item) => NearbyHospital(
          name: item['name']?.toString() ?? 'Hospital',
          latitude: (item['lat'] as num?)?.toDouble() ?? latitude,
          longitude: (item['lng'] as num?)?.toDouble() ?? longitude,
          distanceMeters: (item['distance_m'] as num?)?.toDouble() ?? 0.0,
        )).toList();
        if (hospitals.isNotEmpty) return hospitals;
      }
    } catch (_) {}

    return _fallbackHospitals.map((item) {
      final hospitalLatitude = (item['lat'] as num).toDouble();
      final hospitalLongitude = (item['lng'] as num).toDouble();
      return NearbyHospital(
        name: item['name'].toString(),
        latitude: hospitalLatitude,
        longitude: hospitalLongitude,
        distanceMeters: _distanceMeters(
          latitude: latitude,
          longitude: longitude,
          otherLatitude: hospitalLatitude,
          otherLongitude: hospitalLongitude,
        ),
      );
    }).toList();
  }

  double _distanceMeters({
    required double latitude,
    required double longitude,
    required double otherLatitude,
    required double otherLongitude,
  }) {
    const earthRadius = 6371000.0;
    final dLat = _degToRad(otherLatitude - latitude);
    final dLng = _degToRad(otherLongitude - longitude);
    final a = 
        (math.sin(dLat / 2) * math.sin(dLat / 2)) +
        math.cos(_degToRad(latitude)) *
            math.cos(_degToRad(otherLatitude)) *
            (math.sin(dLng / 2) * math.sin(dLng / 2));
    final c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
    return earthRadius * c;
  }

  double _degToRad(double degree) => degree * (math.pi / 180.0);
}

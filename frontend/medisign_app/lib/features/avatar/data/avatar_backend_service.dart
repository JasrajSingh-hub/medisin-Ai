import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

import '../../../core/config/backend_endpoints.dart';

class AvatarBackendService {
  const AvatarBackendService();

  Future<Map<String, dynamic>> loadCoordinateLibrary() async {
    final jsonString = await rootBundle.loadString('assets/avatar_library.json');
    final decoded = jsonDecode(jsonString);
    if (decoded is Map) {
      return Map<String, dynamic>.from(decoded);
    }
    throw Exception('Avatar library must be a JSON object');
  }

  List<String> tokenizeText(String text) {
    final rawText = text.trim();
    if (rawText.isEmpty) {
      return const [];
    }

    final cleanText = rawText
        .toLowerCase()
        .replaceAll(RegExp(r'[^\w\s]'), '');
    final words = cleanText.split(RegExp(r'\s+')).where((word) => word.isNotEmpty);

    final tokens = <String>[];
    for (final word in words) {
      for (final letter in word.runes.map((rune) => String.fromCharCode(rune))) {
        if (RegExp(r'[a-zA-Z]').hasMatch(letter)) {
          tokens.add(letter.toUpperCase());
        }
      }
      tokens.add('SPACE');
    }

    if (tokens.isNotEmpty && tokens.last == 'SPACE') {
      tokens.removeLast();
    }

    return tokens;
  }
}

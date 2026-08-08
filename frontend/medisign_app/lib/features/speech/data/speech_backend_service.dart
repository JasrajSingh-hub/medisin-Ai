import 'dart:typed_data';

class VoiceOption {
  final String name;
  final String shortName;
  final String genderSymbol;
  final String locale;

  const VoiceOption({
    required this.name,
    required this.shortName,
    required this.genderSymbol,
    required this.locale,
  });
}

class SpeechBackendService {
  const SpeechBackendService();

  Future<List<VoiceOption>> fetchVoices() async {
    return [
      const VoiceOption(name: 'en-US-Wavenet-D', shortName: 'English (US) - D', genderSymbol: '♂', locale: 'en-US'),
      const VoiceOption(name: 'en-US-Wavenet-C', shortName: 'English (US) - C', genderSymbol: '♀', locale: 'en-US'),
      const VoiceOption(name: 'hi-IN-Wavenet-B', shortName: 'Hindi (IN) - B', genderSymbol: '♂', locale: 'hi-IN'),
    ];
  }

  String? resolvePreferredVoiceName(List<VoiceOption> voices) {
    if (voices.isEmpty) return null;
    return voices.first.name;
  }

  String resolveLanguage({required List<VoiceOption> voices, String? selectedVoiceName}) {
    if (selectedVoiceName == null) return 'en-US';
    final match = voices.firstWhere((v) => v.name == selectedVoiceName, orElse: () => voices.first);
    return match.locale;
  }

  Future<Uint8List> synthesizeSpeech({required String text, required String language}) async {
    // Return empty sound bytes for stub
    return Uint8List(0);
  }

  Future<String> transcribeAudio({required Uint8List audioBytes, required String language}) async {
    return 'Transcribed audio input successfully';
  }
}

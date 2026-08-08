import 'dart:io';

class BackendEndpoints {
  const BackendEndpoints._();

  static String get _baseUrl => 'https://medisin-ai-p9q1.onrender.com';
  static String get moduleBBaseUrl => _baseUrl;

  static String get signPrediction => '$_baseUrl/predict';
  static String get signPredictionLandmarks => '$_baseUrl/predict_landmarks';
  static String get avatarParse => '$_baseUrl/api/v1/avatar/parse';
  static String get ttsVoices => '$_baseUrl/api/v1/tts/voices';
  static String get ttsSpeak => '$_baseUrl/api/v1/tts/speak';
  static String get sttTranscribe => '$_baseUrl/api/v1/stt/transcribe';
  static String get emergencyHealth => '$_baseUrl/api/v1/emergency/health';
  static String get emergencyStatus => '$_baseUrl/api/v1/emergency/status';
  static String get emergencyPredict => '$_baseUrl/api/v1/emergency/predict';
  static String get moduleBHealth => '$_baseUrl/health';
  static String get moduleBOcrAudit => '$_baseUrl/api/v1/prescription/ocr-audit';
}

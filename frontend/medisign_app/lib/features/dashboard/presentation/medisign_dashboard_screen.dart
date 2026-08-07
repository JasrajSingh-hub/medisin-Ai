import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:path/path.dart' as path;
import 'package:record/record.dart';
import 'package:hand_landmarker/hand_landmarker.dart';

import '../../../core/utils/web_camera_helper.dart';
import '../../avatar/data/avatar_backend_service.dart';
import '../../avatar/presentation/avatar_pose_painter.dart';
import '../../sign_detection/data/sign_detection_service.dart';
import '../../speech/data/speech_backend_service.dart';

class MediSignDashboardScreen extends StatefulWidget {
  const MediSignDashboardScreen({
    super.key,
    required this.availableCameras,
  });

  final List<CameraDescription> availableCameras;

  @override
  State<MediSignDashboardScreen> createState() => _MediSignDashboardScreenState();
}

class _MediSignDashboardScreenState extends State<MediSignDashboardScreen> {
  final SpeechBackendService _speechService = const SpeechBackendService();
  final SignDetectionService _signDetectionService = const SignDetectionService();
  final AvatarBackendService _avatarService = const AvatarBackendService();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final AudioRecorder _audioRecorder = AudioRecorder();
  final TextEditingController _speechController = TextEditingController();
  final TextEditingController _avatarController = TextEditingController();

  CameraController? _cameraController;
  HandLandmarkerPlugin? _handLandmarker;
  StreamSubscription<List<Hand>>? _landmarkSubscription;
  Timer? _frameTimer;
  Timer? _avatarPlaybackTimer;
  int _activeCameraIndex = 0;

  bool _cameraReady = false;
  bool _processing = false;
  bool _isDetectingHands = false;
  bool _isSpeaking = false;
  bool _isRecording = false;
  bool _isTranscribing = false;
  bool _isLoadingVoices = false;
  bool _isLoadingAvatarLibrary = false;
  bool _isParsingAvatarText = false;
  bool _isPlayingAvatar = false;
  String? _cameraError;
  String? _recordingPath;
  String? _selectedVoiceName;
  String _predictionText = 'Waiting for clinician sign language input...';
  String _currentPredictedLetter = '';
  String _avatarPreviewText = 'Type above to preview a sign pose.';
  List<List<Map<String, double>>> _latestHands = [];
  List<VoiceOption> _voices = [];
  Map<String, dynamic> _avatarLibrary = {};
  Map<String, dynamic> _currentAvatarJoints = {};
  List<String> _activeAvatarTokens = [];
  int _currentAvatarTokenIndex = 0;
  String _currentAvatarToken = '';

  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _loadVoices();
    _loadAvatarLibrary();
  }

  @override
  void dispose() {
    _frameTimer?.cancel();
    _avatarPlaybackTimer?.cancel();
    _landmarkSubscription?.cancel();
    _handLandmarker?.dispose();
    _cameraController?.dispose();
    _speechController.dispose();
    _avatarController.dispose();
    _audioPlayer.dispose();
    _audioRecorder.dispose();
    super.dispose();
  }

  Future<void> _initializeCamera() async {
    String? permissionError;
    if (kIsWeb) {
      try {
        await requestWebCameraPermission();
      } catch (error) {
        permissionError = '$error';
      }
    }

    final cameras = widget.availableCameras.isNotEmpty ? widget.availableCameras : await availableCameras();
    if (cameras.isEmpty) {
      if (mounted) {
        setState(() => _cameraError = 'No camera found${permissionError != null ? ': $permissionError' : ''}');
      }
      return;
    }

    _activeCameraIndex = _activeCameraIndex.clamp(0, cameras.length - 1);
    final controller = CameraController(
      cameras[_activeCameraIndex],
      ResolutionPreset.low,
      enableAudio: false,
    );

    try {
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _cameraController = controller;
        _cameraReady = true;
        _cameraError = null;
      });
      _initializeHandLandmarker();
      await controller.startImageStream(_handleCameraImage);
      _frameTimer?.cancel();
      _frameTimer = Timer.periodic(const Duration(milliseconds: 350), (_) => _processFrame());
    } catch (error) {
      await controller.dispose();
      if (mounted) {
        setState(() => _cameraError = 'Camera init failed: $error');
      }
    }
  }

  Future<void> _switchCamera() async {
    final cameras = widget.availableCameras.isNotEmpty ? widget.availableCameras : await availableCameras();
    if (cameras.length < 2) {
      _showSnackBar('No alternate camera available.');
      return;
    }

    _frameTimer?.cancel();
    final controller = _cameraController;
    _cameraController = null;
    setState(() => _cameraReady = false);

    if (controller != null) {
      if (controller.value.isStreamingImages) {
        await controller.stopImageStream();
      }
      await controller.dispose();
    }

    _activeCameraIndex = (_activeCameraIndex + 1) % cameras.length;
    await _initializeCamera();
  }

  Future<void> _initializeHandLandmarker() async {
    await _landmarkSubscription?.cancel();
    _handLandmarker?.dispose();
    _handLandmarker = HandLandmarkerPlugin.create(
      numHands: 2,
      minHandDetectionConfidence: 0.7,
      delegate: HandLandmarkerDelegate.gpu,
    );
    _landmarkSubscription = _handLandmarker!.landmarkStream.listen((hands) {
      if (!mounted) return;
      setState(() {
        _latestHands = hands
            .map((hand) => hand.landmarks
                .map((landmark) => <String, double>{
                      'x': landmark.x,
                      'y': landmark.y,
                      'z': landmark.z,
                    })
                .toList())
            .toList();
      });
    }, onError: (error) {
      debugPrint('Hand landmark stream failed: $error');
    });
  }

  void _handleCameraImage(CameraImage image) {
    final controller = _cameraController;
    final handLandmarker = _handLandmarker;
    if (controller == null || handLandmarker == null || _isDetectingHands) {
      return;
    }

    _isDetectingHands = true;
    try {
      handLandmarker.processFrame(
        image,
        controller.description.sensorOrientation,
      );
    } catch (error) {
      debugPrint('Hand landmark processing failed: $error');
    } finally {
      _isDetectingHands = false;
    }
  }

  Future<void> _processFrame() async {
    final controller = _cameraController;
    final handLandmarker = _handLandmarker;
    if (_processing || controller == null || handLandmarker == null || !controller.value.isInitialized) {
      return;
    }

    setState(() => _processing = true);
    try {
      final hands = _latestHands;
      if (hands.isEmpty) {
        return;
      }

      final landmarkVector = _signDetectionService.build126Vector(hands);
      final prediction = await _signDetectionService.predictFromLandmarks(landmarkVector);
      if (!mounted || prediction == null) return;
      setState(() {
        _predictionText = prediction.displayText;
        _currentPredictedLetter = prediction.isUnknown ? '-' : prediction.letter;
      });
    } catch (error) {
      debugPrint('Frame processing failed: $error');
    } finally {
      if (mounted) setState(() => _processing = false);
    }
  }

  Future<void> _loadVoices() async {
    setState(() => _isLoadingVoices = true);
    try {
      final voices = await _speechService.fetchVoices();
      if (!mounted) return;
      setState(() {
        _voices = voices;
        _selectedVoiceName ??= voices.isNotEmpty ? _speechService.resolvePreferredVoiceName(voices) : null;
      });
    } catch (_) {
      if (mounted) _showSnackBar('Failed to load voices');
    } finally {
      if (mounted) setState(() => _isLoadingVoices = false);
    }
  }

  Future<void> _loadAvatarLibrary() async {
    setState(() => _isLoadingAvatarLibrary = true);
    try {
      final library = await _avatarService.loadCoordinateLibrary();
      if (!mounted) return;
      setState(() => _avatarLibrary = library);
    } catch (error) {
      debugPrint('Avatar library load failed: $error');
    } finally {
      if (mounted) setState(() => _isLoadingAvatarLibrary = false);
    }
  }

  void _updateAvatarPreview(String text) {
    final tokens = _avatarService.tokenizeText(text);
    final availableTokens = tokens.where((token) => token != 'SPACE' && _avatarLibrary[token] is List).toList();
    _avatarPlaybackTimer?.cancel();
    setState(() {
      _activeAvatarTokens = availableTokens;
      _currentAvatarTokenIndex = 0;
      _currentAvatarToken = '';
      _avatarPreviewText = tokens.isEmpty
          ? 'Type above to preview a sign pose.'
          : 'Tokens: ${tokens.join(' ')}';
      _currentAvatarJoints = {};
    });

    if (availableTokens.isNotEmpty) {
      _applyAvatarTokenFrame(availableTokens.first);
      _avatarPlaybackTimer = Timer.periodic(const Duration(milliseconds: 850), (_) {
        if (!mounted || _activeAvatarTokens.isEmpty) return;
        _currentAvatarTokenIndex = (_currentAvatarTokenIndex + 1) % _activeAvatarTokens.length;
        _applyAvatarTokenFrame(_activeAvatarTokens[_currentAvatarTokenIndex]);
      });
    }
  }

  void _applyAvatarTokenFrame(String token) {
    final libraryEntry = _avatarLibrary[token];
    if (libraryEntry is! List || libraryEntry.isEmpty) return;

    final firstFrame = libraryEntry.first;
    if (firstFrame is! Map<String, dynamic>) return;

    setState(() {
      _currentAvatarToken = token;
      _currentAvatarJoints = firstFrame;
    });
  }

  Future<void> _convertTextToAvatar() async {
    final text = _avatarController.text.trim();
    if (text.isEmpty) {
      _showSnackBar('Type a sentence first.');
      return;
    }

    setState(() {
      _isParsingAvatarText = true;
    });

    try {
      _updateAvatarPreview(text);
    } catch (error) {
      _showSnackBar('Avatar conversion failed: $error');
    } finally {
      if (mounted) setState(() => _isParsingAvatarText = false);
    }
  }

  Future<void> _speakText() async {
    final text = _speechController.text.trim();
    if (text.isEmpty) return;
    setState(() => _isSpeaking = true);
    try {
      final language = _speechService.resolveLanguage(voices: _voices, selectedVoiceName: _selectedVoiceName);
      final audioBytes = await _speechService.synthesizeSpeech(text: text, language: language);
      await _audioPlayer.play(BytesSource(audioBytes));
    } catch (error) {
      _showSnackBar('TTS Error: $error');
    } finally {
      if (mounted) setState(() => _isSpeaking = false);
    }
  }

  Future<void> _toggleRecording() async {
    if (_isRecording) {
      await _stopRecordingAndTranscribe();
    } else {
      await _startRecording();
    }
  }

  Future<void> _startRecording() async {
    if (!await _audioRecorder.hasPermission()) {
      _showSnackBar('Microphone permission denied');
      return;
    }
    const config = RecordConfig(encoder: AudioEncoder.pcm16bits, sampleRate: 16000, numChannels: 1);
    final recordingPath = path.join(Directory.systemTemp.path, 'medisign_dashboard_${DateTime.now().millisecondsSinceEpoch}.wav');
    await _audioRecorder.start(config, path: recordingPath);
    if (!mounted) return;
    setState(() {
      _isRecording = true;
      _recordingPath = recordingPath;
    });
  }

  Future<void> _stopRecordingAndTranscribe() async {
    setState(() {
      _isRecording = false;
      _isTranscribing = true;
    });
    try {
      final recordedPath = await _audioRecorder.stop() ?? _recordingPath;
      if (recordedPath == null || recordedPath.isEmpty) throw Exception('No audio recorded');
      final audioBytes = await File(recordedPath).readAsBytes();
      final language = _speechService.resolveLanguage(voices: _voices, selectedVoiceName: _selectedVoiceName);
      final text = await _speechService.transcribeAudio(audioBytes: audioBytes, language: language);
      if (!mounted) return;
      setState(() {
        _speechController.text = _speechController.text.isEmpty ? text : '${_speechController.text} $text';
      });
    } catch (error) {
      _showSnackBar('Transcription failed: $error');
    } finally {
      final recordedPath = _recordingPath;
      if (recordedPath != null) {
        try {
          await File(recordedPath).delete();
        } catch (_) {}
      }
      _recordingPath = null;
      if (mounted) setState(() => _isTranscribing = false);
    }
  }

  void _showSnackBar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.of(context).pushNamed('/emergency'),
        icon: const Icon(Icons.warning_amber_rounded),
        label: const Text('Emergency AI'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            AspectRatio(
              aspectRatio: 3 / 4,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(18),
                child: Container(
                  color: const Color(0xFF111827),
                  child: Stack(
                    children: [
                      Positioned.fill(
                        child: _cameraReady && _cameraController != null
                            ? CameraPreview(_cameraController!)
                            : const Center(child: CircularProgressIndicator()),
                      ),
                      Positioned(
                        top: 12,
                        right: 12,
                        child: FilledButton.icon(
                          onPressed: _switchCamera,
                          icon: const Icon(Icons.cameraswitch, size: 18),
                          label: const Text('Switch'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(_predictionText, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text('Current letter: $_currentPredictedLetter'),
            const SizedBox(height: 16),
            TextField(
              controller: _speechController,
              maxLines: 4,
              decoration: const InputDecoration(hintText: 'Type or speak a message...'),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _isSpeaking ? null : _speakText,
                    icon: const Icon(Icons.volume_up),
                    label: Text(_isSpeaking ? 'Speaking...' : 'Play Speech'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _isTranscribing ? null : _toggleRecording,
                    icon: Icon(_isRecording ? Icons.stop : Icons.mic),
                    label: Text(_isRecording ? 'Stop & Transcribe' : 'Record Speech'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF122031),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Text to Sign Avatar', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFFD5E4FA))),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _avatarController,
                    maxLines: 3,
                    onChanged: _updateAvatarPreview,
                    decoration: const InputDecoration(
                      hintText: 'Type a sentence to convert into sign poses...',
                    ),
                  ),
                  const SizedBox(height: 10),
                  FilledButton.icon(
                    onPressed: (_isParsingAvatarText || _isLoadingAvatarLibrary) ? null : _convertTextToAvatar,
                    icon: _isParsingAvatarText
                        ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.translate),
                    label: Text(_isParsingAvatarText ? 'Converting...' : 'Convert to Sign'),
                  ),
                  if (_currentAvatarToken.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text('Current sign token: $_currentAvatarToken', style: const TextStyle(color: Color(0xFFBBC9CD))),
                  ],
                  const SizedBox(height: 8),
                  Text(_avatarPreviewText, style: const TextStyle(color: Color(0xFFBBC9CD))),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF122031),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    height: 220,
                    child: CustomPaint(
                      painter: AvatarPosePainter(joints: _currentAvatarJoints),
                      child: Center(
                        child: Text(
                          _isLoadingAvatarLibrary
                              ? 'Loading avatar library...'
                              : (_currentAvatarJoints.isEmpty ? 'Convert text above to render a sign pose.' : 'Showing the first matching sign pose.'),
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Color(0xFFBBC9CD)),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

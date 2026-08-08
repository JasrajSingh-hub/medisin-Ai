import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'app/app_theme.dart';
import 'features/dashboard/presentation/medisign_dashboard_screen.dart';
import 'features/emergency/presentation/emergency_screen.dart';
import 'features/hub/presentation/feature_hub_screen.dart';
import 'features/prescription/presentation/prescription_screen.dart';
import 'features/speech/presentation/speech_screen.dart';
import 'features/vital_guard/presentation/vital_guard_screen.dart';

List<CameraDescription> _cameras = [];

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    _cameras = await availableCameras();
  } catch (e) {
    debugPrint('No cameras found: $e');
  }
  runApp(MediSignApp(availableCameras: _cameras));
}

class MediSignApp extends StatelessWidget {
  const MediSignApp({super.key, required this.availableCameras});

  final List<CameraDescription> availableCameras;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MediSign AI',
      theme: buildMediSignTheme(),
      initialRoute: '/',
      routes: {
        '/': (context) => FeatureHubScreen(availableCameras: availableCameras),
        '/sign': (context) => MediSignDashboardScreen(availableCameras: availableCameras),
        '/prescription': (context) => const PrescriptionScreen(),
        '/emergency': (context) => EmergencyScreen(availableCameras: availableCameras),
        '/speech': (context) => const SpeechScreen(),
        '/vital_guard': (context) => const VitalGuardScreen(),
      },
    );
  }
}

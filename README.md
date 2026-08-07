<<<<<<< HEAD
# medisin-Ai
=======
# MediSign AI

MediSign AI is a full-stack assistive communication app for clinical and emergency use.
It combines Flutter, FastAPI, computer vision, and a JSON-trained ISL model to support:

- sign-language detection
- text-to-sign avatar playback+
- speech input/output
- emergency gesture detection
- prescription OCR and triage support

## About The Project

MediSign AI is built for local-first deployment during development:

- the Flutter client runs on Android or an emulator
- Python backend services run on your laptop
- the frontend talks to those services over `127.0.0.1`
- for a physical Android device, use `adb reverse` so the phone can reach the local ports

The sign-language classifier is driven by the trained JSON artifact in `backend/models/isl_trained_model.json`.

## Key Features

- Real-time sign detection from camera input
- JSON-based ISL prediction with confidence scoring
- Tokenized text-to-sign avatar playback
- Speech-to-text and text-to-speech support
- Emergency gesture detection with hospital fallback display
- Prescription OCR and medication safety support

## Tech Stack

- Flutter
- Dart
- FastAPI
- Python
- OpenCV
- MediaPipe
- NumPy
- HTTP / REST APIs
- JSON and CSV for model/data storage

## Project Structure

- `backend/` - main FastAPI services, model loader, and trainer
- `frontend/medisign_app/` - Flutter mobile application
- `backend/models/` - trained model artifacts and runtime assets
- `backend/module_b_backend/` - prescription safety and triage support

## Step-by-Step Setup

### 1) Clone the repo

```powershell
git clone https://github.com/JasrajSingh-hub/medisin-Ai.git
cd medisin-Ai
```

### 2) Create the backend environment

```powershell
cd backend
python -m venv env
. .\env\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3) Get Flutter dependencies

```powershell
cd ..\frontend\medisign_app
flutter pub get
```

### 4) Optional: set up the prescription backend

```powershell
cd ..\..\backend\module_b_backend
python -m venv env
. .\env\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run The App

Open separate terminals for each service.

### Main sign backend

```powershell
cd backend
. .\env\Scripts\Activate.ps1
python app.py
```

### TTS and STT backend

```powershell
cd backend
. .\env\Scripts\Activate.ps1
python tts_service.py
```

### Prescription backend

```powershell
cd backend\module_b_backend
. .\env\Scripts\Activate.ps1
python main.py
```

### Flutter frontend

```powershell
cd frontend\medisign_app
flutter run
```

## USB / ADB Setup

If you are using a physical Android phone, forward the local backend ports:

```powershell
adb reverse tcp:5000 tcp:5000
adb reverse tcp:5001 tcp:5001
adb reverse tcp:8002 tcp:8002
```

If you enable extra services later, reverse those ports too.

## How It Works

1. The Flutter camera captures a frame.
2. The backend extracts hand landmarks or emergency features.
3. The JSON-trained ISL model predicts the sign.
4. The avatar converts tokens into sign poses.
5. Emergency and prescription flows show supporting clinical context.

## Troubleshooting

- `Connection refused` usually means the backend is not running or the port is wrong.
- If the phone cannot reach `127.0.0.1`, use `adb reverse` for USB debugging.
- If Flutter keeps stale build files, run `flutter clean` in `frontend/medisign_app` and then `flutter pub get`.
- If a Python package is missing, reinstall `backend/requirements.txt` inside the same virtual environment you use to run the backend.

## Notes

- The trained ISL model is stored as JSON in `backend/models/isl_trained_model.json`.
- Generated files, virtual environments, build outputs, and local caches should stay out of version control.
>>>>>>> c90c5af3 (Update docs, model flow, and emergency UI)

import sys
# Prevent MediaPipe from attempting to import optional TensorFlow components during feature extraction
sys.modules["tensorflow"] = None

import os
import gc
import json
import argparse
import cv2
import numpy as np
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor


def extract_frame_landmarks(image_rgb, pose, hands):
    """
    Extracts landmark features for a single RGB frame.
    Returns np.ndarray of shape (258,).
    """
    # 1. Pose Landmarks (132 values)
    pose_res = np.zeros(132, dtype=np.float32)
    results_pose = pose.process(image_rgb)
    if results_pose and results_pose.pose_landmarks:
        pose_res = np.array(
            [[lm.x, lm.y, lm.z, lm.visibility] for lm in results_pose.pose_landmarks.landmark],
            dtype=np.float32
        ).flatten()

    # 2. Hand Landmarks (63 left + 63 right = 126 values)
    left_hand_res = np.zeros(63, dtype=np.float32)
    right_hand_res = np.zeros(63, dtype=np.float32)
    
    results_hands = hands.process(image_rgb)
    if results_hands and results_hands.multi_hand_landmarks and results_hands.multi_handedness:
        for hand_landmarks, handedness in zip(results_hands.multi_hand_landmarks, results_hands.multi_handedness):
            label = handedness.classification[0].label  # "Left" or "Right"
            coords = np.array(
                [[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark],
                dtype=np.float32
            ).flatten()
            
            if label == "Left":
                left_hand_res = coords
            else:
                right_hand_res = coords

    # 3. Concatenate into single feature vector of length 258
    return np.concatenate([pose_res, left_hand_res, right_hand_res])


def sample_or_pad_sequence(sequence, target_len=30):
    """
    Resamples or pads a sequence of landmarks to be exactly `target_len` frames.
    """
    num_frames = len(sequence)

    if num_frames == 0:
        return np.zeros((target_len, 258), dtype=np.float32)

    if num_frames == target_len:
        return np.array(sequence, dtype=np.float32)

    if num_frames > target_len:
        indices = np.linspace(0, num_frames - 1, target_len, dtype=int)
        return np.array([sequence[i] for i in indices], dtype=np.float32)

    sequence_arr = np.array(sequence, dtype=np.float32)
    pad_count = target_len - num_frames
    last_frame = sequence_arr[-1:]
    padding = np.repeat(last_frame, pad_count, axis=0)
    
    return np.concatenate([sequence_arr, padding], axis=0)


def process_video(video_path, pose, hands, target_len=30):
    """
    Processes a single video file, extracts landmarks for each frame,
    and returns a sequence array of shape (target_len, 258).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    frame_sequence = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_features = extract_frame_landmarks(image_rgb, pose, hands)
            frame_sequence.append(frame_features)
            
            del frame
            del image_rgb

    except Exception:
        pass
    finally:
        cap.release()
        gc.collect()

    if len(frame_sequence) == 0:
        return None

    return sample_or_pad_sequence(frame_sequence, target_len=target_len)


def _worker_process_video(task):
    """
    Worker function executed in parallel across CPU cores.
    """
    video_path, cache_file, target_len = task

    # Skip if already cached
    if os.path.exists(cache_file):
        return True

    # Lazy import inside worker process
    try:
        import mediapipe.solutions.pose as mp_pose
        import mediapipe.solutions.hands as mp_hands
    except (AttributeError, ModuleNotFoundError):
        import mediapipe as mp
        mp_pose = mp.solutions.pose
        mp_hands = mp.solutions.hands

    try:
        with mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as pose, mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as hands:
            sequence = process_video(video_path, pose, hands, target_len=target_len)
            if sequence is not None:
                np.save(cache_file, sequence)
                del sequence
    except Exception as e:
        print(f"\n[WARNING] Failed to process {video_path}: {e}")
    finally:
        gc.collect()

    return True


def process_dataset(data_dir, output_dir="dataset", target_len=30, num_workers=None):
    """
    Walks through dataset and extracts features using multi-core parallel processing.
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Dataset directory not found: {data_dir}")

    classes = sorted([
        d for d in os.listdir(data_dir) 
        if os.path.isdir(os.path.join(data_dir, d))
    ])

    if not classes:
        raise ValueError(f"No class folders found inside {data_dir}")

    label_map = {class_name: idx for idx, class_name in enumerate(classes)}
    
    if num_workers is None:
        num_workers = max(1, os.cpu_count() - 1)

    print("=" * 60)
    print(" MULTI-CORE ISL LANDMARK EXTRACTION PIPELINE")
    print("=" * 60)
    print(f"Dataset Path    : {data_dir}")
    print(f"Classes Found   : {len(classes)} -> {list(label_map.keys())}")
    print(f"CPU Parallelism : {num_workers} Worker Cores")
    print("=" * 60)

    cache_dir = os.path.join(output_dir, "extracted")
    os.makedirs(cache_dir, exist_ok=True)
    valid_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')

    # Build task list for parallel execution
    tasks = []
    for class_name in label_map.keys():
        class_folder = os.path.join(data_dir, class_name)
        class_cache_folder = os.path.join(cache_dir, class_name)
        os.makedirs(class_cache_folder, exist_ok=True)

        video_files = [
            f for f in os.listdir(class_folder)
            if f.lower().endswith(valid_extensions)
        ]

        for video_file in video_files:
            video_path = os.path.join(class_folder, video_file)
            cache_file = os.path.join(class_cache_folder, f"{os.path.splitext(video_file)[0]}.npy")
            tasks.append((video_path, cache_file, target_len))

    print(f"\n Processing {len(tasks)} videos using {num_workers} parallel CPU workers...\n")

    # Run multi-processing pool
    if num_workers > 1:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            list(tqdm(
                executor.map(_worker_process_video, tasks),
                total=len(tasks),
                desc=" Parallel Extraction"
            ))
    else:
        for task in tqdm(tasks, desc=" Extracting Videos"):
            _worker_process_video(task)

    # Aggregate extracted landmark arrays
    X_list = []
    y_list = []

    for class_name, class_label in label_map.items():
        class_cache_folder = os.path.join(cache_dir, class_name)
        if not os.path.exists(class_cache_folder):
            continue

        cached_files = [f for f in os.listdir(class_cache_folder) if f.endswith('.npy')]
        for cf in cached_files:
            c_path = os.path.join(class_cache_folder, cf)
            try:
                seq = np.load(c_path)
                if seq.shape == (target_len, 258):
                    X_list.append(seq)
                    y_list.append(class_label)
            except Exception as e:
                print(f"[WARNING] Skipping corrupted cache file {c_path}: {e}")

    if len(X_list) == 0:
        raise RuntimeError("Extraction failed: 0 valid samples extracted.")

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)

    return X, y, label_map


def save_dataset(X, y, label_map, output_dir):
    """
    Saves extracted features X.npy, labels y.npy, and label_map.json.
    """
    os.makedirs(output_dir, exist_ok=True)

    x_path = os.path.join(output_dir, "X.npy")
    y_path = os.path.join(output_dir, "y.npy")
    label_path = os.path.join(output_dir, "label_map.json")

    np.save(x_path, X)
    np.save(y_path, y)

    with open(label_path, "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=4)

    print("\n" + "=" * 60)
    print(" SUCCESS! EXTRACTION COMPLETE & FILES SAVED")
    print("=" * 60)
    print(f" Saved X.npy        -> {x_path}")
    print(f" Saved y.npy        -> {y_path}")
    print(f" Saved label_map.json -> {label_path}")
    print("=" * 60)
    print(f" Total Samples Extracted: {len(y)}")
    print(f" X Shape               : {X.shape}")
    print(f" y Shape               : {y.shape}")
    print("\n Class Label Distribution:")
    
    inv_label_map = {v: k for k, v in label_map.items()}
    unique_labels, counts = np.unique(y, return_counts=True)
    for lbl, count in zip(unique_labels, counts):
        print(f"   - {inv_label_map[lbl]:<15} -> {count} samples")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Core MediaPipe Landmark Extractor for Sign Language")
    parser.add_argument(
        "--data_dir",
        type=str,
        default=os.path.join("dataset", "data"),
        help="Path to dataset root folder containing class directories"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="dataset",
        help="Path to save output X.npy, y.npy, and label_map.json"
    )
    parser.add_argument(
        "--sequence_length",
        type=int,
        default=30,
        help="Number of target frames per video sample (default: 30)"
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=None,
        help="Number of parallel CPU worker processes (default: max CPU cores)"
    )

    args = parser.parse_args()

    X, y, label_map = process_dataset(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        target_len=args.sequence_length,
        num_workers=args.num_workers
    )
    save_dataset(X, y, label_map, output_dir=args.output_dir)


python extract_landmarks.py --num_workers 8

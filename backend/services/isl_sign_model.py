from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
JSON_MODEL_PATH = BASE_DIR / "models" / "isl_trained_model.json"


def _as_float_vector(values: list[float]) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float64)
    if vector.ndim != 1:
        raise ValueError("Expected a flat feature vector.")
    return vector


def _combined_distance(a: np.ndarray, b: np.ndarray, similarity_weight: float = 0.7) -> float:
    euclidean = float(np.linalg.norm(a - b))
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    cosine = 1.0 if denominator == 0 else float(np.dot(a, b) / denominator)
    cosine_distance = 1.0 - max(-1.0, min(1.0, cosine))
    return similarity_weight * euclidean + (1.0 - similarity_weight) * cosine_distance


@dataclass
class JsonISLKNNModel:
    model: Any

    @classmethod
    def load(cls, path: Path = JSON_MODEL_PATH) -> "JsonISLKNNModel":
        if not path.exists():
            raise FileNotFoundError(f"ISL JSON model not found at {path}")

        import json

        with path.open("r", encoding="utf-8") as fh:
            model = json.load(fh)

        if not isinstance(model, dict):
            raise ValueError("ISL JSON model must be an object.")
        if not model.get("samples"):
            raise ValueError("ISL JSON model contains no samples.")

        return cls(model=model)

    def predict_one(self, vector: list[float]) -> dict[str, Any]:
        query = _as_float_vector(vector)
        if hasattr(self.model, "predict"):
            expected_features = getattr(self.model, "n_features_in_", None)
            if expected_features is not None:
                expected_features = int(expected_features)
                if query.size < expected_features:
                    query = np.pad(query, (0, expected_features - query.size))
                elif query.size > expected_features:
                    query = query[:expected_features]
            query = query.reshape(1, -1)
            prediction = self.model.predict(query)[0]

            confidence = 0.0
            class_probabilities: dict[str, float] = {}

            if hasattr(self.model, "predict_proba"):
                probabilities = self.model.predict_proba(query)[0]
                classes = [str(label) for label in getattr(self.model, "classes_", [])]
                class_probabilities = dict(zip(classes, map(float, probabilities)))
                if len(probabilities):
                    confidence = float(max(probabilities) * 100.0)

            return {
                "letter": str(prediction),
                "confidence": confidence,
                "probabilities": class_probabilities,
            }

        if isinstance(self.model, dict):
            samples = self.model.get("samples") or []
            hyperparameters = self.model.get("hyperparameters") or {}
            k_neighbors = int(hyperparameters.get("kNeighbors", 3))
            similarity_weight = float(hyperparameters.get("similarityWeight", 0.7))
            confidence_floor = float(hyperparameters.get("confidenceFloor", 0.45))
            if not samples:
                raise ValueError("Model package contains no samples.")

            vectors = np.asarray([sample["data"] for sample in samples], dtype=np.float64)
            labels = [str(sample["label"]) for sample in samples]
            distances = np.asarray([
                _combined_distance(query, vector, similarity_weight)
                for vector in vectors
            ], dtype=np.float64)
            k_neighbors = max(1, min(k_neighbors, len(distances)))
            neighbour_indices = np.argpartition(distances, k_neighbors - 1)[:k_neighbors]
            neighbour_pairs = sorted(
                [(float(distances[index]), labels[index]) for index in neighbour_indices],
                key=lambda item: item[0],
            )

            vote_scores: dict[str, float] = {}
            for rank, (distance, label) in enumerate(neighbour_pairs):
                weight = 1.0 / (distance + 1e-6)
                # Slightly favor the closest neighbour while keeping the vote stable.
                weight *= 1.0 + (0.15 * (k_neighbors - rank - 1) / max(1, k_neighbors - 1))
                vote_scores[label] = vote_scores.get(label, 0.0) + weight

            prediction = max(vote_scores.items(), key=lambda item: (item[1], item[0]))[0]
            total_vote = sum(vote_scores.values()) or 1.0
            confidence_ratio = vote_scores[prediction] / total_vote
            if confidence_ratio < confidence_floor:
                return {
                    "letter": "Unknown",
                    "confidence": confidence_ratio * 100.0,
                    "probabilities": vote_scores,
                }
            confidence = confidence_ratio * 100.0

            return {
                "letter": str(prediction),
                "confidence": confidence,
                "probabilities": vote_scores,
            }

        raise ValueError(f"Unsupported model type: {type(self.model).__name__}")


_MODEL: JsonISLKNNModel | None = None


def get_model() -> JsonISLKNNModel:
    global _MODEL
    if _MODEL is None:
        _MODEL = JsonISLKNNModel.load()
    return _MODEL

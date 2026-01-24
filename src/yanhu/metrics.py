"""Metrics persistence for throughput tracking and ETA improvement.

Stores observed processing rates per preset to improve future estimates.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ThroughputMetrics:
    """Throughput metrics for a specific preset/strategy combination."""

    samples: int = 0
    avg_rate_ema: float = 0.0  # Exponential moving average of segments/second
    last_updated_at: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "samples": self.samples,
            "avg_rate_ema": self.avg_rate_ema,
            "last_updated_at": self.last_updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThroughputMetrics":
        """Create from dictionary."""
        return cls(
            samples=data.get("samples", 0),
            avg_rate_ema=data.get("avg_rate_ema", 0.0),
            last_updated_at=data.get("last_updated_at"),
        )


class MetricsStore:
    """Storage for processing throughput metrics.

    Metrics are keyed by preset and segment_duration_bucket (auto_short/auto_medium/auto_long).
    """

    def __init__(self, metrics_file: Path):
        """Initialize metrics store.

        Args:
            metrics_file: Path to _metrics.json file
        """
        self.metrics_file = metrics_file
        self._metrics: dict[str, dict[str, ThroughputMetrics]] = {}
        self._load()

    def _load(self):
        """Load metrics from file."""
        if not self.metrics_file.exists():
            return

        try:
            with open(self.metrics_file, encoding="utf-8") as f:
                data = json.load(f)

            for preset, buckets in data.items():
                self._metrics[preset] = {}
                for bucket, metrics_data in buckets.items():
                    self._metrics[preset][bucket] = ThroughputMetrics.from_dict(metrics_data)
        except (json.JSONDecodeError, OSError):
            # Corrupted file, start fresh
            self._metrics = {}

    def _save(self):
        """Save metrics to file atomically."""
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict
        data = {}
        for preset, buckets in self._metrics.items():
            data[preset] = {}
            for bucket, metrics in buckets.items():
                data[preset][bucket] = metrics.to_dict()

        # Atomic write
        fd, temp_path = tempfile.mkstemp(
            dir=self.metrics_file.parent,
            prefix=".metrics_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.metrics_file)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def update_metrics(
        self,
        preset: str,
        segment_duration: int,
        observed_rate: float,
        alpha: float = 0.2,
    ):
        """Update metrics with a new observation.

        Uses exponential moving average (EMA) for smoothing:
            new_ema = alpha * observed_rate + (1 - alpha) * old_ema

        Args:
            preset: Processing preset (fast/quality)
            segment_duration: Segment duration in seconds (5/15/30)
            observed_rate: Observed processing rate in segments/second
            alpha: EMA smoothing factor (default: 0.2)
        """
        # Map segment duration to bucket
        if segment_duration <= 5:
            bucket = "auto_short"
        elif segment_duration <= 15:
            bucket = "auto_medium"
        else:
            bucket = "auto_long"

        # Get or create metrics
        if preset not in self._metrics:
            self._metrics[preset] = {}
        if bucket not in self._metrics[preset]:
            self._metrics[preset][bucket] = ThroughputMetrics()

        metrics = self._metrics[preset][bucket]

        # Update EMA
        if metrics.samples == 0:
            # First sample - use observed rate directly
            metrics.avg_rate_ema = observed_rate
        else:
            # Apply EMA smoothing
            metrics.avg_rate_ema = alpha * observed_rate + (1 - alpha) * metrics.avg_rate_ema

        metrics.samples += 1
        metrics.last_updated_at = datetime.now().isoformat()

        # Save to disk
        self._save()

    def get_metrics(self, preset: str, segment_duration: int) -> ThroughputMetrics | None:
        """Get metrics for a preset/segment_duration combination.

        Args:
            preset: Processing preset (fast/quality)
            segment_duration: Segment duration in seconds (5/15/30)

        Returns:
            ThroughputMetrics if available, None otherwise
        """
        # Map segment duration to bucket
        if segment_duration <= 5:
            bucket = "auto_short"
        elif segment_duration <= 15:
            bucket = "auto_medium"
        else:
            bucket = "auto_long"

        if preset not in self._metrics:
            return None
        if bucket not in self._metrics[preset]:
            return None

        return self._metrics[preset][bucket]


def compute_observed_rate(done: int, elapsed_sec: float) -> float | None:
    """Compute observed processing rate.

    Args:
        done: Number of completed segments
        elapsed_sec: Elapsed time in seconds

    Returns:
        Rate in segments/second, or None if cannot compute
    """
    if done < 1 or elapsed_sec <= 0:
        return None
    return done / elapsed_sec


def compute_calibrated_eta(
    done: int,
    total: int,
    elapsed_sec: float,
    rate_ema: float | None = None,
    alpha: float = 0.2,
) -> tuple[float | None, float | None]:
    """Compute calibrated ETA with optional EMA smoothing.

    Args:
        done: Number of completed segments
        total: Total segments
        elapsed_sec: Elapsed time in seconds
        rate_ema: Previous EMA rate (for smoothing), None for first call
        alpha: EMA smoothing factor (default: 0.2)

    Returns:
        Tuple of (new_rate_ema, eta_sec) or (None, None) if cannot compute
    """
    if done < 1 or elapsed_sec <= 0 or done >= total:
        return (None, None)

    # Compute current rate
    current_rate = done / elapsed_sec

    # Apply EMA smoothing if previous rate exists
    if rate_ema is None:
        new_rate_ema = current_rate
    else:
        new_rate_ema = alpha * current_rate + (1 - alpha) * rate_ema

    # Compute ETA
    remaining = total - done
    eta_sec = remaining / new_rate_ema

    return (new_rate_ema, eta_sec)

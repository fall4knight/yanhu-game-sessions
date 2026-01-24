"""Tests for metrics module."""

from yanhu.metrics import (
    MetricsStore,
    ThroughputMetrics,
    compute_calibrated_eta,
    compute_observed_rate,
)


class TestComputeObservedRate:
    """Test compute_observed_rate function."""

    def test_compute_rate_valid_inputs(self):
        """Compute rate with valid inputs."""
        rate = compute_observed_rate(done=10, elapsed_sec=20.0)
        assert rate == 0.5  # 10 segments in 20 seconds = 0.5 seg/s

    def test_compute_rate_zero_done(self):
        """Return None when done is zero."""
        rate = compute_observed_rate(done=0, elapsed_sec=10.0)
        assert rate is None

    def test_compute_rate_zero_elapsed(self):
        """Return None when elapsed is zero."""
        rate = compute_observed_rate(done=10, elapsed_sec=0.0)
        assert rate is None

    def test_compute_rate_negative_elapsed(self):
        """Return None when elapsed is negative."""
        rate = compute_observed_rate(done=10, elapsed_sec=-5.0)
        assert rate is None


class TestComputeCalibratedEta:
    """Test compute_calibrated_eta function."""

    def test_calibrated_eta_first_call(self):
        """First call (no EMA history) uses current rate directly."""
        rate_ema, eta = compute_calibrated_eta(
            done=10, total=20, elapsed_sec=20.0, rate_ema=None
        )

        # Current rate: 10 / 20 = 0.5 seg/s
        assert rate_ema == 0.5
        # Remaining: 10 segments, rate: 0.5 seg/s → 20s
        assert eta == 20.0

    def test_calibrated_eta_with_ema_smoothing(self):
        """Subsequent calls apply EMA smoothing."""
        # First observation: 10 done in 20s → 0.5 seg/s
        rate_ema1, eta1 = compute_calibrated_eta(
            done=10, total=20, elapsed_sec=20.0, rate_ema=None
        )
        assert rate_ema1 == 0.5

        # Second observation: 15 done in 25s → 0.6 seg/s
        # EMA: 0.2 * 0.6 + 0.8 * 0.5 = 0.52 seg/s
        rate_ema2, eta2 = compute_calibrated_eta(
            done=15, total=20, elapsed_sec=25.0, rate_ema=rate_ema1, alpha=0.2
        )
        assert abs(rate_ema2 - 0.52) < 0.001
        # Remaining: 5 segments, rate: 0.52 seg/s → 9.615s
        assert abs(eta2 - (5 / 0.52)) < 0.01

    def test_calibrated_eta_custom_alpha(self):
        """Custom alpha value changes smoothing."""
        # First call
        rate_ema1, _ = compute_calibrated_eta(done=10, total=20, elapsed_sec=20.0, rate_ema=None)

        # Second call with alpha=0.5 (more responsive)
        rate_ema2, _ = compute_calibrated_eta(
            done=15, total=20, elapsed_sec=25.0, rate_ema=rate_ema1, alpha=0.5
        )
        # EMA: 0.5 * 0.6 + 0.5 * 0.5 = 0.55 seg/s
        assert abs(rate_ema2 - 0.55) < 0.001

    def test_calibrated_eta_zero_done(self):
        """Return (None, None) when done is zero."""
        rate_ema, eta = compute_calibrated_eta(done=0, total=20, elapsed_sec=10.0)
        assert rate_ema is None
        assert eta is None

    def test_calibrated_eta_done_equals_total(self):
        """Return (None, None) when done equals total."""
        rate_ema, eta = compute_calibrated_eta(done=20, total=20, elapsed_sec=40.0)
        assert rate_ema is None
        assert eta is None


class TestThroughputMetrics:
    """Test ThroughputMetrics dataclass."""

    def test_to_dict(self):
        """Convert to dictionary."""
        metrics = ThroughputMetrics(
            samples=5, avg_rate_ema=0.42, last_updated_at="2026-01-23T10:00:00"
        )
        d = metrics.to_dict()

        assert d["samples"] == 5
        assert d["avg_rate_ema"] == 0.42
        assert d["last_updated_at"] == "2026-01-23T10:00:00"

    def test_from_dict(self):
        """Create from dictionary."""
        d = {"samples": 3, "avg_rate_ema": 0.35, "last_updated_at": "2026-01-23T09:00:00"}
        metrics = ThroughputMetrics.from_dict(d)

        assert metrics.samples == 3
        assert metrics.avg_rate_ema == 0.35
        assert metrics.last_updated_at == "2026-01-23T09:00:00"


class TestMetricsStore:
    """Test MetricsStore persistence."""

    def test_update_and_get_metrics(self, tmp_path):
        """Update and retrieve metrics."""
        metrics_file = tmp_path / "_metrics.json"
        store = MetricsStore(metrics_file)

        # Update with first observation
        store.update_metrics(preset="fast", segment_duration=5, observed_rate=0.5)

        # Retrieve
        metrics = store.get_metrics(preset="fast", segment_duration=5)
        assert metrics is not None
        assert metrics.samples == 1
        assert metrics.avg_rate_ema == 0.5

    def test_update_applies_ema(self, tmp_path):
        """Multiple updates apply EMA smoothing."""
        metrics_file = tmp_path / "_metrics.json"
        store = MetricsStore(metrics_file)

        # First observation: 0.5 seg/s
        store.update_metrics(preset="fast", segment_duration=5, observed_rate=0.5, alpha=0.2)
        metrics1 = store.get_metrics(preset="fast", segment_duration=5)
        assert metrics1.avg_rate_ema == 0.5

        # Second observation: 0.6 seg/s
        # EMA: 0.2 * 0.6 + 0.8 * 0.5 = 0.52
        store.update_metrics(preset="fast", segment_duration=5, observed_rate=0.6, alpha=0.2)
        metrics2 = store.get_metrics(preset="fast", segment_duration=5)
        assert abs(metrics2.avg_rate_ema - 0.52) < 0.001
        assert metrics2.samples == 2

    def test_metrics_persisted_to_file(self, tmp_path):
        """Metrics are persisted to JSON file."""
        metrics_file = tmp_path / "_metrics.json"

        # Create store and update
        store1 = MetricsStore(metrics_file)
        store1.update_metrics(preset="fast", segment_duration=5, observed_rate=0.5)

        # Load in new store instance
        store2 = MetricsStore(metrics_file)
        metrics = store2.get_metrics(preset="fast", segment_duration=5)

        assert metrics is not None
        assert metrics.avg_rate_ema == 0.5

    def test_different_presets_separate(self, tmp_path):
        """Different presets have separate metrics."""
        metrics_file = tmp_path / "_metrics.json"
        store = MetricsStore(metrics_file)

        store.update_metrics(preset="fast", segment_duration=5, observed_rate=0.5)
        store.update_metrics(preset="quality", segment_duration=5, observed_rate=0.2)

        metrics_fast = store.get_metrics(preset="fast", segment_duration=5)
        metrics_quality = store.get_metrics(preset="quality", segment_duration=5)

        assert metrics_fast.avg_rate_ema == 0.5
        assert metrics_quality.avg_rate_ema == 0.2

    def test_different_buckets_separate(self, tmp_path):
        """Different segment duration buckets have separate metrics."""
        metrics_file = tmp_path / "_metrics.json"
        store = MetricsStore(metrics_file)

        # Short bucket (5s)
        store.update_metrics(preset="fast", segment_duration=5, observed_rate=0.5)
        # Medium bucket (15s)
        store.update_metrics(preset="fast", segment_duration=15, observed_rate=0.3)
        # Long bucket (30s)
        store.update_metrics(preset="fast", segment_duration=30, observed_rate=0.2)

        metrics_short = store.get_metrics(preset="fast", segment_duration=5)
        metrics_medium = store.get_metrics(preset="fast", segment_duration=15)
        metrics_long = store.get_metrics(preset="fast", segment_duration=30)

        assert metrics_short.avg_rate_ema == 0.5
        assert metrics_medium.avg_rate_ema == 0.3
        assert metrics_long.avg_rate_ema == 0.2

    def test_get_nonexistent_metrics(self, tmp_path):
        """Get returns None for nonexistent metrics."""
        metrics_file = tmp_path / "_metrics.json"
        store = MetricsStore(metrics_file)

        metrics = store.get_metrics(preset="nonexistent", segment_duration=5)
        assert metrics is None

    def test_corrupted_file_starts_fresh(self, tmp_path):
        """Corrupted metrics file starts fresh."""
        metrics_file = tmp_path / "_metrics.json"
        metrics_file.write_text("not valid json{")

        store = MetricsStore(metrics_file)
        metrics = store.get_metrics(preset="fast", segment_duration=5)
        assert metrics is None  # No data loaded

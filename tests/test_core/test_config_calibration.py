"""Tests for writing the calibrated tau_div back into the config file.

The threshold decides which tasks receive MT consistency assertions, so a
half-applied or misplaced edit would quietly change what RQ4 measures.
"""

import pytest

from meta_real_eval.core.config import (
    CalibrationError,
    Config,
    write_divergence_threshold,
)

CONFIG = """\
rq3:
  n_shared_inputs: 200          # shared random inputs
  # Calibrate this from the Tier-1 pilot ROC curve.
  divergence_threshold: null

rq4:
  degradation_levels: [0.0, 0.5]
"""


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "default.yaml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


def test_writes_the_value_and_reports_the_previous_one(config_file):
    previous = write_divergence_threshold(config_file, 0.234)
    assert previous is None
    assert Config.from_yaml(config_file).rq3.divergence_threshold == 0.234


def test_comments_survive_the_edit(config_file):
    """The file's comments carry the calibration instructions themselves."""
    write_divergence_threshold(config_file, 0.5)
    text = config_file.read_text(encoding="utf-8")
    assert "# Calibrate this from the Tier-1 pilot ROC curve." in text
    assert "# shared random inputs" in text
    assert "degradation_levels: [0.0, 0.5]" in text


def test_recalibration_overwrites_a_previous_value(config_file):
    write_divergence_threshold(config_file, 0.2)
    previous = write_divergence_threshold(config_file, 0.7)
    assert previous == 0.2
    assert Config.from_yaml(config_file).rq3.divergence_threshold == 0.7


def test_trailing_comment_on_the_key_is_kept(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("rq3:\n  divergence_threshold: null  # set by the pilot\n",
                    encoding="utf-8")
    write_divergence_threshold(path, 0.3)
    assert "# set by the pilot" in path.read_text(encoding="utf-8")
    assert Config.from_yaml(path).rq3.divergence_threshold == 0.3


def test_missing_key_is_an_error_not_a_silent_no_op(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("rq3:\n  n_shared_inputs: 200\n", encoding="utf-8")
    with pytest.raises(CalibrationError, match="no 'divergence_threshold:' key"):
        write_divergence_threshold(path, 0.3)


def test_ambiguous_duplicate_keys_are_refused(tmp_path):
    """Two keys means we cannot tell which one rq3 actually reads."""
    path = tmp_path / "c.yaml"
    path.write_text(
        "rq3:\n  divergence_threshold: null\nother:\n  divergence_threshold: 0.9\n",
        encoding="utf-8",
    )
    with pytest.raises(CalibrationError, match="cannot tell"):
        write_divergence_threshold(path, 0.3)

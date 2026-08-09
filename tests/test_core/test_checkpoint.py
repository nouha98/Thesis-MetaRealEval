"""Tests for the marker-file checkpointing helpers."""

import argparse

from meta_real_eval.core.checkpoint import (
    add_force_arg,
    clear_done,
    is_done,
    mark_done,
)


def test_is_done_false_when_no_marker(tmp_path):
    assert is_done(tmp_path / "task_1") is False


def test_mark_done_then_is_done(tmp_path):
    out = tmp_path / "task_1"
    mark_done(out)
    assert is_done(out) is True


def test_clear_done_removes_marker_and_outputs(tmp_path):
    out = tmp_path / "task_1"
    out.mkdir(parents=True)
    (out / "result.json").write_text("{}")
    mark_done(out)
    assert is_done(out) is True

    clear_done(out)

    assert is_done(out) is False
    assert not out.exists()


def test_clear_done_on_missing_dir_is_a_no_op(tmp_path):
    # Never-started task: nothing to clear, must not raise.
    clear_done(tmp_path / "never_ran")


def test_force_arg_defaults_false():
    parser = argparse.ArgumentParser()
    add_force_arg(parser)
    args = parser.parse_args([])
    assert args.force is False


def test_force_arg_can_be_set():
    parser = argparse.ArgumentParser()
    add_force_arg(parser)
    args = parser.parse_args(["--force"])
    assert args.force is True

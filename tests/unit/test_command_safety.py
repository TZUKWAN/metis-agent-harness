"""Tests for dangerous command pattern detection."""

from __future__ import annotations

from metis.tools.builtin import _check_dangerous_patterns


def test_blocks_rm_rf_root():
    assert _check_dangerous_patterns("rm -rf /") is not None


def test_blocks_rm_rf_home():
    assert _check_dangerous_patterns("rm -rf ~") is not None


def test_blocks_git_force_push():
    assert _check_dangerous_patterns("git push origin --force") is not None


def test_blocks_git_reset_hard():
    assert _check_dangerous_patterns("git reset --hard HEAD") is not None


def test_blocks_git_clean_force():
    assert _check_dangerous_patterns("git clean -fdx") is not None


def test_blocks_dd_to_disk():
    assert _check_dangerous_patterns("dd if=/dev/zero of=/dev/sda") is not None


def test_allows_safe_commands():
    assert _check_dangerous_patterns("ls -la") is None
    assert _check_dangerous_patterns("python -m pytest -q") is None
    assert _check_dangerous_patterns("git status") is None
    assert _check_dangerous_patterns("cat file.txt") is None
    assert _check_dangerous_patterns("npm install") is None


def test_allows_rm_safe_files():
    assert _check_dangerous_patterns("rm temp.txt") is None


def test_allows_git_push_normal():
    assert _check_dangerous_patterns("git push origin main") is None


def test_blocks_git_checkout_dot():
    assert _check_dangerous_patterns("git checkout .") is not None

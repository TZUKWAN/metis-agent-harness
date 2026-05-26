"""Tests for per-profile session tool call limits."""

from __future__ import annotations

from metis.runtime.profiles import PROFILES, get_model_profile


def test_small_profile_has_session_limit():
    p = get_model_profile("small")
    assert p.max_session_tool_calls == 150


def test_balanced_profile_has_default_session_limit():
    p = get_model_profile("balanced")
    assert p.max_session_tool_calls == 200


def test_deep_profile_has_higher_session_limit():
    p = get_model_profile("deep")
    assert p.max_session_tool_calls == 500


def test_small_strict_has_default_session_limit():
    p = get_model_profile("small_strict")
    assert p.max_session_tool_calls == 200


def test_all_profiles_have_session_limit():
    for name, profile in PROFILES.items():
        assert profile.max_session_tool_calls >= 50, f"{name} has too low session limit"
        assert profile.max_session_tool_calls <= 10_000, f"{name} has too high session limit"

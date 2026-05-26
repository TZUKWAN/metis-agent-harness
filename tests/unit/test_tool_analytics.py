"""Tests for tool usage analytics."""

from __future__ import annotations

from metis.tools.analytics import ToolAnalytics


class TestToolAnalytics:
    def test_record_single_call(self):
        analytics = ToolAnalytics()
        analytics.record("read_file", "files", 50.0, "ok")
        summary = analytics.summary()
        assert summary["tools"]["read_file"]["calls"] == 1
        assert summary["tools"]["read_file"]["errors"] == 0
        assert summary["tools"]["read_file"]["avg_duration_ms"] == 50.0
        assert summary["categories"]["files"]["calls"] == 1

    def test_record_error(self):
        analytics = ToolAnalytics()
        analytics.record("run_shell", "shell", 100.0, "error")
        summary = analytics.summary()
        assert summary["tools"]["run_shell"]["errors"] == 1
        assert summary["categories"]["shell"]["errors"] == 1

    def test_multiple_calls_avg(self):
        analytics = ToolAnalytics()
        analytics.record("read_file", "files", 10.0, "ok")
        analytics.record("read_file", "files", 30.0, "ok")
        summary = analytics.summary()
        assert summary["tools"]["read_file"]["calls"] == 2
        assert summary["tools"]["read_file"]["avg_duration_ms"] == 20.0

    def test_clear(self):
        analytics = ToolAnalytics()
        analytics.record("read_file", "files", 10.0, "ok")
        analytics.clear()
        summary = analytics.summary()
        assert summary["tools"] == {}
        assert summary["categories"] == {}

    def test_empty_summary(self):
        analytics = ToolAnalytics()
        summary = analytics.summary()
        assert summary["tools"] == {}
        assert summary["categories"] == {}

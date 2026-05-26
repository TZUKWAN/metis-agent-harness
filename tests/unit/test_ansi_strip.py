"""Tests for ANSI escape sequence stripping in shell tools."""

from __future__ import annotations

from metis.tools.builtin import _strip_ansi


class TestStripAnsi:
    def test_removes_color_codes(self):
        colored = "\x1b[31mred\x1b[0m"
        assert _strip_ansi(colored) == "red"

    def test_removes_bold(self):
        bold = "\x1b[1mbold\x1b[0m"
        assert _strip_ansi(bold) == "bold"

    def test_multiple_codes(self):
        text = "\x1b[1;31;40mtext\x1b[0m"
        assert _strip_ansi(text) == "text"

    def test_no_ansi_unchanged(self):
        plain = "hello world"
        assert _strip_ansi(plain) == "hello world"

    def test_empty_string(self):
        assert _strip_ansi("") == ""

    def test_ls_color_output(self):
        ls_output = "\x1b[0m\x1b[01;34mdir\x1b[0m  file.txt"
        stripped = _strip_ansi(ls_output)
        assert "\x1b" not in stripped
        assert stripped == "dir  file.txt"

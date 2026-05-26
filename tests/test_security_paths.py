"""Tests for metis/security/paths.py."""

import sys

import pytest

from metis.security.paths import (
    is_read_denied,
    is_write_denied,
    resolve_workspace_path,
)


class TestIsDenied:
    def test_ssh_dir_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / ".ssh" / "config"))

    def test_aws_dir_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / ".aws" / "credentials"))

    def test_env_file_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / "project" / ".env"))

    def test_pem_file_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / "cert.pem"))

    def test_key_file_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / "server.key"))

    def test_id_rsa_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / "id_rsa"))

    def test_normal_file_allowed(self, tmp_path):
        assert not is_write_denied(str(tmp_path / "output.txt"))

    def test_normal_subdir_allowed(self, tmp_path):
        assert not is_write_denied(str(tmp_path / "src" / "main.py"))

    def test_git_dir_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / ".git" / "HEAD"))

    def test_docker_dir_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / ".docker" / "config.json"))

    def test_read_denied_same_as_write(self, tmp_path):
        path = str(tmp_path / ".ssh" / "key")
        assert is_read_denied(path) == is_write_denied(path)

    def test_pfx_file_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / "cert.pfx"))

    def test_p12_file_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / "cert.p12"))

    def test_netrc_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / ".netrc"))

    def test_bashrc_denied(self, tmp_path):
        assert is_write_denied(str(tmp_path / ".bashrc"))

    def test_normal_json_allowed(self, tmp_path):
        assert not is_write_denied(str(tmp_path / "data.json"))

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific")
    def test_windows_system_dir_denied(self, tmp_path):
        assert is_write_denied("C:\\Windows\\System32\\test.txt")


class TestResolveWorkspacePath:
    def test_normal_path_resolves(self, tmp_path):
        result = resolve_workspace_path(tmp_path, "src/main.py")
        assert result == (tmp_path / "src" / "main.py").resolve()

    def test_path_escape_raises(self, tmp_path):
        with pytest.raises(PermissionError, match="escapes workspace"):
            resolve_workspace_path(tmp_path, "../../etc/passwd")

    def test_absolute_path_within_workspace(self, tmp_path):
        target = tmp_path / "output.txt"
        result = resolve_workspace_path(tmp_path, str(target))
        assert result == target.resolve()

    def test_dot_dot_escapes_raises(self, tmp_path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        with pytest.raises(PermissionError, match="escapes workspace"):
            resolve_workspace_path(subdir, "../output.txt")

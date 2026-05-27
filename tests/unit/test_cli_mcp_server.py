"""Tests for the metis mcp-server CLI command."""

from unittest.mock import AsyncMock, MagicMock, patch

from metis.adapters import cli


def test_cli_mcp_server_starts_server_with_defaults():
    with patch("metis.adapters.cli.MCPServer") as mock_server_cls:
        mock_server = MagicMock()
        mock_server.run = AsyncMock(return_value=None)
        mock_server_cls.return_value = mock_server

        exit_code = cli.main(["mcp-server"])

        assert exit_code == 0
        mock_server_cls.assert_called_once()
        registry = mock_server_cls.call_args[0][0]
        assert "read_file" in [spec.name for spec in registry.iter_specs()]


def test_cli_mcp_server_uses_manifest_workspace(tmp_path):
    manifest_path = tmp_path / "metis-agent.json"
    manifest_path.write_text(
        '{"name": "Test", "workspace": "' + str(tmp_path).replace("\\", "/") + '"}',
        encoding="utf-8",
    )

    with patch("metis.adapters.cli.MCPServer") as mock_server_cls:
        mock_server = MagicMock()
        mock_server.run = AsyncMock(return_value=None)
        mock_server_cls.return_value = mock_server

        exit_code = cli.main(["mcp-server", "--manifest", str(manifest_path)])

        assert exit_code == 0
        mock_server_cls.assert_called_once()
        assert mock_server_cls.call_args[1]["name"] == "metis-mcp-server"


def test_cli_mcp_server_uses_custom_name():
    with patch("metis.adapters.cli.MCPServer") as mock_server_cls:
        mock_server = MagicMock()
        mock_server.run = AsyncMock(return_value=None)
        mock_server_cls.return_value = mock_server

        exit_code = cli.main(["mcp-server", "--name", "custom-mcp"])

        assert exit_code == 0
        assert mock_server_cls.call_args[1]["name"] == "custom-mcp"

import json

from metis.package_lifecycle import build_package, export_package, install_package, verify_package


def _write_package_source(root):
    prompts = root / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "agent-system.md").write_text("system", encoding="utf-8")
    (prompts / "agent-developer.md").write_text("developer", encoding="utf-8")
    (root / "README.md").write_text("# Agent", encoding="utf-8")
    (root / "metis-agent.json").write_text(
        json.dumps(
            {
                "name": "Agent",
                "workspace": ".",
                "model": "glm-4.7-flash",
                "profile": "small",
                "system_prompt_path": "prompts/agent-system.md",
                "developer_prompt_path": "prompts/agent-developer.md",
            }
        ),
        encoding="utf-8",
    )


def test_build_package_writes_file_hash_manifest(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _write_package_source(source)

    manifest = build_package(source, tmp_path / "package")

    assert manifest["artifact_type"] == "metis_agent_package"
    assert manifest["file_count"] >= 4
    assert (tmp_path / "package" / "metis-package.json").exists()


def test_verify_package_accepts_dev_package_after_build(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _write_package_source(source)
    package_dir = tmp_path / "package"
    build_package(source, package_dir)

    result = verify_package(package_dir, profile="dev")

    assert result["valid"] is True
    assert result["manifest"]["name"] == "Agent"


def test_verify_package_accepts_bom_agent_manifest(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _write_package_source(source)
    (source / "metis-agent.json").write_text(
        json.dumps(
            {
                "name": "BOM Agent",
                "workspace": ".",
                "model": "glm-4.7-flash",
                "profile": "small",
                "system_prompt_path": "prompts/agent-system.md",
                "developer_prompt_path": "prompts/agent-developer.md",
            }
        ),
        encoding="utf-8-sig",
    )
    package_dir = tmp_path / "package"
    build_package(source, package_dir)

    result = verify_package(package_dir, profile="dev")

    assert result["valid"] is True
    assert result["manifest"]["name"] == "BOM Agent"


def test_verify_release_package_requires_eval_suite(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _write_package_source(source)
    package_dir = tmp_path / "package"
    build_package(source, package_dir)

    result = verify_package(package_dir, profile="release")

    assert result["valid"] is False
    assert any("requires at least one eval suite" in failure for failure in result["failures"])


def test_verify_package_detects_hash_mismatch(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _write_package_source(source)
    package_dir = tmp_path / "package"
    build_package(source, package_dir)
    (package_dir / "README.md").write_text("tampered", encoding="utf-8")

    result = verify_package(package_dir, profile="dev")

    assert result["valid"] is False
    assert "Package manifest hash mismatch: README.md" in result["failures"]


def test_install_package_copies_verified_package(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _write_package_source(source)
    package_dir = tmp_path / "package"
    build_package(source, package_dir)

    result = install_package(package_dir, tmp_path / "installed")

    assert result["installed"] is True
    assert (tmp_path / "installed" / "metis-agent.json").exists()


def test_export_package_writes_zip_with_hash(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    _write_package_source(source)
    package_dir = tmp_path / "package"
    build_package(source, package_dir)

    result = export_package(package_dir, tmp_path / "agent.zip")

    assert result["exported"] is True
    assert (tmp_path / "agent.zip").exists()
    assert result["sha256"]

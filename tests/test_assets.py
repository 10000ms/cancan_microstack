from pathlib import Path

from cancan_microstack.core.assets import AssetManager


def test_export_compose_asset(tmp_path):
    manager = AssetManager()
    destination = tmp_path / "compose.yml"

    exported = manager.export_asset("docker/docker-compose.infra.yml", destination)

    assert exported.exists()
    assert exported.read_text(encoding="utf-8"), "exported compose must not be empty"


def test_list_assets_includes_ddl_and_scripts():
    manager = AssetManager()
    records = manager.list_assets("ddl")
    logical_names = {record.logical_name for record in records}

    assert any(name.startswith("ddl/infra") for name in logical_names)
    assert any(name.startswith("ddl/ops") for name in logical_names)
    assert "ddl/create_db.sql" in logical_names
    assert "ddl/trigger.sql" in logical_names

    script_records = manager.list_assets("scripts")
    script_names = {record.logical_name for record in script_records}
    assert "scripts/start_controllersrv.sh" in script_names


def test_caddy_bundle_is_packaged(tmp_path):
    manager = AssetManager()

    exported_dir = manager.export_asset("builds/caddy", tmp_path / "caddy")

    assert (exported_dir / "Caddyfile").exists()
    assert (exported_dir / "Dockerfile").exists()
    assert (exported_dir / "start.sh").exists()
    assert (exported_dir / "waf" / "coraza.conf").exists()


def test_service_dockerfile_asset(tmp_path):
    manager = AssetManager()
    destination = tmp_path / "service" / "Dockerfile"

    exported = manager.export_asset("builds/service/Dockerfile", destination)

    assert exported.exists()
    assert "PYTHON_VERSION" in exported.read_text(encoding="utf-8")


def test_create_db_sql_asset(tmp_path):
    manager = AssetManager()
    destination = tmp_path / "ddl" / "create_db.sql"

    exported = manager.export_asset("ddl/create_db.sql", destination)

    content = exported.read_text(encoding="utf-8")
    assert "CREATE DATABASE infra" in content
    assert "CREATE DATABASE ops" in content

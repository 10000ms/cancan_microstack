import yaml

from cancan_microstack.core.compose_builder import ComposeBuilder


def test_compose_builder_merges_service_file(tmp_path):
    builder = ComposeBuilder()
    service_file = tmp_path / "docker-compose.services.yml"
    service_file.write_text(
        """
        services:
          demo-service:
            image: demo:latest
        """,
        encoding="utf-8",
    )

    output = builder.build(workspace=tmp_path, service_file=service_file)

    assert output.exists()
    data = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert "services" in data
    assert "demo-service" in data["services"]

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[3]


def test_collector_connects_logs_to_loki_and_traces_to_tempo() -> None:
    config = (REPOSITORY_ROOT / "docker/otel-collector/config.yml").read_text()
    assert "endpoint: 0.0.0.0:4317" in config
    assert "endpoint: 0.0.0.0:4318" in config
    assert "endpoint: tempo:4317" in config
    assert "endpoint: http://loki:3100/otlp" in config
    assert "exporters: [otlp/tempo, debug]" in config
    assert "exporters: [otlphttp/loki, debug]" in config


def test_grafana_provisions_all_datasources_and_trace_correlation() -> None:
    config = (
        REPOSITORY_ROOT / "docker/grafana/provisioning/datasources/datasources.yml"
    ).read_text()
    assert "type: prometheus" in config
    assert "type: loki" in config
    assert "type: tempo" in config
    assert "derivedFields:" in config
    assert "tracesToLogsV2:" in config

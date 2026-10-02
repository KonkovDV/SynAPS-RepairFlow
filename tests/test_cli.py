from repairflow.cli import main


def test_cli_version(capsys) -> None:
    assert main(["version"]) == 0
    out = capsys.readouterr().out
    assert "repairflow 0.1.0" in out
    assert "9d6eafb8bda7de67a303764990fbb24b4e28340b" in out

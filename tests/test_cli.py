from repairflow.cli import main


def test_cli_version(capsys) -> None:
    assert main(["version"]) == 0
    out = capsys.readouterr().out
    assert "repairflow 0.1.0" in out
    assert "1f7d5e0ede2944d21579574edf84976fe5e78808" in out

from repairflow.cli import main


def test_cli_version(capsys) -> None:
    assert main(["version"]) == 0
    out = capsys.readouterr().out
    assert "repairflow 0.1.0" in out
    assert "f939727cd9369fd9b36438bfac7198f0c39c6d3b" in out

from repairflow.cli import main


def test_cli_version(capsys) -> None:
    assert main(["version"]) == 0
    out = capsys.readouterr().out
    assert "repairflow 0.1.0" in out
    assert "6178c93b705ff58be21fa74a98651883a2da1169" in out

from repairflow.cli import main


def test_cli_version(capsys) -> None:
    assert main(["version"]) == 0
    out = capsys.readouterr().out
    assert "repairflow 0.1.0" in out
    assert "6250abd3fd4ee0ce71c82c284a530b086927fc99" in out

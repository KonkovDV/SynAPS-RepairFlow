import json

from repairflow.cli import main


def test_one_command_mvp_readiness(tmp_path, capsys) -> None:
    assert main(["demo", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "MVP readiness: PASS" in out
    assert "CPSAT status=ERROR" in out
    assert "code=KERNEL_CALENDAR_UNSUPPORTED" in out
    assert (tmp_path / "greed.html").is_file()
    assert (tmp_path / "fifo.html").is_file()
    assert (tmp_path / "broken.html").is_file()
    html = (tmp_path / "greed.html").read_text(encoding="utf-8")
    assert "Gantt по постам" in html
    assert "input_hash" in html
    greed = json.loads((tmp_path / "greed.json").read_text(encoding="utf-8"))
    assert html.count('class="bar') == len(greed["assignments"])
    assert html.count('class="bar') > 0

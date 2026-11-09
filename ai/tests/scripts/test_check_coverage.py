import json

import pytest

from scripts.check_coverage import CoverageRates, coverage_rates, main, shortfalls


def _report(covered_lines=95, num_statements=100, covered_branches=9, num_branches=10):
    return {"totals": {
        "covered_lines": covered_lines, "num_statements": num_statements,
        "covered_branches": covered_branches, "num_branches": num_branches,
    }}


def test_라인과_분기_비율을_따로_계산한다():
    assert coverage_rates(_report()) == CoverageRates(line=95.0, branch=90.0)


def test_대상이_없으면_100으로_본다():
    rates = coverage_rates(_report(covered_lines=0, num_statements=0, covered_branches=0, num_branches=0))

    assert rates == CoverageRates(line=100.0, branch=100.0)


def test_분기_측정이_없는_결과면_KeyError():
    with pytest.raises(KeyError):
        coverage_rates({"totals": {"covered_lines": 1, "num_statements": 1}})


def test_기준과_같으면_통과한다():
    assert shortfalls(CoverageRates(line=95.0, branch=90.0), min_line=95, min_branch=90) == []


def test_라인과_분기를_따로_검사한다():
    assert shortfalls(CoverageRates(line=94.9, branch=95.0), min_line=95, min_branch=90) == ["라인 94.90% < 기준 95%"]
    assert shortfalls(CoverageRates(line=99.0, branch=89.9), min_line=95, min_branch=90) == ["분기 89.90% < 기준 90%"]


def test_기준을_넘으면_종료_코드_0(tmp_path, capsys):
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")

    assert main([str(path), "--line", "95", "--branch", "90"]) == 0
    assert "라인 95.00% (기준 95%), 분기 90.00% (기준 90%)" in capsys.readouterr().out


def test_하나라도_미달이면_종료_코드_1(tmp_path, capsys):
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(_report(covered_branches=8)), encoding="utf-8")

    assert main([str(path), "--line", "95", "--branch", "90"]) == 1
    assert "커버리지 기준 미달: 분기 80.00% < 기준 90%" in capsys.readouterr().err

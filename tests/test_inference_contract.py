from __future__ import annotations

import re

import inference


def test_inference_stdout_contract_offline(monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPENENV_OFFLINE", "1")
    monkeypatch.setattr(inference, "TASKS", ["bug_triage_easy"])

    exit_code = inference.main()
    assert exit_code == 0

    output_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]

    start_indices = [idx for idx, line in enumerate(output_lines) if line.startswith("[START]")]
    step_indices = [idx for idx, line in enumerate(output_lines) if line.startswith("[STEP]")]
    end_indices = [idx for idx, line in enumerate(output_lines) if line.startswith("[END]")]

    assert len(start_indices) == 1
    assert len(step_indices) >= 1
    assert len(end_indices) == 1
    assert start_indices[0] < step_indices[0] < end_indices[0]

    end_line = output_lines[end_indices[0]]
    score_match = re.search(r"score=(\d+\.\d+)", end_line)
    assert score_match is not None

    score = float(score_match.group(1))
    assert 0.0 < score < 1.0

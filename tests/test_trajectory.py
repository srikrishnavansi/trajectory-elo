"""Two runs with the same final answer: the one with a bad step must rank lower, and the deciding step must be named."""

import json
from pathlib import Path

from trajectory_elo import RuleStepJudge, build_report, rank

DOC = {"id": "RPT-1", "text": "2023 study. Additive X cut capacity fade from 18% to 11%."}
SEARCH = {"type": "tool_call", "tool": "search", "args": {"query": "additive fade 2023"}, "result": {"docs": [DOC]}}
WRONG_MEMORY = {
    "type": "memory_write",
    "key": "additive_x.fade",
    "value": "Additive X cuts fade to 9%",
    "scope": "project",
    "confirmed": False,
}
FINAL = {
    "type": "final_answer",
    "text": "Additive X cut capacity fade from 18% to 11% [RPT-1].",
    "citations": ["RPT-1"],
}


def test_equal_final_answers_bad_step_ranks_lower(tmp_path):
    path = tmp_path / "runs.json"
    path.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "qid": "q1",
                        "query": "Which 2023 additive cut capacity fade?",
                        "trajectories": [
                            {"agent": "clean", "steps": [SEARCH, FINAL]},
                            {"agent": "bad-memory", "steps": [SEARCH, WRONG_MEMORY, FINAL]},
                        ],
                    }
                ]
            }
        )
    )

    experiment, elo = rank(path, RuleStepJudge())
    assert elo.scores["bad-memory"] < elo.scores["clean"]

    (game,) = experiment["q1"].pairwise_games.values()
    (result,) = game.evaluations.values()
    assert game.agent_a_answer.text == game.agent_b_answer.text  # identical final answers
    assert {"A": game.agent_a_answer.agent, "B": game.agent_b_answer.agent}[result.winner] == "clean"
    deciding = game.metadata["deciding_step"]
    assert (deciding["agent"], deciding["step"], deciding["issue"]) == ("bad-memory", 2, "ungrounded_memory_write")
    assert result.answer.winner_reasoning.startswith("bad-memory step 2 (memory_write")

    # Baseline: judging only the final answer cannot tell them apart.
    _, answer_only = rank(path, RuleStepJudge(), answer_only=True)
    assert answer_only.scores["bad-memory"] == answer_only.scores["clean"]


def test_shipped_trajectories():
    report = build_report(Path(__file__).parent.parent / "data" / "trajectories.json", RuleStepJudge())
    assert report["leaderboard"][0]["agent"] == "superagent"
    decided = [g for g in report["games"] if g["winner"] != "tie"]
    assert decided and all(g["deciding"] for g in decided)
    assert sum(g["answer_only"] == "tie" and g["winner"] != "tie" for g in report["games"]) >= 15

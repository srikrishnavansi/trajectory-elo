# Trajectory Elo

Pairwise Elo for agent runs that judges the path, not only the final message. Built on RAGElo 0.7.0.

## What it adds to RAGElo

1. `TrajectoryEvaluator`, a RAGElo pairwise answer evaluator that scores every step of a run (tool call, sub-agent hand-off, memory write, final answer) against a rubric, so two runs with the same final answer can still rank apart.
2. Its games go into RAGElo's own `Experiment` and `EloRanker` unchanged, and each game records the step that decided it.
3. A deterministic offline step judge, plus an optional Claude step judge behind `AnthropicProvider`, a RAGElo `BaseLLMProvider`.

## Run

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install ragelo==0.7.0 pytest
python trajectory_elo.py data/trajectories.json   # prints the tables below, writes out/report.html
pytest -q
```

Optional LLM judge: `pip install anthropic`, set `ANTHROPIC_API_KEY`, add `--judge llm` (one structured call per trajectory, `claude-haiku-5-5`).

## Leaderboard

Rule judge, 5 queries, 4 agent configs, 30 pairwise games. "Answer-only" is the same judge restricted to the final answer step, which is what a final-message evaluation sees.

| Rank | Agent | Trajectory Elo | Answer-only Elo | W-L-T | Step issues |
|---:|---|---:|---:|---|---|
| 1 | superagent | 1090 | 1005 | 9-0-6 | none |
| 2 | single-agent | 1023 | 1006 | 7-4-4 | wasted_tool_call x2 |
| 3 | superagent-compact | 965 | 1006 | 5-8-2 | lost_context_handoff x3, wasted_tool_call x1 |
| 4 | superagent-memory | 894 | 963 | 2-11-2 | unconfirmed_user_memory x1, ungrounded_citation x1, ungrounded_memory_write x2 |

Answer-only judging tied 27 of 30 games; step evidence decided 20 of those. Example deciding steps:

| Query | Game | Answer-only | Trajectory | Deciding step |
|---|---|---|---|---|
| q1 | superagent vs superagent-memory | tie | superagent | superagent-memory step 2 memory_write: "Al2O3 ALD cuts NMC811 fade at 45 C from 18% to 9% after 500 cycles": 9 is in no evidence seen before this step |
| q3 | superagent vs superagent-compact | tie | superagent | superagent-compact step 1 handoff: sub-agent never saw 2023, EZ-7, 20, 9 |
| q4 | single-agent vs superagent | tie | superagent | single-agent step 2 tool_call: none of its new results were used later |

All 30 games: `out/report.html`, screenshot `shots/leaderboard.png`.

A single run of the LLM judge on the same data gave the same order (1083, 1032, 987, 870) for about USD 0.005. It also caught what the rules cannot, the q3 answer that reports EZ-5 data as EZ-7. Its main error: it marked five clean hand-offs as lost context, and in the three that decided a game its own reason said nothing was dropped. The step schema now asks for the reason before the label; that version has not been run against the API.

## Input

`data/trajectories.json` is synthetic: fictional R&D reports and hand-written runs.

```json
{"queries": [{"qid": "q1", "query": "...", "trajectories": [{"agent": "superagent", "steps": [
  {"type": "tool_call", "tool": "search", "args": {"query": "..."}, "result": {"docs": [{"id": "RPT-0412", "text": "..."}]}},
  {"type": "handoff", "to": "literature-agent", "message": "...", "result": {"text": "...", "docs": []}},
  {"type": "memory_write", "key": "...", "value": "...", "scope": "project", "confirmed": false},
  {"type": "final_answer", "text": "...", "citations": ["RPT-0412"]}
]}]}]}
```

## Rubric

One issue per step, weighted by the damage it does after the run ends. Issues of the same kind on both sides cancel; the loser's heaviest remaining issue is the deciding step.

| Issue | Weight | Rule judge check |
|---|---:|---|
| ungrounded_memory_write | 3 | a number or identifier in the stored value appears in no evidence seen before the write |
| lost_context_handoff | 2 | a number or identifier from the query is missing from the hand-off message |
| ungrounded_citation | 2 | the answer cites an id the run never retrieved |
| unsupported_claim | 2 | a number or identifier in the answer appears in no evidence |
| unconfirmed_user_memory | 1.5 | a `scope: "user"` write without `confirmed: true` |
| wasted_tool_call | 1 | nothing new it returned is referenced by a later step |
| uncited_answer | 1 | the answer cites nothing |

The evaluator uses RAGElo's `custom_pairwise` name because `AnswerEvaluatorTypes` is a closed enum; inside RAGElo it would be its own member.

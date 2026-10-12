"""Trajectory Elo: judge every step of an agent run, then rank whole runs with RAGElo's pairwise Elo.

A RAGElo answer evaluator whose pairwise games are decided by step-level evidence (tool calls,
sub-agent hand-offs, memory writes, final answer) instead of by the final message alone.

    python trajectory_elo.py data/trajectories.json            # offline rule judge
    python trajectory_elo.py data/trajectories.json --judge llm  # Claude step judge, needs ANTHROPIC_API_KEY
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from ragelo import AgentAnswer, Experiment, get_agent_ranker
from ragelo.evaluators.answer_evaluators import BaseAnswerEvaluator
from ragelo.llm_providers.base_llm_provider import BaseLLMProvider
from ragelo.types.answer_formats import PairwiseEvaluationAnswer
from ragelo.types.configurations import PairwiseEvaluatorConfig
from ragelo.types.configurations.llm_provider_configs import LLMProviderConfig
from ragelo.types.formats import LLMInputPrompt, LLMResponseType, LLMUsage
from ragelo.types.query import Query
from ragelo.types.results import PairwiseGameEvaluatorResult
from ragelo.types.types import AnswerEvaluatorTypes

# Rubric: one issue per step, weighted by how much damage it does after the run ends.
WEIGHTS = {
    "ungrounded_memory_write": 3.0,  # a wrong fact persists into every later session
    "lost_context_handoff": 2.0,  # the sub-agent works on a different question
    "ungrounded_citation": 2.0,  # cites a source the run never retrieved
    "unsupported_claim": 2.0,  # states a number or identifier no evidence contains
    "unconfirmed_user_memory": 1.5,  # writes to the user's profile without asking
    "wasted_tool_call": 1.0,  # nothing new it returned was used later
    "uncited_answer": 1.0,
}
STEP_TYPES = {"tool_call", "handoff", "memory_write", "final_answer"}
# Claude Haiku 5.5, USD per million tokens (prompts under 100K tokens).
HAIKU_PRICE_IN, HAIKU_PRICE_OUT = 0.10, 0.50


@dataclass
class StepVerdict:
    step: int  # 1-based position in the trajectory
    type: str
    issue: str | None
    reason: str

    @property
    def penalty(self) -> float:
        return WEIGHTS.get(self.issue or "", 0.0)


def anchors(text: str) -> list[str]:
    """Numbers and identifiers (NMC811, EZ-7, 2022, RPT-0412), in order: what a hand-off must not drop and a claim must not invent."""
    tokens = re.findall(r"[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*", text)
    return list(dict.fromkeys(t for t in tokens if any(c.isdigit() for c in t) or sum(c.isupper() for c in t) >= 2))


class RuleStepJudge:
    """Deterministic, offline. Checks only what is mechanically checkable: ids, numbers, identifiers."""

    name = "rules"

    def score(self, query: str, steps: list[dict]) -> list[StepVerdict]:
        seen: dict[str, str] = {}  # doc id -> text, everything retrieved so far
        known = set(anchors(query))  # anchors the agent may legitimately use at this point
        verdicts = []
        for i, step in enumerate(steps):
            issue, reason = None, "ok"
            kind = step["type"]
            if kind == "tool_call":
                new = [d["id"] for d in step.get("result", {}).get("docs", []) if seen.get(d["id"]) != d["text"]]
                later = json.dumps([{k: v for k, v in s.items() if k != "result"} for s in steps[i + 1 :]])
                if not any(doc_id in later for doc_id in new):
                    issue = "wasted_tool_call"
                    reason = (
                        "none of its new results were used later" if new else "returned only evidence already seen"
                    )
            elif kind == "handoff":
                sent = set(anchors(step["message"]))
                missing = [t for t in anchors(query) if t not in sent]
                if missing:
                    issue = "lost_context_handoff"
                    reason = f"sub-agent never saw {', '.join(missing)}"
            elif kind == "memory_write":
                invented = [t for t in anchors(step["value"]) if t not in known]
                if invented:
                    issue = "ungrounded_memory_write"
                    reason = f'"{step["value"]}": {", ".join(invented)} is in no evidence seen before this step'
                elif step.get("scope") == "user" and not step.get("confirmed"):
                    issue, reason = "unconfirmed_user_memory", "writes to the user profile without asking"
            elif kind == "final_answer":
                citations = step.get("citations", [])
                unretrieved = [c for c in citations if c not in seen]
                unsupported = [t for t in anchors(step["text"]) if t not in known]
                if unretrieved:
                    issue, reason = "ungrounded_citation", f"cites {', '.join(unretrieved)}, never retrieved"
                elif not citations:
                    issue, reason = "uncited_answer", "no citations"
                elif unsupported:
                    issue, reason = "unsupported_claim", f"{', '.join(unsupported)} not in any evidence"
            result = step.get("result") or {}
            known.update(anchors(result.get("text", "")))
            for d in result.get("docs", []):
                seen[d["id"]] = d["text"]
                known.update(anchors(f"{d['id']} {d['text']}"))
            verdicts.append(StepVerdict(i + 1, kind, issue, reason))
        return verdicts


class AnthropicProvider(BaseLLMProvider):
    """RAGElo LLM provider for the Anthropic Messages API, structured output via messages.parse."""

    api_key_env_var = "ANTHROPIC_API_KEY"

    def __init__(self, model: str = "claude-haiku-5-5", max_tokens: int = 4000):
        super().__init__(LLMProviderConfig(max_tokens=max_tokens))
        import anthropic  # optional dependency, only the LLM judge needs it

        self.client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY
        self.model = model

    async def call_async(self, input: LLMInputPrompt, response_schema: type[BaseModel]) -> LLMResponseType:
        msg = await self.client.messages.parse(
            model=self.model,
            max_tokens=self.config.max_tokens,
            system=input.system_prompt,
            messages=[{"role": "user", "content": input.user_message}],
            output_format=response_schema,
            output_config={"effort": "low"},
        )
        if msg.parsed_output is None:
            raise ValueError(f"no structured output, stop_reason={msg.stop_reason}")
        return LLMResponseType(
            raw_answer="".join(b.text for b in msg.content if b.type == "text"),
            parsed_answer=msg.parsed_output,
            usage=LLMUsage(input_tokens=msg.usage.input_tokens, output_tokens=msg.usage.output_tokens),
        )


class _StepCall(BaseModel):
    step: int
    # reason comes before issue so the label follows the reasoning; with issue first, a live run
    # sometimes labelled a step that its own reason had cleared.
    reason: str
    issue: Literal[("none", *WEIGHTS)]  # type: ignore[valid-type]


class _StepCalls(BaseModel):
    steps: list[_StepCall]


LLM_RUBRIC = """You audit the steps of a research-assistant agent run, not just its answer.
Judge each step only with what was visible up to that step. Give each step exactly one issue, the most severe, or "none":
- ungrounded_memory_write: a memory write stores a fact or number that the evidence retrieved before it does not support.
- lost_context_handoff: a hand-off message drops a constraint of the user query (entity, date range, condition, threshold).
- ungrounded_citation: the final answer cites a source id the run never retrieved.
- unsupported_claim: the final answer states something the retrieved evidence does not support.
- unconfirmed_user_memory: a write to the user's long-term profile (scope "user") without the user confirming it.
- wasted_tool_call: a tool call whose new results nothing later uses, or that repeats an earlier call.
- uncited_answer: the final answer cites nothing.
Return one entry per step, numbered as given, with a one-sentence reason."""


class LLMStepJudge:
    """One structured LLM call per trajectory, scoring every step against the same rubric as RuleStepJudge."""

    name = "llm"

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider
        self.usage = LLMUsage()
        self._cache: dict[str, list[StepVerdict]] = {}  # the answer-only baseline reuses the same verdicts

    def score(self, query: str, steps: list[dict]) -> list[StepVerdict]:
        key = json.dumps([query, steps], sort_keys=True)
        if key not in self._cache:
            listing = "\n".join(f"{i}. {json.dumps(s)}" for i, s in enumerate(steps, 1))
            prompt = LLMInputPrompt(system_prompt=LLM_RUBRIC, user_message=f"User query: {query}\n\nSteps:\n{listing}")
            response = self.provider(prompt, _StepCalls)
            self.usage += response.usage or LLMUsage()
            calls = {c.step: c for c in response.parsed_answer.steps}
            self._cache[key] = [
                StepVerdict(
                    i,
                    s["type"],
                    None if (c := calls.get(i)) is None or c.issue == "none" else c.issue,
                    c.reason if c else "not judged",
                )
                for i, s in enumerate(steps, 1)
            ]
        return self._cache[key]

    @property
    def cost_usd(self) -> float:
        return (self.usage.input_tokens * HAIKU_PRICE_IN + self.usage.output_tokens * HAIKU_PRICE_OUT) / 1e6


def decide(va: list[StepVerdict], vb: list[StepVerdict]) -> tuple[str, StepVerdict | None]:
    """RAGElo winner ("A", "B" or "C" for a tie) and the loser's step that decided it.

    Issues of the same kind on both sides cancel out; of the loser's remaining issues the heaviest
    (earliest on ties) is the deciding step.
    """
    pa, pb = sum(v.penalty for v in va), sum(v.penalty for v in vb)
    if pa == pb:
        return "C", None
    winner, loser = ("A", vb) if pa < pb else ("B", va)
    cancel = Counter(v.issue for v in (va if winner == "A" else vb) if v.issue)
    remaining = []
    for v in loser:
        if v.issue and cancel[v.issue]:
            cancel[v.issue] -= 1
        elif v.issue:
            remaining.append(v)
    return winner, max(remaining, key=lambda v: v.penalty)  # max keeps the first of equal penalties


class TrajectoryEvaluatorConfig(PairwiseEvaluatorConfig):
    # ponytail: RAGElo's evaluator-name enum is closed, so this rides its custom_pairwise slot.
    # Upstream it would be a new AnswerEvaluatorTypes.TRAJECTORY_PAIRWISE member.
    evaluator_name: AnswerEvaluatorTypes = AnswerEvaluatorTypes.CUSTOM_PAIRWISE
    answer_only: bool = False  # baseline: judge only the final_answer step, like a final-message eval
    use_progress_bar: bool = False


class TrajectoryEvaluator(BaseAnswerEvaluator[TrajectoryEvaluatorConfig, PairwiseGameEvaluatorResult]):
    """Pairwise answer evaluator over agent trajectories stored in AgentAnswer.metadata["steps"]."""

    config: TrajectoryEvaluatorConfig
    answer_format = PairwiseEvaluationAnswer
    result_type = PairwiseGameEvaluatorResult

    def __init__(self, config: TrajectoryEvaluatorConfig, judge: RuleStepJudge | LLMStepJudge):
        super().__init__(config, getattr(judge, "provider", None))  # type: ignore[arg-type]
        self.judge = judge

    def prepare_query(self, query: Query) -> None:
        """RAGElo's hook for producing what an evaluator grades against: here, the per-step verdicts."""
        for answer in query.answers.values():
            verdicts = self.judge.score(query.query, answer.metadata["steps"])
            answer.metadata["step_verdicts"] = [asdict(v) for v in verdicts]

    def _verdicts(self, answer: AgentAnswer) -> list[StepVerdict]:
        verdicts = [StepVerdict(**v) for v in answer.metadata["step_verdicts"]]
        return [v for v in verdicts if v.type == "final_answer"] if self.config.answer_only else verdicts

    async def evaluate_async(self, eval_sample):
        query, game = eval_sample
        a, b = game.agent_a_answer, game.agent_b_answer
        va, vb = self._verdicts(a), self._verdicts(b)
        winner, deciding = decide(va, vb)
        loser = {"A": b.agent, "B": a.agent}.get(winner)
        game.metadata = {"deciding_step": asdict(deciding) | {"agent": loser} if deciding else None}
        pa, pb = sum(v.penalty for v in va), sum(v.penalty for v in vb)
        return PairwiseGameEvaluatorResult(
            qid=query.qid,
            agent_a=a.agent,
            agent_b=b.agent,
            evaluator_name=str(self.config.evaluator_name),
            answer=PairwiseEvaluationAnswer(
                answer_a_weaknesses=[f"step {v.step} {v.issue}: {v.reason}" for v in va if v.issue],
                answer_b_weaknesses=[f"step {v.step} {v.issue}: {v.reason}" for v in vb if v.issue],
                answer_a_analysis=f"step penalty {pa:g}",
                answer_b_analysis=f"step penalty {pb:g}",
                comparison_reasoning=f"[[A]] {pa:g} vs [[B]] {pb:g}",
                winner_reasoning=(
                    f"{loser} step {deciding.step} ({deciding.type}, {deciding.issue}): {deciding.reason}"
                    if deciding
                    else "no step separates them"
                ),
                winner=winner,
            ),
        )


def load_experiment(path: str | Path, name: str = "trajectories") -> Experiment:
    """Each trajectory becomes a RAGElo AgentAnswer: text is the final answer, metadata["steps"] the run."""
    data = json.loads(Path(path).read_text())
    experiment = Experiment(name, save_on_disk=False, rich_print=False)
    for q in data["queries"]:
        experiment.add_query(q["query"], query_id=q["qid"])
        for t in q["trajectories"]:
            steps = t["steps"]
            bad = {s.get("type") for s in steps} - STEP_TYPES
            if bad or not steps or steps[-1]["type"] != "final_answer":
                raise ValueError(
                    f"{q['qid']}/{t['agent']}: steps must use {sorted(STEP_TYPES)} and end in final_answer"
                )
            answer = AgentAnswer(qid=q["qid"], agent=t["agent"], text=steps[-1]["text"], metadata={"steps": steps})
            experiment.add_agent_answer(answer)
    return experiment


def rank(path: str | Path, judge: RuleStepJudge | LLMStepJudge, answer_only: bool = False, seed: int = 0):
    """Judge every pair with TrajectoryEvaluator, then run RAGElo's EloRanker over the games."""
    random.seed(seed)  # RAGElo shuffles game order in every Elo tournament
    experiment = load_experiment(path)
    TrajectoryEvaluator(TrajectoryEvaluatorConfig(answer_only=answer_only), judge).evaluate_experiment(experiment)
    elo = get_agent_ranker("elo").run(experiment)
    return experiment, elo


def build_report(path: str | Path, judge: RuleStepJudge | LLMStepJudge) -> dict:
    exp, elo = rank(path, judge)
    base_exp, base_elo = rank(path, judge, answer_only=True)
    name = str(AnswerEvaluatorTypes.CUSTOM_PAIRWISE)
    games, record, issues = [], {}, {}
    for q in exp:
        for agent, answer in q.answers.items():
            issues.setdefault(agent, Counter()).update(
                v["issue"] for v in answer.metadata["step_verdicts"] if v["issue"]
            )
        for gid, game in q.pairwise_games.items():
            a, b = game.agent_a_answer.agent, game.agent_b_answer.agent
            winner = game.evaluations[name].winner
            base_winner = base_exp[q.qid].pairwise_games[gid].evaluations[name].winner
            for agent, result in ((a, {"A": "W", "B": "L"}), (b, {"A": "L", "B": "W"})):
                record.setdefault(agent, Counter())[result.get(winner, "T")] += 1
            pick = {"A": a, "B": b, "C": "tie"}
            games.append(
                {
                    "qid": q.qid,
                    "a": a,
                    "b": b,
                    "answer_only": pick[base_winner],
                    "winner": pick[winner],
                    "deciding": game.metadata["deciding_step"],
                }
            )
    games.sort(key=lambda g: (g["qid"], g["a"], g["b"]))
    leaderboard = [
        {
            "agent": agent,
            "elo": score,
            "answer_only_elo": base_elo.scores[agent],
            "wlt": f"{record[agent]['W']}-{record[agent]['L']}-{record[agent]['T']}",
            "issues": dict(issues[agent]),
        }
        for agent, score in sorted(elo.scores.items(), key=lambda kv: -kv[1])
    ]
    return {"judge": judge.name, "queries": len(exp), "leaderboard": leaderboard, "games": games}


def to_markdown(report: dict) -> str:
    lines = [
        f"Judge: {report['judge']}. {report['queries']} queries, {len(report['games'])} pairwise games, RAGElo EloRanker.",
        "",
        "| Rank | Agent | Trajectory Elo | Answer-only Elo | W-L-T | Step issues |",
        "|---:|---|---:|---:|---|---|",
    ]
    for i, row in enumerate(report["leaderboard"], 1):
        found = ", ".join(f"{k} x{n}" for k, n in sorted(row["issues"].items())) or "none"
        lines.append(
            f"| {i} | {row['agent']} | {row['elo']:.0f} | {row['answer_only_elo']:.0f} | {row['wlt']} | {found} |"
        )
    lines += ["", "| Query | Game | Answer-only | Trajectory | Deciding step |", "|---|---|---|---|---|"]
    for g in report["games"]:
        d = g["deciding"]
        step = f"{d['agent']} step {d['step']} {d['type']}: {d['reason']}" if d else "none, steps tie"
        lines.append(f"| {g['qid']} | {g['a']} vs {g['b']} | {g['answer_only']} | {g['winner']} | {step} |")
    return "\n".join(lines)


def to_html(report: dict) -> str:
    e = html.escape
    top = max(r["elo"] for r in report["leaderboard"])
    low = min(r["elo"] for r in report["leaderboard"])
    flipped = sum(g["answer_only"] == "tie" and g["winner"] != "tie" for g in report["games"])
    ties = sum(g["answer_only"] == "tie" for g in report["games"])
    rows = []
    for i, r in enumerate(report["leaderboard"], 1):
        width = 18 + 82 * (r["elo"] - low) / ((top - low) or 1)
        chips = (
            "".join(
                f'<span class="chip">{e(k.replace("_", " "))} <b>{n}</b></span>'
                for k, n in sorted(r["issues"].items())
            )
            or '<span class="clean">no step issues</span>'
        )
        rows.append(
            f'<tr><td class="num">{i}</td><td class="agent nm">{e(r["agent"])}</td>'
            f'<td><div class="bar"><span style="width:{width:.0f}%"></span><em>{r["elo"]:.0f}</em></div></td>'
            f'<td class="num muted">{r["answer_only_elo"]:.0f}</td><td class="num">{e(r["wlt"])}</td><td>{chips}</td></tr>'
        )
    game_rows = []
    for g in report["games"]:
        d = g["deciding"]
        if d is None:
            continue
        hidden = g["answer_only"] == "tie"
        game_rows.append(
            f'<tr class="{"flip" if hidden else ""}"><td class="mono">{e(g["qid"])}</td>'
            f'<td><span class="nm">{e(g["a"])}</span> <span class="muted">vs</span> <span class="nm">{e(g["b"])}</span></td>'
            f'<td class="nm {"muted" if hidden else ""}">{e(g["answer_only"])}</td><td class="agent nm">{e(g["winner"])}</td>'
            f'<td><span class="step">{e(d["agent"])} · step {d["step"]} · {e(d["type"])}</span> '
            f'<span class="issue">{e(d["issue"].replace("_", " "))}</span><div class="why">{e(d["reason"])}</div></td></tr>'
        )
    n_ties = sum(g["deciding"] is None for g in report["games"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Trajectory Elo</title>
<style>
:root{{--bg:#f7f7f5;--card:#fff;--ink:#16181d;--muted:#6b7079;--line:#e6e6e1;--accent:#1f6f6b;--bad:#b4322c;--badbg:#fbeceb;--flip:#fff8e6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Inter","Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:36px 16px 48px}}
h1{{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}}h2{{font-size:15px;margin:30px 0 10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}}
.sub{{color:var(--muted);margin:0 0 22px}}
.callout{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:10px;padding:14px 18px;font-size:15px}}
.callout b{{color:var(--accent)}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
th{{text-align:left;font-size:12px;color:var(--muted);font-weight:600;padding:10px 12px;border-bottom:1px solid var(--line);background:#fbfbf9}}
td{{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top}}tr:last-child td{{border-bottom:0}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}.nm{{white-space:nowrap}}.muted{{color:var(--muted)}}.agent{{font-weight:600}}.mono{{font-family:ui-monospace,Menlo,monospace}}
.bar{{position:relative;height:22px;background:#eef3f2;border-radius:6px;min-width:220px}}
.bar span{{position:absolute;inset:0 auto 0 0;background:var(--accent);border-radius:6px;opacity:.85}}
.bar em{{position:absolute;right:8px;top:2px;font-style:normal;font-weight:700;font-variant-numeric:tabular-nums}}
.chip{{display:inline-block;margin:0 6px 4px 0;padding:2px 8px;border-radius:999px;background:var(--badbg);color:var(--bad);font-size:12px}}
.clean{{color:var(--accent);font-size:12px}}
.flip td{{background:var(--flip)}}.step{{font-weight:600}}.issue{{color:var(--bad);font-weight:600;margin-left:4px;white-space:nowrap}}.why{{color:var(--muted);font-size:13px}}
.legend{{color:var(--muted);font-size:12px;margin:8px 2px 0}}.legend i{{display:inline-block;width:10px;height:10px;background:var(--flip);border:1px solid #f0dfae;margin-right:5px;vertical-align:-1px}}
</style></head><body><main>
<h1>Trajectory Elo</h1>
<p class="sub">RAGElo pairwise Elo over whole agent runs · judge: {e(report["judge"])} · {report["queries"]} queries ·
{len(report["games"])} games · synthetic data</p>
<div class="callout">Judging only the final answer tied <b>{ties} of {len(report["games"])}</b> games.
Step-level evidence decided <b>{flipped}</b> of those ties.</div>
<h2>Leaderboard</h2>
<table><thead><tr><th class="num">#</th><th>Agent</th><th>Trajectory Elo</th><th class="num">Answer-only Elo</th>
<th class="num">W-L-T</th><th>Step issues across all runs</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
<h2>Deciding step per game</h2>
<table><thead><tr><th>Query</th><th>Game</th><th>Answer-only</th><th>Trajectory winner</th><th>Deciding step (loser)</th></tr></thead>
<tbody>{"".join(game_rows)}</tbody></table>
<p class="legend"><i></i>final answers judged equal, decided by a step · {n_ties} games tied on steps too are not listed</p>
</main></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("trajectories")
    parser.add_argument("--judge", choices=["rules", "llm"], default="rules")
    parser.add_argument("--html", default="out/report.html")
    args = parser.parse_args()
    judge = LLMStepJudge(AnthropicProvider()) if args.judge == "llm" else RuleStepJudge()
    report = build_report(args.trajectories, judge)
    print(to_markdown(report))
    Path(args.html).parent.mkdir(parents=True, exist_ok=True)
    Path(args.html).write_text(to_html(report))
    print(f"\nwrote {args.html}")
    if isinstance(judge, LLMStepJudge):
        u = judge.usage
        print(f"LLM judge: {u.input_tokens} input + {u.output_tokens} output tokens, about USD {judge.cost_usd:.4f}")


if __name__ == "__main__":
    main()

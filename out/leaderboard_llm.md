Judge: llm. 5 queries, 30 pairwise games, RAGElo EloRanker.

| Rank | Agent | Trajectory Elo | Answer-only Elo | W-L-T | Step issues |
|---:|---|---:|---:|---|---|
| 1 | superagent | 1083 | 1024 | 9-1-5 | lost_context_handoff x1 |
| 2 | single-agent | 1032 | 981 | 9-5-1 | unsupported_claim x1, wasted_tool_call x3 |
| 3 | superagent-compact | 987 | 984 | 5-6-4 | lost_context_handoff x3, unsupported_claim x1 |
| 4 | superagent-memory | 870 | 984 | 1-12-2 | lost_context_handoff x4, unconfirmed_user_memory x1, ungrounded_citation x1, ungrounded_memory_write x2 |

| Query | Game | Answer-only | Trajectory | Deciding step |
|---|---|---|---|---|
| q1 | single-agent vs superagent | tie | tie | none, steps tie |
| q1 | single-agent vs superagent-compact | tie | single-agent | superagent-compact step 1 handoff: The handoff message to the literature agent drops the user's constraints on NMC811 chemistry, 45 C cycling, and the since-2022 date range, asking only for coatings that reduce fade generally. |
| q1 | single-agent vs superagent-memory | tie | single-agent | superagent-memory step 2 memory_write: The memory write states Al2O3 fade fell from 18% to 9%, but the retrieved evidence (RPT-0412) reports a drop from 18% to 11%. |
| q1 | superagent vs superagent-compact | tie | superagent | superagent-compact step 1 handoff: The handoff message to the literature agent drops the user's constraints on NMC811 chemistry, 45 C cycling, and the since-2022 date range, asking only for coatings that reduce fade generally. |
| q1 | superagent vs superagent-memory | tie | superagent | superagent-memory step 2 memory_write: The memory write states Al2O3 fade fell from 18% to 9%, but the retrieved evidence (RPT-0412) reports a drop from 18% to 11%. |
| q1 | superagent-compact vs superagent-memory | tie | superagent-compact | superagent-memory step 2 memory_write: The memory write states Al2O3 fade fell from 18% to 9%, but the retrieved evidence (RPT-0412) reports a drop from 18% to 11%. |
| q2 | single-agent vs superagent | superagent | superagent | single-agent step 3 final_answer: The answer says 'Both 2024 pilot-line reports' but the evidence shows RPT-0533 is a 2024 follow-up that reports reduced drift, not a separate report of drift, so the framing is only loosely supported; the cited figures themselves match the evidence. |
| q2 | single-agent vs superagent-compact | superagent-compact | superagent-compact | single-agent step 3 final_answer: The answer says 'Both 2024 pilot-line reports' but the evidence shows RPT-0533 is a 2024 follow-up that reports reduced drift, not a separate report of drift, so the framing is only loosely supported; the cited figures themselves match the evidence. |
| q2 | single-agent vs superagent-memory | superagent-memory | single-agent | superagent-memory step 1 handoff: The handoff message asks for 12-hour runs only and 2024 reports, which it preserves, so no constraint is dropped; the retrieved docs also match the constraints. |
| q2 | superagent vs superagent-compact | tie | tie | none, steps tie |
| q2 | superagent vs superagent-memory | tie | superagent | superagent-memory step 1 handoff: The handoff message asks for 12-hour runs only and 2024 reports, which it preserves, so no constraint is dropped; the retrieved docs also match the constraints. |
| q2 | superagent-compact vs superagent-memory | tie | superagent-compact | superagent-memory step 1 handoff: The handoff message asks for 12-hour runs only and 2024 reports, which it preserves, so no constraint is dropped; the retrieved docs also match the constraints. |
| q3 | single-agent vs superagent | tie | superagent | single-agent step 2 tool_call: Reading RPT-0611 repeats information already fully present in the search snippet and adds no new facts that the answer uses beyond what step 1 showed. |
| q3 | single-agent vs superagent-compact | single-agent | single-agent | superagent-compact step 1 handoff: The handoff message 'Check enzyme stability data at high pH' drops the specific constraints of the query: enzyme EZ-7, the 2023 date range, and the pH 9 condition with the 20% activity-loss threshold. |
| q3 | single-agent vs superagent-memory | tie | single-agent | superagent-memory step 1 handoff: The handoff message keeps the enzyme, pH 9, year 2023, and the 20% threshold, so no query constraint is dropped. |
| q3 | superagent vs superagent-compact | superagent | superagent | superagent-compact step 1 handoff: The handoff message 'Check enzyme stability data at high pH' drops the specific constraints of the query: enzyme EZ-7, the 2023 date range, and the pH 9 condition with the 20% activity-loss threshold. |
| q3 | superagent vs superagent-memory | tie | superagent | superagent-memory step 1 handoff: The handoff message keeps the enzyme, pH 9, year 2023, and the 20% threshold, so no query constraint is dropped. |
| q3 | superagent-compact vs superagent-memory | superagent-memory | superagent-memory | superagent-compact step 2 final_answer: The final answer claims the study shows EZ-7 retaining 88% activity, but the retrieved document RPT-0598 reports that enzyme EZ-5 (not EZ-7) retained 88% activity, so the answer misattributes the evidence and its conclusion about EZ-7 is unsupported. |
| q4 | single-agent vs superagent | tie | superagent | single-agent step 2 tool_call: The second search re-retrieves RPT-0702, which was already returned in step 1, and its new result (RPT-0450, a 2021 screening) is never used in the final answer. |
| q4 | single-agent vs superagent-compact | tie | superagent-compact | single-agent step 2 tool_call: The second search re-retrieves RPT-0702, which was already returned in step 1, and its new result (RPT-0450, a 2021 screening) is never used in the final answer. |
| q4 | single-agent vs superagent-memory | tie | single-agent | superagent-memory step 2 memory_write: The memory stores a first-cycle efficiency of 93.5%, but the retrieved evidence reports 91.5% for the adopted 1.2 wt% loading, so the stored number is unsupported. |
| q4 | superagent vs superagent-compact | tie | tie | none, steps tie |
| q4 | superagent vs superagent-memory | tie | superagent | superagent-memory step 2 memory_write: The memory stores a first-cycle efficiency of 93.5%, but the retrieved evidence reports 91.5% for the adopted 1.2 wt% loading, so the stored number is unsupported. |
| q4 | superagent-compact vs superagent-memory | tie | superagent-compact | superagent-memory step 2 memory_write: The memory stores a first-cycle efficiency of 93.5%, but the retrieved evidence reports 91.5% for the adopted 1.2 wt% loading, so the stored number is unsupported. |
| q5 | single-agent vs superagent | tie | single-agent | superagent step 1 handoff: The handoff message drops nothing material from the query; it keeps both pilots, both metrics, the 2024 scope, and asks for report IDs, so the issue is none. |
| q5 | single-agent vs superagent-compact | tie | single-agent | superagent-compact step 2 handoff: The handoff message drops the 2024 date constraint and the SR-A/SR-B pilot names, asking to compare 'solvent-recovery pilots' generally, which loses the user's scope. |
| q5 | single-agent vs superagent-memory | single-agent | single-agent | superagent-memory step 2 final_answer: The final answer cites RPT-0811, which the run never retrieved; the retrieved documents were only RPT-0801 and RPT-0806. |
| q5 | superagent vs superagent-compact | tie | tie | none, steps tie |
| q5 | superagent vs superagent-memory | superagent | tie | none, steps tie |
| q5 | superagent-compact vs superagent-memory | superagent-compact | tie | none, steps tie |

wrote out/report_llm.html
LLM judge: 25645 input + 4045 output tokens, about USD 0.0046

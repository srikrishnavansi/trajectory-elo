Judge: rules. 5 queries, 30 pairwise games, RAGElo EloRanker.

| Rank | Agent | Trajectory Elo | Answer-only Elo | W-L-T | Step issues |
|---:|---|---:|---:|---|---|
| 1 | superagent | 1090 | 1005 | 9-0-6 | none |
| 2 | single-agent | 1023 | 1006 | 7-4-4 | wasted_tool_call x2 |
| 3 | superagent-compact | 965 | 1006 | 5-8-2 | lost_context_handoff x3, wasted_tool_call x1 |
| 4 | superagent-memory | 894 | 963 | 2-11-2 | unconfirmed_user_memory x1, ungrounded_citation x1, ungrounded_memory_write x2 |

| Query | Game | Answer-only | Trajectory | Deciding step |
|---|---|---|---|---|
| q1 | single-agent vs superagent | tie | tie | none, steps tie |
| q1 | single-agent vs superagent-compact | tie | single-agent | superagent-compact step 1 handoff: sub-agent never saw NMC811, 45, 2022 |
| q1 | single-agent vs superagent-memory | tie | single-agent | superagent-memory step 2 memory_write: "Al2O3 ALD cuts NMC811 fade at 45 C from 18% to 9% after 500 cycles": 9 is in no evidence seen before this step |
| q1 | superagent vs superagent-compact | tie | superagent | superagent-compact step 1 handoff: sub-agent never saw NMC811, 45, 2022 |
| q1 | superagent vs superagent-memory | tie | superagent | superagent-memory step 2 memory_write: "Al2O3 ALD cuts NMC811 fade at 45 C from 18% to 9% after 500 cycles": 9 is in no evidence seen before this step |
| q1 | superagent-compact vs superagent-memory | tie | superagent-compact | superagent-memory step 2 memory_write: "Al2O3 ALD cuts NMC811 fade at 45 C from 18% to 9% after 500 cycles": 9 is in no evidence seen before this step |
| q2 | single-agent vs superagent | tie | superagent | single-agent step 2 tool_call: none of its new results were used later |
| q2 | single-agent vs superagent-compact | tie | superagent-compact | single-agent step 2 tool_call: none of its new results were used later |
| q2 | single-agent vs superagent-memory | tie | single-agent | superagent-memory step 2 memory_write: writes to the user profile without asking |
| q2 | superagent vs superagent-compact | tie | tie | none, steps tie |
| q2 | superagent vs superagent-memory | tie | superagent | superagent-memory step 2 memory_write: writes to the user profile without asking |
| q2 | superagent-compact vs superagent-memory | tie | superagent-compact | superagent-memory step 2 memory_write: writes to the user profile without asking |
| q3 | single-agent vs superagent | tie | tie | none, steps tie |
| q3 | single-agent vs superagent-compact | tie | single-agent | superagent-compact step 1 handoff: sub-agent never saw 2023, EZ-7, 20, 9 |
| q3 | single-agent vs superagent-memory | tie | tie | none, steps tie |
| q3 | superagent vs superagent-compact | tie | superagent | superagent-compact step 1 handoff: sub-agent never saw 2023, EZ-7, 20, 9 |
| q3 | superagent vs superagent-memory | tie | tie | none, steps tie |
| q3 | superagent-compact vs superagent-memory | tie | superagent-memory | superagent-compact step 1 handoff: sub-agent never saw 2023, EZ-7, 20, 9 |
| q4 | single-agent vs superagent | tie | superagent | single-agent step 2 tool_call: none of its new results were used later |
| q4 | single-agent vs superagent-compact | tie | superagent-compact | single-agent step 2 tool_call: none of its new results were used later |
| q4 | single-agent vs superagent-memory | tie | single-agent | superagent-memory step 2 memory_write: "2025 standard: 1.2 wt% CMC, first-cycle efficiency 93.5%": 93.5 is in no evidence seen before this step |
| q4 | superagent vs superagent-compact | tie | tie | none, steps tie |
| q4 | superagent vs superagent-memory | tie | superagent | superagent-memory step 2 memory_write: "2025 standard: 1.2 wt% CMC, first-cycle efficiency 93.5%": 93.5 is in no evidence seen before this step |
| q4 | superagent-compact vs superagent-memory | tie | superagent-compact | superagent-memory step 2 memory_write: "2025 standard: 1.2 wt% CMC, first-cycle efficiency 93.5%": 93.5 is in no evidence seen before this step |
| q5 | single-agent vs superagent | tie | tie | none, steps tie |
| q5 | single-agent vs superagent-compact | tie | single-agent | superagent-compact step 2 handoff: sub-agent never saw 2024, SR-A, SR-B |
| q5 | single-agent vs superagent-memory | single-agent | single-agent | superagent-memory step 2 final_answer: cites RPT-0811, never retrieved |
| q5 | superagent vs superagent-compact | tie | superagent | superagent-compact step 2 handoff: sub-agent never saw 2024, SR-A, SR-B |
| q5 | superagent vs superagent-memory | superagent | superagent | superagent-memory step 2 final_answer: cites RPT-0811, never retrieved |
| q5 | superagent-compact vs superagent-memory | superagent-compact | superagent-memory | superagent-compact step 2 handoff: sub-agent never saw 2024, SR-A, SR-B |

wrote out/report.html

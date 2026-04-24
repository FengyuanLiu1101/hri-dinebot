# DineBot Test Results

This file is populated by running the evaluation against both Agent A and
Agent B with the 10 canonical test questions in `test_questions.txt`.

## How to generate

From the project root:

```bash
python main.py --agent a     # run Agent A interactively and paste each Q
python main.py --agent b     # run Agent B interactively and paste each Q
```

Copy each answer into the matching row below.

| # | Question | Agent A answer | Agent B answer |
|---|----------|----------------|----------------|
| 1 | Hello, what can you do? | _fill in_ | _fill in_ |
| 2 | What is the minimum distance you keep from people? | _fill in_ | _fill in_ |
| 3 | Can you deliver to table 13? | _fill in_ | _fill in_ |
| 4 | What happens if you detect an obstacle? | _fill in_ | _fill in_ |
| 5 | What main courses do you have? | _fill in_ | _fill in_ |
| 6 | How do you confirm an order before delivering? | _fill in_ | _fill in_ |
| 7 | What is your current status? | _fill in_ | _fill in_ |
| 8 | Can you take my order? | _fill in_ | _fill in_ |
| 9 | What do you do if there is a fire alarm? | _fill in_ | _fill in_ |
| 10 | How many dishes can you carry at once? | _fill in_ | _fill in_ |

## Observations

- Agent A latency: ~instant (offline).
- Agent B latency: varies with OpenAI round-trip plus critic retries.
- See `comparison_report.md` for a qualitative assessment.

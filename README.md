# DineBot — HRI Food Delivery Robot Agent

DineBot is a Human–Robot Interaction (HRI) AI project for a fictional
indoor restaurant food-delivery robot. It ships with **two
interchangeable agents** and an animated **Streamlit control panel**
that visualizes the robot and the restaurant floor in real time.

- **Agent A – Rule-Based** (`agent_a/`): fully offline. Intent
  classification + TF retrieval + handcrafted templates. No API needed.
- **Agent B – RAG + MAS** (`agent_b/`): a Multi-Agent System composed
  of `RetrieverAgent` (OpenAI embeddings + Chroma), `GeneratorAgent`
  (GPT-4o-mini), and `CriticAgent` (GPT-4o-mini) orchestrated with a
  self-revision loop.

## Project Layout

```
HRIagent/
├── main.py
├── requirements.txt
├── .env
├── config/agent_config.py
├── knowledge_base/                # 5 authoritative text files
├── utils/                         # file_loader, text_processing, logger
├── agent_a/                       # Rule-based agent
├── agent_b/
│   ├── rag_agent.py
│   └── mas/                       # retriever / generator / critic / orchestrator
├── evaluation/                    # test questions + comparison report
├── ui/                            # Streamlit app + animated robot
└── logs/                          # auto-created at runtime
```

## Setup

1. **Python 3.10+** recommended.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Edit `.env` and set your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-...
   ```
   Agent A does **not** need the key. Agent B will gracefully fall back
   to an offline stub mode if the key is missing, but for real answers
   you need a valid key.

## Running

- **Agent A (terminal)**
  ```bash
  python main.py --agent a
  ```

- **Agent B (terminal)**
  ```bash
  python main.py --agent b
  ```

- **Animated UI (Streamlit)**
  ```bash
  streamlit run ui/app.py
  ```

The UI lets you switch between Agent A and Agent B from the sidebar.
Switching agents clears the chat but preserves session stats such as
deliveries completed and battery level.

## Features

- Restaurant-floor SVG map with live robot position, target-table
  highlighting, and hatched off-limits zones (tables 11-15 terrace).
- Seven animated robot states (IDLE, LOADING, DELIVERING, WAITING,
  RETURNING, EMERGENCY, LOW_BATTERY) with CSS keyframe animations.
- Chat bubbles with typing indicator; Agent B responses come with an
  expandable **MAS Trace** panel showing retrieved chunks, critic
  verdict, and retry count.
- Session logger writes to `logs/session_YYYYMMDD_HHMMSS.log`.

## Evaluation

See `evaluation/comparison_report.md` for the qualitative comparison of
Agent A vs. Agent B on the canonical 10-question test set in
`evaluation/test_questions.txt`.

## Notes

- Chroma persists its vector store to `agent_b/vectorstore/`; it is
  built the first time you run Agent B with a valid API key.
- Agent A is deterministic and runs without any external API call.
- Every safety-relevant response is gated by the shared `CAN_DO` /
  `CANNOT_DO` contract defined in `config/agent_config.py` and is
  enforced at runtime by the `CriticAgent` in Agent B.

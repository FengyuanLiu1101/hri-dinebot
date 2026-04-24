"""
Orchestrator: coordinates the Retriever, Generator, and Critic sub-agents.

Pipeline:
    retrieve -> generate -> critic -> (optional regenerate with feedback)

The loop terminates either when the critic returns PASS or when
``MAS_CONFIG["critic_max_retries"]`` is reached.
"""

from __future__ import annotations

from config.agent_config import AGENT_NAME, AGENT_VERSION, MAS_CONFIG
from utils.logger import log_error, log_mas_trace, log_query, log_response

from agent_b.mas.critic_agent import CriticAgent
from agent_b.mas.generator_agent import GeneratorAgent
from agent_b.mas.retriever_agent import RetrieverAgent


class Orchestrator:
    """End-to-end MAS pipeline for Agent B."""

    def __init__(self) -> None:
        self.agent_name: str = f"{AGENT_NAME}-B"
        self.top_k: int = int(MAS_CONFIG["retriever_top_k"])
        self.max_retries: int = int(MAS_CONFIG["critic_max_retries"])

        log_mas_trace("orchestrator_init", "Building sub-agents...")
        self.retriever = RetrieverAgent()
        self.generator = GeneratorAgent()
        self.critic = CriticAgent()
        log_mas_trace("orchestrator_init", "Sub-agents ready.")

    def run_once(self, query: str) -> dict:
        """Execute one full retrieve/generate/critic cycle for ``query``.

        Returns
        -------
        dict
            ``{"response", "context", "retries", "verdict"}``.
        """
        log_query(self.agent_name, query)

        context: list[str] = []
        response: str = ""
        verdict: dict = {"status": "PASS", "feedback": ""}
        retries: int = 0

        try:
            log_mas_trace("orchestrator_step", "Starting pipeline for new query.")
            context = self.retriever.retrieve(query, k=self.top_k)
            log_mas_trace("retriever_output", f"{len(context)} chunks retrieved.")

            response = self.generator.generate(query, context)
            verdict = self.critic.evaluate(query, response)

            while verdict["status"] == "REVISE" and retries < self.max_retries:
                retries += 1
                log_mas_trace(
                    "critic_retry",
                    f"Attempt {retries}: {verdict.get('feedback','')}",
                )
                response = self.generator.generate(
                    query,
                    context,
                    feedback=verdict.get("feedback"),
                )
                verdict = self.critic.evaluate(query, response)

            if verdict["status"] == "REVISE":
                log_mas_trace("orchestrator", "Max retries hit; returning last draft.")
            log_mas_trace("final", "Final response delivered to user.")
        except Exception as exc:  # noqa: BLE001 - loop must never crash the UI
            log_error(self.agent_name, exc)
            response = (
                "I hit an internal issue while answering. Please ask a human "
                "staff member for assistance."
            )
            verdict = {"status": "REVISE", "feedback": f"Pipeline error: {exc}"}

        log_response(self.agent_name, response)
        return {
            "response": response,
            "context": context,
            "retries": retries,
            "verdict": verdict,
        }

    def _banner(self) -> str:
        return (
            f"\n==============================================\n"
            f"  {AGENT_NAME} v{AGENT_VERSION} | Agent B (RAG + MAS)\n"
            f"  Sub-agents: Retriever -> Generator -> Critic\n"
            f"  Type 'exit' or 'quit' to end the session.\n"
            f"==============================================\n"
        )

    def run(self) -> None:
        """Launch the blocking CLI loop for Agent B."""
        print(self._banner())
        while True:
            try:
                query = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                return
            if not query:
                continue
            if query.lower() in {"exit", "quit"}:
                print("DineBot: Goodbye! Returning to dock.")
                return
            result = self.run_once(query)
            print(f"DineBot: {result['response']}")
            print(
                f"[MAS] retries={result['retries']} | "
                f"verdict={result['verdict'].get('status')} | "
                f"ctx_chunks={len(result['context'])}\n"
            )

"""
GeneratorAgent: produces the natural language answer using GPT-4o-mini.

The generator takes the retrieved context and a user query, optionally
incorporates critic feedback on retries, and returns a final response
grounded in the DineBot system prompt.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from config.agent_config import MAS_CONFIG, SYSTEM_PROMPT
from utils.logger import log_error, log_mas_trace

load_dotenv()


class GeneratorAgent:
    """LLM-backed response generator with offline stub fallback."""

    def __init__(self) -> None:
        self.model: str = MAS_CONFIG["model"]
        self.temperature: float = float(MAS_CONFIG["generator_temperature"])
        self._client = None
        self._ready: bool = False
        self._init_client()

    def _init_client(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key == "your_api_key_here":
            log_mas_trace("generator_init", "No OPENAI_API_KEY. Using stub mode.")
            return
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)
            self._ready = True
            log_mas_trace("generator_init", f"OpenAI client ready ({self.model}).")
        except Exception as exc:  # noqa: BLE001
            log_error("GeneratorAgent", f"Client init failed: {exc}")
            self._client = None
            self._ready = False

    def generate(
        self,
        query: str,
        context: list[str],
        feedback: str | None = None,
    ) -> str:
        """Produce a response string grounded in ``context``.

        Parameters
        ----------
        query:
            The user query.
        context:
            Retrieved knowledge base chunks.
        feedback:
            Optional critic feedback that must be addressed on this attempt.
        """
        log_mas_trace(
            "generator_build",
            "Building prompt with context + system rules...",
        )
        context_block = (
            "\n\n".join(f"- {c}" for c in context) if context else "(no context retrieved)"
        )
        feedback_block = (
            f"\n\n[CRITIC FEEDBACK - address these issues]\n{feedback}"
            if feedback
            else ""
        )
        user_prompt = (
            f"[RETRIEVED KNOWLEDGE]\n{context_block}\n\n"
            f"[USER QUERY]\n{query}\n"
            f"{feedback_block}\n\n"
            f"Respond as DineBot. Be concise, friendly, and strictly within your "
            f"capabilities. If the request violates any CANNOT_DO item, politely "
            f"redirect the user to human staff."
        )
        log_mas_trace("generator_prompt", user_prompt)

        if not self._ready or self._client is None:
            log_mas_trace(
                "generator_call",
                "OpenAI unavailable - using grounded offline stub.",
            )
            stub = self._offline_stub(query, context, feedback)
            log_mas_trace(
                "generator_response",
                f"Draft response generated ({len(stub)} chars, stub).",
            )
            return stub

        try:
            log_mas_trace(
                "generator_call",
                f"Calling {self.model} (temp={self.temperature})...",
            )
            completion = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = (completion.choices[0].message.content or "").strip()
            if not text:
                text = self._offline_stub(query, context, feedback)
            log_mas_trace(
                "generator_response",
                f"Draft response generated ({len(text)} chars).",
            )
            return text
        except Exception as exc:  # noqa: BLE001
            log_error("GeneratorAgent", f"LLM call failed: {exc}")
            log_mas_trace("generator_error", f"LLM call failed: {exc}")
            return self._offline_stub(query, context, feedback)

    @staticmethod
    def _offline_stub(query: str, context: list[str], feedback: str | None) -> str:
        """Deterministic response used when the LLM is unavailable."""
        head = (
            "I am DineBot. I am currently running without live model access, "
            "so here is a knowledge-grounded reply based on my stored rules:"
        )
        if context:
            body = "\n".join(f"- {c}" for c in context[:3])
        else:
            body = (
                "- I deliver food to tables 1-10 and 16-20.\n"
                "- I keep at least 0.5 m from humans.\n"
                "- For anything outside my scope, please ask human staff."
            )
        tail = f"\n(Your question: {query})"
        if feedback:
            tail += f"\n(Addressed critic note: {feedback})"
        return f"{head}\n{body}{tail}"

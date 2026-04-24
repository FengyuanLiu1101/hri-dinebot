"""
CriticAgent: safety and quality judge for DineBot responses.

The critic inspects a generator response against the CAN_DO / CANNOT_DO
contract, safety considerations, factual relevance, and tone. It returns
a structured verdict ``{"status": "PASS" | "REVISE", "feedback": str}``.
"""

from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv

from config.agent_config import CAN_DO, CANNOT_DO, MAS_CONFIG
from utils.logger import log_error, log_mas_trace

load_dotenv()


_CRITIC_SYSTEM_PROMPT = """You are the Critic sub-agent for a restaurant
food delivery robot called DineBot. You must strictly evaluate every
candidate response produced by the Generator sub-agent.

You will be given:
- The user's query.
- The candidate response.
- The robot's CAN_DO and CANNOT_DO capability lists.

Evaluate the candidate response on four criteria:
1. Does the response violate any CANNOT_DO rule?
2. Does the response contain unsafe or unverifiable information
   (e.g. medical/allergen advice, age verification, payment)?
3. Is the response accurate and relevant to the query, grounded in the
   robot's stated capabilities?
4. Is the response concise, polite, and professional?

Return ONLY a compact JSON object on a single line, with exactly two keys:
- "status": "PASS" if all four criteria are satisfied, otherwise "REVISE".
- "feedback": a short actionable note (one sentence) for the generator.

Do not include any other text outside the JSON."""


class CriticAgent:
    """LLM-backed critic with a conservative offline heuristic fallback."""

    def __init__(self) -> None:
        self.model: str = MAS_CONFIG["model"]
        self.temperature: float = float(MAS_CONFIG["critic_temperature"])
        self.can_do: list[str] = list(CAN_DO)
        self.cannot_do: list[str] = list(CANNOT_DO)
        self._client = None
        self._ready: bool = False
        self._init_client()

    def _init_client(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key == "your_api_key_here":
            log_mas_trace("critic_init", "No OPENAI_API_KEY. Using heuristic mode.")
            return
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)
            self._ready = True
            log_mas_trace("critic_init", f"OpenAI client ready ({self.model}).")
        except Exception as exc:  # noqa: BLE001
            log_error("CriticAgent", f"Client init failed: {exc}")
            self._client = None
            self._ready = False

    def evaluate(self, query: str, response: str) -> dict:
        """Judge the response and return a verdict dict."""
        log_mas_trace("critic_start", "Evaluating draft response...")
        log_mas_trace("critic_check", "Checking safety compliance...")
        log_mas_trace("critic_check", "Checking capability boundaries...")
        log_mas_trace("critic_check", "Checking accuracy and tone...")

        can_block = "\n".join(f"- {item}" for item in self.can_do)
        cannot_block = "\n".join(f"- {item}" for item in self.cannot_do)
        user_prompt = (
            f"[CAN_DO]\n{can_block}\n\n"
            f"[CANNOT_DO]\n{cannot_block}\n\n"
            f"[USER QUERY]\n{query}\n\n"
            f"[CANDIDATE RESPONSE]\n{response}\n\n"
            f"Evaluate and return the JSON verdict now."
        )
        log_mas_trace("critic_prompt", user_prompt)

        if not self._ready or self._client is None:
            verdict = self._heuristic_verdict(query, response)
            log_mas_trace("critic_verdict", json.dumps(verdict))
            return verdict

        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": _CRITIC_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw = (completion.choices[0].message.content or "").strip()
            verdict = self._parse_verdict(raw)
            log_mas_trace("critic_verdict", json.dumps(verdict))
            return verdict
        except Exception as exc:  # noqa: BLE001
            log_error("CriticAgent", f"LLM critic failed: {exc}")
            log_mas_trace("critic_error", f"LLM critic failed: {exc}")
            verdict = self._heuristic_verdict(query, response)
            log_mas_trace("critic_verdict", json.dumps(verdict))
            return verdict

    @staticmethod
    def _parse_verdict(raw: str) -> dict:
        """Robustly extract a JSON verdict from a model response."""
        match = re.search(r"\{.*?\}", raw, flags=re.DOTALL)
        candidate = match.group(0) if match else raw
        try:
            data = json.loads(candidate)
            status = str(data.get("status", "PASS")).upper()
            if status not in {"PASS", "REVISE"}:
                status = "REVISE"
            feedback = str(data.get("feedback", "")).strip() or "No specific feedback."
            return {"status": status, "feedback": feedback}
        except json.JSONDecodeError:
            return {
                "status": "REVISE",
                "feedback": "Critic could not parse verdict; ask the generator to be more concise and policy-compliant.",
            }

    def _heuristic_verdict(self, query: str, response: str) -> dict:
        """Conservative offline fallback when no LLM is available."""
        text = (response or "").lower()
        issues: list[str] = []
        if any(bad in text for bad in ("diagnose", "medical advice", "allergic reaction treatment")):
            issues.append("contains medical advice")
        if "i'll take your order" in text or "placing your order" in text:
            issues.append("claims to take orders (CANNOT_DO)")
        if "payment" in text and "cannot" not in text and "ask" not in text:
            issues.append("implies handling payment (CANNOT_DO)")
        if any(f"table {n}" in text for n in range(11, 16)) and "cannot" not in text and "not allowed" not in text:
            issues.append("mentions terrace tables without refusal")
        if len(response) > 1200:
            issues.append("response is too long")

        if issues:
            return {
                "status": "REVISE",
                "feedback": "Fix: " + "; ".join(issues) + ". Redirect to staff where needed.",
            }
        return {"status": "PASS", "feedback": "Response meets safety and scope rules."}

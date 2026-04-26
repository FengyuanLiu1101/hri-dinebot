"""
Agent A: offline, rule-based DineBot.

This agent performs intent classification via keyword matching, retrieves
supporting lines from the knowledge base using a term-frequency score,
and returns a handcrafted template response. It never calls an external
LLM API and is therefore fully deterministic and fast.
"""

from __future__ import annotations

from typing import Iterable

from config.agent_config import (
    AGENT_NAME,
    AGENT_VERSION,
    KEYWORD_CATEGORIES,
    ROBOT_STATES,
)
from utils.file_loader import get_all_documents
from utils.logger import log_error, log_query, log_response
from utils.table_parser import (
    is_servable_table,
    is_terrace_table,
    mentioned_table_number,
)
from utils.text_processing import classify_intent, tf_score, tokenize

from agent_a.templates import (
    DELIVERY_TEMPLATES,
    EMERGENCY_TEMPLATES,
    FALLBACK_TEMPLATE,
    GREETING_TEMPLATES,
    MENU_TEMPLATES,
    SAFETY_TEMPLATES,
    STATUS_TEMPLATES,
)


class SimpleAgent:
    """Rule-based DineBot agent with no external API dependencies."""

    def __init__(self) -> None:
        self.agent_name: str = f"{AGENT_NAME}-A"
        self.documents: list[str] = get_all_documents()
        self.corpus_tokens: list[list[str]] = [tokenize(doc) for doc in self.documents]
        self._greet_index: int = 0

    def retrieve(self, query: str, k: int = 3) -> list[str]:
        """Return the ``k`` highest scoring knowledge base lines for ``query``."""
        q_tokens = tokenize(query)
        if not q_tokens or not self.documents:
            return []
        scored: list[tuple[float, int]] = []
        for idx, d_tokens in enumerate(self.corpus_tokens):
            score = tf_score(q_tokens, d_tokens)
            if score > 0:
                scored.append((score, idx))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = scored[: max(1, k)]
        return [self.documents[idx] for _, idx in top]

    def classify_intent(self, query: str) -> str:
        """Return an intent category for ``query`` using shared keyword rules."""
        return classify_intent(query, KEYWORD_CATEGORIES)

    def generate_response(
        self,
        query: str,
        intent: str,
        context: Iterable[str],
    ) -> str:
        """Build the final response string given intent and retrieved context."""
        ctx_list = list(context)
        query_lower = (query or "").lower()

        if intent == "greeting":
            base = GREETING_TEMPLATES[self._greet_index % len(GREETING_TEMPLATES)]
            self._greet_index += 1
            return base

        if intent == "safety":
            template = self._pick_sub(query_lower, SAFETY_TEMPLATES)
            return self._with_context(template, ctx_list)

        if intent == "delivery":
            sub = self._pick_delivery_sub(query_lower)
            template = DELIVERY_TEMPLATES.get(sub, DELIVERY_TEMPLATES["default"])
            table_number = mentioned_table_number(query)
            if is_terrace_table(table_number) or "terrace" in query_lower:
                return (
                    "I am not allowed on the outdoor terrace (tables 11-15). "
                    "Please ask a human staff member to deliver there."
                )
            if table_number is not None and not is_servable_table(table_number):
                return (
                    f"I cannot deliver to table {table_number}. I can only serve "
                    "indoor tables 1-10 and 16-20; please ask human staff for help."
                )
            return self._with_context(template, ctx_list)

        if intent == "menu":
            sub = self._pick_menu_sub(query_lower)
            template = MENU_TEMPLATES.get(sub, MENU_TEMPLATES["default"])
            return template

        if intent == "status":
            sub = self._pick_status_sub(query_lower)
            template = STATUS_TEMPLATES.get(sub, STATUS_TEMPLATES["default"])
            return template

        if intent == "emergency":
            template = self._pick_sub(query_lower, EMERGENCY_TEMPLATES)
            return self._with_context(template, ctx_list)

        return FALLBACK_TEMPLATE

    @staticmethod
    def _pick_sub(query_lower: str, table: dict[str, str]) -> str:
        """Pick the first matching sub-key in ``table``; fall back to ``default``."""
        for key, value in table.items():
            if key == "default":
                continue
            if key.lower() in query_lower:
                return value
        return table.get("default", FALLBACK_TEMPLATE)

    @staticmethod
    def _pick_delivery_sub(query_lower: str) -> str:
        if any(kw in query_lower for kw in ("confirm", "verify")):
            return "confirm"
        if any(kw in query_lower for kw in ("arrive", "arrival", "reached")):
            return "arrive"
        if any(kw in query_lower for kw in ("wait", "how long", "time", "minutes")):
            return "wait"
        if any(kw in query_lower for kw in ("return", "back", "dock")):
            return "return"
        if any(kw in query_lower for kw in ("fail", "wrong", "blocked", "spill")):
            return "fail"
        return "default"

    @staticmethod
    def _pick_menu_sub(query_lower: str) -> str:
        if "appetizer" in query_lower or "starter" in query_lower:
            return "appetizers"
        if "main" in query_lower or "entree" in query_lower or "course" in query_lower:
            return "mains"
        if "dessert" in query_lower or "sweet" in query_lower:
            return "desserts"
        if any(kw in query_lower for kw in ("drink", "beverage", "wine", "coffee", "tea")):
            return "beverages"
        return "default"

    @staticmethod
    def _pick_status_sub(query_lower: str) -> str:
        for state in ROBOT_STATES:
            if state.lower() in query_lower:
                return state
        return "default"

    @staticmethod
    def _with_context(template: str, ctx: list[str]) -> str:
        """Append top context lines to a template response."""
        if not ctx:
            return template
        trimmed = [line for line in ctx[:2] if line]
        if not trimmed:
            return template
        return f"{template}\n\nReference:\n- " + "\n- ".join(trimmed)

    def _banner(self) -> str:
        return (
            f"\n==============================================\n"
            f"  {AGENT_NAME} v{AGENT_VERSION} | Agent A (Rule-Based)\n"
            f"  Type 'exit' or 'quit' to end the session.\n"
            f"==============================================\n"
        )

    def run(self) -> None:
        """Launch the blocking CLI loop for Agent A."""
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
            try:
                log_query(self.agent_name, query)
                intent = self.classify_intent(query)
                context = self.retrieve(query, k=3)
                response = self.generate_response(query, intent, context)
                log_response(self.agent_name, response)
                print(f"DineBot: {response}\n")
            except Exception as exc:  # noqa: BLE001 - CLI must stay resilient
                log_error(self.agent_name, exc)
                print(f"DineBot: I ran into a local issue: {exc}")


if __name__ == "__main__":
    SimpleAgent().run()

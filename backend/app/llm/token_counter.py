from __future__ import annotations

from typing import Dict

# -----------------------------
# Provider-aware token counting
# with budget reservation
# -----------------------------


class TokenBudgetError(Exception):
    pass


class TokenCounter:
    """
    Deterministic token counting abstraction.
    Real providers can override estimation logic.
    """

    def __init__(self, provider: str, model: str, max_tokens: int):
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens

    def count_text(self, text: str) -> int:
        """
        Conservative approximation:
        1 token ~= 4 characters (provider-agnostic fallback)
        """
        return max(1, len(text) // 4)

    def count_messages(self, messages: list[Dict[str, str]]) -> int:
        total = 0
        for m in messages:
            total += self.count_text(m.get("content", ""))
        return total

    def reserve(self, prompt_tokens: int, output_tokens: int) -> None:
        """
        Ensure total token usage stays within model limit.
        """
        if prompt_tokens + output_tokens > self.max_tokens:
            raise TokenBudgetError(
                f"Token budget exceeded: prompt={prompt_tokens}, "
                f"output={output_tokens}, max={self.max_tokens}"
            )

    def estimate_request(self, messages: list[Dict[str, str]], output_tokens: int) -> Dict[str, int]:
        prompt_tokens = self.count_messages(messages)
        self.reserve(prompt_tokens, output_tokens)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": prompt_tokens + output_tokens,
        }

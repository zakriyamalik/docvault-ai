from __future__ import annotations

from typing import Dict, Any
from string import Template

# -----------------------------
# Versioned prompt templates with safe formatting
# - No f-strings on user input
# - Explicit variables only
# -----------------------------


class PromptError(Exception):
    pass


class PromptTemplate:
    def __init__(self, version: str, template: str, required_vars: set[str]):
        self.version = version
        self.template = Template(template)
        self.required_vars = required_vars

    def render(self, variables: Dict[str, Any]) -> str:
        missing = self.required_vars - variables.keys()
        if missing:
            raise PromptError(f"Missing prompt variables: {missing}")
        try:
            return self.template.substitute(**variables)
        except KeyError as e:
            raise PromptError(f"Invalid prompt variable: {e}")


# -----------------------------
# Prompt Registry
# -----------------------------

PROMPTS: Dict[str, PromptTemplate] = {}


def register_prompt(name: str, prompt: PromptTemplate) -> None:
    if name in PROMPTS:
        raise PromptError(f"Prompt '{name}' already registered")
    PROMPTS[name] = prompt


def get_prompt(name: str) -> PromptTemplate:
    if name not in PROMPTS:
        raise PromptError(f"Prompt '{name}' not found")
    return PROMPTS[name]


# -----------------------------
# Prompt Definitions
# -----------------------------

register_prompt(
    name="qa_v1",
    prompt=PromptTemplate(
        version="v1",
        template=(
            "You are a factual assistant.\n"
            "Answer the question using ONLY the provided context.\n"
            "Cite sources using citation ids.\n\n"
            "Context:\n${context}\n\n"
            "Question:\n${question}\n"
        ),
        required_vars={"context", "question"},
    ),
)


register_prompt(
    name="summarize_v1",
    prompt=PromptTemplate(
        version="v1",
        template=(
            "Summarize the following content concisely.\n"
            "Do not add new information.\n\n"
            "Content:\n${content}\n"
        ),
        required_vars={"content"},
    ),
)

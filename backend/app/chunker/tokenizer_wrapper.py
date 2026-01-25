# backend/app/chunker/tokenizer_wrapper.py
from __future__ import annotations
import os
from typing import List, Tuple, Optional
from transformers import AutoTokenizer

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def get_tokenizer(model_name: Optional[str] = None):
    model = model_name or os.environ.get("EMBEDDING_MODEL") or DEFAULT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(model, use_fast=True)
    if not getattr(tokenizer, "is_fast", False):
        raise ValueError(
            f"Tokenizer for model {model!r} is not a fast tokenizer; "
            "offset mappings are required."
        )
    return tokenizer


def tokenize_text(tokenizer, text: str) -> Tuple[List[int], List[Tuple[int, int]]]:
    if text is None:
        text = ""
    enc = tokenizer(
        text,
        return_offsets_mapping=True,
        add_special_tokens=False,
    )
    return enc.get("input_ids", []), enc.get("offset_mapping", [])


def token_spans_to_char_offsets(
    offsets: List[Tuple[int, int]],
    start_idx: int,
    end_idx: int,
) -> Tuple[int, int]:
    if not offsets:
        return 0, 0

    total = len(offsets)
    if not (0 <= start_idx < total):
        raise ValueError(f"start_idx {start_idx} out of range")
    if not (0 < end_idx <= total):
        raise ValueError(f"end_idx {end_idx} out of range")
    if start_idx >= end_idx:
        raise ValueError("start_idx must be < end_idx")

    char_start = offsets[start_idx][0] or 0
    char_end = offsets[end_idx - 1][1] or 0
    return char_start, char_end

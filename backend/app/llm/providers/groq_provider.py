import os
import re
from typing import Dict, Any

import groq

from app.llm.schemas import LLMRequest, LLMResponse, LLMAnswer, Citation


class GroqProvider:
    """Groq LLM provider - fast inference with free tier (1M tokens/day)."""
    
    DEFAULT_MODEL = "llama3-8b-8192"
    
    MODELS = {
    "llama-3.1-8b-instant": "Meta Llama 3.1 8B",
    "llama-3.3-70b-versatile": "Meta Llama 3.3 70B",
    "llama-3.3-70b-specdec": "Meta Llama 3.3 70B SpecDec",
    "llama-3.2-1b-preview": "Meta Llama 3.2 1B",
    "llama-3.2-3b-preview": "Meta Llama 3.2 3B",
    "mixtral-8x7b-32768": "Mixtral 8x7B",
    "gemma-7b-it": "Google Gemma 7B",
    "gemma2-9b-it": "Google Gemma 2 9B",
    }
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Get free API key at: https://console.groq.com/keys"
            )
        self.client = groq.Groq(api_key=self.api_key)
    
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Call Groq API with structured request."""
        messages = []
        
        # Add system message if present
        for m in request.messages:
            messages.append({"role": m.role, "content": m.content})
        
        model = request.model if request.model in self.MODELS else self.DEFAULT_MODEL
        
        start_time = __import__('time').time()
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_output_tokens,
        )
        
        latency_ms = int((__import__('time').time() - start_time) * 1000)
        
        content = response.choices[0].message.content
        citations = self._extract_citations(content)
        
        return LLMResponse(
            provider="groq",
            model=model,
            answer=LLMAnswer(
                text=content,
                citations=citations
            ),
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            latency_ms=latency_ms,
            request_id=request.request_id
        )
    
    def _extract_citations(self, text: str) -> list:
        """Extract citation markers like [1], [2] from response."""
        citations = []
        seen = set()
        
        for match in re.finditer(r'\[(\d+)\]', text):
            cid = match.group(1)
            if cid not in seen:
                seen.add(cid)
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                quote = text[start:end].strip()
                citations.append(Citation(id=f"cite_{cid}", quote=quote))
        
        return citations
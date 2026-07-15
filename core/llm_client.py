"""Provider-switching inference client. Set LLM_PROVIDER in .env to change backends."""
import uuid
from typing import Any
import structlog

from core.config import get_settings
from core.cost_tracker import cost_tracker

log = structlog.get_logger()

PROVIDER_PRICING = {
    "gemini-2.0-flash":          {"input": 0.10,  "output": 0.40},
    "gemini-1.5-flash":          {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro":            {"input": 1.25,  "output": 5.00},
    "llama-3.3-70b-versatile":   {"input": 0.59,  "output": 0.79},
    "llama3-70b-8192":           {"input": 0.59,  "output": 0.79},
    "mixtral-8x7b-32768":        {"input": 0.27,  "output": 0.27},
}


class LLMClient:
    def __init__(self):
        self.settings = get_settings()
        self.provider = self.settings.llm_provider.lower()
        self._client = self._init_client()

    def _init_client(self):
        if self.provider == "anthropic":
            import anthropic
            return anthropic.Anthropic(api_key=self.settings.anthropic_api_key)

        elif self.provider == "openai":
            import openai
            return openai.OpenAI(api_key=self.settings.openai_api_key)

        elif self.provider == "gemini":
            import openai
            return openai.OpenAI(
                api_key=self.settings.gemini_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )

        elif self.provider == "groq":
            import openai
            return openai.OpenAI(
                api_key=self.settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )

        raise ValueError(
            f"Unknown LLM_PROVIDER: '{self.provider}'. Use 'anthropic', 'openai', 'gemini', or 'groq'."
        )

    def _model(self) -> str:
        if self.provider == "anthropic":
            return self.settings.anthropic_model
        if self.provider == "gemini":
            return self.settings.gemini_model
        if self.provider == "groq":
            return self.settings.groq_model
        return self.settings.openai_model

    def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        query_id: str | None = None,
    ) -> dict[str, Any]:
        qid = query_id or str(uuid.uuid4())[:8]

        if self.provider == "anthropic":
            return self._anthropic_chat(messages, system, tools, max_tokens, qid)
        return self._openai_chat(messages, system, tools, max_tokens, qid)

    def _anthropic_chat(self, messages, system, tools, max_tokens, query_id) -> dict:
        kwargs: dict[str, Any] = {
            "model": self._model(),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = self._client.messages.create(**kwargs)

        content_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})

        cost_tracker.record(
            query_id=query_id,
            model=self._model(),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        return {
            "content": content_text,
            "tool_calls": tool_calls or None,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

    def _openai_chat(self, messages, system, tools, max_tokens, query_id) -> dict:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": self._model(),
            "max_tokens": max_tokens,
            "messages": all_messages,
        }
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        content_text = choice.content or ""
        tool_calls = None
        if choice.tool_calls:
            import json
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                }
                for tc in choice.tool_calls
            ]

        input_tokens  = response.usage.prompt_tokens     if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        if self.provider in ("gemini", "groq"):
            rates = PROVIDER_PRICING.get(self._model(), {"input": 0.10, "output": 0.40})
            cost  = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
            from core.cost_tracker import QueryCost
            from datetime import datetime, timezone
            cost_tracker._queries.append(QueryCost(
                query_id=query_id,
                model=self._model(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                timestamp=datetime.now(timezone.utc),
            ))
        else:
            cost_tracker.record(
                query_id=query_id,
                model=self._model(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        return {
            "content": content_text,
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

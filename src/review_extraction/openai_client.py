from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from .schema import build_extraction_prompt, build_repair_prompt


@dataclass(slots=True)
class OpenAIResponsePayload:
    output_text: str
    usage: dict[str, int]
    response_id: str


class OpenAIPdfExtractionClient:
    def __init__(self, model: str) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing. Set it in your environment or .env file.")
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def extract(self, pdf_path: Path) -> OpenAIResponsePayload:
        prompt = build_extraction_prompt()
        return self._call_with_pdf(pdf_path, prompt)

    def repair(self, pdf_path: Path, previous_output: str, issues: list[str]) -> OpenAIResponsePayload:
        prompt = build_repair_prompt(previous_output=previous_output, issues=issues)
        return self._call_with_pdf(pdf_path, prompt)

    def _call_with_pdf(self, pdf_path: Path, prompt: str) -> OpenAIResponsePayload:
        file_data = self._encode_pdf_data_uri(pdf_path)
        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "filename": pdf_path.name,
                            "file_data": file_data,
                        },
                        {
                            "type": "input_text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )
        usage = self._usage_dict(getattr(response, "usage", None))
        output_text = getattr(response, "output_text", "") or ""
        response_id = getattr(response, "id", "")
        return OpenAIResponsePayload(output_text=output_text, usage=usage, response_id=response_id)

    @staticmethod
    def _encode_pdf_data_uri(pdf_path: Path) -> str:
        data = pdf_path.read_bytes()
        base64_string = base64.b64encode(data).decode("utf-8")
        return f"data:application/pdf;base64,{base64_string}"

    @staticmethod
    def _usage_dict(usage: Any) -> dict[str, int]:
        if usage is None:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }


"""Minimal A2A client used to test client_insights_agent directly (no WXO involved).

It performs the same steps WXO does:
  1. Fetch the Agent Card from  <base>/.well-known/agent-card.json
  2. Send a `message/send` JSON-RPC request
  3. Print the resulting task state and the answer

Usage:
  python tests/a2a_client.py [BASE_URL] [QUESTION]
"""

from __future__ import annotations

import asyncio
import sys

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory, create_text_message_object
from a2a.types import Message, Task
from a2a.utils import get_message_text

DEFAULT_URL = "http://localhost:10000"
DEFAULT_QUESTION = "Help me understand the client: background, requirements, pain points and key drivers."


async def main(base_url: str, question: str) -> int:
    async with httpx.AsyncClient(timeout=180) as http:
        card = await A2ACardResolver(http, base_url).get_agent_card()
        print(f"Agent card: {card.name} v{card.version} (A2A {card.protocol_version}) -> {card.url}")
        print("Skills    :", ", ".join(s.id for s in card.skills))

        client = ClientFactory(ClientConfig(httpx_client=http, streaming=False)).create(card)
        print(f"\nQuestion  : {question}\n")

        answer, state = "", "unknown"
        async for event in client.send_message(create_text_message_object(content=question)):
            if isinstance(event, Message):
                answer, state = get_message_text(event), "message"
            else:  # (Task, update) tuple
                task: Task = event[0]
                state = task.status.state.value
                if task.status.message:
                    answer = get_message_text(task.status.message)
                for art in task.artifacts or []:
                    answer = "\n".join(
                        p.root.text for p in art.parts if getattr(p.root, "text", None)
                    ) or answer

        print(f"Task state: {state}\n")
        print(answer)
        return 0 if state in ("completed", "message") and answer else 1


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    q = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_QUESTION
    sys.exit(asyncio.run(main(url, q)))

"""A2A server for client_insights_agent.

Implements the A2A 0.3.0 JSON-RPC protocol using the a2a-sdk 0.3.x.
The server exposes:
  GET  /.well-known/agent-card.json  → AgentCard (discovered by WXO)
  POST /                             → JSON-RPC A2A endpoint

Run with:
  cd agents/client_insights_agent
  uvicorn server:app --host 0.0.0.0 --port 10000

Or via the helper script:  scripts/run_agent_server.sh
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps.jsonrpc.starlette_app import A2AStarletteApplication
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message, new_text_artifact

from graph import build_agent, run_agent

logger = logging.getLogger("client_insights_agent.server")

# ------------------------------------------------------------------
# Agent card definition — this is what WXO discovers and imports.
# ------------------------------------------------------------------

AGENT_URL_PLACEHOLDER = "http://localhost:10000"  # overridden by run_agent_server.sh


def build_agent_card(public_url: str = AGENT_URL_PLACEHOLDER) -> AgentCard:
    return AgentCard(
        name="client_insights_agent",
        description=(
            "A LangGraph agent that reads a public-sector tender PDF and extracts: "
            "client background, client requirements, client pain points, and client "
            "key drivers. Route any request to understand a client or a tender here."
        ),
        version="1.0.0",
        url=public_url,
        capabilities=AgentCapabilities(
            streaming=False,
            push_notifications=False,
            state_transition_history=False,
        ),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="extract_client_insights",
                name="Extract Client Insights from Tender",
                description=(
                    "Given a request about a client or tender document, returns a "
                    "structured summary of background, requirements, pain points, "
                    "and key drivers sourced directly from the tender PDF."
                ),
                tags=["tender", "client-insights", "procurement", "pdf"],
                examples=[
                    "Summarise the client for me",
                    "What are the client requirements?",
                    "What pain points is the client experiencing?",
                    "What are the key drivers behind this procurement?",
                ],
            )
        ],
    )


# ------------------------------------------------------------------
# AgentExecutor — bridges A2A task events → LangGraph agent
# ------------------------------------------------------------------


class ClientInsightsExecutor(AgentExecutor):
    """Wraps the LangGraph client_insights_agent for A2A task execution."""

    def __init__(self) -> None:
        self._agent = None

    async def _get_agent(self):
        if self._agent is None:
            self._agent = build_agent()
        return self._agent

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id,
            context_id=context.context_id,
        )
        await updater.start_work()

        user_text = context.get_user_input().strip()
        logger.info("Received request: %r", user_text[:200])

        try:
            agent = await self._get_agent()
            answer = await run_agent(agent, user_text)
        except Exception as exc:
            logger.exception("Agent run failed: %s", exc)
            await updater.failed(
                new_agent_text_message(
                    f"An error occurred while processing your request: {exc}",
                    context_id=context.context_id,
                    task_id=context.task_id,
                )
            )
            return

        # Emit the answer as an artifact and complete the task.
        text_part = Part(root=TextPart(text=answer))
        await updater.add_artifact(parts=[text_part], name="client_insights")
        await updater.complete(
            new_agent_text_message(
                answer,
                context_id=context.context_id,
                task_id=context.task_id,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id,
            context_id=context.context_id,
        )
        await updater.update_status(TaskState.canceled, final=True)


# ------------------------------------------------------------------
# Build the Starlette ASGI application
# ------------------------------------------------------------------


def create_app(public_url: str = AGENT_URL_PLACEHOLDER):
    agent_card = build_agent_card(public_url)
    executor = ClientInsightsExecutor()
    task_store = InMemoryTaskStore()

    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
    )
    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=handler,
    ).build()


import os

_PUBLIC_URL = os.getenv("A2A_PUBLIC_URL", AGENT_URL_PLACEHOLDER)
app = create_app(public_url=_PUBLIC_URL)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("A2A_PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

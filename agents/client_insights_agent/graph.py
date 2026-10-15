"""LangGraph/LangChain agent that answers questions about the tender PDF.

Uses a prebuilt ReAct-style tool-calling agent (`langchain.agents.create_agent`, which
is built on LangGraph) backed by an OpenAI chat model. The OpenAI key is read from the
OPENAI_API_KEY entry in the repository's `.env` file.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from pdf_tools import ALL_TOOLS

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are client_insights_agent, an analyst that extracts client insight \
from a public-sector tender document (a Network Rail Road Haulage and Warehousing \
procurement).

You MUST ground every statement in text returned by your tools. Never invent facts.

How to work:
- For a general "understand the client" request, call ALL FOUR tools: \
extract_client_background, extract_client_requirements, extract_client_pain_points and \
extract_client_key_drivers. You may also call get_document_overview.
- For narrower questions, call only the relevant tool(s); use search_tender_document \
for anything else.
- Pain points and key drivers are often implicit. Infer them from the text, and label \
inferences clearly as "(inferred)".

Output format (Markdown, concise, cite pages like "p.4"):
## Client Background
## Client Requirements
## Client Pain Points
## Client Key Drivers
Use bullet points. Omit a section only if the user did not ask about it.
"""


def build_agent():
    """Create the LangGraph agent. Raises a clear error if the API key is missing."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set (expected in the repo .env file).")
    model = ChatOpenAI(model=OPENAI_MODEL, temperature=0)
    return create_agent(model=model, tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT)


async def run_agent(agent, user_text: str) -> str:
    """Invoke the agent on a user request and return the final text answer."""
    result = await agent.ainvoke({"messages": [{"role": "user", "content": user_text}]})
    final = result["messages"][-1]
    content = final.content
    if isinstance(content, list):  # some providers return content blocks
        content = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return content

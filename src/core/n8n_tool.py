"""
core/n8n_tool.py — LangChain tool for triggering n8n workflows.

The system-agent calls this to fire n8n webhooks by workflow name.
n8n workflows that should be callable must expose a Webhook trigger node
with the path: /webhook/jarvis/<workflow_name>

Environment variables used:
  N8N_MCP_URL  — n8n base URL on the internal bridge (e.g. http://172.70.0.160:5678)
  N8N_API_KEY  — n8n API key for authenticated webhook calls
"""
from __future__ import annotations

import logging
import os

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_N8N_BASE = os.environ.get("N8N_MCP_URL", "").rstrip("/")
_N8N_KEY  = os.environ.get("N8N_API_KEY", "")


@tool
async def trigger_n8n_workflow(workflow_name: str, payload: dict = {}) -> str:
    """
    Trigger an n8n workflow by name via its webhook endpoint.

    Use this when the user asks to run an automation, send a notification,
    execute a scheduled task, or interact with any external service that
    has an n8n workflow defined for it.

    Args:
        workflow_name: The webhook path name (e.g. 'morning-brief', 'notify-slack').
        payload: Optional JSON payload to pass to the workflow.

    Returns:
        The workflow's response body, or an error message.
    """
    if not _N8N_BASE:
        return "n8n is not configured (N8N_MCP_URL not set)."

    url = f"{_N8N_BASE}/webhook/jarvis/{workflow_name}"
    headers = {}
    if _N8N_KEY:
        headers["X-N8N-API-KEY"] = _N8N_KEY

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.text or "Workflow triggered successfully."
    except httpx.HTTPStatusError as exc:
        logger.error("n8n_tool: HTTP %s from %s", exc.response.status_code, url)
        return f"n8n workflow '{workflow_name}' returned HTTP {exc.response.status_code}."
    except Exception as exc:
        logger.error("n8n_tool: %s", exc)
        return f"Failed to trigger n8n workflow '{workflow_name}': {exc}"

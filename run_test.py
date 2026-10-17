#!/usr/bin/env python3
"""
Standalone invocation test — run inside the container:
  docker exec system-agent python /app/run_test.py
No TTY needed. PYTHONPATH must be /app/src (set in container env).
"""
import asyncio
import sys
import traceback

sys.path.insert(0, "/app/src")

from swarm.graph import system_agent


async def test():
    print("=== Testing: 'Hello, JARVIS.' (expect FINISH — no LLM call) ===")
    try:
        result = await asyncio.wait_for(
            system_agent.ainvoke(
                {"messages": [{"role": "user", "content": "Hello, JARVIS."}]},
                config={"configurable": {"thread_id": "test-hello"}, "recursion_limit": 25},
            ),
            timeout=90,
        )
        msgs = result.get("messages", [])
        print(f"  message count : {len(msgs)}")
        for m in msgs:
            mtype = getattr(m, "type", type(m).__name__)
            content = getattr(m, "content", str(m))[:300]
            name = getattr(m, "name", "")
            print(f"  [{mtype}][{name}] {content!r}")
        print(f"  next_agent     : {result.get('next_agent', 'N/A')}")
        print(f"  current_agent  : {result.get('current_agent', 'N/A')}")
        print("  RESULT: OK")
    except asyncio.TimeoutError:
        print("  RESULT: TIMEOUT — Ollama did not respond within 90s")
        print("  -> run: docker exec ollama ollama ps")
    except Exception:
        print("  RESULT: EXCEPTION")
        traceback.print_exc()

    print()
    print("=== Testing: 'What time is it?' (expect router -> FINISH or executor) ===")
    try:
        result = await asyncio.wait_for(
            system_agent.ainvoke(
                {"messages": [{"role": "user", "content": "What time is it?"}]},
                config={"configurable": {"thread_id": "test-time"}, "recursion_limit": 25},
            ),
            timeout=90,
        )
        msgs = result.get("messages", [])
        for m in msgs:
            mtype = getattr(m, "type", type(m).__name__)
            content = getattr(m, "content", str(m))[:300]
            name = getattr(m, "name", "")
            print(f"  [{mtype}][{name}] {content!r}")
        print(f"  next_agent     : {result.get('next_agent', 'N/A')}")
        print(f"  current_agent  : {result.get('current_agent', 'N/A')}")
        print("  RESULT: OK")
    except asyncio.TimeoutError:
        print("  RESULT: TIMEOUT")
    except Exception:
        print("  RESULT: EXCEPTION")
        traceback.print_exc()


asyncio.run(test())

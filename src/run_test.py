import asyncio, traceback
from swarm.graph import system_agent

async def test():
    print("=== Test 1: Hello, JARVIS. (expect FINISH) ===")
    try:
        result = await asyncio.wait_for(
            system_agent.ainvoke(
                {"messages": [{"role": "user", "content": "Hello, JARVIS."}]},
                config={"configurable": {"thread_id": "test-hello"}, "recursion_limit": 25},
            ),
            timeout=90,
        )
        msgs = result.get("messages", [])
        for m in msgs:
            print(f"  [{getattr(m,'type','?')}][{getattr(m,'name','')}] {str(getattr(m,'content',''))[:300]!r}")
        print(f"  next_agent={result.get('next_agent','N/A')}  current_agent={result.get('current_agent','N/A')}")
        print("  RESULT: OK")
    except asyncio.TimeoutError:
        print("  RESULT: TIMEOUT (90s) — check: docker exec ollama ollama ps")
    except Exception:
        traceback.print_exc()

    print()
    print("=== Test 2: What time is it? (expect FINISH or executor) ===")
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
            print(f"  [{getattr(m,'type','?')}][{getattr(m,'name','')}] {str(getattr(m,'content',''))[:300]!r}")
        print(f"  next_agent={result.get('next_agent','N/A')}  current_agent={result.get('current_agent','N/A')}")
        print("  RESULT: OK")
    except asyncio.TimeoutError:
        print("  RESULT: TIMEOUT (90s)")
    except Exception:
        traceback.print_exc()

asyncio.run(test())

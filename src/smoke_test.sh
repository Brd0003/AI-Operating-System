#!/usr/bin/env bash
# AOS Smoke Test Script
# Run inside the system-agent container after applying all fixes.
# Usage: docker compose exec system-agent bash /app/src/smoke_test.sh
set -euo pipefail

echo "============================================"
echo "AOS SMOKE TESTS"
echo "============================================"
echo ""

# 1. Clean pycache
echo "[1/6] Cleaning __pycache__ directories..."
find /app/src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
echo "  OK"
echo ""

# 2. Compile check
echo "[2/6] Compiling all Python files..."
python -m compileall /app/src -q
echo "  OK — no syntax errors"
echo ""

# 3. Import test: LiteLLM router
echo "[3/6] Testing LiteLLM router import..."
python -c 'from core.router import ai_router; print("  OK — LiteLLM router imported")'
echo ""

# 4. Import test: Graph
echo "[4/6] Testing graph import..."
python -c 'from swarm.graph import system_agent; print("  OK — Graph imported, compiled")'
echo ""

# 5. Environment check
echo "[5/6] Checking environment variables..."
python -c "
import os
print(f'  OLLAMA_API_BASE = {os.getenv(\"OLLAMA_API_BASE\", \"MISSING\")}')
print(f'  AGENT_URL = {os.getenv(\"AGENT_URL\", \"MISSING\")}')
print(f'  SYSTEM_AGENT_KEY present = {bool(os.getenv(\"SYSTEM_AGENT_KEY\"))}')
print(f'  NVIDIA_API_KEY present = {bool(os.getenv(\"NVIDIA_API_KEY\"))}')
print(f'  PYTHONPATH = {os.getenv(\"PYTHONPATH\", \"NOT SET\")}')
"
echo ""

# 6. Quick functional test (non-streaming)
echo "[6/6] Testing /chat/completions endpoint (non-stream)..."
curl -s -X POST http://localhost:10001/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${SYSTEM_AGENT_KEY}" \
  -d '{
    "model": "system-agent",
    "messages": [{"role": "user", "content": "Hello, JARVIS."}],
    "stream": false
  }' | python -m json.tool
echo ""

echo "============================================"
echo "ALL SMOKE TESTS PASSED"
echo "============================================"

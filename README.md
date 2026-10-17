# AI Operating System (AOS): J.A.R.V.I.S. Core

The **AI Operating System (AOS)** is a production-grade, self-hosted autonomous orchestration engine. Built from the ground up for Unraid and Docker Swarm environments, AOS provides a deterministic LangGraph multi-agent architecture powered by local GPU inference. It merges the boundary between local system administration, Model Context Protocol (MCP) tooling, and conversational AI into a single, cohesive, self-healing environment.

If you are looking to deploy a private, bleeding-edge AI infrastructure that validates its own configurations, manages its own memory, and orchestrates complex tasks without relying on cloud gateways, you are in the right place.

---

## 🧠 Core Philosophy & Architecture

AOS is engineered on a strict "Self-Hosted First" paradigm. It avoids fragile external dependencies by running its orchestration logic, inference, memory, and validation entirely on-premises.

* **The Orchestrator (`system-agent`):** A FastAPI-driven harness wrapping a LangGraph Swarm. It leverages the LiteLLM SDK directly in-memory to route tasks with near-zero latency.


* **Inference Pipeline (`ollama`):** Defaults to `qwen2.5-coder:7b-instruct` via local NVIDIA GPU reservation, seamlessly falling back to high-parameter cloud models via NVIDIA API only when explicitly required.


* **Persistent Memory & Vector State (`qdrant` & `postgres`):** Qdrant handles payload-accelerated semantic memory and checkpointing, while a multi-database PostgreSQL instance governs strict state for workflows and user interfaces.


* **Extensibility (MCP Integration):** Pre-configured Model Context Protocol containers expose filesystem, GitHub, and code snippet contexts directly to the swarm network.



### The J.A.R.V.I.S. Agent Swarm

At the heart of the `system-agent` is a deterministic execution loop handled by six specialized LangGraph nodes:

| Agent | Domain Responsibility | Execution Profile |
| --- | --- | --- |
| **Router** | Intent Classification | Categorizes the user prompt and dispatches to the correct specialist. Resolves idle chat immediately (FINISH).

 |
| **Planner** | Task Decomposition | Breaks complex multi-step goals into ordered, actionable steps without writing code.

 |
| **Developer** | Code Generation | Writes, reviews, and edits production-ready code, YAML, and shell scripts.

 |
| **Executor** | System Action | Diagnoses infrastructure states and outlines precise commands or file modifications required.

 |
| **Research** | Data Synthesis | Degrades gracefully or queries live endpoints to ground answers strictly in retrieved documentation.

 |
| **Evaluator** | Quality Assurance | Reviews the specialist's output for completeness, formatting, and accuracy before surfacing it to the user.

 |

---

## 🛠️ The Verification Arsenal

AOS ships with a suite of highly crafted, self-healing diagnostic tools designed to guarantee infrastructure integrity *before* boot.

* **`app_config_validator.sh`**: A self-healing engine that automatically bootstraps missing Python dependencies (like `PyYAML` via `uv`) and strictly validates all Bash syntax and YAML structures across the project.


* **`compose_infrastructure_auditor.sh`**: Compiles multi-file Docker Compose stacks dynamically to audit host-to-container volume bind mounts against strict Unraid ownership standards (`nobody:users`).


* **`gather_context.sh`**: The master policy sync engine. It dynamically audits live container network endpoints, compiles modular YAMLs, embeds test arsenals, and snapshots the exact Python SDK package footprint into a timestamped Markdown telemetry report.


* **`smoke_test.sh` & `run_test.py**`: Executes an immediate post-build verification pass, cleaning `__pycache__`, compiling the LangGraph topology, and hitting the live FastAPI `/chat/completions` endpoint to ensure the LiteLLM SDK router is healthy.



---

## 🚀 Deployment: First-Take Execution

This repository is structured for modular composition. Configurations are split logically across `kernel.yaml`, `monitoring.yaml`, `system-agent.yaml`, and dedicated service files within `config/services/`.

### Prerequisites

* A Linux Docker host (Optimized for Unraid 7.x).


* NVIDIA GPU with Docker runtime configured.


* Dual-bridge networking: Ensure `br0` (LAN) and `nestworks` (Internal Docker Bridge) are pre-created.



### Step 1: Environment Configuration

Copy the environment template and populate your local secrets, API keys, and static IP allocations.

```bash
cp .env.example .env
nano .env

```

### Step 2: Pre-Flight Validation

Execute the configuration validator to ensure your environment is structurally sound. The script will self-heal dependencies and parse your entire tree.

```bash
bash app_config_validator.sh

```

*Look for: `🎉 ALL CONFIGURATIONS PASSED VALIDATION.*`

### Step 3: Bootstrapping the Kernel

Bring up the entire stack using the root composed manifest.

```bash
docker compose up -d

```

### Step 4: Live Smoke Testing

Verify the swarm topology and local LLM inference pipeline are communicating correctly.

```bash
docker exec system-agent bash /app/src/smoke_test.sh

```

*Look for: `ALL SMOKE TESTS PASSED*`.

Once verified, the J.A.R.V.I.S. Core is fully operational. You can interface with the swarm via the `open-webui` frontend or by hitting the `system-agent` API natively on port `10001`.

---

## 🤝 Contributing

AOS is built to push the bleeding edge of what is possible on local hardware. If you are a systems engineer, AI enthusiast, or homelab architect, your contributions to the routing logic, MCP integrations, or self-healing scripts are welcome. Fork the repository, adhere to the strict `nobody:users` permission guidelines, and ensure your pull requests pass the `app_config_validator.sh` pipeline.

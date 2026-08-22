---

# AI Operating System (AOS)

A production-grade, domain-driven, self-hosted AI infrastructure orchestrator built natively for Unraid. AOS utilizes a modular micro-orchestration pattern, absolute environment variable mapping, consolidated 16k-optimized ZFS PostgreSQL databases, local GPU-accelerated LLM execution, and dynamic Model Context Protocol (MCP) agent discovery.

## 📋 Project Blueprint (The 5 Ws)

* **Who:** Designed for homelab administrators, AI engineers, and developers seeking a robust, self-hosted intelligence stack without cloud vendor lock-in.
* **What:** A modular Docker Compose orchestrator managed via a unified operational CLI wrapper (`./bin/aos`), featuring isolated bridge networks, 1:1 environment variable mapping, and integrated LangGraph, n8n, and Open WebUI pipelines.
* **Where:** Deployed locally on an Unraid NAS node utilizing high-performance ZFS storage pools configured with custom record sizes (`/mnt/cache/appdata/`) for maximum database and vector throughput.
* **When:** Modernized for production-grade stability, container isolation, and stateful persistence.
* **Why:** To eliminate monolithic configuration fragility, prevent silent container drift, isolate heavy relational and vector workloads, and provide a lightning-fast, highly resilient local AI operational environment.

## 🏗️  Repository Architecture & Directory Tree

The system is organized into decoupled functional domains, separating service definitions, kernel modules, agent configurations, and documentation:

```text
AI-Operating-System/
├── .env.example            # Master environment variable template / source of truth
├── README.md               # System documentation
├── agents/                 # Specialized LangGraph agent configurations (developer, planner, router, etc.)
├── bin/
│   └── aos                 # Unified operational wrapper CLI (validate, up, down, logs, ps)
├── compose/                # Modular Docker Compose manifests
│   ├── agents.yaml         # LangGraph Core Agent & MCP Qdrant services
│   ├── compose.yaml        # Master orchestrator file (includes all modular YAMLs)
│   ├── kernel.yaml         # Core kernel dependency mappings
│   ├── monitoring.yaml     # Prometheus telemetry scrape service
│   ├── optional.yaml       # Opt-in profiles for MCP tools (Filesystem, GitHub)
│   └── services/           # Individual service modules (litellm, n8n, ollama, webui, etc.)
├── docs/                   # Architecture decisions, diagrams, inventories, and runbooks
├── kernel/                 # Kernel-level service states and bindings
│   ├── litellm/
│   │   └── config.yaml     # LiteLLM hybrid proxy router, MCPs, and virtual keys
│   ├── postgres/
│   │   └── init-multi-db.sh# Automated multi-database bootstrap initialization script
│   └── prometheus/
│       └── prometheus.yml  # Prometheus scrape definitions
├── memory/                 # Persistent memory and storage integrations (Qdrant, Redis)
├── diagnose.sh             # Automated health, configuration, and log diagnostic suite
├── export_safe_env.sh      # Utility to generate sanitized .env files for sharing
└── volume_mapper.sh        # Utility to verify ZFS paths and container mount ownership
```

## 🌐 Network Architecture & IP Allocation

AOS implements a dual-network topology to ensure strict routing predictability for telemetry, API routing, and webhooks:

1. **nestworks_docker_bridge_network (172.70.0.0/16):** Internal container-to-container mesh network.
2. **br0 (10.70.10.0/24):** Direct physical LAN bridge with explicit static IP and MAC bindings.

Administrators should reserve the corresponding IP range in their router's DHCP scope to avoid address collisions.

## 💾 Storage & ZFS Data Persistence Strategy

To eliminate database page fragmentation under heavy vector embedding and high-frequency relational queries, datasets are explicitly mapped to tuned ZFS cache paths:

* **PostgreSQL 16 (postgres-shared):** Mounted to `/mnt/cache/appdata/postgres-shared-recordsize-16k` (Optimized 16k ZFS record size matching database block allocation size). Automatically provisions isolated databases via `init-multi-db.sh`.
* **Qdrant Vector Storage (qdrant):** Mounted to `/mnt/cache/appdata/qdrant-recordsize-16k` (16k ZFS dataset record size optimized for high-throughput vector chunk persistence).
* **Local LLM Weights (ollama):** Mounted to `/mnt/cache/appdata/ollama:/root/.ollama` with NVIDIA GPU container runtime reservations.
* **Stateful Mounts:** Open WebUI, n8n, and Redis maintain dedicated appdata volumes to ensure zero state loss across reboots.

## 🚀 Administrator Quickstart & Deployment Guide

For new administrators deploying this repository into a production environment, follow this initialization sequence:

### 1. Clone and Configure Environment

Copy the environment template and populate your local infrastructure variables (domains, passwords, API keys):

```bash
cp .env.example .env

# Edit .env with your specific production credentials and IP parameters
nano .env

```

### 2. Validate Configuration Syntax

Use the built-in management CLI wrapper to audit your compose syntax and variable resolution before booting:

```bash
./bin/aos validate

```

### 3. Ignition (Build and Launch)

Spin up the modular operating system stack with build hooks enabled:

```bash
./bin/aos up --build

```

*(Note: To include optional services like GitHub or Filesystem MCPs, append the profile flag: `./bin/aos up --profile optional --build`)*

### 4. Execute System Diagnostics

Run the unified health and error inspection utility to confirm all containers report healthy:

```bash
./diagnose.sh

```

## 🛠️ The `aos` Operational CLI Reference

System lifecycle management is centralized through the `./bin/aos` wrapper script:

* `./bin/aos up [service]` — Spin up the stack or specific services.
* `./bin/aos down` — Gracefully tear down active containers.
* `./bin/aos ps` — Display real-time container status and health checks.
* `./bin/aos logs [service]` — Inspect unified or service-specific container logs.
* `./bin/aos validate` — Audit configuration files against the active `.env` file.
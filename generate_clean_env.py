import re

# Read the current .env file
with open(".env", "r") as f:
    content = f.read()

# Helper to extract value for a key
def get_val(key, default=""):
    match = re.search(rf"^{key}=(.*)$", content, re.MULTILINE)
    return match.group(1).strip() if match else default

# Define the clean, structured template with dynamic value lookups
clean_template = f"""# ============================================================================
# AI OPERATING SYSTEM (AOS) - MASTER ENVIRONMENT TEMPLATE & ACTIVE CONFIG
# ============================================================================

# ────────────────────────────────────────────────────────────────────────────
# 0. GLOBAL PROXY, SSL & DOMAIN (Caddy / DuckDNS)
# ────────────────────────────────────────────────────────────────────────────
DOMAIN={get_val("DOMAIN")}
DUCKDNS_TOKEN={get_val("DUCKDNS_TOKEN")}
CADDY_LETSENCRYPT_EMAIL={get_val("CADDY_LETSENCRYPT_EMAIL")}

# ────────────────────────────────────────────────────────────────────────────
# 1. SYSTEM & INFRASTRUCTURE PINNED VERSIONS
# ────────────────────────────────────────────────────────────────────────────
TZ={get_val("TZ")}
AGENT_PORT={get_val("AGENT_PORT")}
MCP_GITHUB_PORT={get_val("MCP_GITHUB_PORT")}
VERSION_POSTGRES={get_val("VERSION_POSTGRES")}
VERSION_QDRANT={get_val("VERSION_QDRANT")}
VERSION_OLLAMA={get_val("VERSION_OLLAMA")}
VERSION_OPEN_WEBUI={get_val("VERSION_OPEN_WEBUI")}
VERSION_N8N={get_val("VERSION_N8N")}
VERSION_PROMETHEUS={get_val("VERSION_PROMETHEUS")}
VERSION_CODE_SERVER={get_val("VERSION_CODE_SERVER")}
VERSION_HERMES={get_val("VERSION_HERMES")}
VERSION_MCP_GITHUB={get_val("VERSION_MCP_GITHUB")}

# ────────────────────────────────────────────────────────────────────────────
# 2. INTERNAL BRIDGE IPs (nestworks_docker_bridge_network - 172.70.0.0/16)
# ────────────────────────────────────────────────────────────────────────────
INT_IP_DB_SHARED={get_val("INT_IP_DB_SHARED")}
INT_IP_DB_N8N={get_val("INT_IP_DB_N8N")}
INT_IP_DB_OPEN_WEBUI={get_val("INT_IP_DB_OPEN_WEBUI")}
INT_IP_QDRANT={get_val("INT_IP_QDRANT")}
INT_IP_OLLAMA={get_val("INT_IP_OLLAMA")}
INT_IP_OPEN_WEBUI={get_val("INT_IP_OPEN_WEBUI")}
INT_IP_N8N={get_val("INT_IP_N8N")}
INT_IP_N8N_RUNNER={get_val("INT_IP_N8N_RUNNER")}
INT_IP_SYSTEM_AGENT={get_val("INT_IP_SYSTEM_AGENT")}
INT_IP_PROMETHEUS={get_val("INT_IP_PROMETHEUS")}
INT_IP_MCP_QDRANT={get_val("INT_IP_MCP_QDRANT")}
INT_IP_MCP_FILESYSTEM={get_val("INT_IP_MCP_FILESYSTEM")}
INT_IP_MCP_GITHUB={get_val("INT_IP_MCP_GITHUB")}
INT_IP_MCP_CODE_SNIPPETS={get_val("INT_IP_MCP_CODE_SNIPPETS")}
INT_IP_HOME_ASSISTANT={get_val("INT_IP_HOME_ASSISTANT")}
INT_IP_CODE_SERVER={get_val("INT_IP_CODE_SERVER")}
INT_IP_HERMES_AGENT={get_val("INT_IP_HERMES_AGENT")}
INT_IP_HERMES_WEBUI={get_val("INT_IP_HERMES_WEBUI")}

# ────────────────────────────────────────────────────────────────────────────
# 3. PHYSICAL LAN STATIC IPs & MAC BINDINGS (br0 Bridge - 10.70.10.0/24)
# ────────────────────────────────────────────────────────────────────────────
IP_DB_SHARED={get_val("IP_DB_SHARED")}
IP_DB_N8N={get_val("IP_DB_N8N")}
IP_DB_OPEN_WEBUI={get_val("IP_DB_OPEN_WEBUI")}
IP_QDRANT={get_val("IP_QDRANT")}
IP_OLLAMA={get_val("IP_OLLAMA")}
IP_OPEN_WEBUI={get_val("IP_OPEN_WEBUI")}
IP_N8N={get_val("IP_N8N")}
IP_N8N_RUNNER={get_val("IP_N8N_RUNNER")}
IP_SYSTEM_AGENT={get_val("IP_SYSTEM_AGENT")}
IP_PROMETHEUS={get_val("IP_PROMETHEUS")}
IP_MCP_QDRANT={get_val("IP_MCP_QDRANT")}
IP_MCP_FILESYSTEM={get_val("IP_MCP_FILESYSTEM")}
IP_MCP_GITHUB={get_val("IP_MCP_GITHUB")}
IP_MCP_CODE_SNIPPETS={get_val("IP_MCP_CODE_SNIPPETS")}
IP_HOME_ASSISTANT={get_val("IP_HOME_ASSISTANT")}
IP_CODE_SERVER={get_val("IP_CODE_SERVER")}
IP_HERMES_AGENT={get_val("IP_HERMES_AGENT")}
IP_HERMES_WEBUI={get_val("IP_HERMES_WEBUI")}

MAC_DB_SHARED={get_val("MAC_DB_SHARED")}
MAC_DB_N8N={get_val("MAC_DB_N8N")}
MAC_DB_OPEN_WEBUI={get_val("MAC_DB_OPEN_WEBUI")}
MAC_QDRANT={get_val("MAC_QDRANT")}
MAC_OLLAMA={get_val("MAC_OLLAMA")}
MAC_OPEN_WEBUI={get_val("MAC_OPEN_WEBUI")}
MAC_N8N={get_val("MAC_N8N")}
MAC_N8N_RUNNER={get_val("MAC_N8N_RUNNER")}
MAC_SYSTEM_AGENT={get_val("MAC_SYSTEM_AGENT")}
MAC_PROMETHEUS={get_val("MAC_PROMETHEUS")}
MAC_MCP_QDRANT={get_val("MAC_MCP_QDRANT")}
MAC_MCP_FILESYSTEM={get_val("MAC_MCP_FILESYSTEM")}
MAC_MCP_GITHUB={get_val("MAC_MCP_GITHUB")}
MAC_MCP_CODE_SNIPPETS={get_val("MAC_MCP_CODE_SNIPPETS")}
MAC_HOME_ASSISTANT={get_val("MAC_HOME_ASSISTANT")}
MAC_CODE_SERVER={get_val("MAC_CODE_SERVER")}
MAC_HERMES_AGENT={get_val("MAC_HERMES_AGENT")}
MAC_HERMES_WEBUI={get_val("MAC_HERMES_WEBUI")}

# ────────────────────────────────────────────────────────────────────────────
# 4. INTERNAL SERVICE & AGENT URLS
# ────────────────────────────────────────────────────────────────────────────
OLLAMA_API_BASE={get_val("OLLAMA_API_BASE")}
SYSTEM_AGENT_API_BASE={get_val("SYSTEM_AGENT_API_BASE")}
URL_QDRANT={get_val("URL_QDRANT")}
URL_QDRANT_GRPC={get_val("URL_QDRANT_GRPC")}
URL_OPEN_WEBUI={get_val("URL_OPEN_WEBUI")}
URL_MCP_FILESYSTEM={get_val("URL_MCP_FILESYSTEM")}
URL_MCP_QDRANT={get_val("URL_MCP_QDRANT")}
URL_MCP_CODE_SNIPPETS={get_val("URL_MCP_CODE_SNIPPETS")}
URL_MCP_GITHUB={get_val("URL_MCP_GITHUB")}
AGENT_URL={get_val("AGENT_URL")}
HOMEASSISTANT_MCP_URL={get_val("HOMEASSISTANT_MCP_URL")}
N8N_MCP_URL={get_val("N8N_MCP_URL")}
URL_CODE_SERVER={get_val("URL_CODE_SERVER")}
URL_HOME_ASSISTANT={get_val("URL_HOME_ASSISTANT")}
URL_HERMES_AGENT={get_val("URL_HERMES_AGENT")}
URL_HERMES_WEBUI={get_val("URL_HERMES_WEBUI")}

# ────────────────────────────────────────────────────────────────────────────
# 5. DATABASE CONFIGURATION & CREDENTIALS
# ────────────────────────────────────────────────────────────────────────────
POSTGRES_SUPERUSER_PASSWORD={get_val("POSTGRES_SUPERUSER_PASSWORD")}
N8N_DB_USER={get_val("N8N_DB_USER")}
N8N_DB_PASSWORD={get_val("N8N_DB_PASSWORD")}
OPEN_WEBUI_DB_USER={get_val("OPEN_WEBUI_DB_USER")}
OPEN_WEBUI_DB_PASSWORD={get_val("OPEN_WEBUI_DB_PASSWORD")}

# ────────────────────────────────────────────────────────────────────────────
# 6. WORKFLOW ENGINE CORE & SECURITY (n8n)
# ────────────────────────────────────────────────────────────────────────────
N8N_HOST={get_val("N8N_HOST")}
N8N_WEBHOOK_URL={get_val("N8N_WEBHOOK_URL")}
N8N_EDITOR_BASE_URL={get_val("N8N_EDITOR_BASE_URL")}
N8N_PORT={get_val("N8N_PORT")}
N8N_PROTOCOL={get_val("N8N_PROTOCOL")}
N8N_PROXY_HOPS={get_val("N8N_PROXY_HOPS")}
N8N_CORS_ALLOWED_ORIGINS={get_val("N8N_CORS_ALLOWED_ORIGINS")}
N8N_ENCRYPTION_KEY={get_val("N8N_ENCRYPTION_KEY")}
N8N_USER_MANAGEMENT_JWT_SECRET={get_val("N8N_USER_MANAGEMENT_JWT_SECRET")}
N8N_RUNNERS_AUTH_TOKEN={get_val("N8N_RUNNERS_AUTH_TOKEN")}
N8N_API_KEY={get_val("N8N_API_KEY")}
INSTANCE_LEVEL_ACCESS_TOKEN_N8N={get_val("INSTANCE_LEVEL_ACCESS_TOKEN_N8N")}

# ────────────────────────────────────────────────────────────────────────────
# 7. AI GATEWAY, SYSTEM AGENT & CORE KEYS
# ────────────────────────────────────────────────────────────────────────────
SYSTEM_AGENT_KEY={get_val("SYSTEM_AGENT_KEY")}
SYSTEM_AGENT_UUID={get_val("SYSTEM_AGENT_UUID")}
NVIDIA_API_KEY={get_val("NVIDIA_API_KEY")}
OPENAI_API_KEY={get_val("OPENAI_API_KEY")}
WEBUI_SECRET_KEY={get_val("WEBUI_SECRET_KEY")}

# ────────────────────────────────────────────────────────────────────────────
# 8. EXTERNAL PROVIDER & TOOL INTEGRATION TOKENS
# ────────────────────────────────────────────────────────────────────────────
HF_TOKEN={get_val("HF_TOKEN")}
GITHUB_PERSONAL_ACCESS_TOKEN={get_val("GITHUB_PERSONAL_ACCESS_TOKEN")}
BRAVE_API_KEY={get_val("BRAVE_API_KEY")}
HA_LONG_LIVED_TOKEN={get_val("HA_LONG_LIVED_TOKEN")}
CODE_SERVER_PASSWORD={get_val("CODE_SERVER_PASSWORD")}
CODE_SERVER_SUDO_PASSWORD={get_val("CODE_SERVER_SUDO_PASSWORD")}

# ────────────────────────────────────────────────────────────────────────────
# 9. MCP RUNTIME POLICIES & PERMISSIONS
# ────────────────────────────────────────────────────────────────────────────
ALLOW_WRITE={get_val("ALLOW_WRITE", "true")}
ENABLE_ROOTS={get_val("ENABLE_ROOTS", "false")}
"""

with open(".env.temp", "w") as f:
    f.write(clean_template)

print("✅ Successfully generated .env.temp using real values!")

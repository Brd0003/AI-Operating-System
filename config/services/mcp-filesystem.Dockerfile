FROM ghcr.io/sparfenyuk/mcp-proxy:latest

# Install Node.js on Alpine for npx.
# NOTE: @rustmcp/rust-mcp-filesystem is a Rust binary package that only
# supports glibc Linux (x86_64-unknown-linux-gnu, glibc >= 2.35).
# Alpine uses musl -- it WILL FAIL on this base image.
# Use @modelcontextprotocol/server-filesystem: official MCP filesystem server,
# pure Node.js, works correctly on Alpine/musl.
RUN apk add --no-cache nodejs npm

# Pre-install globally to avoid npx download on every container start.
# Binary entrypoint: mcp-server-filesystem
RUN npm install -g @modelcontextprotocol/server-filesystem

EXPOSE 8000
ENTRYPOINT ["catatonit", "--", "mcp-proxy"]
# --pass-environment required: without it node cannot find PATH, HOME, NODE_PATH.
# /projects is the allowed root, matches the volume mount.
CMD ["--pass-environment", "--port", "8000", "--host", "0.0.0.0", "--", \
     "mcp-server-filesystem", "/projects"]
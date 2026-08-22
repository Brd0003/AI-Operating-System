#!/usr/bin/env bash
set -e

create_service_db () {
  local db_user="$1"
  local db_password="$2"
  local db_name="$3"

  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${db_user}') THEN
        CREATE ROLE "${db_user}" WITH LOGIN PASSWORD '${db_password}';
      END IF;
    END
    \$\$;

    SELECT 'CREATE DATABASE "${db_name}" OWNER "${db_user}"'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${db_name}')\gexec

    GRANT ALL PRIVILEGES ON DATABASE "${db_name}" TO "${db_user}";
EOSQL
}

create_service_db "$N8N_DB_USER" "$N8N_DB_PASSWORD" "n8n"
create_service_db "$LITELLM_DB_USER" "$LITELLM_DB_PASSWORD" "litellm"
create_service_db "$OPEN_WEBUI_DB_USER" "$OPEN_WEBUI_DB_PASSWORD" "open_webui"

echo "init-multi-db.sh: n8n / litellm / open_webui databases + roles ready."

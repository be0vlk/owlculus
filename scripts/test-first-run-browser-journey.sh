#!/usr/bin/env bash
# Run the first-install browser journey against disposable Owlculus stacks.

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_script="$repository_root/scripts/compose.sh"
gateway_port="${E2E_GATEWAY_PORT:-80}"
gateway_https_port="${E2E_GATEWAY_HTTPS_PORT:-18443}"
vite_port="${E2E_VITE_PORT:-5173}"
backend_port="${E2E_BACKEND_PORT:-18000}"
active_project=""
active_topology=""
active_frontend_port=""
active_vite_pid=""

run_compose() {
    FRONTEND_PORT="$active_frontend_port" \
        HTTPS_PORT="$gateway_https_port" \
        BACKEND_PORT="$backend_port" \
        OWLCULUS_LOG_FILE="/tmp/owlculus-e2e.log" \
        "$compose_script" "$active_topology" --project-name "$active_project" "$@"
}

cleanup_stack() {
    if [[ -n "$active_vite_pid" ]]; then
        if kill -0 "$active_vite_pid" 2>/dev/null; then
            kill "$active_vite_pid"
            wait "$active_vite_pid" 2>/dev/null || true
        fi
        active_vite_pid=""
    fi

    if [[ -z "$active_project" ]]; then
        return
    fi

    echo "Removing ephemeral stack $active_project (including volumes)..."
    run_compose down --volumes --remove-orphans
    active_project=""
}

start_vite_server() {
    (
        cd "$repository_root/frontend"
        API_PROXY_TARGET="http://127.0.0.1:$backend_port" \
            exec ./node_modules/.bin/vite --host 0.0.0.0 --port "$vite_port" --strictPort
    ) &
    active_vite_pid=$!

    for _attempt in {1..30}; do
        if ! kill -0 "$active_vite_pid" 2>/dev/null; then
            echo "Vite exited before becoming ready on port $vite_port." >&2
            return 1
        fi
        if curl --fail --silent --output /dev/null "http://127.0.0.1:$vite_port"; then
            return
        fi
        sleep 1
    done

    echo "Vite did not become ready on port $vite_port." >&2
    return 1
}

trap cleanup_stack EXIT INT TERM

read_setup_token_from_logs() {
    run_compose logs --no-color backend | awk '
        /SETUP TOKEN \(use this to create your admin account\):/ {
            token_follows = 1
            next
        }
        token_follows && !token_printed {
            line = $0
            sub(/^[^|]*\|[[:space:]]*/, "", line)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
            if (length(line) > 0) {
                print line
                token_printed = 1
            }
        }
    '
}

browser_url() {
    local host="$1"
    local port="$2"

    if [[ "$port" == "80" ]]; then
        printf 'http://%s' "$host"
    else
        printf 'http://%s:%s' "$host" "$port"
    fi
}

run_variant() {
    local server_kind="$1"
    local host="$2"
    local setup_token
    local test_status=0

    active_project="owlculus-e2e-${server_kind}-${host//./-}-$$"
    if [[ "$server_kind" == "gateway" ]]; then
        active_topology="direct"
        active_frontend_port="$gateway_port"
    else
        active_topology="development"
        active_frontend_port="$vite_port"
    fi

    echo "Starting a fresh $server_kind stack for $host..."
    if [[ "$server_kind" == "gateway" ]]; then
        run_compose up --detach --build --wait --wait-timeout 240
    else
        run_compose up --detach --build --wait --wait-timeout 240 backend
        start_vite_server
    fi

    setup_token="$(read_setup_token_from_logs)"
    if [[ -z "$setup_token" ]]; then
        echo "Could not read the setup token from backend logs." >&2
        run_compose logs --no-color backend >&2
        return 1
    fi

    (
        cd "$repository_root/frontend"
        OWLCULUS_BASE_URL="$(browser_url "$host" "$active_frontend_port")" \
            OWLCULUS_SETUP_TOKEN="$setup_token" \
            npm run test:e2e:playwright -- --project=chromium
    ) || test_status=$?

    cleanup_stack
    return "$test_status"
}

read -r -a server_kinds <<< "${E2E_SERVER_KINDS:-gateway vite}"
read -r -a browser_hosts <<< "${E2E_HOSTS:-localhost 127.0.0.1}"

for server_kind in "${server_kinds[@]}"; do
    for host in "${browser_hosts[@]}"; do
        run_variant "$server_kind" "$host"
    done
done

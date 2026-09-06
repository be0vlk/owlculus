#!/usr/bin/env bash
# Run browser journeys against disposable Owlculus stacks. Arguments select
# focused Playwright files/options, e.g. e2e/frontend-workflows.spec.js.

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_script="$repository_root/scripts/compose.sh"
gateway_port="${E2E_GATEWAY_PORT:-80}"
gateway_https_port="${E2E_GATEWAY_HTTPS_PORT:-18443}"
vite_port="${E2E_VITE_PORT:-5173}"
backend_port="${E2E_BACKEND_PORT:-18000}"
execution_controls=""
execution_compose=()
if [[ "${E2E_EXECUTIONS:-0}" == "1" || "$*" == *"durable-executions.spec.js"* ]]; then
    execution_compose=(-f "$repository_root/frontend/e2e/execution-support/compose.yml")
fi
active_project=""
active_topology=""
active_frontend_port=""
active_hmr_probe_path=""
active_artifact_directory=""

run_compose() {
    OWLCULUS_EXECUTION_CONTROLS="$execution_controls" \
        FRONTEND_PORT="$active_frontend_port" \
        DEV_FRONTEND_PORT="$vite_port" \
        HTTPS_PORT="$gateway_https_port" \
        BACKEND_PORT="$backend_port" \
        OWLCULUS_LOG_FILE="/tmp/owlculus-e2e.log" \
        "$compose_script" "$active_topology" --project-name "$active_project" "${execution_compose[@]}" "$@"
}

cleanup_stack() {
    if [[ -n "$active_project" ]]; then
        if mkdir -p "$active_artifact_directory"; then
            run_compose logs --no-color frontend backend execution-dispatcher plugin-worker hunt-worker > "$active_artifact_directory/stack.log" 2>&1 || true
        fi
        if [[ -n "$execution_controls" ]]; then
            for ready_file in "$execution_controls"/*.ready; do
                [[ -e "$ready_file" ]] || continue
                touch "${ready_file%.ready}.release"
            done
            cp -R "$execution_controls" "$active_artifact_directory/provider-controls" || true
        fi
        echo "Removing ephemeral stack $active_project (including volumes)..."
        run_compose down --volumes --remove-orphans
        active_project=""
    fi

    if [[ -n "$execution_controls" ]]; then
        rm -rf -- "$execution_controls"
        execution_controls=""
    fi

    if [[ -n "$active_hmr_probe_path" ]]; then
        rm -f -- "$active_hmr_probe_path"
        active_hmr_probe_path=""
    fi
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

wait_for_frontend() {
    local frontend_url="http://127.0.0.1:$active_frontend_port"
    local consecutive_successes=0

    for _attempt in {1..60}; do
        if curl --fail --silent --output /dev/null "$frontend_url"; then
            ((consecutive_successes += 1))
            if (( consecutive_successes == 2 )); then
                return
            fi
        else
            consecutive_successes=0
        fi
        sleep 1
    done

    echo "Frontend did not become stable at $frontend_url." >&2
    run_compose logs --no-color frontend backend execution-dispatcher plugin-worker hunt-worker >&2
    return 1
}

run_variant() {
    local server_kind="$1"
    local host="$2"
    local viewport="$3"
    shift 3
    local setup_token
    local expired_token=""
    local test_status=0

    active_project="owlculus-e2e-${server_kind}-${viewport}-${host//./-}-$$"
    active_artifact_directory="$repository_root/frontend/test-results/${server_kind}-${host}-${viewport}${E2E_ARTIFACT_GROUP:+-$E2E_ARTIFACT_GROUP}"
    if [[ "$server_kind" == "gateway" ]]; then
        active_topology="direct"
        active_frontend_port="$gateway_port"
    else
        active_topology="development"
        active_frontend_port="$vite_port"
        active_hmr_probe_path="$(mktemp "$repository_root/frontend/src/e2e-hmr-probe.XXXXXX.js")"
        cp "$repository_root/frontend/e2e/fixtures/hmr-probe.js" "$active_hmr_probe_path"
    fi

    if (( ${#execution_compose[@]} )); then
        execution_controls="$(mktemp -d /tmp/owlculus-browser-executions.XXXXXX)"
        chmod 777 "$execution_controls"
    fi

    echo "Starting a fresh $server_kind stack for $host at the $viewport viewport..."
    run_compose up --detach --build --wait --wait-timeout 240
    wait_for_frontend
    if (( ${#execution_compose[@]} )); then
        run_compose exec -T backend python /e2e/seed.py
    fi

    setup_token="$(read_setup_token_from_logs)"
    if [[ -z "$setup_token" ]]; then
        echo "Could not read the setup token from backend logs." >&2
        run_compose logs --no-color backend >&2
        return 1
    fi

    if [[ "$*" == *"case-session.spec.js"* ]]; then
        expired_token="$(run_compose exec -T backend python -c 'from datetime import timedelta; from app.core.security import create_access_token; print(create_access_token({"sub": "coverage_admin"}, timedelta(seconds=-60)))')"
    fi

    (
        cd "$repository_root/frontend"
        OWLCULUS_EXPIRED_TOKEN="$expired_token" \
        OWLCULUS_EXECUTION_CONTROLS="$execution_controls" \
        OWLCULUS_BASE_URL="$(browser_url "$host" "$active_frontend_port")" \
            OWLCULUS_SETUP_TOKEN="$setup_token" \
            OWLCULUS_SERVER_KIND="$server_kind" \
            OWLCULUS_VIEWPORT="$viewport" \
            OWLCULUS_HMR_PROBE_PATH="$active_hmr_probe_path" \
            npm run test:e2e:playwright -- --project=chromium --output="$active_artifact_directory" "$@"
    ) || test_status=$?

    cleanup_stack
    return "$test_status"
}

read -r -a server_kinds <<< "${E2E_SERVER_KINDS:-gateway vite}"
read -r -a browser_hosts <<< "${E2E_HOSTS:-localhost 127.0.0.1}"
read -r -a viewports <<< "${E2E_VIEWPORTS:-desktop narrow}"

for server_kind in "${server_kinds[@]}"; do
    for host in "${browser_hosts[@]}"; do
        for viewport in "${viewports[@]}"; do
            if (( $# > 0 )); then
                run_variant "$server_kind" "$host" "$viewport" "$@"
            else
                # Both groups bootstrap their own administrator. Keep the
                # first-install assertions independent from workflow fixtures.
                run_variant "$server_kind" "$host" "$viewport" e2e/first-run.spec.js e2e/active-case.spec.js
                E2E_ARTIFACT_GROUP=workflows run_variant "$server_kind" "$host" "$viewport" e2e/frontend-workflows.spec.js
            fi
        done
    done
done

#!/usr/bin/env bash
# Run Docker Compose against a named Owlculus deployment topology.

set -euo pipefail

if (( $# < 2 )); then
    echo "Usage: $0 <direct|development|reverse-proxy> <compose arguments...>" >&2
    exit 2
fi

topology="$1"
shift

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_files=(-f "$repository_root/docker-compose.yml")

case "$topology" in
    direct)
        ;;
    development)
        compose_files+=(-f "$repository_root/docker-compose.dev.yml")
        ;;
    reverse-proxy)
        compose_files+=(-f "$repository_root/docker-compose.reverse-proxy.yml")
        ;;
    *)
        echo "Unknown Compose topology: $topology" >&2
        exit 2
        ;;
esac

exec docker compose --project-directory "$repository_root" "${compose_files[@]}" "$@"

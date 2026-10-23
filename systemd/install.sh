#!/usr/bin/env bash
# Host setup for running the LRIS2 daemons under systemd. For admins / IT.
# Run as root. Safe to re-run: it converges the host onto the current repo.
#
#   sudo ./systemd/install.sh                    # set the host up
#   sudo ./systemd/install.sh alice bob          # ... and enrol two operators
#   sudo ./systemd/install.sh --extra camera     # ... with the camera daemon's module
#
# Extras are recorded in /etc/lris2/extras, and every later run syncs them
# again, so a plain re-run keeps the camera module.
#
# This builds the virtualenv and hands over to `lris2 install`, which does the
# rest: the ops group, the daemon account, /etc/lris2, the template unit, the
# polkit rule and the operator commands. Everything after that needs no root.

set -euo pipefail

REPO_DIR="${LRIS2_REPO_DIR:-/opt/lris2/app}"
VENV_DIR="${LRIS2_VENV_DIR:-/opt/lris2/venv}"
EXTRAS_FILE="${LRIS2_ETC_DIR:-/etc/lris2}/extras"
UV_VERSION="${LRIS2_UV_VERSION:-0.12.23}"
# Its own copy rather than whatever uv is on PATH, since a snap refreshes
# itself and would unpin the resolver
UV_BIN=/usr/local/bin/uv

# Keeps uv out of .venv and on the path every unit already references
export UV_PROJECT_ENVIRONMENT="$VENV_DIR"

# The daemons run as `lris2`, and this script runs as root, so a uv-managed
# interpreter would land under root's home where they could not read it. Use
# the system Python.
export UV_NO_MANAGED_PYTHON=1

if [[ $EUID -ne 0 ]]; then
    echo "Run as root (sudo)." >&2
    exit 1
fi

if [[ ! -d "$REPO_DIR" ]]; then
    echo "error: REPO_DIR $REPO_DIR does not exist." >&2
    echo "Clone the repo there first, e.g.:" >&2
    echo "  git clone <repo-url> $REPO_DIR" >&2
    echo "  cd $REPO_DIR && git submodule update --init --recursive" >&2
    exit 1
fi

# --extra is ours; everything else goes to `lris2 install`
INSTALL_ARGS=()
EXTRAS=()
if [[ -f "$EXTRAS_FILE" ]]; then
    mapfile -t EXTRAS <"$EXTRAS_FILE"
fi
while (($#)); do
    case $1 in
        --extra) EXTRAS+=("$2"); shift 2 ;;
        *) INSTALL_ARGS+=("$1"); shift ;;
    esac
done
if ((${#EXTRAS[@]})); then
    mapfile -t EXTRAS < <(printf '%s\n' "${EXTRAS[@]}" | sort -u)
fi
EXTRA_FLAGS=()
for extra in "${EXTRAS[@]}"; do
    EXTRA_FLAGS+=(--extra "$extra")
done

# Pinned, so re-running the installer cannot resolve with a different uv
if [[ "$("$UV_BIN" --version 2>/dev/null)" != "uv $UV_VERSION"* ]]; then
    curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" |
        env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
    echo "installed uv $UV_VERSION at $UV_BIN"
fi

# The virtualenv has to exist before the rest, since `lris2 install` lives in
# it. Upgrade the lock first: the git dependencies track their default branch
# deliberately, and a reinstall is how a merged libby fix reaches a host.
(
    cd "$REPO_DIR"
    "$UV_BIN" lock --upgrade
    "$UV_BIN" sync "${EXTRA_FLAGS[@]}"
)

# Only once the sync accepted them, so a mistyped extra is not kept
if ((${#EXTRAS[@]})); then
    mkdir -p "$(dirname "$EXTRAS_FILE")"
    printf '%s\n' "${EXTRAS[@]}" >"$EXTRAS_FILE"
fi

exec "$VENV_DIR/bin/lris2" install "${INSTALL_ARGS[@]}"

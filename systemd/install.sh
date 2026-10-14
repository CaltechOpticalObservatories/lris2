#!/usr/bin/env bash
# Host setup for running the LRIS2 daemons under systemd. For admins / IT.
# Run as root. Safe to re-run: it converges the host onto the current repo.
#
#   sudo ./systemd/install.sh                    # set the host up
#   sudo ./systemd/install.sh alice bob          # ... and enrol two operators
#
# This builds the virtualenv and hands over to `lris2 install`, which does the
# rest: the ops group, the daemon account, /etc/lris2, the template unit, the
# polkit rule and the operator commands. Everything after that needs no root.

set -euo pipefail

REPO_DIR="${LRIS2_REPO_DIR:-/opt/lris2/app}"
VENV_DIR="${LRIS2_VENV_DIR:-/opt/lris2/venv}"

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

# Editable, so the deployed CLI and daemons follow a git pull
if [[ ! -x "$VENV_DIR/bin/python3" ]]; then
    python3 -m venv "$VENV_DIR"
    echo "created venv at $VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -U pip
"$VENV_DIR/bin/pip" install -e "$REPO_DIR"

# Reading a keyword is libby, which otherwise lives only inside the venv
ln -sf "$VENV_DIR/bin/libby" /usr/local/bin/libby
echo "linked /usr/local/bin/libby"

# Every login shell rather than every operator's shell rc
install -m 0644 /dev/stdin /etc/profile.d/lris2.sh <<'PROFILE'
# TAB completion over libby keyword names
if command -v libby >/dev/null 2>&1; then
    eval "$(libby completion bash)"
fi
PROFILE
echo "installed /etc/profile.d/lris2.sh"

exec "$VENV_DIR/bin/lris2" install "$@"

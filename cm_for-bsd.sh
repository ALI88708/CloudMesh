#!/bin/sh

# ============================================
# CloudMesh Installer - BSD (FreeBSD, OpenBSD, NetBSD)
# Created by MRSX PRO
# ============================================
# POSIX sh on purpose: a stock BSD host has no /bin/bash, so the shebang and
# every construct below must work with the base-system /bin/sh.
set -e

# ============================================
# NON-INTERACTIVE MODE
# ============================================
# The interactive path asks once and then installs. CI cannot answer prompts, so
# `sh cm_for-bsd.sh --yes` (or CM_NONINTERACTIVE=1) runs the whole install with
# no prompts and no pauses.
#
#   --yes / -y          install without prompting
#   --source=DIR        install from a local checkout instead of downloading
#   --skip-node         controller only; do not install the node agent
#   --verify-only       do not install; assert the current install works
NONINTERACTIVE="${CM_NONINTERACTIVE:-0}"
SOURCE_DIR="${CM_SOURCE_DIR:-}"
SKIP_NODE="${CM_SKIP_NODE:-0}"
VERIFY_ONLY="${CM_VERIFY_ONLY:-0}"

for arg in "$@"; do
    case "$arg" in
        -y|--yes)          NONINTERACTIVE=1 ;;
        --source=*)        SOURCE_DIR="${arg#--source=}" ;;
        --skip-node)       SKIP_NODE=1 ;;
        --verify-only)     VERIFY_ONLY=1 ;;
        -h|--help)
            cat <<'USAGE'
CloudMesh Installer - BSD (FreeBSD, OpenBSD, NetBSD) (MRSX PRO)

  sh cm_for-bsd.sh                 interactive (asks once before installing)
  sh cm_for-bsd.sh --yes           install with no prompts (used by CI)
  sh cm_for-bsd.sh --verify-only   assert the current install works

Options:
  -y, --yes              install without prompting
      --source=DIR       install from a local checkout instead of downloading
      --skip-node        controller only; do not install the node agent
      --verify-only      do not install; only run the checks

The install goes into ~/.cloudmesh with its own virtual environment; if the
system python cannot build one, the installer falls back to
`python3 -m pip install --user .` and puts `cm` in ~/.local/bin.
USAGE
            exit 0
            ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

# ============================================
# HOST CHECK
# ============================================
# This installer drives pkg/pkg_add and rc.d units, so it is BSD-only. Saying so
# up front beats failing halfway through on a package manager that is not there.
OS_TYPE="$(uname -s)"
case "$OS_TYPE" in
    FreeBSD|OpenBSD|NetBSD) ;;
    *)
        echo "[FAIL] cm_for-bsd.sh is for FreeBSD, OpenBSD and NetBSD; this host is $OS_TYPE." >&2
        echo "[INFO] On Linux use cm_for-linux.sh, on Windows use cm_for-windows.bat." >&2
        exit 1
        ;;
esac

# -- CONFIG ---------------------------------------------------------------
GITHUB_USER="ALI88708"
GITHUB_REPO="CloudMesh"
GITHUB_BRANCH="main"

# ============================================
# PATHS
# ============================================
INSTALL_DIR="$HOME/.cloudmesh"
PROJECT_DIR="$INSTALL_DIR/project"
CLOUDMESH_DIR="$PROJECT_DIR/cloudmesh"
NODE_DIR="$HOME/.cloudmesh-node"
NODE_SCRIPT="cloudmesh_node.py"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"

# ============================================
# OUTPUT HELPERS
# ============================================
# printf handles escapes portably and colour is only used on a terminal, so
# logs and CI output stay readable.
if [ -t 1 ]; then
    BOLD="$(printf '\033[1m')"
    NC="$(printf '\033[0m')"
else
    BOLD=""
    NC=""
fi

log()  { printf '%s\n' "[OK] $*"; }
info() { printf '%s\n' "[INFO] $*"; }
warn() { printf '%s\n' "[WARN] $*"; }
fail() { printf '%s\n' "[FAIL] $*" >&2; }

banner() {
    printf '\n%s\n' "${BOLD}============================================${NC}"
    printf '%s\n' "${BOLD}   $1${NC}"
    printf '%s\n' "${BOLD}============================================${NC}"
}

# ============================================
# PRIVILEGES
# ============================================
# root, else the sudo most hosts have, else OpenBSD's doas. An empty PRIV is
# correct for root; every call below tolerates it.
if [ "$(id -u)" -eq 0 ]; then
    PRIV=""
elif command -v sudo >/dev/null 2>&1; then
    PRIV="sudo"
elif command -v doas >/dev/null 2>&1; then
    PRIV="doas"
else
    PRIV=""
    warn "Neither sudo nor doas found; system steps need root."
fi

# ============================================
# PYTHON
# ============================================
install_python() {
    info "Python3 not found. Installing..."
    case "$OS_TYPE" in
        FreeBSD)
            $PRIV pkg install -y python3
            ;;
        OpenBSD)
            $PRIV pkg_add python%3 || $PRIV pkg_add python3
            ;;
        NetBSD)
            $PRIV pkg_add python3
            ;;
    esac
}

ensure_python() {
    if command -v python3 >/dev/null 2>&1; then
        log "Python3 found: $(python3 --version 2>&1 | awk '{print $2}')"
        return 0
    fi
    install_python
    if ! command -v python3 >/dev/null 2>&1; then
        fail "Python installation failed"
        return 1
    fi
    log "Python3 installed: $(python3 --version 2>&1 | awk '{print $2}')"
    return 0
}

# BSD ships pip as a separate package, so it may be missing next to python3.
ensure_pip() {
    if python3 -m pip --version >/dev/null 2>&1; then
        return 0
    fi
    PY_FLAVOUR="$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])' 2>/dev/null || true)"
    if [ -n "$PY_FLAVOUR" ]; then
        info "Installing pip for python$PY_FLAVOUR..."
        case "$OS_TYPE" in
            FreeBSD)
                $PRIV pkg install -y "py$PY_FLAVOUR-pip" >/dev/null 2>&1 || true
                ;;
            OpenBSD)
                $PRIV pkg_add "py$PY_FLAVOUR-pip" >/dev/null 2>&1 || \
                    $PRIV pkg_add py3-pip >/dev/null 2>&1 || true
                ;;
            NetBSD)
                $PRIV pkg_add "py$PY_FLAVOUR-pip" >/dev/null 2>&1 || true
                ;;
        esac
    fi
    if python3 -m pip --version >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

# ============================================
# STAGE THE PROJECT TREE
# ============================================
# pyproject.toml declares packages = ["cloudmesh", ...], so the directory handed
# to pip has to CONTAIN the cloudmesh/ package. PROJECT_DIR is that root.
stage_payload() {
    SRC_ROOT="$1"
    rm -rf "$PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"
    cp -r "$SRC_ROOT/cloudmesh" "$PROJECT_DIR/cloudmesh"
    for extra in pyproject.toml README.md License LICENSE; do
        if [ -f "$SRC_ROOT/$extra" ]; then
            cp "$SRC_ROOT/$extra" "$PROJECT_DIR/"
        fi
    done
    if [ ! -f "$PROJECT_DIR/pyproject.toml" ]; then
        fail "pyproject.toml missing from $SRC_ROOT; cannot build an installable project"
        return 1
    fi
    return 0
}

# ============================================
# DOWNLOAD
# ============================================
# curl and wget are packages on BSD, but fetch(1) (FreeBSD) and ftp(1) (all
# three) are in the base system, so a bare host can still install.
download_file() {
    URL="$1"
    OUT="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -L --connect-timeout 10 --retry 3 -s -o "$OUT" "$URL"
    elif command -v wget >/dev/null 2>&1; then
        wget -q --timeout=10 --tries=3 -O "$OUT" "$URL"
    elif command -v fetch >/dev/null 2>&1; then
        fetch -q -o "$OUT" "$URL"
    elif command -v ftp >/dev/null 2>&1; then
        ftp -q -o "$OUT" "$URL"
    else
        fail "No downloader found (tried curl, wget, fetch, ftp)"
        return 1
    fi
    if [ ! -s "$OUT" ]; then
        fail "Download failed: $URL"
        return 1
    fi
    return 0
}

fetch_payload() {
    # A local checkout is preferred so CI verifies the branch under test rather
    # than whatever happens to be on main.
    if [ -n "$SOURCE_DIR" ]; then
        if [ ! -d "$SOURCE_DIR/cloudmesh" ]; then
            fail "--source=$SOURCE_DIR has no cloudmesh/ directory"
            return 1
        fi
        stage_payload "$SOURCE_DIR" || return 1
        log "Copied source from $SOURCE_DIR"
        return 0
    fi

    banner "   Downloading from GitHub..."
    info "[1/2] Downloading ZIP..."
    ZIP_URL="https://github.com/$GITHUB_USER/$GITHUB_REPO/archive/refs/heads/$GITHUB_BRANCH.zip"
    ZIP_FILE="$(mktemp "${TMPDIR:-/tmp}/cloudmesh.XXXXXX")"
    EXTRACT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/cloudmesh_extract.XXXXXX")"

    if ! download_file "$ZIP_URL" "$ZIP_FILE"; then
        rm -rf "$EXTRACT_DIR" "$ZIP_FILE"
        return 1
    fi

    info "[2/2] Extracting files..."
    # bsdtar is in the base system on all three BSDs and reads ZIP; unzip is an
    # extra package, so it is only used when it happens to be installed.
    if command -v unzip >/dev/null 2>&1; then
        unzip -q -o "$ZIP_FILE" -d "$EXTRACT_DIR"
    else
        tar -xf "$ZIP_FILE" -C "$EXTRACT_DIR"
    fi

    EXTRACTED="$(find "$EXTRACT_DIR" -maxdepth 1 -type d -name 'CloudMesh*' | head -1)"
    if [ -z "$EXTRACTED" ]; then
        fail "Extract failed"
        rm -rf "$EXTRACT_DIR" "$ZIP_FILE"
        return 1
    fi

    if ! stage_payload "$EXTRACTED"; then
        rm -rf "$EXTRACT_DIR" "$ZIP_FILE"
        return 1
    fi
    rm -rf "$EXTRACT_DIR"
    rm -f "$ZIP_FILE"

    if [ ! -f "$CLOUDMESH_DIR/main.py" ]; then
        fail "Download failed"
        return 1
    fi
    log "Download complete"
    return 0
}

# ============================================
# INSTALL
# ============================================
install_project() {
    banner "   Setting up CloudMesh..."

    rm -rf "$VENV_DIR"
    info "Creating virtual environment..."
    if python3 -m venv "$VENV_DIR" >/dev/null 2>&1; then
        "$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
        info "Installing CloudMesh into the virtual environment..."
        if ! "$VENV_DIR/bin/python" -m pip install --quiet "$PROJECT_DIR"; then
            fail "pip install failed"
            return 1
        fi
        log "CloudMesh installed into $VENV_DIR"
        return 0
    fi

    # A stripped-down system can lack the pieces venv needs; the brief lays down
    # python3 and pip as separate packages on the BSD family.
    warn "python3 -m venv failed; falling back to pip install --user"
    if ! ensure_pip; then
        fail "pip is not available for python3"
        return 1
    fi
    if ! python3 -m pip install --user --quiet "$PROJECT_DIR"; then
        fail "pip install --user failed"
        return 1
    fi
    log "CloudMesh installed into $BIN_DIR"
    return 0
}

install_node_agent() {
    if [ "$SKIP_NODE" = "1" ]; then
        warn "skipping node agent (--skip-node)"
        return 0
    fi
    NODE_INSTALLER="$CLOUDMESH_DIR/node/node-install.sh"
    if [ ! -f "$NODE_INSTALLER" ]; then
        warn "node-install.sh not found; skipping the node agent"
        return 0
    fi
    banner "   Installing the node agent..."
    # node-install.sh is POSIX sh and BSD-aware, so this installer does not
    # duplicate the package and rc.d work.
    if ! sh "$NODE_INSTALLER"; then
        warn "node agent install failed; the controller is still usable"
    fi
    return 0
}

# ============================================
# VERIFY THE INSTALL ACTUALLY WORKS
# ============================================
# Reporting success the moment files land is how a broken dependency set looks
# like a clean install. `cm_for-bsd.sh --verify-only` re-runs just these checks.
verify_install() {
    banner "   Verifying the install..."
    failed=0

    CM_CMD=""
    if [ -x "$VENV_DIR/bin/cm" ]; then
        CM_CMD="$VENV_DIR/bin/cm"
    elif [ -x "$BIN_DIR/cm" ]; then
        CM_CMD="$BIN_DIR/cm"
    fi

    if [ -z "$CM_CMD" ]; then
        fail "cm shortcut missing"
        failed=1
    else
        log "cm shortcut present: $CM_CMD"
    fi

    if [ -n "$CM_CMD" ] && "$CM_CMD" --version >/dev/null 2>&1; then
        log "cm --version: $("$CM_CMD" --version 2>&1 | head -1)"
    else
        fail "'cm --version' failed"
        failed=1
    fi

    if [ -n "$CM_CMD" ] && "$CM_CMD" --help >/dev/null 2>&1; then
        log "cm --help works"
    else
        fail "'cm --help' failed"
        failed=1
    fi

    PYTHON_BIN="$VENV_DIR/bin/python"
    if [ ! -x "$PYTHON_BIN" ]; then
        PYTHON_BIN="python3"
    fi
    if "$PYTHON_BIN" -c "import cloudmesh, rich, paramiko, psutil, cryptography, Crypto, bcrypt" >/dev/null 2>&1; then
        log "all runtime dependencies import"
    else
        fail "one or more runtime dependencies are missing"
        failed=1
    fi

    if [ "$SKIP_NODE" != "1" ]; then
        if [ -f "$NODE_DIR/$NODE_SCRIPT" ] && [ -x "$NODE_DIR/start.sh" ] && [ -x "$NODE_DIR/stop.sh" ]; then
            log "node agent scripts present"
        else
            warn "node agent scripts missing"
        fi
    fi

    if [ "$failed" -ne 0 ]; then
        fail "install verification failed"
        return 1
    fi
    log "install verified"
    return 0
}

# ============================================
# SUMMARY
# ============================================
print_summary() {
    AUTH_KEY="$(cat "$NODE_DIR/.node_key" 2>/dev/null || echo "N/A")"
    IP_ADDRESS="$(ifconfig -a 2>/dev/null | awk '/inet /{print $2; exit}')"
    if [ -z "$IP_ADDRESS" ]; then
        IP_ADDRESS="YOUR_IP"
    fi
    if [ -z "$CM_CMD" ]; then
        CM_CMD="cm"
    fi

    banner "   CloudMesh Installed!"
    printf '\n'
    printf '%s\n' "  [OK] Python:   $(python3 --version 2>&1)"
    printf '%s\n' "  [OK] System:   $OS_TYPE $(uname -r)"
    printf '%s\n' "  [OK] Location: $INSTALL_DIR"
    printf '%s\n' "  [OK] Command:  $CM_CMD"
    printf '%s\n' "  [OK] Node:     $NODE_DIR (auth key $AUTH_KEY)"
    printf '\n'
    printf '%s\n' "  === Use CloudMesh ==="
    printf '%s\n' "  $CM_CMD --version"
    printf '%s\n' "  $CM_CMD --help"
    printf '\n'
    printf '%s\n' "  === Put cm on your PATH ==="
    printf '%s\n' "  export PATH=\"$VENV_DIR/bin:\$PATH\"    # add this to ~/.profile"
    printf '\n'
    printf '%s\n' "  === Add this node from your controller ==="
    printf '%s\n' "  cm node add -n $(hostname) -H $IP_ADDRESS -p 9999 -k $AUTH_KEY"
    printf '\n'
    printf '%s\n' "  === Auto-start the node on boot ==="
    case "$OS_TYPE" in
        FreeBSD)
            printf '%s\n' "  $PRIV sysrc cloudmesh_node_enable=YES"
            printf '%s\n' "  $PRIV service cloudmesh_node start"
            ;;
        OpenBSD)
            printf '%s\n' "  doas rcctl enable cloudmesh_node"
            printf '%s\n' "  doas rcctl start cloudmesh_node"
            ;;
        NetBSD)
            printf '%s\n' "  $PRIV sh -c 'echo cloudmesh_node=YES >> /etc/rc.conf'"
            printf '%s\n' "  $PRIV /etc/rc.d/cloudmesh_node start"
            ;;
    esac
    printf '\n'
}

# ============================================
# RUN
# ============================================
run_scripted() {
    if [ "$VERIFY_ONLY" = "1" ]; then
        verify_install
        return $?
    fi

    ensure_python || return 1
    fetch_payload || return 1
    install_project || return 1
    install_node_agent
    verify_install || return 1
    print_summary
    return 0
}

if [ "$NONINTERACTIVE" = "1" ] || [ "$VERIFY_ONLY" = "1" ]; then
    run_scripted
    exit $?
fi

banner "   CloudMesh Installer - $OS_TYPE"
printf '%s\n' "   This installs CloudMesh into $INSTALL_DIR"
printf '%s' "   Continue? [y/N]: "
REPLY=""
if read -r REPLY; then
    :
fi
case "$REPLY" in
    y|Y|yes|YES) ;;
    *)
        printf '%s\n' "Aborted."
        exit 0
        ;;
esac

run_scripted
exit $?

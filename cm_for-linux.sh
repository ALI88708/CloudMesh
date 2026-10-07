#!/bin/bash

# ============================================
# CloudMesh Installer - Linux
# Created by MRSX PRO
# ============================================

set -e

# ============================================
# NON-INTERACTIVE MODE
# ============================================
# The interactive menu below cannot be driven by CI, so this installer has a
# scripted path: `cm.sh --yes` (or CM_NONINTERACTIVE=1) runs the install with no
# prompts, no menus, and no pauses. CI uses it to prove a Linux install actually
# works end to end instead of only checking that the file downloads.
#
#   --yes / -y          install without prompting
#   --source=DIR        install from a local checkout instead of downloading
#   --skip-node         controller only; do not install the node agent
#   --skip-systemd      do not write or enable the systemd unit
#   --verify-only       do not install; assert the current install works
NONINTERACTIVE="${CM_NONINTERACTIVE:-0}"
SOURCE_DIR="${CM_SOURCE_DIR:-}"
SKIP_NODE="${CM_SKIP_NODE:-0}"
SKIP_SYSTEMD="${CM_SKIP_SYSTEMD:-0}"
VERIFY_ONLY="${CM_VERIFY_ONLY:-0}"

for arg in "$@"; do
    case "$arg" in
        -y|--yes)          NONINTERACTIVE=1 ;;
        --source=*)        SOURCE_DIR="${arg#--source=}" ;;
        --skip-node)       SKIP_NODE=1 ;;
        --skip-systemd)    SKIP_SYSTEMD=1 ;;
        --verify-only)     VERIFY_ONLY=1 ;;
        -h|--help)
            cat <<'USAGE'
CloudMesh Installer - Linux (MRSX PRO)

  cm.sh                      interactive menu
  cm.sh --yes                install with no prompts (used by CI)
  cm.sh --verify-only        assert the current install works

Options:
  -y, --yes              install without prompting
      --source=DIR        install from a local checkout instead of downloading
      --skip-node         controller only; do not install the node agent
      --skip-systemd      do not write or enable the systemd unit
      --verify-only       do not install; only run the checks
USAGE
            exit 0
            ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

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
# Where installs from before the project/ layout kept their state.
LEGACY_CLOUDMESH_DIR="$INSTALL_DIR/cloudmesh"
NODE_DIR="$HOME/.cloudmesh-node"
VENV_DIR="$INSTALL_DIR/venv"
NODE_SCRIPT="cloudmesh_node.py"

# ============================================
# COLORS
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# PROMPT HELPERS
# ============================================
# ask PROMPT DEFAULT VARNAME
# In interactive mode this reads a line into VARNAME, falling back to DEFAULT
# on an empty answer. In non-interactive mode DEFAULT is used without reading,
# so no `set -e` trap and no hang on a closed stdin.
ask() {
    local prompt="$1" default="$2" varname="$3" reply=""
    if [ "$NONINTERACTIVE" != "1" ]; then
        read -r -p "$prompt" reply || reply=""
    fi
    [ -n "$reply" ] || reply="$default"
    eval "$varname=\$reply"
}

ui_clear() { clear 2>/dev/null || true; }
ui_pause() { ask "" "" _unused; }

log()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*" >&2; }

# ============================================
# STAGE THE PROJECT TREE
# ============================================
# pyproject.toml declares `packages = ["cloudmesh", ...]`, so the directory we
# hand to pip has to CONTAIN the cloudmesh/ package. Laying the package out at
# the install root instead would install nothing and leave no `cm` script.
# PROJECT_DIR is that root; CLOUDMESH_DIR points inside it so the existing
# file references keep working.
stage_payload() {
    local src_root="$1"
    rm -rf "$PROJECT_DIR"
    mkdir -p "$PROJECT_DIR"
    cp -r "$src_root/cloudmesh" "$PROJECT_DIR/cloudmesh"
    local extra
    for extra in pyproject.toml README.md License; do
        [ -f "$src_root/$extra" ] && cp "$src_root/$extra" "$PROJECT_DIR/"
    done
    if [ ! -f "$PROJECT_DIR/pyproject.toml" ]; then
        fail "pyproject.toml missing from $src_root; cannot build an installable project"
        return 1
    fi
    return 0
}

# ============================================
# GIT
# ============================================
# `cm update` is git-based (fetch + pull), and pushing your own work needs git
# too. Nothing used to check for it, so a user could install CloudMesh, read
# "cm update (recommended)" in the README, and only find out at the worst moment.
check_git() {
    if command -v git > /dev/null 2>&1; then
        log "Git found: $(git --version 2>/dev/null || echo present)"
        GIT_AVAILABLE=1
        return 0
    fi

    GIT_AVAILABLE=0
    warn "Git not found. Without it, 'cm update' cannot pull, and git push will not work."

    ask "   Install Git now? (y/n): " "n" INSTALL_GIT
    if [ "$INSTALL_GIT" != "y" ] && [ "$INSTALL_GIT" != "Y" ]; then
        warn "Skipping Git. CloudMesh still works; 'cm update' will need 'pip install --upgrade cloudmesh' instead."
        return 0
    fi

    if command -v apt-get > /dev/null 2>&1; then
        sudo apt-get update -qq && sudo apt-get install -y -qq git
    elif command -v yum > /dev/null 2>&1; then
        sudo yum install -y git
    elif command -v dnf > /dev/null 2>&1; then
        sudo dnf install -y git
    elif command -v pacman > /dev/null 2>&1; then
        sudo pacman -Sy --noconfirm git
    elif command -v zypper > /dev/null 2>&1; then
        sudo zypper install -y git
    elif command -v apk > /dev/null 2>&1; then
        sudo apk add --no-cache git
    elif command -v brew > /dev/null 2>&1; then
        brew install git
    else
        warn "Cannot detect a package manager. Install Git manually: https://git-scm.com/downloads"
        return 0
    fi

    if command -v git > /dev/null 2>&1; then
        log "Git installed: $(git --version 2>/dev/null || echo present)"
        GIT_AVAILABLE=1
    else
        warn "Git install did not complete. 'cm update' will need pip instead."
    fi
}

# ============================================
# CHECK INSTALL STATUS
# ============================================
IS_INSTALLED=0
GIT_AVAILABLE=0
if [ -f "$CLOUDMESH_DIR/main.py" ] || [ -f "$LEGACY_CLOUDMESH_DIR/main.py" ]; then
    IS_INSTALLED=1
fi
if [ -d "$VENV_DIR" ]; then
    IS_INSTALLED=1
fi
if command -v git > /dev/null 2>&1; then
    GIT_AVAILABLE=1
fi

# ============================================
# DOWNLOAD FUNCTION
# ============================================
fetch_payload() {
    # Prefer a local checkout so CI verifies the branch under test rather than
    # whatever happens to be on main.
    if [ -n "$SOURCE_DIR" ]; then
        if [ ! -d "$SOURCE_DIR/cloudmesh" ]; then
            fail "--source=$SOURCE_DIR has no cloudmesh/ directory"
            return 1
        fi
        stage_payload "$SOURCE_DIR"
        log "Copied source from $SOURCE_DIR"
        return 0
    fi

    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Downloading from GitHub...${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""

    echo "[1/2] Downloading ZIP..."
    ZIP_URL="https://github.com/$GITHUB_USER/$GITHUB_REPO/archive/refs/heads/$GITHUB_BRANCH.zip"
    ZIP_FILE="$(mktemp -t cloudmesh.XXXXXX.zip)"
    EXTRACT_DIR="$(mktemp -d -t cloudmesh_extract.XXXXXX)"

    if command -v curl &> /dev/null; then
        curl -L --connect-timeout 10 --retry 3 -s -o "$ZIP_FILE" "$ZIP_URL"
    elif command -v wget &> /dev/null; then
        wget -q --timeout=10 --tries=3 "$ZIP_URL" -O "$ZIP_FILE"
    else
        echo -e "${RED}[ERROR] Neither curl nor wget found!${NC}"
        echo "[INFO] Install with: sudo apt install curl"
        return 1
    fi

    if [ ! -f "$ZIP_FILE" ] || [ ! -s "$ZIP_FILE" ]; then
        echo -e "${RED}[ERROR] Download failed! Check your internet connection.${NC}"
        return 1
    fi

    echo "[2/2] Extracting files..."
    rm -rf "$EXTRACT_DIR"
    unzip -q -o "$ZIP_FILE" -d "$EXTRACT_DIR" 2>/dev/null

    EXTRACTED=$(find "$EXTRACT_DIR" -maxdepth 1 -type d -name "CloudMesh*" | head -1)

    if [ -z "$EXTRACTED" ]; then
        echo -e "${RED}[ERROR] Extract failed!${NC}"
        rm -rf "$EXTRACT_DIR" "$ZIP_FILE"
        return 1
    fi

    stage_payload "$EXTRACTED"
    rm -rf "$EXTRACT_DIR"
    rm -f "$ZIP_FILE"

    if [ ! -f "$CLOUDMESH_DIR/main.py" ]; then
        echo -e "${RED}[ERROR] Download failed!${NC}"
        return 1
    fi

    echo -e "${GREEN}[OK] Download complete!${NC}"
    echo ""
    return 0
}

# ============================================
# VERIFY THE INSTALL ACTUALLY WORKS
# ============================================
# The installer used to report success the moment files landed on disk, so a
# broken dependency set or a missing console script looked like a clean
# install. CI calls this and a real user can run `cm.sh --verify-only`.
verify_install() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Verifying the install...${NC}"
    echo -e "${BLUE}============================================${NC}"
    local failed=0

    if [ ! -x "$VENV_DIR/bin/cm" ] && [ ! -x "$HOME/.local/bin/cm" ]; then
        fail "cm shortcut missing"
        failed=1
    else
        log "cm shortcut present"
    fi

    if [ "$GIT_AVAILABLE" = "1" ]; then
        log "git available"
    else
        warn "git not available; cm update will need pip"
    fi

    if ! "$VENV_DIR/bin/cm" --version >/dev/null 2>&1; then
        fail "'cm --version' failed"
        failed=1
    else
        log "cm --version: $("$VENV_DIR/bin/cm" --version 2>&1 | head -1)"
    fi

    if ! "$VENV_DIR/bin/cm" --help >/dev/null 2>&1; then
        fail "'cm --help' failed"
        failed=1
    else
        log "cm --help works"
    fi

    if ! "$VENV_DIR/bin/python" -c "import cloudmesh, rich, paramiko, psutil, cryptography, Crypto, bcrypt" >/dev/null 2>&1; then
        fail "one or more runtime dependencies are missing"
        failed=1
    else
        log "all runtime dependencies import"
    fi

    if [ "$SKIP_NODE" != "1" ]; then
        [ -f "$NODE_DIR/$NODE_SCRIPT" ] || { fail "node agent missing"; failed=1; }
        [ -x "$NODE_DIR/start.sh" ]  || { fail "node start.sh missing"; failed=1; }
        [ -x "$NODE_DIR/stop.sh" ]   || { fail "node stop.sh missing"; failed=1; }
        [ "$failed" -eq 0 ] && log "node agent scripts present"
    fi

    if [ "$failed" -ne 0 ]; then
        echo ""
        fail "install verification failed"
        return 1
    fi
    log "install verified"
    echo ""
    return 0
}

# ============================================
# UNINSTALL FUNCTION
# ============================================
do_uninstall() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Uninstalling CloudMesh...${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""

    [ -d "$CLOUDMESH_DIR" ] && rm -rf "$CLOUDMESH_DIR" && log "Removed program files"
    [ -d "$PROJECT_DIR" ] && rm -rf "$PROJECT_DIR" && log "Removed project directory"
    [ -d "$LEGACY_CLOUDMESH_DIR" ] && rm -rf "$LEGACY_CLOUDMESH_DIR" && log "Removed legacy program files"
    [ -d "$NODE_DIR" ] && rm -rf "$NODE_DIR" && log "Removed node agent"
    [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR" && log "Removed virtual environment"

    if command -v systemctl &> /dev/null; then
        sudo systemctl stop cloudmesh-node 2>/dev/null || true
        sudo systemctl disable cloudmesh-node 2>/dev/null || true
        sudo rm -f /etc/systemd/system/cloudmesh-node.service
        sudo systemctl daemon-reload 2>/dev/null || true
        echo -e "${GREEN}[OK] Removed systemd service${NC}"
    fi

    CM_BIN="$HOME/.local/bin/cm"
    [ -f "$CM_BIN" ] && rm -f "$CM_BIN" && echo -e "${GREEN}[OK] Removed cm shortcut${NC}"

    rm -f /tmp/cloudmesh.zip /tmp/cm_*.sh 2>/dev/null || true

    echo ""
    echo -e "${GREEN}[OK] CloudMesh has been uninstalled.${NC}"
    echo ""
}

# ============================================
# SETUP FUNCTION
# ============================================
do_setup() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Setting up CloudMesh...${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""

    echo "[0/6] Checking for Git..."
    check_git
    echo ""

    # Check Python
    echo "[1/6] Checking Python..."

    install_python() {
        echo -e "${YELLOW}[INFO] Python3 not found. Installing...${NC}"
        if command -v apt &> /dev/null; then
            sudo apt update -qq
            sudo apt install -y -qq python3 python3-pip python3-venv
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3 python3-pip
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y python3 python3-pip
        elif command -v pacman &> /dev/null; then
            sudo pacman -Sy --noconfirm python python-pip
        elif command -v zypper &> /dev/null; then
            sudo zypper install -y python3 python3-pip
        elif command -v apk &> /dev/null; then
            sudo apk add --no-cache python3 py3-pip
        else
            echo -e "${RED}[ERROR] Cannot detect package manager.${NC}"
            echo "[INFO] Install Python3 manually"
            return 1
        fi
    }

    if command -v python3 &> /dev/null; then
        PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}[OK] Python3 found: $PY_VERSION${NC}"
    elif command -v python &> /dev/null; then
        PY_VERSION=$(python --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}[OK] Python found: $PY_VERSION${NC}"
        if ! command -v python3 &> /dev/null; then
            PYTHON_PATH=$(which python)
            sudo ln -sf "$PYTHON_PATH" /usr/local/bin/python3 2>/dev/null || true
        fi
    else
        install_python
        if ! command -v python3 &> /dev/null; then
            echo -e "${RED}[ERROR] Python installation failed.${NC}"
            return 1
        fi
        PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}[OK] Python3 installed: $PY_VERSION${NC}"
    fi

    echo "[2/6] Installing dependencies..."
    # psutil only: the venv below owns the full dependency set.
    python3 -m pip install --user psutil 2>/dev/null || true
    log "Bootstrap dependencies installed"

    echo "[3/6] Creating node directory..."
    if [ "$SKIP_NODE" = "1" ]; then
        warn "skipping node directory (--skip-node)"
    else
        mkdir -p "$NODE_DIR" "$NODE_DIR/logs" "$NODE_DIR/data"
    fi

    echo "[4/6] Installing node agent..."
    NODE_SOURCE="$CLOUDMESH_DIR/node/$NODE_SCRIPT"
    if [ "$SKIP_NODE" = "1" ]; then
        warn "skipping node agent (--skip-node)"
        do_controller_setup
        return
    fi
    if [ -f "$NODE_SOURCE" ]; then
        cp "$NODE_SOURCE" "$NODE_DIR/$NODE_SCRIPT"
        chmod +x "$NODE_DIR/$NODE_SCRIPT"
        log "Node agent installed"
    else
        warn "cloudmesh_node.py not found, skipping node"
        echo ""
        do_controller_setup
        return
    fi

    echo "[5/6] Generating TLS certificate..."
    TLS_CERT="$NODE_DIR/cert.pem"
    TLS_KEY="$NODE_DIR/key.pem"
    if [ ! -f "$TLS_CERT" ]; then
        if command -v openssl &> /dev/null; then
            openssl req -x509 -newkey rsa:2048 -nodes \
                -keyout "$TLS_KEY" -out "$TLS_CERT" \
                -days 3650 -subj "/CN=cloudmesh-node-$(hostname)" 2>/dev/null
            echo -e "${GREEN}[OK] TLS certificate generated (10 years)${NC}"
        else
            echo -e "${YELLOW}[WARNING] openssl not found, running without TLS${NC}"
            TLS_CERT=""
            TLS_KEY=""
        fi
    else
        echo -e "${GREEN}[OK] TLS certificate exists${NC}"
    fi

    echo "[6/6] Creating node scripts..."

    cat > "$NODE_DIR/start.sh" << SEOF
#!/bin/bash
cd "\$(dirname "\$0")"
BIND_HOST="127.0.0.1"
for arg in "\$@"; do
    case "\$arg" in
        --bind=*) BIND_HOST="\${arg#--bind=}" ;;
        --bind) shift; BIND_HOST="\$1"; shift ;;
    esac
done
TLS_ARGS=""
if [ -f "$TLS_CERT" ] && [ -f "$TLS_KEY" ]; then
    TLS_ARGS="--tls-cert $TLS_CERT --tls-key $TLS_KEY"
fi
python3 cloudmesh_node.py start --bind "\$BIND_HOST" \$TLS_ARGS "\$@"
SEOF
    chmod +x "$NODE_DIR/start.sh"

    cat > "$NODE_DIR/stop.sh" << 'SEOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cloudmesh_node.py stop
SEOF
    chmod +x "$NODE_DIR/stop.sh"

    cat > "$NODE_DIR/status.sh" << 'SEOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cloudmesh_node.py status
SEOF
    chmod +x "$NODE_DIR/status.sh"

    if command -v systemctl &> /dev/null && [ "$SKIP_SYSTEMD" != "1" ]; then
        TLS_CERT_FLAG=""
        TLS_KEY_FLAG=""
        if [ -f "$NODE_DIR/cert.pem" ] && [ -f "$NODE_DIR/key.pem" ]; then
            TLS_CERT_FLAG="--tls-cert $NODE_DIR/cert.pem"
            TLS_KEY_FLAG="--tls-key $NODE_DIR/key.pem"
        fi
        if [ "$(id -u)" -ne 0 ]; then
            sudo tee /etc/systemd/system/cloudmesh-node.service > /dev/null << SERVICEEOF
[Unit]
Description=CloudMesh Node Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$NODE_DIR
ExecStart=$(which python3) $NODE_DIR/$NODE_SCRIPT start --bind 127.0.0.1 $TLS_CERT_FLAG $TLS_KEY_FLAG
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF
        else
            # Already root: no sudo in CI containers and no password prompt.
            cat > /etc/systemd/system/cloudmesh-node.service << SERVICEEOF
[Unit]
Description=CloudMesh Node Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$NODE_DIR
ExecStart=$(which python3) $NODE_DIR/$NODE_SCRIPT start --bind 127.0.0.1 $TLS_CERT_FLAG $TLS_KEY_FLAG
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF
        fi
        sudo systemctl daemon-reload 2>/dev/null || systemctl daemon-reload 2>/dev/null || true
        log "Systemd service created (binds to 127.0.0.1)"
    elif [ "$SKIP_SYSTEMD" = "1" ]; then
        warn "skipping systemd unit (--skip-systemd)"
    fi

    log "Node scripts created"

    echo "[6/6] Node setup complete!"
    echo ""
    AUTH_KEY=$(cat "$NODE_DIR/.node_key" 2>/dev/null || echo "N/A")
    IP_ADDRESS=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_IP")

    log "Node Location: $NODE_DIR"
    log "Auth Key: $AUTH_KEY"
    if [ -f "$NODE_DIR/cert.pem" ]; then
        log "TLS: enabled"
    else
        warn "TLS: disabled (no openssl)"
    fi
    log "Bind: 127.0.0.1 (local only)"
    echo ""
    echo "  === Add from Controller ==="
    echo "  cm node add -n $(hostname) -H $IP_ADDRESS -p 9999 -k $AUTH_KEY"
    echo ""

    # Default 'n' so a scripted install does not leave a daemon running.
    ask "   Start node now? (y/n): " "n" START_NODE
    if [ "$START_NODE" = "y" ] || [ "$START_NODE" = "Y" ]; then
        bash "$NODE_DIR/start.sh"
    fi
    echo ""

    do_controller_setup
}

# ============================================
# CONTROLLER SETUP
# ============================================
do_controller_setup() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Controller Setup Complete!${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""

    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        log "Virtual environment created"
    else
        log "Virtual environment exists"
    fi

    # Install the project, not a list of dependencies. requirements.txt pins
    # exact versions and pulls in pytest, which is not what a user wants on
    # their machine; `pip install .` also creates the real `cm` console script.
    echo "Installing CloudMesh..."
    "$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
    "$VENV_DIR/bin/python" -m pip install --quiet "$PROJECT_DIR"
    log "Environment ready"
    echo ""

    echo "Creating cm shortcut..."
    CM_BIN="$HOME/.local/bin/cm"
    mkdir -p "$HOME/.local/bin"

    cat > "$CM_BIN" << CMEOF
#!/bin/bash
# Prefer the console script pip created; fall back to the source tree so a
# source install still works after the venv is rebuilt by hand.
VENV_CM="$VENV_DIR/bin/cm"
CLOUDMESH_DIR="$CLOUDMESH_DIR"
if [ -x "\$VENV_CM" ]; then
    exec "\$VENV_CM" "\$@"
fi
if [ ! -f "\$CLOUDMESH_DIR/main.py" ]; then
    echo "[ERROR] CloudMesh not found at \$CLOUDMESH_DIR. Reinstall with cm.sh --yes"
    exit 1
fi
exec "$VENV_DIR/bin/python" "\$CLOUDMESH_DIR/main.py" "\$@"
CMEOF
    chmod +x "$CM_BIN"

    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        export PATH="$HOME/.local/bin:$PATH"
        log "Added ~/.local/bin to PATH"
    fi

    log "cm command available"
    echo ""
}

# ============================================
# SCRIPTED PATH
# ============================================
# Runs the install with no prompts and then asserts the result works. CI calls
# this; `cm.sh --verify-only` re-runs just the assertions against an existing
# install.
run_scripted() {
    if [ "$VERIFY_ONLY" = "1" ]; then
        verify_install
        return $?
    fi

    if [ "$IS_INSTALLED" -eq 1 ]; then
        warn "CloudMesh is already installed; reinstalling"
        [ -d "$CLOUDMESH_DIR" ] && rm -rf "$CLOUDMESH_DIR"
        [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"
    fi

    fetch_payload || return 1
    do_setup || return 1
    verify_install
}

# ============================================
# MAIN MENU
# ============================================
if [ "$NONINTERACTIVE" = "1" ]; then
    run_scripted
    exit $?
fi

while true; do
    ui_clear
    echo ""
    echo -e "${BLUE}+==========================================+${NC}"
    echo -e "${BLUE}|        CloudMesh Installer v2.0          |${NC}"
    echo -e "${BLUE}|            Created by MRSX PRO           |${NC}"
    echo -e "${BLUE}+==========================================+${NC}"
    echo ""

    if [ "$IS_INSTALLED" -eq 1 ]; then
        echo -e "   ${GREEN}[OK] CloudMesh is already installed${NC}"
        echo ""
        echo "   [1] Update        - Keep data, get latest version"
        echo "   [2] Reinstall     - Delete everything, install fresh"
        echo "   [3] Uninstall     - Remove CloudMesh completely"
        echo ""
        ask "   Choose [1-3]: " "1" CHOICE

        case "$CHOICE" in
            1)
                echo ""
                echo -e "${BLUE}============================================${NC}"
                echo -e "${BLUE}   Updating CloudMesh...${NC}"
                echo -e "${BLUE}============================================${NC}"
                echo ""

                BACKUP_DIR="$(mktemp -d -t cloudmesh_backup.XXXXXX)"
                # Look in the new layout and the legacy one. An install created
                # before PROJECT_DIR existed keeps its state in
                # $INSTALL_DIR/cloudmesh, and an update that only checked the
                # new path would silently drop the user's keys.
                saved=0
                for f in .node_keys.json .secret.key; do
                    for d in "$CLOUDMESH_DIR" "$LEGACY_CLOUDMESH_DIR"; do
                        if [ -f "$d/$f" ]; then
                            cp -p "$d/$f" "$BACKUP_DIR/"
                            saved=$((saved + 1))
                            break
                        fi
                    done
                done
                [ "$saved" -gt 0 ] && log "Backed up $saved state file(s)"
                [ -f "$INSTALL_DIR/cloudmesh.json" ] && cp -p "$INSTALL_DIR/cloudmesh.json" "$BACKUP_DIR/"

                fetch_payload || { rm -rf "$BACKUP_DIR"; ui_pause; continue; }

                # fetch_payload replaces the whole project dir, so put the
                # state back. Restoring .secret.key matters most: without it
                # every Fernet-encrypted password and node key is unreadable.
                for f in .node_keys.json .secret.key; do
                    [ -f "$BACKUP_DIR/$f" ] && cp -p "$BACKUP_DIR/$f" "$CLOUDMESH_DIR/" 2>/dev/null
                done
                [ -f "$BACKUP_DIR/cloudmesh.json" ] && cp -p "$BACKUP_DIR/cloudmesh.json" "$INSTALL_DIR/" 2>/dev/null
                rm -rf "$BACKUP_DIR"
                # The old tree is now redundant; leaving it would confuse
                # do_uninstall and keep stale secrets on disk.
                rm -rf "$LEGACY_CLOUDMESH_DIR"
                log "Config restored"

                do_setup
                echo -e "${GREEN}[OK] Update complete!${NC}"
                echo ""
                ui_pause
                ;;
            2)
                echo ""
                echo -e "${YELLOW}[WARNING] This will delete ALL data!${NC}"
                ask "   Are you sure? (y/n): " "n" CONFIRM
                if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
                    echo ""
                    echo "Removing old installation..."
                    [ -d "$CLOUDMESH_DIR" ] && rm -rf "$CLOUDMESH_DIR"
                    [ -d "$NODE_DIR" ] && rm -rf "$NODE_DIR"
                    [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"
                    echo -e "${GREEN}[OK] Old files removed${NC}"
                    echo ""

                    fetch_payload || { ui_pause; continue; }
                    do_setup
                    IS_INSTALLED=1
                    echo ""
                    echo -e "${GREEN}+==========================================+${NC}"
                    echo -e "${GREEN}|    CloudMesh Installed Successfully!     |${NC}"
                    echo -e "${GREEN}+==========================================+${NC}"
                    echo ""
                    echo "  Quick Start:"
                    echo "  cm --help              Show all commands"
                    echo "  cm interactive         Interactive TUI"
                    echo "  cm version             Show version"
                    echo "  cm ping                Test connections"
                    echo "  cm discover 192.168.1  Scan network"
                    echo "  cm bench               Benchmark"
                    echo ""
                fi
                ui_pause
                ;;
            3)
                do_uninstall
                IS_INSTALLED=0
                ui_pause
                ;;
            *)
                echo -e "${RED}[ERROR] Invalid choice!${NC}"
                ui_pause
                ;;
        esac
    else
        echo -e "   ${YELLOW}[!] CloudMesh is NOT installed${NC}"
        echo ""
        echo "   [1] Install CloudMesh"
        echo "   [2] Exit"
        echo ""
        ask "   Choose [1-2]: " "1" CHOICE

        case "$CHOICE" in
            1)
                fetch_payload || { ui_pause; continue; }
                do_setup
                IS_INSTALLED=1
                echo ""
                echo -e "${GREEN}+==========================================+${NC}"
                echo -e "${GREEN}|    CloudMesh Installed Successfully!     |${NC}"
                echo -e "${GREEN}+==========================================+${NC}"
                echo ""
                echo "  Quick Start:"
                echo "  cm --help              Show all commands"
                echo "  cm interactive         Interactive TUI"
                echo "  cm version             Show version"
                echo "  cm ping                Test connections"
                echo "  cm discover 192.168.1  Scan network"
                echo "  cm bench               Benchmark"
                echo ""
                ui_pause
                ;;
            2)
                echo ""
                echo -e "${BLUE}Goodbye!${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo -e "${RED}[ERROR] Invalid choice!${NC}"
                ui_pause
                ;;
        esac
    fi
done

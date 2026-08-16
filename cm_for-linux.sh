#!/bin/bash
echo "============================================"
echo "   CloudMesh Installer (Auto-Download)"
echo "============================================"
echo ""

# ============================================
# CONFIG - CHANGE THIS TO YOUR GITHUB REPO
# ============================================
GITHUB_USER="your-username"
GITHUB_REPO="CloudMesh"
GITHUB_BRANCH="main"

# ============================================
# PATHS
# ============================================
INSTALL_DIR="$HOME/.cloudmesh"
CLOUDMESH_DIR="$INSTALL_DIR/cloudmesh"
NODE_DIR="$HOME/.cloudmesh-node"
VENV_DIR="$INSTALL_DIR/venv"
NODE_SCRIPT="cloudmesh_node.py"

# ============================================
# STEP 1: Check if cloudmesh folder exists locally
# ============================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_SOURCE="$SCRIPT_DIR/cloudmesh"
USE_LOCAL=0

if [ -f "$LOCAL_SOURCE/main.py" ]; then
    echo "[OK] Found local cloudmesh folder"
    USE_LOCAL=1
    CLOUDMESH_DIR="$LOCAL_SOURCE"
else
    echo "[INFO] Local cloudmesh folder not found"
    echo "[INFO] Will download from GitHub..."
    echo ""
fi

# ============================================
# STEP 2: Download from GitHub if needed
# ============================================
if [ "$USE_LOCAL" -eq 0 ]; then
    echo "[INFO] Downloading CloudMesh from GitHub..."
    echo ""

    # Create install directory
    mkdir -p "$CLOUDMESH_DIR"
    mkdir -p "$CLOUDMESH_DIR/core"
    mkdir -p "$CLOUDMESH_DIR/node"

    # Check for curl or wget
    if command -v curl &> /dev/null; then
        DOWNLOADER="curl"
    elif command -v wget &> /dev/null; then
        DOWNLOADER="wget"
    else
        echo "[ERROR] Neither curl nor wget found!"
        echo "[INFO] Install with: sudo apt install curl"
        exit 1
    fi

    BASE_URL="https://raw.githubusercontent.com/$GITHUB_USER/$GITHUB_REPO/$GITHUB_BRANCH"

    download_file() {
        local url="$1"
        local dest="$2"
        if [ "$DOWNLOADER" = "curl" ]; then
            curl -sL "$url" -o "$dest"
        else
            wget -q "$url" -O "$dest"
        fi
    }

    echo "[1/12] Downloading main.py..."
    download_file "$BASE_URL/cloudmesh/main.py" "$CLOUDMESH_DIR/main.py"

    echo "[2/12] Downloading requirements.txt..."
    download_file "$BASE_URL/requirements.txt" "$CLOUDMESH_DIR/requirements.txt"

    echo "[3/12] Downloading core/features.py..."
    download_file "$BASE_URL/cloudmesh/core/features.py" "$CLOUDMESH_DIR/core/features.py"

    echo "[4/12] Downloading core/advanced.py..."
    download_file "$BASE_URL/cloudmesh/core/advanced.py" "$CLOUDMESH_DIR/core/advanced.py"

    echo "[5/12] Downloading core/server.py..."
    download_file "$BASE_URL/cloudmesh/core/server.py" "$CLOUDMESH_DIR/core/server.py"

    echo "[6/12] Downloading core/monitor.py..."
    download_file "$BASE_URL/cloudmesh/core/monitor.py" "$CLOUDMESH_DIR/core/monitor.py"

    echo "[7/12] Downloading core/scheduler.py..."
    download_file "$BASE_URL/cloudmesh/core/scheduler.py" "$CLOUDMESH_DIR/core/scheduler.py"

    echo "[8/12] Downloading core/node_client.py..."
    download_file "$BASE_URL/cloudmesh/core/node_client.py" "$CLOUDMESH_DIR/core/node_client.py"

    echo "[9/12] Downloading core/gpu.py..."
    download_file "$BASE_URL/cloudmesh/core/gpu.py" "$CLOUDMESH_DIR/core/gpu.py"

    echo "[10/12] Downloading core/jobs.py..."
    download_file "$BASE_URL/cloudmesh/core/jobs.py" "$CLOUDMESH_DIR/core/jobs.py"

    echo "[11/12] Downloading remaining core files..."
    for f in security sync deploy alerts groups dashboard tui service history cmdlog; do
        download_file "$BASE_URL/cloudmesh/core/$f.py" "$CLOUDMESH_DIR/core/$f.py" 2>/dev/null
    done

    echo "[12/12] Downloading node agent..."
    download_file "$BASE_URL/cloudmesh/node/cloudmesh_node.py" "$CLOUDMESH_DIR/node/$NODE_SCRIPT"
    download_file "$BASE_URL/cloudmesh/node/node-install.sh" "$CLOUDMESH_DIR/node/node-install.sh" 2>/dev/null

    # Create __init__.py
    touch "$CLOUDMESH_DIR/core/__init__.py"

    # Verify download
    if [ ! -f "$CLOUDMESH_DIR/main.py" ]; then
        echo "[ERROR] Download failed!"
        echo "[INFO] Check your internet connection."
        exit 1
    fi

    echo "[OK] Download complete!"
    echo ""
fi

# ============================================
# STEP 3: Node Agent Installation
# ============================================
echo "============================================"
echo "   Installing CloudMesh Node..."
echo "============================================"
echo ""

# --- Check Python ---
echo "[1/6] Checking Python..."

install_python() {
    echo "[INFO] Python3 not found. Installing..."
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
        echo "[ERROR] Cannot detect package manager."
        exit 1
    fi
}

if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "[OK] Python3 found: $PY_VERSION"
else
    install_python
    if ! command -v python3 &> /dev/null; then
        echo "[ERROR] Python installation failed."
        exit 1
    fi
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "[OK] Python3 installed: $PY_VERSION"
fi

# --- Install psutil ---
echo "[2/6] Installing node dependencies..."
python3 -m pip install --user psutil 2>/dev/null || true
echo "[OK] Dependencies installed"

# --- Create node directory ---
echo "[3/6] Creating node directory..."
mkdir -p "$NODE_DIR"
mkdir -p "$NODE_DIR/logs"
mkdir -p "$NODE_DIR/data"

# --- Install node agent ---
echo "[4/6] Installing CloudMesh Node agent..."
NODE_SOURCE="$CLOUDMESH_DIR/node/$NODE_SCRIPT"
if [ -f "$NODE_SOURCE" ]; then
    cp "$NODE_SOURCE" "$NODE_DIR/$NODE_SCRIPT"
else
    echo "[ERROR] cloudmesh_node.py not found"
    exit 1
fi
chmod +x "$NODE_DIR/$NODE_SCRIPT"
echo "[OK] Node agent installed"

# --- Create node helper scripts ---
echo "[5/6] Creating node scripts..."

cat > "$NODE_DIR/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cloudmesh_node.py start "$@"
EOF
chmod +x "$NODE_DIR/start.sh"

cat > "$NODE_DIR/stop.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cloudmesh_node.py stop
EOF
chmod +x "$NODE_DIR/stop.sh"

cat > "$NODE_DIR/status.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cloudmesh_node.py status
EOF
chmod +x "$NODE_DIR/status.sh"

# Systemd service
if command -v systemctl &> /dev/null; then
    sudo tee /etc/systemd/system/cloudmesh-node.service > /dev/null << SERVICEEOF
[Unit]
Description=CloudMesh Node
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$NODE_DIR
ExecStart=$(which python3) $NODE_DIR/$NODE_SCRIPT start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF
    sudo systemctl daemon-reload
    echo "[OK] Systemd service created"
fi

echo "[OK] Node scripts created"

# --- Print node info ---
echo "[6/6] Node setup complete!"
echo ""
AUTH_KEY=$(cat "$NODE_DIR/.node_key" 2>/dev/null || echo "N/A")
IP_ADDRESS=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_IP")

echo "  [OK] Node Location: $NODE_DIR"
echo "  [OK] Auth Key: $AUTH_KEY"
echo ""
echo "  === Add from Controller ==="
echo "  cm node add -n $(hostname) -H $IP_ADDRESS -p 9999 -k $AUTH_KEY"
echo ""

# Ask to start node now
read -p "Start node now? (y/n): " START_NODE
if [ "$START_NODE" = "y" ] || [ "$START_NODE" = "Y" ]; then
    bash "$NODE_DIR/start.sh"
fi
echo ""

# ============================================
# STEP 4: Controller Setup
# ============================================
echo "============================================"
echo "   CloudMesh Controller Setup"
echo "============================================"
echo ""

# Create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install -q -r "$CLOUDMESH_DIR/requirements.txt"
    echo "[OK] Environment ready!"
else
    source "$VENV_DIR/bin/activate"
    echo "[OK] Virtual environment exists"
fi
echo ""

# ============================================
# STEP 5: Create cm shortcut
# ============================================
echo "[INFO] Creating cm shortcut..."

CM_BIN="$HOME/.local/bin/cm"
mkdir -p "$HOME/.local/bin"

cat > "$CM_BIN" << CMEOF
#!/bin/bash
VENV_PYTHON="$VENV_DIR/bin/python"
CLOUDMESH_DIR="$CLOUDMESH_DIR"
if [ ! -f "\$VENV_PYTHON" ]; then
    echo "[ERROR] Virtual environment not found"
    exit 1
fi
"\$VENV_PYTHON" "\$CLOUDMESH_DIR/main.py" "\$@"
CMEOF
chmod +x "$CM_BIN"

# Add to PATH if not already
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    export PATH="$HOME/.local/bin:$PATH"
    echo "[OK] Added ~/.local/bin to PATH"
fi

echo "[OK] cm command available!"
echo ""

# ============================================
# DONE
# ============================================
echo "============================================"
echo "   CloudMesh Installed Successfully!"
echo "============================================"
echo ""
echo "=== Quick Start ==="
echo "  cm --help           # Show all commands"
echo "  cm interactive      # Interactive TUI"
echo "  cm version          # Show version"
echo "  cm ping             # Test connections"
echo "  cm discover 192.168.1  # Scan network"
echo "  cm bench            # Benchmark"
echo ""
echo "=== Node Commands ==="
echo "  Start:    $NODE_DIR/start.sh"
echo "  Status:   $NODE_DIR/status.sh"
echo "  Stop:     $NODE_DIR/stop.sh"
echo ""
echo "=== Files Installed ==="
echo "  Program:  $CLOUDMESH_DIR"
echo "  Node:     $NODE_DIR"
echo "  Shortcut: $CM_BIN"
echo ""
echo "Usage: cm [command] [options]"
echo ""

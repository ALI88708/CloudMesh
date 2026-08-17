#!/bin/bash
echo "============================================"
echo "   CloudMesh Installer (Auto-Download)"
echo "============================================"
echo ""

# ============================================
# CONFIG - CHANGE THIS TO YOUR GITHUB REPO
# ============================================
GITHUB_USER="MrAli88708"
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

    mkdir -p "$CLOUDMESH_DIR"

    echo "[1/2] Downloading ZIP from GitHub..."
    ZIP_URL="https://github.com/$GITHUB_USER/$GITHUB_REPO/archive/refs/heads/$GITHUB_BRANCH.zip"
    ZIP_FILE="/tmp/cloudmesh.zip"
    EXTRACT_DIR="/tmp/cloudmesh_extract"

    if command -v curl &> /dev/null; then
        curl -L --connect-timeout 10 --retry 3 -s -o "$ZIP_FILE" "$ZIP_URL"
    elif command -v wget &> /dev/null; then
        wget -q --timeout=10 --tries=3 "$ZIP_URL" -O "$ZIP_FILE"
    else
        echo "[ERROR] Neither curl nor wget found!"
        echo "[INFO] Install with: sudo apt install curl"
        exit 1
    fi

    if [ ! -f "$ZIP_FILE" ] || [ ! -s "$ZIP_FILE" ]; then
        echo "[ERROR] Download failed! Check your internet connection."
        exit 1
    fi

    echo "[2/2] Extracting files..."
    rm -rf "$EXTRACT_DIR"
    unzip -q -o "$ZIP_FILE" -d "$EXTRACT_DIR" 2>/dev/null

    # Find the extracted folder (CloudMesh-main or similar)
    EXTRACTED=$(find "$EXTRACT_DIR" -maxdepth 1 -type d -name "CloudMesh*" | head -1)

    if [ -z "$EXTRACTED" ]; then
        echo "[ERROR] Extract failed!"
        exit 1
    fi

    # Copy files
    rm -rf "$CLOUDMESH_DIR"
    cp -r "$EXTRACTED/cloudmesh" "$CLOUDMESH_DIR"

    # Cleanup
    rm -rf "$EXTRACT_DIR"
    rm -f "$ZIP_FILE"

    # Verify
    if [ ! -f "$CLOUDMESH_DIR/main.py" ]; then
        echo "[ERROR] Download failed!"
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
        echo "[INFO] Please install Python3 manually:"
        echo "  Ubuntu/Debian:  sudo apt install python3 python3-pip python3-venv"
        echo "  CentOS/RHEL:    sudo yum install python3 python3-pip"
        echo "  Arch:           sudo pacman -S python python-pip"
        exit 1
    fi
}

# Try multiple Python commands
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "[OK] Python3 found: $PY_VERSION"
elif command -v python &> /dev/null; then
    PY_VERSION=$(python --version 2>&1 | awk '{print $2}')
    echo "[OK] Python found: $PY_VERSION"
    # Create python3 alias if only python exists
    if ! command -v python3 &> /dev/null; then
        PYTHON_PATH=$(which python)
        sudo ln -sf "$PYTHON_PATH" /usr/local/bin/python3 2>/dev/null || true
    fi
elif command -v py &> /dev/null; then
    PY_VERSION=$(py --version 2>&1 | awk '{print $2}')
    echo "[OK] Python (py) found: $PY_VERSION"
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

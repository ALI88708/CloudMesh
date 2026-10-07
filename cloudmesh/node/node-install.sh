#!/bin/bash
echo "============================================"
echo "   CloudMesh Node Installer"
echo "============================================"
echo ""

INSTALL_DIR="$HOME/.cloudmesh-node"
NODE_SCRIPT="cloudmesh_node.py"

# ============================================
# 1. Detect and install Python
# ============================================
echo "[1/5] Checking Python..."

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
        echo "  Ubuntu/Debian:  sudo apt install python3 python3-pip"
        echo "  CentOS/RHEL:    sudo yum install python3 python3-pip"
        echo "  Arch:           sudo pacman -S python python-pip"
        echo "  Alpine:         sudo apk add python3 py3-pip"
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

# ============================================
# 2. Install psutil (no sudo needed)
# ============================================
echo "[2/5] Installing dependencies..."

python3 -m pip install --user psutil 2>/dev/null || true

python3 -c "import psutil" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[INFO] Trying with sudo..."
    sudo python3 -m pip install psutil 2>/dev/null || true
fi

python3 -c "import psutil" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "[OK] psutil installed"
else
    echo "[WARN] psutil not available, will use fallback metrics"
fi

# ============================================
# 3. Create install directory
# ============================================
echo "[3/5] Creating installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/data"

# ============================================
# 4. Install CloudMesh Node (COMPLETE)
# ============================================
echo "[4/5] Installing CloudMesh Node..."

# Copy standalone node agent (with GPU + async jobs)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_SOURCE="$SCRIPT_DIR/cloudmesh_node.py"
if [ ! -f "$NODE_SOURCE" ]; then
    echo "[ERROR] cloudmesh_node.py not found at $NODE_SOURCE"
    exit 1
fi
cp "$NODE_SOURCE" "$INSTALL_DIR/$NODE_SCRIPT"
chmod +x "$INSTALL_DIR/$NODE_SCRIPT"

# ============================================
# 5. Create helper scripts
# ============================================
echo "[5/5] Creating scripts..."

cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cloudmesh_node.py start "$@"
EOF
chmod +x "$INSTALL_DIR/start.sh"

cat > "$INSTALL_DIR/stop.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cloudmesh_node.py stop
EOF
chmod +x "$INSTALL_DIR/stop.sh"

cat > "$INSTALL_DIR/status.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cloudmesh_node.py status
EOF
chmod +x "$INSTALL_DIR/status.sh"

cat > "$INSTALL_DIR/restart.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./stop.sh
sleep 1
./start.sh
EOF
chmod +x "$INSTALL_DIR/restart.sh"

# Create systemd service
if command -v systemctl &> /dev/null; then
    sudo tee /etc/systemd/system/cloudmesh-node.service > /dev/null << SERVICEEOF
[Unit]
Description=CloudMesh Node
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$(which python3) $INSTALL_DIR/$NODE_SCRIPT start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF
    sudo systemctl daemon-reload
    echo "[OK] Systemd service created"
fi

# ============================================
# Done! Print info
# ============================================
AUTH_KEY=$(cat "$INSTALL_DIR/.node_key" 2>/dev/null || echo "N/A")
IP_ADDRESS=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_IP")

echo ""
echo "============================================"
echo "   CloudMesh Node Installed!"
echo "============================================"
echo ""
echo "  [OK] Python:   $(python3 --version 2>&1)"
echo "  [OK] Location: $INSTALL_DIR"
echo "  [OK] Auth Key: $AUTH_KEY"
echo ""
echo "  === Commands ==="
echo "  Start:    $INSTALL_DIR/start.sh"
echo "  Stop:     $INSTALL_DIR/stop.sh"
echo "  Status:   $INSTALL_DIR/status.sh"
echo "  Restart:  $INSTALL_DIR/restart.sh"
echo ""
echo "  === Auto-start on boot ==="
echo "  sudo systemctl enable cloudmesh-node"
echo "  sudo systemctl start cloudmesh-node"
echo ""
echo "  === Add from Controller (your laptop) ==="
echo "  cloudmesh node add -n $(hostname) -H $IP_ADDRESS -p 9999 -k $AUTH_KEY"
echo ""
echo "  === Test connection ==="
echo "  cloudmesh node test -n $(hostname)"
echo ""

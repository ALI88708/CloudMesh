#!/bin/bash

# ============================================
# CONFIG
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
# Check if already installed
# ============================================
IS_INSTALLED=0
if [ -f "$CLOUDMESH_DIR/main.py" ]; then
    IS_INSTALLED=1
fi

# ============================================
# DOWNLOAD FUNCTION
# ============================================
download_from_github() {
    echo "============================================"
    echo "   Downloading from GitHub..."
    echo "============================================"
    echo ""

    mkdir -p "$CLOUDMESH_DIR"

    echo "[1/2] Downloading ZIP..."
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
        return 1
    fi

    if [ ! -f "$ZIP_FILE" ] || [ ! -s "$ZIP_FILE" ]; then
        echo "[ERROR] Download failed! Check your internet connection."
        return 1
    fi

    echo "[2/2] Extracting files..."
    rm -rf "$EXTRACT_DIR"
    unzip -q -o "$ZIP_FILE" -d "$EXTRACT_DIR" 2>/dev/null

    EXTRACTED=$(find "$EXTRACT_DIR" -maxdepth 1 -type d -name "CloudMesh*" | head -1)

    if [ -z "$EXTRACTED" ]; then
        echo "[ERROR] Extract failed!"
        rm -rf "$EXTRACT_DIR" "$ZIP_FILE"
        return 1
    fi

    rm -rf "$CLOUDMESH_DIR"
    cp -r "$EXTRACTED/cloudmesh" "$CLOUDMESH_DIR"

    rm -rf "$EXTRACT_DIR"
    rm -f "$ZIP_FILE"

    if [ ! -f "$CLOUDMESH_DIR/main.py" ]; then
        echo "[ERROR] Download failed!"
        return 1
    fi

    echo "[OK] Download complete!"
    echo ""
    return 0
}

# ============================================
# UNINSTALL FUNCTION
# ============================================
do_uninstall() {
    echo "============================================"
    echo "   Uninstalling CloudMesh..."
    echo "============================================"
    echo ""

    [ -d "$CLOUDMESH_DIR" ] && rm -rf "$CLOUDMESH_DIR" && echo "[OK] Removed program files"
    [ -d "$NODE_DIR" ] && rm -rf "$NODE_DIR" && echo "[OK] Removed node agent"
    [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR" && echo "[OK] Removed virtual environment"

    if command -v systemctl &> /dev/null; then
        sudo systemctl stop cloudmesh-node 2>/dev/null
        sudo systemctl disable cloudmesh-node 2>/dev/null
        sudo rm -f /etc/systemd/system/cloudmesh-node.service
        sudo systemctl daemon-reload 2>/dev/null
        echo "[OK] Removed systemd service"
    fi

    CM_BIN="$HOME/.local/bin/cm"
    [ -f "$CM_BIN" ] && rm -f "$CM_BIN" && echo "[OK] Removed cm shortcut"

    rm -f /tmp/cloudmesh.zip /tmp/cm_*.sh 2>/dev/null

    echo ""
    echo "[OK] CloudMesh has been uninstalled."
    echo ""
}

# ============================================
# FULL SETUP FUNCTION
# ============================================
do_setup() {
    echo "============================================"
    echo "   Installing CloudMesh Node..."
    echo "============================================"
    echo ""

    # Check Python
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
            echo "[INFO] Install Python3 manually"
            return 1
        fi
    }

    if command -v python3 &> /dev/null; then
        PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo "[OK] Python3 found: $PY_VERSION"
    elif command -v python &> /dev/null; then
        PY_VERSION=$(python --version 2>&1 | awk '{print $2}')
        echo "[OK] Python found: $PY_VERSION"
        if ! command -v python3 &> /dev/null; then
            PYTHON_PATH=$(which python)
            sudo ln -sf "$PYTHON_PATH" /usr/local/bin/python3 2>/dev/null || true
        fi
    else
        install_python
        if ! command -v python3 &> /dev/null; then
            echo "[ERROR] Python installation failed."
            return 1
        fi
        PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo "[OK] Python3 installed: $PY_VERSION"
    fi

    echo "[2/6] Installing node dependencies..."
    python3 -m pip install --user psutil 2>/dev/null || true
    echo "[OK] Dependencies installed"

    echo "[3/6] Creating node directory..."
    mkdir -p "$NODE_DIR" "$NODE_DIR/logs" "$NODE_DIR/data"

    echo "[4/6] Installing CloudMesh Node agent..."
    NODE_SOURCE="$CLOUDMESH_DIR/node/$NODE_SCRIPT"
    if [ -f "$NODE_SOURCE" ]; then
        cp "$NODE_SOURCE" "$NODE_DIR/$NODE_SCRIPT"
        chmod +x "$NODE_DIR/$NODE_SCRIPT"
        echo "[OK] Node agent installed"
    else
        echo "[WARNING] cloudmesh_node.py not found, skipping node"
        echo ""
        do_controller_setup
        return
    fi

    echo "[5/6] Creating node scripts..."

    cat > "$NODE_DIR/start.sh" << 'SEOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 cloudmesh_node.py start "$@"
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

    read -p "Start node now? (y/n): " START_NODE
    if [ "$START_NODE" = "y" ] || [ "$START_NODE" = "Y" ]; then
        bash "$NODE_DIR/start.sh"
    fi
    echo ""

    do_controller_setup
}

do_controller_setup() {
    echo "============================================"
    echo "   CloudMesh Controller Setup"
    echo "============================================"
    echo ""

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

    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        export PATH="$HOME/.local/bin:$PATH"
        echo "[OK] Added ~/.local/bin to PATH"
    fi

    echo "[OK] cm command available!"
    echo ""
}

# ============================================
# MAIN MENU
# ============================================
while true; do
    clear
    echo "============================================"
    echo "   CloudMesh Installer"
    echo "============================================"
    echo ""

    if [ "$IS_INSTALLED" -eq 1 ]; then
        echo "   [CloudMesh is already installed]"
        echo ""
        echo "   [1] Fresh Install"
        echo "   [2] Update (keep config)"
        echo "   [3] Factory Reset"
        echo "   [4] Uninstall"
        echo "   [5] Exit"
        echo ""
        read -p "   Choose [1-5]: " CHOICE
    else
        echo "   [CloudMesh is NOT installed]"
        echo ""
        echo "   [1] Install CloudMesh"
        echo "   [2] Exit"
        echo ""
        read -p "   Choose [1-2]: " CHOICE
    fi
    echo ""

    if [ "$IS_INSTALLED" -eq 1 ]; then
        case "$CHOICE" in
            1)
                download_from_github || { read -p "Press Enter to continue..."; continue; }
                do_setup
                echo ""
                echo "============================================"
                echo "   CloudMesh Installed Successfully!"
                echo "============================================"
                echo ""
                echo "=== Quick Start ==="
                echo "  cm --help              # Show all commands"
                echo "  cm interactive         # Interactive TUI"
                echo "  cm version             # Show version"
                echo "  cm ping                # Test connections"
                echo "  cm discover 192.168.1  # Scan network"
                echo "  cm bench               # Benchmark"
                echo ""
                echo "Usage: cm [command] [options]"
                echo ""
                read -p "Press Enter to continue..."
                ;;
            2)
                echo "============================================"
                echo "   Updating CloudMesh..."
                echo "============================================"
                echo ""

                BACKUP_DIR="/tmp/cloudmesh_backup"
                mkdir -p "$BACKUP_DIR"
                [ -f "$CLOUDMESH_DIR/.node_keys.json" ] && cp "$CLOUDMESH_DIR/.node_keys.json" "$BACKUP_DIR/" && echo "[OK] Backed up node keys"
                [ -f "$INSTALL_DIR/cloudmesh.json" ] && cp "$INSTALL_DIR/cloudmesh.json" "$BACKUP_DIR/" && echo "[OK] Backed up server config"

                download_from_github || { read -p "Press Enter to continue..."; continue; }

                [ -f "$BACKUP_DIR/.node_keys.json" ] && cp "$BACKUP_DIR/.node_keys.json" "$CLOUDMESH_DIR/" 2>/dev/null
                [ -f "$BACKUP_DIR/cloudmesh.json" ] && cp "$BACKUP_DIR/cloudmesh.json" "$INSTALL_DIR/" 2>/dev/null
                rm -rf "$BACKUP_DIR"
                echo "[OK] Config restored"

                do_setup
                echo "[OK] Update complete!"
                echo ""
                read -p "Press Enter to continue..."
                ;;
            3)
                echo "[WARNING] This will delete ALL data!"
                read -p "Are you sure? (y/n): " CONFIRM
                if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
                    echo ""
                    echo "[INFO] Removing old installation..."
                    [ -d "$CLOUDMESH_DIR" ] && rm -rf "$CLOUDMESH_DIR"
                    [ -d "$NODE_DIR" ] && rm -rf "$NODE_DIR"
                    [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"
                    echo "[OK] Old files removed"
                    echo ""

                    download_from_github || { read -p "Press Enter to continue..."; continue; }
                    do_setup
                    echo "[OK] Factory Reset complete!"
                    echo ""
                fi
                read -p "Press Enter to continue..."
                ;;
            4)
                do_uninstall
                IS_INSTALLED=0
                read -p "Press Enter to continue..."
                ;;
            5)
                echo "Goodbye!"
                exit 0
                ;;
            *)
                echo "[ERROR] Invalid choice!"
                read -p "Press Enter to continue..."
                ;;
        esac
    else
        case "$CHOICE" in
            1)
                download_from_github || { read -p "Press Enter to continue..."; continue; }
                do_setup
                IS_INSTALLED=1
                echo ""
                echo "============================================"
                echo "   CloudMesh Installed Successfully!"
                echo "============================================"
                echo ""
                echo "=== Quick Start ==="
                echo "  cm --help              # Show all commands"
                echo "  cm interactive         # Interactive TUI"
                echo "  cm version             # Show version"
                echo "  cm ping                # Test connections"
                echo "  cm discover 192.168.1  # Scan network"
                echo "  cm bench               # Benchmark"
                echo ""
                echo "Usage: cm [command] [options]"
                echo ""
                read -p "Press Enter to continue..."
                ;;
            2)
                echo "Goodbye!"
                exit 0
                ;;
            *)
                echo "[ERROR] Invalid choice!"
                read -p "Press Enter to continue..."
                ;;
        esac
    fi
done

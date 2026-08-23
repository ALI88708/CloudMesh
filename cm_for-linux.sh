#!/bin/bash

# ============================================
# CloudMesh Installer - Linux
# Created by MRSX PRO
# ============================================

set -e

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
# COLORS
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# CHECK INSTALL STATUS
# ============================================
IS_INSTALLED=0
if [ -f "$CLOUDMESH_DIR/main.py" ]; then
    IS_INSTALLED=1
fi
if [ -d "$VENV_DIR" ]; then
    IS_INSTALLED=1
fi

# ============================================
# DOWNLOAD FUNCTION
# ============================================
download_from_github() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Downloading from GitHub...${NC}"
    echo -e "${BLUE}============================================${NC}"
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

    rm -rf "$CLOUDMESH_DIR"
    cp -r "$EXTRACTED/cloudmesh" "$CLOUDMESH_DIR"

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
# UNINSTALL FUNCTION
# ============================================
do_uninstall() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}   Uninstalling CloudMesh...${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""

    [ -d "$CLOUDMESH_DIR" ] && rm -rf "$CLOUDMESH_DIR" && echo -e "${GREEN}[OK] Removed program files${NC}"
    [ -d "$NODE_DIR" ] && rm -rf "$NODE_DIR" && echo -e "${GREEN}[OK] Removed node agent${NC}"
    [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR" && echo -e "${GREEN}[OK] Removed virtual environment${NC}"

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
    python3 -m pip install --user psutil 2>/dev/null || true
    echo -e "${GREEN}[OK] Dependencies installed${NC}"

    echo "[3/6] Creating node directory..."
    mkdir -p "$NODE_DIR" "$NODE_DIR/logs" "$NODE_DIR/data"

    echo "[4/6] Installing node agent..."
    NODE_SOURCE="$CLOUDMESH_DIR/node/$NODE_SCRIPT"
    if [ -f "$NODE_SOURCE" ]; then
        cp "$NODE_SOURCE" "$NODE_DIR/$NODE_SCRIPT"
        chmod +x "$NODE_DIR/$NODE_SCRIPT"
        echo -e "${GREEN}[OK] Node agent installed${NC}"
    else
        echo -e "${YELLOW}[WARNING] cloudmesh_node.py not found, skipping node${NC}"
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

    if command -v systemctl &> /dev/null; then
        TLS_CERT_FLAG=""
        TLS_KEY_FLAG=""
        if [ -f "$NODE_DIR/cert.pem" ] && [ -f "$NODE_DIR/key.pem" ]; then
            TLS_CERT_FLAG="--tls-cert $NODE_DIR/cert.pem"
            TLS_KEY_FLAG="--tls-key $NODE_DIR/key.pem"
        fi
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
        sudo systemctl daemon-reload
        echo -e "${GREEN}[OK] Systemd service created (binds to 127.0.0.1)${NC}"
    fi

    echo -e "${GREEN}[OK] Node scripts created${NC}"

    echo "[6/6] Node setup complete!"
    echo ""
    AUTH_KEY=$(cat "$NODE_DIR/.node_key" 2>/dev/null || echo "N/A")
    IP_ADDRESS=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_IP")

    echo -e "${GREEN}  [OK] Node Location: $NODE_DIR${NC}"
    echo -e "${GREEN}  [OK] Auth Key: $AUTH_KEY${NC}"
    echo -e "${GREEN}  [OK] TLS: $([ -f "$NODE_DIR/cert.pem" ] && echo "enabled" || echo "disabled")${NC}"
    echo -e "${GREEN}  [OK] Bind: 127.0.0.1 (local only)${NC}"
    echo ""
    echo "  === Add from Controller ==="
    echo "  cm add -n $(hostname) -H $IP_ADDRESS -p 9999 -k $AUTH_KEY"
    echo ""

    read -p "   Start node now? (y/n): " START_NODE
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
        source "$VENV_DIR/bin/activate"
        pip install -q -r "$CLOUDMESH_DIR/requirements.txt"
        echo -e "${GREEN}[OK] Environment ready!${NC}"
    else
        source "$VENV_DIR/bin/activate"
        echo -e "${GREEN}[OK] Virtual environment exists${NC}"
    fi
    echo ""

    echo "Creating cm shortcut..."
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
        echo -e "${GREEN}[OK] Added ~/.local/bin to PATH${NC}"
    fi

    echo -e "${GREEN}[OK] cm command available!${NC}"
    echo ""
}

# ============================================
# MAIN MENU
# ============================================
while true; do
    clear
    echo ""
    echo -e "${BLUE}+==========================================+${NC}"
    echo -e "${BLUE}|        CloudMesh Installer v2.0          |${NC}"
    echo -e "${BLUE}+==========================================+${NC}"
    echo ""

    if [ "$IS_INSTALLED" -eq 1 ]; then
        echo -e "   ${GREEN}[OK] CloudMesh is already installed${NC}"
        echo ""
        echo "   [1] Fresh Install (overwrite)"
        echo "   [2] Update (keep config)"
        echo "   [3] Factory Reset"
        echo "   [4] Uninstall"
        echo "   [5] Exit"
        echo ""
        read -p "   Choose [1-5]: " CHOICE

        case "$CHOICE" in
            1)
                download_from_github || { read -p "Press Enter to continue..."; continue; }
                do_setup
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
                read -p "Press Enter to continue..."
                ;;
            2)
                echo ""
                echo -e "${BLUE}============================================${NC}"
                echo -e "${BLUE}   Updating CloudMesh...${NC}"
                echo -e "${BLUE}============================================${NC}"
                echo ""

                BACKUP_DIR="/tmp/cloudmesh_backup"
                mkdir -p "$BACKUP_DIR"
                [ -f "$CLOUDMESH_DIR/.node_keys.json" ] && cp "$CLOUDMESH_DIR/.node_keys.json" "$BACKUP_DIR/" && echo -e "${GREEN}[OK] Backed up node keys${NC}"
                [ -f "$INSTALL_DIR/cloudmesh.json" ] && cp "$INSTALL_DIR/cloudmesh.json" "$BACKUP_DIR/" && echo -e "${GREEN}[OK] Backed up server config${NC}"

                download_from_github || { read -p "Press Enter to continue..."; continue; }

                [ -f "$BACKUP_DIR/.node_keys.json" ] && cp "$BACKUP_DIR/.node_keys.json" "$CLOUDMESH_DIR/" 2>/dev/null
                [ -f "$BACKUP_DIR/cloudmesh.json" ] && cp "$BACKUP_DIR/cloudmesh.json" "$INSTALL_DIR/" 2>/dev/null
                rm -rf "$BACKUP_DIR"
                echo -e "${GREEN}[OK] Config restored${NC}"

                do_setup
                echo -e "${GREEN}[OK] Update complete!${NC}"
                echo ""
                read -p "Press Enter to continue..."
                ;;
            3)
                echo -e "${YELLOW}[WARNING] This will delete ALL data!${NC}"
                read -p "   Are you sure? (y/n): " CONFIRM
                if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
                    echo ""
                    echo "Removing old installation..."
                    [ -d "$CLOUDMESH_DIR" ] && rm -rf "$CLOUDMESH_DIR"
                    [ -d "$NODE_DIR" ] && rm -rf "$NODE_DIR"
                    [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"
                    echo -e "${GREEN}[OK] Old files removed${NC}"
                    echo ""

                    download_from_github || { read -p "Press Enter to continue..."; continue; }
                    do_setup
                    echo -e "${GREEN}[OK] Factory Reset complete!${NC}"
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
                echo ""
                echo -e "${BLUE}Goodbye!${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo -e "${RED}[ERROR] Invalid choice!${NC}"
                read -p "Press Enter to continue..."
                ;;
        esac
    else
        echo -e "   ${YELLOW}[!] CloudMesh is NOT installed${NC}"
        echo ""
        echo "   [1] Install CloudMesh"
        echo "   [2] Exit"
        echo ""
        read -p "   Choose [1-2]: " CHOICE

        case "$CHOICE" in
            1)
                download_from_github || { read -p "Press Enter to continue..."; continue; }
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
                read -p "Press Enter to continue..."
                ;;
            2)
                echo ""
                echo -e "${BLUE}Goodbye!${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo -e "${RED}[ERROR] Invalid choice!${NC}"
                read -p "Press Enter to continue..."
                ;;
        esac
    fi
done

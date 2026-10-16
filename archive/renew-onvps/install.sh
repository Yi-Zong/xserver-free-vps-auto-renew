#!/usr/bin/env bash
set -e

REPO_DIR="/opt/xserver-renew-onvps"

echo "[1/6] Updating system packages..."
apt update && apt upgrade -y

echo "[2/6] Installing base packages..."
apt install -y git python3 python3-venv python3-pip xvfb curl unzip

echo "[3/6] Cloning repository..."
if [ -d "$REPO_DIR" ]; then
  echo "Directory $REPO_DIR already exists, skipping clone."
else
  git clone https://github.com/Yi-Zong/xserver-renew-onvps.git "$REPO_DIR"
fi

echo "[4/6] Preparing project files..."
mkdir -p "$REPO_DIR/logs"
if [ ! -f "$REPO_DIR/xserver/.env" ]; then
  cp "$REPO_DIR/xserver/.env.example" "$REPO_DIR/xserver/.env"
  echo "Created $REPO_DIR/xserver/.env (please edit it manually)."
fi
if [ ! -f "$REPO_DIR/.env.runtime" ]; then
  cp "$REPO_DIR/env.runtime.example" "$REPO_DIR/.env.runtime"
  echo "Created $REPO_DIR/.env.runtime (please edit it manually)."
fi

echo "[5/6] Installing Python dependencies..."
cd "$REPO_DIR/xserver"
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install

echo "[6/6] Done."
echo
echo "Next steps:"
echo "1. Edit $REPO_DIR/xserver/.env"
echo "2. Edit $REPO_DIR/.env.runtime"
echo "3. Test manually:"
echo "   cd $REPO_DIR/xserver && . .venv/bin/activate && python main.py"
echo "4. Test notifier:"
echo "   cd $REPO_DIR && . .env.runtime && python3 run_xserver_notify.py"
echo "5. Add cron if everything works."

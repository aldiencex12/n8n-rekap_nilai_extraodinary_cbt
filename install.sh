#!/bin/bash
# ==============================================================================
# Script Instalasi Otomatis Bot Rekap Nilai CBT SMP Hang Tuah 5
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}   🚀 INSTALASI BOT REKAP NILAI EXTRAORDINARY CBT    ${NC}"
echo -e "${BLUE}=====================================================${NC}"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# 1. Cek & Siapkan File Konfigurasi .env
if [ ! -f .env ]; then
    echo -e "${YELLOW}📄 Membuat file konfigurasi .env dari .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ File .env berhasil dibuat.${NC}"
    echo -e "${YELLOW}👉 Anda dapat mengedit kredensial/token kapan saja dengan: nano .env${NC}"
else
    echo -e "${GREEN}✅ File .env ditemukan.${NC}"
fi

# 2. Cek Python3
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}📦 Menginstal Python3...${NC}"
    sudo apt-get update && sudo apt-get install -y python3 python3-pip
fi

# 3. Cek Headless Chrome (Untuk Print PDF)
if ! command -v google-chrome &> /dev/null && ! command -v chromium &> /dev/null && ! command -v chromium-browser &> /dev/null; then
    echo -e "${YELLOW}📦 Google Chrome belum terdeteksi. Menginstal Google Chrome (untuk render PDF)...${NC}"
    sudo apt-get update && sudo apt-get install -y wget
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
    rm -f google-chrome-stable_current_amd64.deb
    echo -e "${GREEN}✅ Google Chrome berhasil diinstal.${NC}"
else
    echo -e "${GREEN}✅ Browser Chrome/Chromium sudah terpasang.${NC}"
fi

# 4. Pasang Systemd Service (Otomatis deteksi Root vs User biasa)
if [ "$EUID" -eq 0 ]; then
    # Jika dijalankan sebagai ROOT di server
    SERVICE_DIR="/etc/systemd/system"
    SERVICE_NAME="telegram-rekap-bot.service"
    SYSTEMCTL_CMD="systemctl"
    WANTED_BY="multi-user.target"
    JOURNAL_CMD="journalctl -u $SERVICE_NAME -f"
else
    # Jika dijalankan sebagai user biasa (desktop/laptop)
    SERVICE_DIR="$HOME/.config/systemd/user"
    SERVICE_NAME="telegram-rekap-bot.service"
    SYSTEMCTL_CMD="systemctl --user"
    WANTED_BY="default.target"
    JOURNAL_CMD="journalctl --user -u $SERVICE_NAME -f"
fi

mkdir -p "$SERVICE_DIR"

echo -e "${YELLOW}⚙️  Mengonfigurasi layanan background systemd di $SERVICE_DIR...${NC}"
cat <<EOF > "$SERVICE_DIR/$SERVICE_NAME"
[Unit]
Description=Telegram Rekap Bot CBT SMP Hang Tuah 5
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/telegram_rekap_bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=$WANTED_BY
EOF

$SYSTEMCTL_CMD daemon-reload
$SYSTEMCTL_CMD enable --now "$SERVICE_NAME"

echo -e "\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}   🎉 INSTALASI SELESAI & BOT BERHASIL DIAKTIFKAN!   ${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo -e "Status Layanan:"
$SYSTEMCTL_CMD status "$SERVICE_NAME" --no-pager
echo -e "\n${BLUE}💡 Catatan Tambahan:${NC}"
echo -e "1. Untuk mengganti Token Bot, URL CBT, atau Password, cukup edit file ${YELLOW}.env${NC} lalu restart bot:"
echo -e "   ${GREEN}$SYSTEMCTL_CMD restart $SERVICE_NAME${NC}"
echo -e "2. Untuk melihat live log bot:"
echo -e "   ${GREEN}$JOURNAL_CMD${NC}"

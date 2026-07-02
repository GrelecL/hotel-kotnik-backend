#!/usr/bin/env bash
# Hotel Kotnik — prvi zagon (interactive setup)
# Testirano na: Debian 12, Ubuntu 22.04/24.04
set -euo pipefail

# ─── Barve ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}  ▸${NC} $*"; }
ok()      { echo -e "${GREEN}  ✓${NC} $*"; }
warn()    { echo -e "${YELLOW}  ⚠${NC} $*"; }
die()     { echo -e "${RED}  ✗ NAPAKA:${NC} $*" >&2; exit 1; }
section() { echo -e "\n${BOLD}${CYAN}┌─ $* ─────────────────────────────────────────${NC}"; }
ask()     { echo -e "${BOLD}  ?${NC} $*"; }

# read z privzetim; vrne vrednost v $REPLY ali $1 (spremenljivka)
prompt() {
  local var="$1" label="$2" default="${3:-}"
  if [[ -n "$default" ]]; then
    ask "${label} [${CYAN}${default}${NC}]: "
  else
    ask "${label}: "
  fi
  IFS= read -r input </dev/tty
  [[ -z "$input" && -n "$default" ]] && input="$default"
  printf -v "$var" '%s' "$input"
}

prompt_secret() {
  local var="$1" label="$2"
  ask "${label}: "
  IFS= read -rs input </dev/tty; echo
  printf -v "$var" '%s' "$input"
}

confirm() {
  # confirm "Vprašanje" → vrne 0 (da) ali 1 (ne)
  ask "$1 [d/N]: "
  IFS= read -r ans </dev/tty
  [[ "${ans,,}" == "d" || "${ans,,}" == "y" ]]
}

# ─── Predpogoji ───────────────────────────────────────────────────────────────
section "Preverjanje predpogojev"

need() { command -v "$1" &>/dev/null || die "Manjka: $1  →  $2"; }
need curl  "apt install curl"
need git   "apt install git"
need python3 "apt install python3"

# Docker
if ! command -v docker &>/dev/null; then
  warn "Docker ni nameščen. Namestim samodejno..."
  curl -fsSL https://get.docker.com | bash
  ok "Docker nameščen"
fi

# Docker Compose plugin
if ! docker compose version &>/dev/null; then
  warn "Docker Compose plugin ni nameščen. Namestim..."
  apt-get install -y docker-compose-plugin 2>/dev/null || \
    die "Namesti ročno: apt install docker-compose-plugin"
  ok "Docker Compose nameščen"
fi

# Tailscale
if ! command -v tailscale &>/dev/null; then
  warn "Tailscale ni nameščen."
  if confirm "Namestim Tailscale zdaj?"; then
    curl -fsSL https://tailscale.com/install.sh | sh
    info "Tailscale nameščen. Povežem z omrežjem..."
    tailscale up
  else
    warn "Tailscale preskoček — TAILSCALE_IP bo nastavljen na 0.0.0.0 (ni priporočeno)"
  fi
fi
ok "Predpogoji OK"

# ─── Kloniranje ───────────────────────────────────────────────────────────────
section "Repozitorij"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$REPO_DIR/docker-compose.yml" ]]; then
  die "Skripta mora biti v mapi hotel-kotnik-backend (z docker-compose.yml)."
fi
cd "$REPO_DIR"
ok "Repozitorij: $REPO_DIR"

# ─── Tailscale IP ─────────────────────────────────────────────────────────────
section "Tailscale IP naslov"

DETECTED_IP=""
if command -v tailscale &>/dev/null; then
  DETECTED_IP=$(tailscale ip -4 2>/dev/null || true)
fi

if [[ -n "$DETECTED_IP" ]]; then
  ok "Zaznani Tailscale IP: ${CYAN}${DETECTED_IP}${NC}"
  if ! confirm "Uporabim ta IP?"; then
    prompt TAILSCALE_IP "Vnesi Tailscale IP" ""
  else
    TAILSCALE_IP="$DETECTED_IP"
  fi
else
  warn "Tailscale ni aktiven ali nima IP naslova."
  prompt TAILSCALE_IP "Vnesi Tailscale IP (ali pusti prazno za 0.0.0.0)" "0.0.0.0"
fi
ok "API bo dosegljiv na: ${CYAN}http://${TAILSCALE_IP}:8000${NC}"

# ─── Generiranje skrivnih ključev ─────────────────────────────────────────────
section "Generiranje skrivnih ključev"

# FERNET_KEY
FERNET_KEY=$(python3 -c "
try:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
except ImportError:
    import base64, os
    key = base64.urlsafe_b64encode(os.urandom(32))
    print(key.decode())
")
ok "FERNET_KEY generiran"

# DB_PASSWORD
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
ok "DB_PASSWORD generiran"

# ─── Ollama model ─────────────────────────────────────────────────────────────
section "Lokalni AI model (Ollama)"

echo "  Razpoložljivi modeli:"
echo "    ${CYAN}1${NC}) qwen2.5:3b   — 2 GB RAM, ~15 s/email  (priporočeno za CPU)"
echo "    ${CYAN}2${NC}) qwen2.5:7b   — 5 GB RAM, ~40 s/email  (boljša kakovost)"
echo "    ${CYAN}3${NC}) llama3.2:3b  — 2 GB RAM, ~15 s/email  (alternativa)"
echo "    ${CYAN}4${NC}) qwen2.5:14b  — 10 GB RAM, ~90 s/email (odlična, potrebuje GPU)"
echo ""
prompt MODEL_CHOICE "Izbira" "1"

case "$MODEL_CHOICE" in
  1) OLLAMA_MODEL="qwen2.5:3b" ;;
  2) OLLAMA_MODEL="qwen2.5:7b" ;;
  3) OLLAMA_MODEL="llama3.2:3b" ;;
  4) OLLAMA_MODEL="qwen2.5:14b" ;;
  *) OLLAMA_MODEL="$MODEL_CHOICE" ;;
esac
ok "Model: ${CYAN}${OLLAMA_MODEL}${NC}"

GPU_LINES=""
if confirm "Ali ima VM NVIDIA GPU s Proxmox passthrough?"; then
  GPU_LINES='    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]'
  warn "GPU: aktivirano. Prepričaj se da je nvidia-container-toolkit nameščen."
fi

# ─── Email (IMAP) ─────────────────────────────────────────────────────────────
section "Email nastavitve (IMAP)"

SETUP_EMAIL=false
if confirm "Nastavi IMAP email za samodejno sprejemanje rezervacij?"; then
  SETUP_EMAIL=true
  prompt IMAP_HOST "IMAP strežnik" "imap.gmail.com"
  prompt IMAP_PORT "IMAP vrata" "993"
  prompt IMAP_USER "Email naslov" ""
  prompt_secret IMAP_PASS "Email geslo (ali App Password)"
fi

# ─── Turistična taksa ─────────────────────────────────────────────────────────
section "Turistična taksa"

prompt TAX_RATE           "Stopnja na osebo na noč (EUR)" "3.13"
prompt TAX_CHILD_AGE      "Starost otroka za oprostitev (pod X let)" "7"
prompt TAX_CHILD_DISCOUNT "Popust za otroke nad to starostjo (%)" "50"

# ─── Admin PIN ────────────────────────────────────────────────────────────────
section "Admin PIN (za GUI aplikacijo)"

while true; do
  prompt_secret ADMIN_PIN   "Nov PIN (4–8 številk)"
  prompt_secret ADMIN_PIN2  "Ponovi PIN"
  if [[ "$ADMIN_PIN" == "$ADMIN_PIN2" && ${#ADMIN_PIN} -ge 4 ]]; then
    break
  elif [[ ${#ADMIN_PIN} -lt 4 ]]; then
    warn "PIN mora imeti vsaj 4 znake."
  else
    warn "PIN-a se ne ujemata. Poskusi znova."
  fi
done
ok "PIN nastavljen"

# ─── Pisanje .env ─────────────────────────────────────────────────────────────
section "Ustvarjanje .env datoteke"

if [[ -f ".env" ]]; then
  warn ".env že obstaja — ustvarim varnostno kopijo: .env.bak"
  cp .env .env.bak
fi

cat > .env <<EOF
# Hotel Kotnik — generiran $(date '+%Y-%m-%d %H:%M:%S')
DB_PASSWORD=${DB_PASSWORD}
FERNET_KEY=${FERNET_KEY}
TAILSCALE_IP=${TAILSCALE_IP}
OLLAMA_MODEL=${OLLAMA_MODEL}
EMAIL_POLL_INTERVAL=45
EOF
ok ".env ustvarjen"

# GPU v docker-compose — dinamično posodobi če je potrebno
if [[ -n "$GPU_LINES" ]]; then
  info "Aktiviram GPU v docker-compose.yml..."
  python3 - <<PYEOF
import re, sys

with open('docker-compose.yml', 'r') as f:
    content = f.read()

# Odkomentiraj GPU blok za ollama servis
content = re.sub(
    r'(  ollama:.*?)(    # --- NVIDIA GPU.*?#           capabilities: \[gpu\]\n)',
    lambda m: m.group(1) + re.sub(r'    # (.*?\n)', r'    \1', m.group(2)),
    content, flags=re.DOTALL
)
with open('docker-compose.yml', 'w') as f:
    f.write(content)
print("  GPU konfiguracija aktivirana")
PYEOF
fi

# ─── Docker build & start ─────────────────────────────────────────────────────
section "Gradnja in zagon Docker storitev"

info "Gradim Docker slike..."
docker compose build --quiet
ok "Docker slike zgrajene"

info "Zaganjam bazo podatkov in Redis..."
docker compose up -d db redis
info "Čakam na bazo..."
docker compose run --rm migrate 2>/dev/null && ok "Migracije izvedene" || true

info "Zaganjam Ollama..."
docker compose up -d ollama

info "Čakam da se Ollama zažene..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    ok "Ollama se je zagnal"
    break
  fi
  [[ $i -eq 30 ]] && die "Ollama se ni zagnal v 5 minutah"
  sleep 10
done

info "Prenašam AI model ${OLLAMA_MODEL} (to traja 5–20 minut ob prvem zagonu)..."
docker compose up ollama-init
ok "Model ${OLLAMA_MODEL} je pripravljen"

info "Zaganjam vse storitve..."
docker compose up -d
ok "Vse storitve se zaganjajo"

# ─── Čakanje na API ───────────────────────────────────────────────────────────
section "Čakanje da API postane dosegljiv"

API_URL="http://localhost:8000"
for i in $(seq 1 30); do
  if curl -sf "${API_URL}/health" > /dev/null 2>&1; then
    ok "API je dosegljiv"
    break
  fi
  [[ $i -eq 30 ]] && die "API se ni zagnal. Preveri: docker compose logs api"
  info "Čakam... (${i}/30)"
  sleep 6
done

# ─── Konfiguracija prek API ───────────────────────────────────────────────────
section "Nastavitve prek API"

PATCH_BODY=$(python3 - <<PYEOF
import json

body = {
    "pin": "",
    "new_pin": "${ADMIN_PIN}",
    "tourist_tax_rate": "${TAX_RATE}",
    "tourist_tax_child_exempt_age": ${TAX_CHILD_AGE},
    "tourist_tax_child_discount_pct": ${TAX_CHILD_DISCOUNT},
}

setup_email = "${SETUP_EMAIL}" == "true"
if setup_email:
    body["imap_host"]     = "${IMAP_HOST:-}"
    body["imap_port"]     = int("${IMAP_PORT:-993}")
    body["imap_user"]     = "${IMAP_USER:-}"
    body["imap_password"] = "${IMAP_PASS:-}"

print(json.dumps(body))
PYEOF
)

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X PATCH "${API_URL}/admin/settings" \
  -H "Content-Type: application/json" \
  -d "$PATCH_BODY")

if [[ "$HTTP_CODE" == "200" ]]; then
  ok "Admin nastavitve shranjene (turistična taksa, PIN, email)"
else
  warn "Admin PATCH vrnil HTTP ${HTTP_CODE} — nastavi ročno prek API ali GUI"
fi

# ─── Sobe ─────────────────────────────────────────────────────────────────────
section "Nastavitev sob"

declare -A CAT_IDS=()

if confirm "Dodaš kategorije sob in sobe zdaj?"; then

  while true; do
    echo ""
    prompt CAT_NAME "Ime kategorije (npr. 'Enoposteljna') — pusti prazno za konec" ""
    [[ -z "$CAT_NAME" ]] && break
    prompt CAT_CAP  "Kapaciteta (število ležišč)" "2"

    RESP=$(curl -s -X POST "${API_URL}/admin/room-categories" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"${CAT_NAME}\",\"capacity\":${CAT_CAP}}")
    CAT_ID=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('id',''))" <<< "$RESP")
    if [[ -n "$CAT_ID" ]]; then
      ok "Kategorija '${CAT_NAME}' dodana (ID: ${CAT_ID})"
      CAT_IDS["$CAT_NAME"]="$CAT_ID"
    else
      warn "Napaka pri dodajanju kategorije: $RESP"
    fi
  done

  if [[ ${#CAT_IDS[@]} -gt 0 ]]; then
    echo ""
    info "Dodane kategorije:"
    for name in "${!CAT_IDS[@]}"; do
      echo "    ${CAT_IDS[$name]}) $name"
    done

    echo ""
    if confirm "Dodaš sobe zdaj?"; then
      while true; do
        echo ""
        prompt ROOM_NUM   "Številka sobe (npr. 101) — pusti prazno za konec" ""
        [[ -z "$ROOM_NUM" ]] && break
        prompt ROOM_FLOOR "Nadstropje" "1"
        prompt ROOM_CAT   "Kategorija ID" ""

        if [[ -z "$ROOM_CAT" ]]; then
          warn "Kategorija ID je obvezna — preskoči sobo"
          continue
        fi

        RESP=$(curl -s -X POST "${API_URL}/admin/rooms" \
          -H "Content-Type: application/json" \
          -d "{\"number\":\"${ROOM_NUM}\",\"floor\":${ROOM_FLOOR},\"category_id\":${ROOM_CAT}}")
        ROOM_ID=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('id',''))" <<< "$RESP")
        if [[ -n "$ROOM_ID" ]]; then
          ok "Soba ${ROOM_NUM} (nadstropje ${ROOM_FLOOR}) dodana"
        else
          warn "Napaka: $RESP"
        fi
      done
    fi
  fi
fi

# ─── Povzetek ─────────────────────────────────────────────────────────────────
section "Namestitev zaključena"

echo ""
echo -e "${BOLD}${GREEN}  Hotel Kotnik backend je zagnan!${NC}"
echo ""
echo -e "  ${BOLD}Endpoint:${NC}       http://${TAILSCALE_IP}:8000"
echo -e "  ${BOLD}Swagger docs:${NC}   http://${TAILSCALE_IP}:8000/docs"
echo -e "  ${BOLD}AI model:${NC}       ${OLLAMA_MODEL}"
echo ""
echo -e "  ${BOLD}${YELLOW}Shrani naslednje:${NC}"
echo -e "  ${BOLD}DB_PASSWORD:${NC}    ${DB_PASSWORD}"
echo -e "  ${BOLD}FERNET_KEY:${NC}     ${FERNET_KEY}"
echo -e "  ${BOLD}Admin PIN:${NC}      (kot si vnesel)"
echo ""
echo -e "  ${BOLD}GUI nastavitve (Windows recepcija):${NC}"
echo -e "    Backend URL:    http://${TAILSCALE_IP}:8000"
echo -e "    WebSocket URL:  ws://${TAILSCALE_IP}:8000/ws/events"
echo ""
echo -e "  ${BOLD}Koristni ukazi:${NC}"
echo -e "    Logi API:       docker compose logs -f api"
echo -e "    Logi email:     docker compose logs -f email-worker"
echo -e "    Logi Ollama:    docker compose logs -f ollama"
echo -e "    Restart:        docker compose restart"
echo -e "    Backup baze:    docker compose exec db pg_dump -U hotel hotel_kotnik > backup.sql"
echo ""
ok "Namestitev uspešna. .env je shranjen v: ${REPO_DIR}/.env"
echo ""

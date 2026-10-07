#!/usr/bin/env bash
# Installs pve-flr-portal on a plain Debian 12 (or compatible) host/LXC
# that already has this repo checked out. Run as root from inside the
# target container/host:
#
#   bash deploy/install.sh
#
# lxc-create.sh calls this automatically after creating the container;
# run it by hand if you provisioned the container/machine yourself.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_USER="pveflr"
SERVICE_NAME="pve-flr-portal"

echo "==> Installing OS packages"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "==> Creating service user $APP_USER"
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi

echo "==> Creating virtualenv and installing dependencies"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --require-hashes -r "$APP_DIR/requirements.lock"

if [ ! -f "$APP_DIR/.env" ]; then
  echo "==> Creating .env from .env.example - EDIT THIS before it'll work"
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi

# Code, .git, .venv and .env stay root-owned, so the service user can't
# change what root later runs (update.sh runs git/pip as root here). The
# service reads .env via its group and writes only certs/ (its
# self-signed cert) and its StateDirectory.
echo "==> Setting ownership (root-owned app, $APP_USER-writable certs/)"
chown -R root:root "$APP_DIR"
chown root:"$APP_USER" "$APP_DIR/.env"
chmod 0640 "$APP_DIR/.env"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$APP_DIR/certs"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR/certs"

echo "==> Installing systemd unit"
# The unit's StateDirectory=pve-flr-portal makes systemd create + own
# /var/lib/pve-flr-portal (PFR_DATA_DIR, issue #30) on first start - no
# mkdir/chown needed here, and `systemctl enable --now` below triggers it.
sed "s#__APP_DIR__#${APP_DIR}#g; s#__APP_USER__#${APP_USER}#g" \
  "$APP_DIR/deploy/pve-flr-portal.service.template" > "/etc/systemd/system/${SERVICE_NAME}.service"

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo
echo "==> Installed. Service status:"
systemctl --no-pager status "$SERVICE_NAME" || true
echo
echo "Edit $APP_DIR/.env (PVE_HOST, PVE_STORAGE) then:"
echo "  systemctl restart $SERVICE_NAME"
echo
echo "To update later, run: bash $APP_DIR/deploy/update.sh"

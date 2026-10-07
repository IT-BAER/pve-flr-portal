"""Static checks on the LXC deploy scripts and the container build.

The scripts run git/pip as root inside the app dir, so that dir must
stay root-owned (only certs/ writable by the service user), and every
dependency install must be hash-checked against requirements.lock.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_scripts_never_hand_the_app_dir_to_the_service_user():
    for name in ("install.sh", "update.sh"):
        text = _read(DEPLOY / name)
        assert not re.search(r'chown -R "\$APP_USER"[^\n]*"\$APP_DIR"\s*$', text, re.M), name
        assert 'chown -R root:root "$APP_DIR"' in text, name
        assert 'chown -R "$APP_USER":"$APP_USER" "$APP_DIR/certs"' in text, name
        assert 'chmod 0640 "$APP_DIR/.env"' in text, name
        assert "safe.directory" not in text, name


def test_unit_only_lets_the_service_write_certs():
    unit = _read(DEPLOY / "pve-flr-portal.service.template")
    assert re.findall(r"^ReadWritePaths=(.*)$", unit, re.M) == ["__APP_DIR__/certs"]
    assert "StateDirectory=pve-flr-portal" in unit


def test_every_install_path_requires_hashes_from_the_lock():
    for path in (DEPLOY / "install.sh", DEPLOY / "update.sh", ROOT / "Dockerfile"):
        installs = [ln for ln in _read(path).splitlines() if re.search(r"pip\"? install", ln)]
        assert installs, path
        for ln in installs:
            assert "--require-hashes -r" in ln and "requirements.lock" in ln, (path, ln)


def test_lock_pins_every_requirement_with_hashes():
    lock = _read(ROOT / "requirements.lock")
    pinned = {m.group(1).lower() for m in re.finditer(r"^([A-Za-z0-9_.-]+)==\S+ \\$", lock, re.M)}
    for line in _read(ROOT / "requirements.txt").splitlines():
        name = re.split(r"[\s\[#=<>]", line.strip(), maxsplit=1)[0].lower()
        if name:
            assert name in pinned, name
    for block in re.split(r"\n(?=[A-Za-z0-9_.-]+==)", lock):
        head = block.split("\n", 1)[0]
        if "==" in head:
            assert "--hash=sha256:" in block, head

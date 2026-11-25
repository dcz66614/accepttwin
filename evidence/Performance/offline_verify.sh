#!/usr/bin/env bash
# Offline verification (P032 T012, PROJECT_BOOK §0.2 items 4/19, §16).
#
# Proves, with external networking removed (a fresh network namespace
# via `unshare -rn` — no route to anything but loopback), that the
# project still does: install from source, test, verify (S0 gate),
# report generation, and HTML export, plus `npm run build` from the
# frozen lockfile. Run from the repository root:
#
#   bash evidence/Performance/offline_verify.sh
#
# The script re-execs itself inside the namespace; all output is the
# evidence log. Exit code 0 only if every step passes. Nothing here
# touches the network: any external request would fail loudly
# instead of being silently skipped.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [ "${ACCEPTTWIN_OFFLINE_INNER:-0}" != "1" ]; then
  echo "== offline verify: entering fresh network namespace (no external network) =="
  exec unshare -rn env ACCEPTTWIN_OFFLINE_INNER=1 bash "$0"
fi

cd "$ROOT" || exit 1
fail=0
step() { echo "== STEP: $1 =="; }

# 1. Loopback up inside the namespace (fresh netns starts with lo down).
step "loopback up"
if command -v ip >/dev/null 2>&1; then
  ip link set lo up || fail=1
else
  .venv/bin/python -c "
import fcntl, socket, struct
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
IFF_UP, IFF_RUNNING = 0x1, 0x40
flags = struct.unpack('H', fcntl.ioctl(s, 0x8913, struct.pack('16sh', b'lo', 0))[16:18])[0]
fcntl.ioctl(s, 0x8914, struct.pack('16sh', b'lo', flags | IFF_UP | IFF_RUNNING))
print('lo up (via ioctl)')
" || fail=1
fi
python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', 9))" 2>/dev/null \
  && echo "NOTE: something listens on 127.0.0.1:9 (unexpected, ignored)" \
  || echo "loopback socket check: port 9 closed as expected"

# 2. Prove external networking is really gone.
step "external network unreachable (expected failure)"
.venv/bin/python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(3)
try:
    s.connect(('8.8.8.8', 53))
    raise SystemExit('UNEXPECTED: external connect succeeded')
except OSError as exc:
    print(f'external connect failed as expected: {exc}')
"

# 3. Tests, offline, in the pre-installed .venv (no download happens).
step "pytest -q (full suite, offline)"
.venv/bin/python -m pytest -q || fail=1

# 4. S0 gate, offline (24/24 + parity + bleed 3/3 + repeat-100).
step "accepttwin verify --suite s0 (offline)"
.venv/bin/python -m accepttwin verify --suite s0 || fail=1

# 5. Report generation + HTML export (to a temp dir, not the evidence tree).
step "build_reports_48.py (offline)"
.venv/bin/python scripts/build_reports_48.py || fail=1
step "embed_report.py --all-48 --check-only (offline)"
.venv/bin/python scripts/embed_report.py --all-48 --check-only || fail=1
step "embed_report.py --all-48 --out-dir /tmp/t012_offline_html (offline)"
rm -rf /tmp/t012_offline_html
.venv/bin/python scripts/embed_report.py --all-48 --out-dir /tmp/t012_offline_html || fail=1
ls /tmp/t012_offline_html | wc -l

# 6. report-ui build from the frozen lockfile, offline.
step "npm run build (report-ui, offline)"
(cd report-ui && npm run build) || fail=1

# 7. Fresh-venv install from source, offline: setuptools comes from
# the system site-packages (--system-site-packages), pip is told not
# to fetch anything (--no-index --no-build-isolation).
step "fresh venv offline install"
rm -rf /tmp/t012_offline_venv
python3 -m venv --system-site-packages /tmp/t012_offline_venv || fail=1
/tmp/t012_offline_venv/bin/python -m pip install --no-build-isolation --no-index -e . || fail=1
/tmp/t012_offline_venv/bin/python -m accepttwin --help || fail=1
/tmp/t012_offline_venv/bin/python -m accepttwin --version || fail=1

if [ "$fail" -eq 0 ]; then
  echo "OFFLINE_VERIFY: PASS"
else
  echo "OFFLINE_VERIFY: FAIL"
fi
exit "$fail"

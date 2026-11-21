#!/usr/bin/env bash
set -euo pipefail

umask 077

usage() {
  cat <<'EOF'
Usage: deploy_staging.sh --sha SHA --root PATH --service UNIT --port PORT --environment staging

Creates and verifies a fresh database/filesystem backup, builds an isolated
release from SHA, swaps only the requested application root, verifies /healthz,
and automatically restores the previous release if any post-swap check fails.
EOF
}

die() {
  printf 'DEPLOY_ERROR %s\n' "$*" >&2
  exit 1
}

sha=""
root=""
service=""
port=""
environment=""
while (( $# )); do
  case "$1" in
    --sha) sha="${2:-}"; shift 2 ;;
    --root) root="${2:-}"; shift 2 ;;
    --service) service="${2:-}"; shift 2 ;;
    --port) port="${2:-}"; shift 2 ;;
    --environment) environment="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "argomento sconosciuto: $1" ;;
  esac
done

[[ ${EUID} -eq 0 ]] || die "eseguire come root"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || die "--sha deve essere uno SHA Git completo"
[[ "$root" == /* && "$root" != "/" ]] || die "--root deve essere un percorso assoluto non radice"
[[ "$service" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || die "--service non valido"
[[ "$port" =~ ^[0-9]+$ ]] && (( port >= 1 && port <= 65535 )) || die "--port non valida"
[[ "$environment" == "staging" ]] || die "questo script accetta esclusivamente --environment staging"

root="$(readlink -f "$root")"
[[ -d "$root/.git" ]] || die "repository Git assente in $root"
[[ ! -L "$root" ]] || die "--root non può essere un collegamento simbolico"
[[ -f "$root/.env" ]] || die ".env staging assente"
[[ -x "$root/venv/bin/python" ]] || die "virtualenv staging assente"
command -v git >/dev/null || die "git assente"
command -v pg_dump >/dev/null || die "pg_dump assente"
command -v pg_restore >/dev/null || die "pg_restore assente"
command -v sha256sum >/dev/null || die "sha256sum assente"
command -v systemctl >/dev/null || die "systemctl assente"

old_sha="$(git -C "$root" rev-parse HEAD)"
[[ "$old_sha" =~ ^[0-9a-f]{40}$ ]] || die "SHA installato non valido"
[[ -z "$(git -C "$root" status --short)" ]] || die "checkout staging non pulito"
git -C "$root" cat-file -e "$sha^{commit}" || die "SHA target non presente nel repository"

timestamp="$(date +%Y%m%d_%H%M%S)"
parent="$(dirname "$root")"
name="$(basename "$root")"
backup_root="${parent}/qrfacile-backups/staging"
backup_dir="${backup_root}/${timestamp}_staging_${old_sha:0:12}"
candidate="${parent}/.${name}.release-${timestamp}-${sha:0:12}"
rollback="${root}.rollback-${timestamp}-${old_sha:0:12}"
failed="${root}.failed-${timestamp}-${sha:0:12}"
swapped=0

cleanup() {
  rc=$?
  if (( rc != 0 && swapped == 1 )); then
    printf 'ROLLBACK_BEGIN target=%s previous=%s\n' "$sha" "$old_sha" >&2
    systemctl stop "$service" || true
    if [[ -d "$root" && ! -e "$failed" ]]; then
      mv "$root" "$failed"
    fi
    if [[ -d "$rollback" && ! -e "$root" ]]; then
      mv "$rollback" "$root"
    fi
    systemctl start "$service" || true
    "$root/venv/bin/python" "$root/scripts/verify_release_health.py" \
      --url "http://127.0.0.1:${port}/healthz" \
      --expected-environment "$environment" \
      --expected-release "$old_sha" || true
    printf 'ROLLBACK_END failed_release=%s\n' "$failed" >&2
  elif (( rc != 0 )) && [[ -d "$candidate" ]]; then
    rm -rf -- "$candidate"
  fi
  exit "$rc"
}
trap cleanup EXIT

install -d -m 0700 "$backup_root" "$backup_dir"
dump_file="${backup_dir}/${timestamp}_staging_${old_sha:0:12}_database.dump"
archive_file="${backup_dir}/${timestamp}_staging_${old_sha:0:12}_filesystem.tar.gz"

"$root/venv/bin/python" - "$root/.env" "$dump_file" <<'PY'
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

env_path, dump_path = sys.argv[1:3]
values = {}
for raw in Path(env_path).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    values[key.strip()] = value

parsed = urlsplit(values.get("DATABASE_URL", ""))
if not parsed.hostname or not parsed.path.lstrip("/") or not parsed.username:
    raise SystemExit("DATABASE_URL staging non valida")
child_env = os.environ.copy()
child_env.update(
    PGHOST=parsed.hostname,
    PGPORT=str(parsed.port or 5432),
    PGUSER=unquote(parsed.username),
    PGPASSWORD=unquote(parsed.password or ""),
    PGDATABASE=unquote(parsed.path.lstrip("/")),
)
query = parse_qs(parsed.query)
if query.get("sslmode"):
    child_env["PGSSLMODE"] = query["sslmode"][0]
subprocess.run(
    ["pg_dump", "--format=custom", "--compress=9", "--no-password", "--file", dump_path],
    env=child_env,
    check=True,
)
PY

chmod 0600 "$dump_file"
pg_restore --list "$dump_file" > "${dump_file}.list"
[[ -s "${dump_file}.list" ]] || die "elenco pg_restore vuoto"
pg_restore --exit-on-error --file=/dev/null "$dump_file"
tar --acls --xattrs --numeric-owner -C "$parent" -czf "$archive_file" "$name"
chmod 0600 "$archive_file"
gzip -t "$archive_file"
tar -tzf "$archive_file" >/dev/null
(
  cd "$backup_dir"
  sha256sum "$(basename "$dump_file")" "$(basename "$archive_file")" > SHA256SUMS
  sha256sum -c SHA256SUMS
)
touch "$backup_dir/BACKUP_COMPLETE"

git clone --no-hardlinks --no-checkout "$root" "$candidate"
git -C "$candidate" checkout --detach "$sha"
cp -a "$root/.env" "$candidate/.env"
cp -a "$root/venv" "$candidate/venv"
for persistent in uploads logs invoices qr; do
  if [[ -e "$root/$persistent" ]]; then
    rm -rf -- "$candidate/$persistent"
    cp -a "$root/$persistent" "$candidate/$persistent"
  fi
done
if [[ -f "$root/gunicorn.conf.py" ]]; then
  cp -a "$root/gunicorn.conf.py" "$candidate/gunicorn.conf.py"
fi

"$candidate/venv/bin/python" - "$candidate/.env" "$sha" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
release = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
result = []
seen = False
for line in lines:
    if line.lstrip().startswith("QRFACILE_RELEASE_SHA="):
        result.append(f"QRFACILE_RELEASE_SHA={release}")
        seen = True
    else:
        result.append(line)
if not seen:
    result.append(f"QRFACILE_RELEASE_SHA={release}")
mode = path.stat().st_mode & 0o777
temporary = path.with_name(".env.deploy-tmp")
temporary.write_text("\n".join(result) + "\n", encoding="utf-8", newline="\n")
os.chmod(temporary, mode)
os.replace(temporary, path)
PY

owner="$(stat -c '%u:%g' "$root")"
chown -R "$owner" "$candidate"
(
  cd "$candidate"
  "$candidate/venv/bin/python" -m pip install --disable-pip-version-check -r requirements.txt
  "$candidate/venv/bin/python" -m compileall -q qrfacile_app scripts tests main.py
  "$candidate/venv/bin/python" scripts/project_security_audit.py --fail-on critical
  "$candidate/venv/bin/python" scripts/check_sql_transactions.py
)

cat > "$backup_dir/ROLLBACK_PLAN.txt" <<EOF
Previous release: $old_sha
Rollback directory: $rollback
Failed target directory: $failed
The EXIT trap stops only $service, restores $rollback to $root, restarts it,
and verifies /healthz on port $port against the previous SHA.
EOF
chmod 0600 "$backup_dir/ROLLBACK_PLAN.txt"

systemctl stop "$service"
mv "$root" "$rollback"
mv "$candidate" "$root"
swapped=1
systemctl start "$service"

for _ in $(seq 1 30); do
  if "$root/venv/bin/python" "$root/scripts/verify_release_health.py" \
      --url "http://127.0.0.1:${port}/healthz" \
      --expected-environment "$environment" \
      --expected-release "$sha"; then
    swapped=0
    trap - EXIT
    printf 'DEPLOY_OK environment=%s release=%s backup=%s rollback=%s\n' \
      "$environment" "$sha" "$backup_dir" "$rollback"
    exit 0
  fi
  sleep 1
done

die "health check non superato entro 30 secondi"

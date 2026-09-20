#!/usr/bin/env bash
# Back up the self-hosted stack's stateful data (docs/self-hosting.md's
# Backups section): a logical Postgres dump (pg_dump -Fc, safe to take
# against a live database, restorable with pg_restore) plus a raw tar of
# the MinIO evidence volume, combined into one timestamped tarball.
# Cron-friendly — no prompts, safe to re-run, exits non-zero on any
# failure (set -e) rather than silently producing a partial backup.
#
# Usage: scripts/backup.sh [output-dir]   (default: ./backups)
# Assumes the stack is already running (docker-compose.self-host.yml).
#
# Cron example (daily at 03:00, keeping the last 14 days):
#   0 3 * * * cd /opt/vigilo && ./scripts/backup.sh /opt/vigilo-backups && \
#     find /opt/vigilo-backups -name 'vigilo-backup-*.tar.gz' -mtime +14 -delete
set -euo pipefail
cd "$(dirname "$0")/.."

output_dir="${1:-./backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

mkdir -p "$output_dir"

echo "==> Dumping Postgres (vigilo)..."
docker compose -f docker-compose.self-host.yml exec -T postgres \
  pg_dump -U vigilo -d vigilo -Fc > "$workdir/postgres.dump"

echo "==> Archiving the MinIO evidence volume..."
minio_volume="$(docker volume ls --filter name=vigilo_self_host_minio_data --format '{{.Name}}' | head -n1)"
if [ -z "$minio_volume" ]; then
  echo "error: no volume matching vigilo_self_host_minio_data found — is the stack running?" >&2
  exit 1
fi
docker run --rm \
  -v "$minio_volume:/data:ro" \
  -v "$workdir:/backup" \
  alpine tar czf /backup/minio-evidence.tar.gz -C /data .

archive="$output_dir/vigilo-backup-$timestamp.tar.gz"
tar czf "$archive" -C "$workdir" postgres.dump minio-evidence.tar.gz

echo "==> Wrote $archive ($(du -h "$archive" | cut -f1))"

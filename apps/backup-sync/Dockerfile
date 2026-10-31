# ==========================================
# STAGE 1: Minimal Rclone Builder (S3 & Local)
# ==========================================
FROM golang:1.22-alpine3.20 AS rclone-builder

WORKDIR /build

COPY apps/backup-sync/rclone-min/main.go ./
RUN go mod init rclone-min && \
    go get github.com/rclone/rclone@v1.66.0 && \
    CGO_ENABLED=0 go build -ldflags "-s -w" -o /build/rclone .

# ==========================================
# STAGE 2: Autonomous Backup & Sync Daemon
# ==========================================
FROM alpine:3.20 AS metabridge5-backup-sync

RUN apk add --no-cache tini ca-certificates tzdata tar bash && \
    adduser -D -u 1000 -h /home/backupuser backupuser && \
    mkdir -p /home/backupuser/.config/rclone /tmp/backups /source/account /source/data /var/log && \
    chown -R backupuser:backupuser /home/backupuser /tmp/backups /source /var/log

# Copy minimal rclone static binary
COPY --from=rclone-builder /build/rclone /usr/local/bin/rclone

# Copy backup, restore, and sync scripts
COPY apps/backup-sync/backup.sh /usr/local/bin/backup.sh
COPY apps/backup-sync/restore.sh /usr/local/bin/restore.sh
COPY apps/backup-sync/sync-parquet.sh /usr/local/bin/sync-parquet.sh
COPY apps/backup-sync/healthcheck.sh /usr/local/bin/healthcheck.sh
COPY apps/backup-sync/crontab /etc/crontabs/backupuser

RUN chmod +x /usr/local/bin/rclone \
             /usr/local/bin/backup.sh \
             /usr/local/bin/restore.sh \
             /usr/local/bin/sync-parquet.sh \
             /usr/local/bin/healthcheck.sh && \
    chown backupuser:backupuser /etc/crontabs/backupuser

ENV VOLUME_MOUNT=/source/account \
    PARQUET_SRC=/source/data/parquet \
    BWLIMIT=2M

USER backupuser
WORKDIR /home/backupuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["/usr/local/bin/healthcheck.sh"]

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["crond", "-f", "-l", "2"]

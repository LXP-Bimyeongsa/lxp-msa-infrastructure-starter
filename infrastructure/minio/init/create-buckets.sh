#!/bin/sh
# MinIO 버킷 초기화
#
# course-service가 강의 동영상 원본을 저장할 버킷을 만든다.
# 업로드/재생은 Presigned URL로 클라이언트가 MinIO와 직접 주고받으므로
# (docs/DECISIONS.md D-07), 버킷은 public이 아니라 private으로 둔다.
set -e

MC_HOST="${MINIO_ENDPOINT:-http://minio:9000}"
MC_USER="${MINIO_ROOT_USER:-minioadmin}"
MC_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"

echo "MinIO 기동 대기..."
until mc alias set local "$MC_HOST" "$MC_USER" "$MC_PASSWORD" >/dev/null 2>&1; do
    sleep 2
done

mc mb --ignore-existing local/course-videos
echo "버킷 준비 완료: course-videos"

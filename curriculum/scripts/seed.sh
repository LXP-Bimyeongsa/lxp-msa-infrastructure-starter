#!/usr/bin/env bash
# 강의 카탈로그를 MongoDB course_db 에 적재한다.
#
# 기존 강의를 지우고 다시 넣는다. 개발 중에 카탈로그를 고쳐가며 여러 번 돌릴 수 있다.
# mongo init 스크립트에 넣지 않은 이유 — init 은 최초 기동에만 실행돼서(D-29)
# 다시 넣으려면 볼륨을 지워야 한다.
#
# 사용법
#   ./curriculum/scripts/seed.sh
#
# 전제
#   docker compose 로 mongo 컨테이너가 떠 있어야 한다.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA="$ROOT/curriculum/data/courses.json"
CONTAINER="${MONGO_CONTAINER:-lxp-mongo}"
DB="${MONGO_DB:-course_db}"

if [ ! -f "$DATA" ]; then
  echo "카탈로그를 찾을 수 없다: $DATA" >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "mongo 컨테이너가 떠 있지 않다: $CONTAINER" >&2
  echo "  docker compose -f compose.data.yaml up -d mongo" >&2
  exit 1
fi

COURSES="$(cat "$DATA")"

docker exec -i "$CONTAINER" mongosh "$DB" --quiet --eval "
  const courses = $COURSES;
  const now = new Date();
  courses.forEach(c => { c.createdAt = now; });

  db.course.deleteMany({});
  db.course.insertMany(courses);

  print('적재 완료: ' + db.course.countDocuments() + '건');
  print('총 학습시간: ' + db.course.aggregate([
    { \$group: { _id: null, sum: { \$sum: '\$estimatedHours' } } }
  ]).toArray()[0].sum + 'h');
"

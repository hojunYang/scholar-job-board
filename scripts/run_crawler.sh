#!/bin/bash

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# 현재 체크아웃의 크롤러와 프롬프트를 사용한다.
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# 현재 시간
TIMESTAMP=$(date "+%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/crawler_$TIMESTAMP.log"

# 크롤러 실행
cd "$SCRIPT_DIR" || exit 1

# 로그 파일에 시작 시간 기록
echo "========================================" >> "$LOG_FILE"
echo "크롤러 시작: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 크롤러 실행
python3 crawler.py "$@" >> "$LOG_FILE" 2>&1

# 종료 상태 기록
EXIT_CODE=$?
echo "========================================" >> "$LOG_FILE"
echo "크롤러 종료: $(date)" >> "$LOG_FILE"
echo "종료 코드: $EXIT_CODE" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 30일 이상 된 로그 파일 삭제
find "$LOG_DIR" -name "crawler_*.log" -mtime +30 -delete

exit $EXIT_CODE


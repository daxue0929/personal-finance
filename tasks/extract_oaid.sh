#!/usr/bin/env bash
# ================================================
# 从 test.json (JSONL 格式) 提取全部 oaId
#
# 用法：
#   ./extract_oaid.sh            # 输出全部 oaId（含重复，每行一个）
#   ./extract_oaid.sh -u         # 输出去重后的 oaId（排序）
#   ./extract_oaid.sh -c         # 只统计数量（全部 / 去重）
#   ./extract_oaid.sh -u -c      # 去重后的数量
#   ./extract_oaid.sh <文件路径>  # 指定其他输入文件
# ================================================
set -euo pipefail

# 默认输入文件
INPUT="/Users/wangxuedi/open_source/personal-finance/tasks/test.json"
UNIQUE=0
COUNT_ONLY=0

# 解析参数
while [ $# -gt 0 ]; do
  case "$1" in
    -u) UNIQUE=1 ;;
    -c) COUNT_ONLY=1 ;;
    *)  INPUT="$1" ;;
  esac
  shift
done

if [ ! -f "$INPUT" ]; then
  echo "错误：文件不存在 -> $INPUT" >&2
  exit 1
fi

# 提取 oaId 值：grep 匹配 "oaId":"xxx"，sed 去掉键名和引号只留值
extract() {
  grep -o '"oaId":"[^"]*"' "$INPUT" | sed 's/"oaId":"//; s/"$//'
}

# 按需求输出
if [ "$COUNT_ONLY" = "1" ]; then
  if [ "$UNIQUE" = "1" ]; then
    extract | sort -u | wc -l | tr -d ' '
    echo "（去重后数量）" >&2
  else
    extract | wc -l | tr -d ' '
    echo "（全部数量，含重复）" >&2
  fi
else
  if [ "$UNIQUE" = "1" ]; then
    extract | sort -u
  else
    extract
  fi
fi

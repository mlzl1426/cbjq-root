#!/usr/bin/env bash
# 下载进度自证：不信任游戏 UI 的百分比，用磁盘增量 + tun 计数判断是真在下载还是真卡住
# 用法: bash watch-download.sh [采样间隔秒, 默认 10] [包体大小 MB, 可选, 填了才估算百分比]
set -u

# Git Bash (MSYS) 下 /data 会被当成路径改写，必须关闭转换
export MSYS_NO_PATHCONV=1

INTERVAL="${1:-10}"
TOTAL_MB="${2:-0}"

avail_kb() { adb shell df /data 2>/dev/null | tail -1 | awk '{print $4}'; }
tun_rx()   { adb shell cat /proc/net/dev 2>/dev/null | awk '/ tun[0-9]+:/{print $2; exit}'; }

prev_a=""; prev_t=""; stall=0; base_a=""

printf "%-8s %10s %10s %10s %8s %s\n" "时间" "剩余空间" "磁盘增速" "tun 入向" "估算进度" "判定"

while true; do
  a="$(avail_kb)"; t="$(tun_rx)"
  [ -z "$a" ] && { echo "读取失败：设备未连接或 adb 未授权"; exit 1; }

  rate="--"; rate_mb="--"; verdict="开始采样"
  [ -z "$base_a" ] && base_a="$a"
  if [ -n "$prev_a" ]; then
    rate_mb=$(( (prev_a - a) / 1024 ))                 # KiB -> MiB
    dt=$(( t - prev_t ))                               # bytes
    rate="$(awk -v b="$dt" -v i="$INTERVAL" 'BEGIN{printf "%.1f MB/s", b/i/1048576}')"
    if [ "$rate_mb" -le 1 ] && [ "$dt" -lt $(( 256 * 1024 * INTERVAL )) ]; then
      stall=$((stall + 1))
      verdict="无流量 ${stall} 次"
      [ "$stall" -ge 3 ] && verdict="疑似卡住（磁盘与 tun 均不动）"
    else
      stall=0
      verdict="正在下载"
    fi
  fi

  pct="--"
  if [ "$TOTAL_MB" -gt 0 ]; then
    pct="$(awk -v b="$base_a" -v a="$a" -v tot="$TOTAL_MB" \
      'BEGIN{d=(b-a)/1024; if(d<0)d=0; if(d>tot)d=tot; printf "%5.1f%%", d*100/tot}')"
  fi

  printf "%-8s %7.1f GiB %6s MiB %10s %8s   %s\n" \
    "$(date +%H:%M:%S)" \
    "$(awk -v k="$a" 'BEGIN{print k/1048576}')" \
    "$rate_mb" "$rate" "$pct" "$verdict"

  prev_a="$a"; prev_t="$t"
  sleep "$INTERVAL"
done

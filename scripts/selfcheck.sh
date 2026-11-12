#!/usr/bin/env bash
# 启动顺序自检：服务端进程 / 监听 / 长连接 / VPN 接口
# 用法: bash selfcheck.sh [服务端包名] [游戏包名]
set -u

SERVER_PKG="${1:-com.mikusb.server}"
GAME_PKG="${2:-com.seasun.snowbreak.google}"
PORT=31000
ok=0
fail=0

pass() { echo "  [ OK ] $1"; ok=$((ok+1)); }
warn() { echo "  [WARN] $1"; fail=$((fail+1)); }

echo "== 1. 服务端进程"
if adb shell pidof "$SERVER_PKG" >/dev/null 2>&1; then
  pass "$SERVER_PKG 正在运行 (pid=$(adb shell pidof "$SERVER_PKG" | tr -d '\r'))"
else
  warn "$SERVER_PKG 未运行：先打开服务端 App"
fi

echo "== 2. 端口监听"
if adb shell ss -tln 2>/dev/null | tr -d '\r' | grep -q ":$PORT "; then
  pass "$PORT 正在监听"
else
  warn "$PORT 未监听：服务端没起来或启动失败"
fi

echo "== 3. 游戏长连接"
if adb shell ss -tn 2>/dev/null | tr -d '\r' | grep -q "127.0.0.1:$PORT"; then
  pass "客户端已连上本地 $PORT"
  adb shell ss -tn 2>/dev/null | tr -d '\r' | grep "127.0.0.1:$PORT" | sed 's/^/         /'
else
  warn "还没有到 $PORT 的连接：登录成功后才会有"
fi

echo "== 4. VPN 接口"
if adb shell ip -o link 2>/dev/null | tr -d '\r' | grep -qE '(^|: )(tun|vpn)[0-9]*:'; then
  pass "tun 接口存在"
else
  warn "未发现 tun 接口：SFA 未启动"
fi

echo "== 5. 游戏进程"
if adb shell pidof "$GAME_PKG" >/dev/null 2>&1; then
  pass "$GAME_PKG 正在运行"
else
  warn "$GAME_PKG 未运行"
fi

echo
echo "结果: $ok 项通过, $fail 项异常"
[ "$fail" -eq 0 ] || exit 1

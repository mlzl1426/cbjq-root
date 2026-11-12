# 03 · 用 VpnService 替代 root iptables

## 社区包的 root 是哪来的

社区包的 `iptables` 规则大致是四条 DNAT：

```
-A OUTPUT -p tcp --dport 13443 -j DNAT --to-destination 127.0.0.1:13443
-A OUTPUT -p tcp --dport 18443 -j DNAT --to-destination 127.0.0.1:18443
-A OUTPUT -p tcp --dport 31443 -j DNAT --to-destination 127.0.0.1:31443
-A OUTPUT -p tcp --dport  5200 -j DNAT --to-destination 127.0.0.1:31000
```

这几条规则只干一件事：改目标地址和端口。它不需要什么特权网络能力，唯一卡住人的地方是 `iptables` 本身要 `CAP_NET_ADMIN`，也就是 root。

## 换成 VpnService + sing-box 规则

安卓的 VpnService 不用 root 就能建 tun 设备，把指定应用的流量导进自己的用户态栈。sing-box 在这个模式下能干三件事：

1. 按 `port` / `domain` 匹配连接；
2. 用 `override_address` + `override_port` 改写目标；
3. 用 `direct` 出站把改写后的连接发出去。

一条规则顶一条 DNAT，意思一样：

```json
{
  "port": 5200,
  "action": "route",
  "outbound": "direct",
  "override_address": "127.0.0.1",
  "override_port": 31000
}
```

## 踩过的四个坑

### 1. tun 栈必须是 `gvisor`

`stack` 用 `system` 或 `mixed` 时，这几个 TLS 端口的 TCP 连接握完手就没数据了，看着是连上了，其实被黑洞了。换 `gvisor` 就正常。

```json
"stack": "gvisor"
```

### 2. 域名规则前必须有 `sniff`

serverlist 走 443，可 443 上还跑着别的域名（资源 CDN、系统流量）。想按域名精确命中，得让 sing-box 先做 TLS SNI 嗅探：

```json
{"action": "sniff"},
{"domain": ["<serverlist-domain>"], "port": 443, "action": "route",
 "outbound": "direct", "override_address": "127.0.0.1", "override_port": 21443}
```

`sniff` 得是非终结规则（不能带 `action: route`），而且排在域名规则前面。不然首包只能按 IP 匹配，规则白写，表现就是「服务器尚未开放」。

### 3. `override_address` / `override_port` 不能嵌套

网上能见到这种写法，1.14.x 会直接拒：

```json
{"action": "route-options", "override_address": "127.0.0.1"}   // ✗ 会被拒
```

正确写法就是上面第 2 节那种扁平字段。

### 4. 必须开 `auto_route`，并限制 `include_package`

```json
"auto_route": true,
"include_package": ["com.seasun.snowbreak.google"]
```

- 不开 `auto_route`，路由表不指向 tun，规则根本不会执行；
- 不限包名，整机流量都往 tun 里灌。加上 `include_package` 之后只有游戏进程被截获，其它 App（包括你的代理和浏览器）不受影响。

## DNS

tun 里的 DNS 要显式劫持，否则走系统解析器，可能拿到真实 CDN 的 IP。对 serverlist 域名来说不影响功能，只是日志会难读：

```json
{"protocol": "dns", "action": "hijack-dns"}
```

## 验证

```bash
# 1) 规则是否被接受
sing-box check -c sfa-vpn.json

# 2) 游戏是否真的连到了本地
adb shell ss -tn | grep 31000
# 期望：127.0.0.1:<随机端口> -> 127.0.0.1:31000 ESTAB

# 3) 服务端是否在听
adb shell ss -tln | grep 31000
# 期望：0.0.0.0:31000 LISTEN
```

## 能不能用 NekoBox 之类的现成 App

能，但别把这份配置盖到你已有订阅的 profile 上。新建一个独立 profile 当「本地端口改写器」用就行，跟科学上网互不干扰，也不需要任何出站节点（`final: direct`）。

# 配置说明

## sfa-vpn.example.json

sing-box / SFA 的 tun 入站加端口重写规则，替代社区包里的 root `iptables` DNAT。

怎么用：

1. SFA 里新建一个空白配置，别覆盖你已有的节点和订阅。
2. 把文件内容粘进去，或者直接导入成新 profile。
3. `inbounds[0].include_package` 只留游戏包名，别的 App 就不受影响了。
4. 启动 profile，状态栏出 VPN 图标之后再开游戏。

## 需要按你的环境调整的地方

| 字段 | 默认 | 说明 |
|---|---|---|
| `dns.servers[0].server` | `223.5.5.5` | 任意可达的 DNS；tun 内的 DNS 会被 hijack |
| `inbounds[0].address` | `172.19.0.1/30` | tun 网段，避免与本地局域网冲突 |
| `inbounds[0].stack` | `gvisor` | 别改成 system/mixed，见 docs/03 |
| `override_port` 等 | 见文件 | 若你的服务端监听端口不同，按实际改 |

## 三条不能错的

1. `override_address` / `override_port` 写在规则对象的扁平字段里。塞进 `{"action":"route-options":{...}}` 会被 sing-box 拒。
2. 按域名匹配的规则（serverlist 那条 443）前面得有 `{"action":"sniff"}`，而且它不能是终结规则。
3. tun 得开 `auto_route`，不开路由表不指向 tun，规则等于没写。

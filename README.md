# cbjq-root · 尘白禁区安卓单机（免 root）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

社区那套手机单机包要 root，只是为了跑 `iptables` 把几个端口转到 `127.0.0.1`。这一步换成 sing-box 的 tun 规则就够，不用 root，也不用改系统 hosts。

## 下载

去 [Releases](https://github.com/mlzl1426/cbjq-root/releases/latest) 下这三个：

| 文件 | 大小 | 装到哪 |
|---|---|---|
| `game_signed.apk` | 1.5 GB | 游戏客户端（已改好，指向本机、CA 已换） |
| `server.apk` | 74 MB | 本地服务端，先装它 |
| `sfa.apk` | 35 MB | sing-box，负责端口重定向 |

服务端的源码在上游 [MikuLeaks/MikuSB](https://github.com/MikuLeaks/MikuSB)，这里只是把安卓移植版打好包。

## 三步装完

### 1. 装服务端，打开

装 `server.apk`，打开，等界面显示「运行中」。

它跑在前台服务里，切后台没事，但别从最近任务里划掉。第一次启动要解包几千个文件，等 30~60 秒正常。

### 2. 装 SFA，导入配置

装 `sfa.apk`，在 SFA 里新建一个空白配置，把 [`configs/sfa-vpn.example.json`](configs/sfa-vpn.example.json) 的内容粘进去，启动。

别覆盖你已有的订阅或节点。`include_package` 里只留游戏包名，别的 App 不受影响。状态栏出现 VPN 图标就行。

### 3. 装游戏，开玩

装 `game_signed.apk`，按顺序开：**服务端 → VPN → 游戏**。

顺序反了就得重启客户端，它只在启动那会儿读一次配置、拉一次服务器列表。

第一次进去要下资源，序章 2.19 GB 下完就能玩，剩下那 26 GB 慢慢补。资源从官方 CDN 来，正常联网就行，不用加速器。

登录走邮箱，随便填个合法邮箱加初始密码，服务端会自动建号。

## 卡住了看这儿

| 现象 | 先查 |
|---|---|
| 初始化报「网络异常」 | 手机上有没有残留的全局 HTTP 代理；或者是不是把 `893` 也重定向了 |
| 卡「伺服器尚未开放」 | VPN 配置里 `sniff` 有没有放在域名规则前面 |
| 点开始游戏没反应 | serverlist 返回格式不对，见 [02](docs/02-client-analysis.md) |
| 登录成功但一直进不去 | 资源清单是不是空的，是不是缺 `*_Maps_*`，见 [02](docs/02-client-analysis.md) |
| 下载看着停在 0% | 大概率在下，用 `scripts/watch-download.sh` 看磁盘增量 |

完整症状表在 [06](docs/06-launch-order.md)，下载相关的坑在 [05](docs/05-troubleshooting.md)。

## 想自己动手改包

上面那个 `game_signed.apk` 是我改好的。如果你想用自己手上那份原始客户端，跑脚本：

```bash
python scripts/check-client.py <客户端.apk> --ca <服务端根CA.pem>
```

`RESULT: OK` 说明那包本来就能用，直接装。`FAIL` 的话：

```bash
python scripts/build-client.py 客户端.apk --ca 根CA.pem --keystore 你的.jks --ks-pass 密码
```

换 CA、改 SDK 地址、按页对齐重写 zip、签好 v1+v2+v3，产物直接能装。需要 JDK、`apksigner` 和一个签名密钥，细节见 [04](docs/04-repack-notes.md)。

## 文档

| 文档 | 讲什么 |
|---|---|
| [00-quickstart](docs/00-quickstart.md) | 三步上机，只想玩看这篇 |
| [01-architecture](docs/01-architecture.md) | 整体怎么串起来的 |
| [02-client-analysis](docs/02-client-analysis.md) | 客户端里有什么，登录后卡住的四个原因 |
| [03-no-root-redirect](docs/03-no-root-redirect.md) | VpnService 怎么替代 iptables，四个坑 |
| [04-repack-notes](docs/04-repack-notes.md) | 改包重签怎么做 |
| [05-troubleshooting](docs/05-troubleshooting.md) | 资源更新慢、看着像卡住 |
| [06-launch-order](docs/06-launch-order.md) | 启动顺序和自检 |
| [07-case-report](docs/07-case-report.md) | 完整跑一遍的过程 |
| [08-anticensor-modpack](docs/08-anticensor-modpack.md) | 反和谐包怎么构成 |
| [THANKS](THANKS.md) | 上游项目 |

## 踩出来的几条

root 不是必需的，tun 规则能顶掉 `iptables`。

按域名匹配 443 必须在规则前面加 `sniff`，而且这条不能是终结规则。

`override_address` / `override_port` 要写成扁平字段，嵌套在 `route-options` 里 sing-box 1.14 直接拒。

tun 栈用 `gvisor`，`system` 和 `mixed` 下这几个 TLS 端口能连上但收不到数据。

资源更新慢跟 VPN、Wi-Fi、手机性能都没关系，卡在境外 CDN 的节点分配上。

下载进度条不可信。语音包实测全程 0%，实际 9–13 MB/s 在下。

「登录后进不去」不是客户端代码的锅。四个原因是残留代理、serverlist 返回格式、空资源清单、清单缺 `*_Maps_*`。别为此去改 dex。

装 CA 别动系统证书库，客户端本来就有自定义 CA 槽位，换掉 `res/raw/*.cer` 就行。

## 免责声明

不分发服务端源码，也不提供绕过付费、联机或反作弊的东西。内容只用于个人本地环境的互操作研究，不连也不干扰官方在线服务。改客户端会改变它的信任边界和签名，风险自己担；别在有正式账号的设备上折腾。商标和版权归各自权利人，这个项目跟他们没关系，也没得到授权。

## License

文档、配置示例、脚本按 MIT 发布，见 [LICENSE](LICENSE)。致谢的第三方项目各自保留原许可证。游戏客户端、资源、服务端不在本仓库的授权范围内。

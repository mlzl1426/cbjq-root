# 00 · 三步上机

不想折腾的话看这一篇就够。不用反编译，不用改 dex，也不用自己签名。

## 先看看你那包能不能直接用

要连本地服务端，客户端得满足两条：

- `assets/sdk_config.properties` 里的 `XgAuthUrl` / `SeasunAuthUrl` 指向 `http://127.0.0.1:21580`；
- `res/raw/` 里内置的 CA，跟服务端实际在用的那张是同一张。

两条都满足，APK 原样装就能用。跑一下看看：

```bash
python scripts/check-client.py <你的客户端.apk> --ca <服务端根CA.pem>
```

`RESULT: OK` 就往下走。

`RESULT: FAIL` 说明手上是没动过的社区原包，地址还指着它自己的私服，CA 也是它自己的。这种情况跑一条命令就行，签名不用你管：

```bash
python scripts/build-client.py 你的客户端.apk \
    --ca 服务端根CA.pem \
    --keystore 你自己的.jks --ks-alias miku --ks-pass 你的密码
```

它会换 CA、把 SDK 地址改成 `127.0.0.1`、按页对齐重写 zip，然后用你的 key 签好 v1+v2+v3，产出 `你的客户端.local.apk`。细节见 [04-repack-notes.md](04-repack-notes.md)。

这条命令需要这些（只有改包的人才要，玩家不用）：

| 依赖 | 说明 |
|---|---|
| Python 3.8+ | 只用标准库，不用 pip |
| JDK | `apksigner` 要 java |
| `apksigner` | Android SDK 的 `build-tools/<ver>/` 里有。设了 `ANDROID_HOME` 会自动找到，也能 `--apksigner` 指定 |
| 一个 `.jks` | 没有就生一个：`keytool -genkeypair -keystore my.jks -alias miku -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Local"` |

改包就得重签，重签得有私钥，所以这步只能在电脑上做。手上是 `OK` 包的人压根碰不到这些。

## 1. 装服务端

装上游那个本地服务端 App（MikuSB 的安卓版），打开，等界面显示「运行中」。

它跑在前台服务里，切后台没事，但别从最近任务里划掉。第一次启动要解包几千个文件，等个 30~60 秒正常。

服务端 APK 是上游的，这里不给也不镜像，去它仓库拿。

## 2. 导入 VPN 配置

在 SFA（sing-box for Android）里新建一个空白配置，把 [`configs/sfa-vpn.example.json`](../configs/sfa-vpn.example.json) 的内容粘进去，启动。

别覆盖你已有的订阅或节点。`include_package` 里只留游戏包名，别的 App 不受影响。状态栏出现 VPN 图标就行。

社区包是靠 root 跑 `iptables` 干这事的，你这一步替的就是它。不用 root 的原因就在这儿。

## 3. 开游戏

顺序是：服务端 → VPN → 游戏。

顺序反了就得重启客户端，它只在启动那会儿读一次配置、拉一次服务器列表。

第一次进去要下资源，序章 2.19 GB 下完就能玩，剩下那 26 GB 慢慢补。资源从官方 CDN 来，正常联网就行，不用加速器。

## 卡住了看这儿

| 现象 | 先查 |
|---|---|
| 初始化报「网络异常」 | 手机上有没有残留的全局 HTTP 代理；或者是不是把 `893` 也重定向了 |
| 卡「伺服器尚未开放」 | VPN 配置里 `sniff` 有没有放在域名规则前面 |
| 点开始游戏没反应 | serverlist 返回格式不对，见 [02](02-client-analysis.md) |
| 登录成功但一直进不去 | 资源清单是不是空的，是不是缺 `*_Maps_*`，见 [02](02-client-analysis.md) |
| 下载看着停在 0% | 大概率在下，用 `scripts/watch-download.sh` 看磁盘增量 |

症状对照表在 [06-launch-order.md](06-launch-order.md)，下载的坑在 [05-troubleshooting.md](05-troubleshooting.md)。

## 什么时候才真要改包

两种情况：

1. `check-client.py` 报 `FAIL` —— 客户端没指向 `127.0.0.1`，或者内置 CA 对不上；
2. 你想把反和谐 pak 打进客户端，见 [08](08-anticensor-modpack.md)。

两个都是动客户端本体，要重签、要卸载重装、已经下好的 26 GB 会没。动手之前先想清楚是不是真需要。

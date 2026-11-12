# 02 · 客户端里都有些什么

基于 `3.6.0.x`（UE4 4.26）的实测，只写行为，不放任何改好的文件。

## 组成

| 文件 | 作用 | 备注 |
|---|---|---|
| `libUE4.so` | 游戏引擎 | 导出 SDK 的 JNI 接口 |
| `libanogs.so` | 反外挂（ACE） | 独立加载，与 SDK 解耦 |
| `liblocalpatch.so` | 上游客户端自带的网络补丁库 | 两件事：关闭 `libUE4.so` 里的 AnoSDK 导入；hook `getaddrinfo` 把连接改到硬编码地址 |
| `assets/sdk_config.properties` | SDK 地址表 | 初始化 / 探测 / 登录 / 活动等 URL 全在这里，改包时最容易下手的一层 |
| `res/xml/network_security_config.xml` | 信任锚配置 | 上游已经预置了一个自定义 CA 槽位，免 root 装 CA 就靠它 |
| `res/raw/*.cer` | 内置 CA | 跟上面的槽位配套，服务端证书链得对得上 |
| `classes*.dex` | Java 层：SDK、Activity、登录回调 | 这套方案不动它，原因见下 |

## 登录之后为什么进不去

我一开始的判断是错的。当时看 `SeasunLoginSuccessActivity` 设置了 back callback 就销毁、没走结果回传，就认定是 Activity 回调链断了、必须改 dex 才能进游戏。后来三组实验把这个说法推翻了：

| 实验 | 结果 | 说明 |
|---|---|---|
| 把补丁库的 `JNI_OnLoad` 和 `.init_array` 构造函数就地改成 `ret`，让补丁彻底失效、ACE 回到原始状态，重定向改由 iptables 顶 | 登录照常，表现跟打补丁时一模一样 | 卡点不在 ACE，也不在补丁库 |
| 把 `RspLogin` 换成 96 字节随机数据 | 卡在「权限识别中」一直转圈 | 客户端确实收到包了，而且在解析 |
| 换回正常的 `RspLogin`（83 KB） | 转圈消失，3~4 秒退回标题页 | 解析完了，自己决定不往下走 |

`strace` 盯了 25 秒：登录之后零网络请求、零文件打开、没有 ENOENT。说明它既不是在等响应，也不是资源加载失败，是在逻辑层直接放弃了。

真正的原因有四个，按发现顺序排，全在配置和资源上，跟代码无关：

| # | 现象 | 根因 | 判据 |
|---|---|---|---|
| 1 | 「网络异常」，初始化失败 | 机器上残留全局 HTTP 代理；或把 `893` 也做了端口重定向 | `settings get global global_http_proxy_host`；`iptables -L -v` 里 893 命中数万包 |
| 2 | 「伺服器尚未开放」/ 点开始无反应 | serverlist 返回格式不对：客户端要 `[{platform,version,host,port}]` 四字段数组，收到 `{code,servers:[…]}` 会反序列化失败 | 服务端日志里一个 `ReqLogin` 都收不到 |
| 3 | 登录成功但一个文件都不读、静默退回标题 | `cdn_manifest.json` 的 `paks` 是空数组 → 客户端认为资源已齐 | `/proc/<pid>/io` 的 `rchar` 增量：资源缺失时 ~2 MB，装好后 ~285 MB |
| 4 | 资源「齐了」仍停在加载画面 | 清单只列了 OBB 里那十几个基础 pak，缺 `Maps` 包，大厅地图加载不了 | OBB 内 `.pak` 全是 `APP_Game_*` / `App_Engine`，没有 `*_Maps_*` |

第 3 条是自己给自己挖的坑。为了不让客户端去下载，我把清单改成只列本地有的包，结果它认定资源齐了，从此再也不下缺的包，表现就是登录成功、不报错、一个包都不发。正确做法是清单保持官方全量，缺什么让它自己去 CDN 下。

## 证书

- 服务端用本地 CA 签的叶子证书，客户端通过 `network_security_config.xml` 里预置的槽位信任它；
- 别指望装系统证书：`targetSdk >= 24` 的应用默认就不信用户自己装的 CA。往 `/system/etc/security/cacerts`（还有 Android 14 的 `/apex/com.android.conscrypt/cacerts`）里塞，还得搞定只读挂载和 APEX 签名校验。这条路要 root，而且经常 root 了也走不通。
- 免 root 靠的是重打包时换掉 `res/raw/` 里那个 `.cer`，XML 一个字不用动。CA 得成对换（服务端叶子证书 + 客户端信任锚），只换一边就是握手失败。
- 真要装进系统库，文件名必须是 `<subject_hash>.0`，而且 `-subject_hash` 和 `-subject_hash_old` 算出来不一样。名字错了只会报 `Trust anchor for certification path not found`，离真正原因差着十万八千里。

## 补丁库与 hosts

`liblocalpatch.so` hook 了 `getaddrinfo`，直接把 SDK 域名解析到硬编码地址，`hosts` 对它没用。所以只要还留着它，就只能按端口重定向（DNAT 或 tun 规则）。改包之后 SDK 地址写在配置文件里了，这条 hook 不再是障碍；但如果要走 hosts 方案，记得它对客户端无效。

## 反外挂（ACE）

- `libanogs.so` 独立加载，查 Frida、调试、异常注入；
- 关掉 `libUE4.so` 对它的导入（补丁库就是这么干的）会改变 SDK 侧行为，但游戏照样能启动；
- 实测把补丁库整个关停、ACE 保持原样，登录和进游戏的行为一点没变。对本地单机来说它根本不是一道门。
- 当然，别在有正式账号的设备上做这类改动。

## 签名

- 原包是发行方的签名，任何重打包都得重签；
- Android 只校验签名自洽，自己签的也能装；
- 但换了签名就等于换了发行者，覆盖安装旧包必然失败，只能先卸载。卸载会清空 `Android/data` 下那 26 GB 资源，顺序得提前想好。

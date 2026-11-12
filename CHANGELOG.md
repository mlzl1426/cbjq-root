# CHANGELOG

只记录方法、配置与脚本的变化；不涉及任何客户端/服务端二进制。

## v6 · 2026-11-12 — 让下载者「装上就能玩」

### 新增

- `scripts/check-client.py`：只读 APK 索引，5 秒判定一个客户端能否直接连本地服务端（SDK 地址是否指向 `127.0.0.1`、信任锚是否声明、内置 CA 与服务端 CA 指纹是否一致）。`OK` 意味着**原样安装即可，不用改包、不用签名**。
- `scripts/build-client.py`：一条命令完成「换 CA + 改 SDK 地址 + 页对齐重写 zip + v1/v2/v3 签名」，产出可直接安装的 APK。需要改包的人不必再手工走 apktool/zipalign/apksigner。
- `docs/00-quickstart.md`：三步上机（装服务端 → 导入 VPN 配置 → 开游戏），把「只想玩」和「要改包」两条路径彻底分开。

### 修正

- 实测本机保留的 `apk_pull/base.apk`：`XgAuthUrl` 已是 `http://127.0.0.1:21580`，内置 `res/raw/mikusb_loopback.cer` 指纹与本地 CA 完全一致 —— 说明「预置好的客户端」这类包本就无需重签。文档此前默认「改了地址就必须自己重签」，与事实不符。
- `build-client.py` 的对齐规则修正为与 `zipalign -p 4` 一致（stored `.so` 页对齐、其余 stored 条目 4 字节对齐）；只在给 `.so` 做页对齐时校验会放过其它 stored 条目，导致 `zipalign -c` 报 `BAD`。
- `docs/04` 改为「先判断是否需要改包」，把手写流程降为排查参考。

## v5 · 2026-11-12 — 修正「登录后进不去」的归因，仓库整理

### 修正

- **推翻「Activity 回调链断裂」结论**：早期把「登录后停在权限识别中 / 静默退回标题页」判为 SDK 中转 Activity 没把结果回传给 UE4，并主张必须改 dex。后续三组实验证伪——关停上游补丁库让 ACE 恢复原始状态后行为完全相同、垃圾 `RspLogin` 只会卡转圈、正常 `RspLogin` 也照样退回。`strace` 显示登录后零请求零文件访问。
- **真正的四道墙**（写入 `docs/02`）：残留全局 HTTP 代理 / 误劫持 893；serverlist 返回格式不是四字段数组；`cdn_manifest.json` 的 `paks` 为空数组；清单缺 `*_Maps_*` 导致大厅地图加载不了。全部属配置与资源层，与客户端代码无关。
- **`docs/04` 去掉「必须改 dex」的前提**：需要重打包的只有 `sdk_config.properties`、`res/raw/*.cer`、可选的 `liblocalpatch.so` 硬编码域名三处。
- `docs/06` 症状表按新归因重写，并显式注明「不要为此改 dex」；`README` 索引与 TL;DR 同步。

### 新增

- `docs/04` 补「原生库必须页对齐」一节：`extractNativeLibs=false` 时 `.so` 数据偏移须 4 KB 对齐，否则 `Failed to extract native libraries, res=-2`；手写 zip 时用 extra 填充块达成，`zipalign -p 4` 不接受手写 zip64 头。
- `docs/02` 补免 root 装 CA 的真实依据：`targetSdk >= 24` 不信任用户 CA、APEX 有签名校验，所以走 `network_security_config.xml` 预置槽位换 `res/raw/*.cer`。
- `docs/02` 补 `liblocalpatch.so` hook `getaddrinfo` 绕过 `hosts` 这一行为，解释它为何迫使早期方案走按端口重定向。

### 整理

- 首页截图改用 JPEG（3.7 MB → 384 KB）。
- `LICENSE` 版权占位符替换为仓库名；移除 `scripts/__pycache__`。

## v4 · 2026-11-01 — 重打包注入：把反和谐 pak 打进单机客户端

### 新增

- `docs/08-anticensor-modpack.md` §7：单机版注入的完整步骤——从 `assets/main.obb.png` 取出 OBB、把 6 个 pak 放进 `Game/Content/Paks/mods/`、按 central directory 重写 zip32、4 KB 对齐 stored `.so`、v2/v3 重签、卸载旧包重装、邮箱登录 + 重新拉资源。
- `docs/08` §8：新增「obb 里 pak 是否齐全 / 装的是不是自己签的那份」两条检查命令。

### 修正

- **「打不进去」只对原包成立**：v3 列的三条阻塞里，包名/证书与私有目录不可写是真的，但「缺私钥」不等于死路——换一把自签 key 重打包即可，代价是必须卸载旧包、丢掉 26 GB 资源（§5.3、§6 路线 B）。
- **DN 可以照抄，公钥不能**：重签时沿用 `CN=MikuSB Local, OU=Client, O=Local, C=CN` 也无法覆盖安装——Android 比对公钥，key 一变就是新签名。
- **登录不需要 VPN**：客户端 `sdk_config.properties` 里的 `XgAuthUrl` / `SeasunAuthUrl` 本就指向 `127.0.0.1:21580`；无 GMS 时空指针的是游客通道，邮箱登录由上游 `AutoCreateUser` 自动建号。
- **pak 不会被资源更新覆盖**：更新只动 CDN 上的资源清单，pak 在 APK 内置 OBB 里；代价是每次改动 pak 都要重打整包、重装、重下资源。

## v3 · 2026-11-01 — 「反和谐」整合包的结构判定

### 新增

- `docs/08-anticensor-modpack.md`：社区反和谐包的分发形态（MIUI 本地备份）、`apps/<pkg>/{_manifest,a,r,f}` 布局、6 个 pak 的逐个清点，以及「能不能打到单机客户端上」的三条硬阻塞。
- `scripts/miui-backup-list.py`：不解包列出 `.bak` 内的包名、APK 与 `f/` 落点。
- `scripts/pak-inspect.py`：读 pak 版本 / 挂载点 / 条目表，并可解码首个压缩块取 `PF_*` 贴图格式。

### 修正

- **「反和谐补丁」不是补丁**：它是「重签客户端 + 预置 pak」的整包，靠系统备份恢复安装，包名与本项目的 `com.seasun.snowbreak.google` 无关。
- **文件名 `WindowsNoEditor` 不是笔误**：该包 1.06 GB 的立绘 pak 确实是 PC cooked（`PF_DXT5`），Android 端只在支持 S3TC 的 GPU 上才有画面；其余 5 个 pak 是 Lua/DataTable，与平台无关。

## v2 · 2026-10-30 — 资源下载「0%」实测与观测脚本

### 新增

- `scripts/watch-download.sh`：用 `df /data` 剩余空间的增量 + tun 收包计数两个指标，判断"真在下载"还是"真卡住"，完全不依赖游戏 UI 的百分比。
- `docs/05-troubleshooting.md`：新增「UI 停在 0% 也可能在满速下载」一节，附语音包实测数据与判定标准。
- `docs/07-case-report.md`：追加第二轮复现记录（语音包 876.95 MB）。

### 修正

- **「準備更新 95.x%」不是卡死**：该阶段是本地逐文件校验，单核接近满载、磁盘与网络都不增长，属预期行为，校验完直接跳到 100%。
- **资源包的 UI 百分比不可信**：实测全程停在 0%，下载弹窗可以在传输中途自行消失，但字节正常落盘，结束后条目显示「已下載」。

### 清理

- 移除排查期间临时加入的 `reject` 诊断规则；最终配置只保留端口/域名重写规则（见 `configs/sfa-vpn.example.json`）。
- 复核 `include_package` 只含游戏包名：用浏览器访问网页，tun 里看不到浏览器连接，说明只有游戏被纳入。

## v1 · 2026-10-29 — 首版

- 无 root 的 VpnService(tun) 重定向方案：链路、端口、规则写法与三个硬性约束。
- 客户端结构分析、改包与重签约束、启动顺序。
- `scripts/selfcheck.sh`：一条命令检查服务端进程、31000 监听、游戏长连接、tun、游戏进程。

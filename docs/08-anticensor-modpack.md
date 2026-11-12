# 08 · 反和谐整合包：长什么样，能不能用

> 这里只写结构和怎么判断。MOD 包、客户端、资源、解包出来的东西，这里都不放也不镜像，自己合法取得。

## 0. 先说结论

| 问题 | 结论 |
|---|---|
| 这个「补丁」是什么 | 一个重签过的官服客户端（`<上游分发包名>` 3.6.0.122）加 6 个 UE4 pak，打成一份 MIUI 本地备份 |
| 怎么装上 | 原来是靠系统备份恢复整个换客户端；单机版只能重打包注入，见 §7 |
| 能不能打到单机客户端上 | 能，但只能重打包：pak 塞进 `assets/main.obb.png` 的 `Paks/mods/`，换证书重签，卸载旧包再装。已经实测过（§7） |
| 落点在哪 | obb 里的 `Game/Content/Paks/mods/`。装好以后它就是 APK 里的 `assets/main.obb.png` |
| 跨平台怎么样 | 6 个里 5 个是 Lua 和 DataTable，不分平台；剩下那个 1.06 GB 的立绘包是 PC 贴图（`PF_DXT5`），手机上很可能白图 |

---

## 1. 包里都有什么

APK：

| 项 | 值 |
|---|---|
| 包名 | `<上游分发包名>`（官服） |
| 版本 | 3.6.0.122（versionCode 8522） |
| targetSdk | 30 |
| 签名 | 重签过的非官方签名（DN 略） |
| 内置数据 | `assets/main.obb.png` 1,333,546,834 字节（伪装成 png 的 ZIP，UE4 的 OBB） |

pak 都在 `Paks/mods/` 下，全是 patch pak，带 `_P` 的优先级更高：

| 文件 | 大小 | 内容 | 平台相关性 |
|---|---:|---|---|
| `illustration-anti-censorship_99_P.pak` | 1,060,097,773 | 2222 张活动/立绘 CG 覆盖（`.uasset` + `.uexp`） | **PC**（`PF_DXT5`） |
| `Patch_Xpand_AntiAmend_Scene-WindowsNoEditor_100_P.pak` | 132,132 | 17 个 `DT_StandByConfig_*` 数据表（互动待机配置） | 无关（DataTable） |
| `Patch_Xpand_AntiAmend_Plot-WindowsNoEditor_P.pak` | 160,503 | DLC35 剧情蓝图 + 对白文本 | 无关（DataTable / txt） |
| `Patch_NonUFS-WindowsNoEditor_99_P.pak` | 14,042 | `Content/Script/Resource/ResourceAmend.lua` | 无关（Lua） |
| `Patch_Xpand_AntiAmend_Login-WindowsNoEditor_P.pak` | 2,030 | 登录背景场景引用 `login_bg025` | 无关（2 KB 引用资产） |
| `Patch_AntiAmend-Windows_100_P.pak` | 64,334 | `ResourceAmend.lua` + `umg_main.lua` | 无关（Lua） |

说白了，真正起作用的是 Lua 和数据表，那是纯文本和结构数据，安卓照样能用。只有立绘包是 PC 上 cooked 出来的贴图。作者等于把整套 PC 整合包原样塞进了手机备份，文件名里那个 `WindowsNoEditor` 就是证据。

---

## 2. 分发形态：MIUI 本地备份

`.bak` 既不是压缩包也不是差分补丁，结构是固定的：

```
"MIUI BACKUP\n2\n<pkg> <label>\n102\n0\nANDROID BACKUP\n5\n0\nnone\n"   ← 86 字节头部
<未压缩 tar>
    apps/<pkg>/_manifest        包名、版本、签名
    apps/<pkg>/a/base.apk       客户端本体（1.43 GB）
    apps/<pkg>/r/...            应用数据
    apps/<pkg>/f/...            files/ 目录，UE4 pak 落在这里
```

同目录还有个 `descript.xml` 当索引（里面是 `<bakVersion>2</bakVersion>`、包名、`pkgSize`、`bakType=2`），恢复的时候系统读的是它。

恢复流程，不挑机型：

1. 把 `descript.xml` 与 `.bak` 放到设备内部存储的 `MIUI/backup/AllBackup/<时间戳>/`；
2. 设置 → 更多设置 → 备份与恢复 → 手机备份恢复（本地）→ 恢复；
3. 选中该时间戳 → 全选 → 开始恢复；
4. 系统会把 `<上游分发包名>` 装上，再把 `f/` 目录还原到它的私有 `files/` 下。

所以它跟这个仓库干的事根本不是一回事。这边是改一个装好的客户端再把网络重定向过去；它那个是直接换掉客户端，顺手把 pak 塞进私有目录。

---

## 3. 拆开看 pak

用 [`scripts/pak-inspect.py`](../scripts/pak-inspect.py) 读出来的：

| 项 | 值 |
|---|---|
| pak 版本 | 3（UE4 早期格式，向后兼容） |
| 挂载点 | `../../../`（相对 `Paks/` 的父级，即 `Game/Content/`） |
| 索引 | 未加密，可直接解析 |
| 压缩 | `Zlib`，按 64 KB 分块（`CompressionBlocks` 在索引里） |

每个 pak 干的事就是覆盖同名资产。UE4 按 pak 名排序挂载，带 `_P` 的 patch pak 优先级更高，同名资产后面挂的赢。所以文件只要出现在 `Paks/mods/` 里就生效了，客户端一行代码都不用改。

---

## 4. 两边对不对得上

| 维度 | 这边的单机客户端 | 那个 MOD 包 |
|---|---|---|
| 包名 | `com.seasun.snowbreak.google` | `<上游分发包名>` |
| 版本 | 3.6.0.186（8491） | 3.6.0.122（8522） |
| 签名 | `CN=MikuSB Local`（自签） | 非官方签名（DN 略） |
| pak 格式 | UE 4.26 客户端 pak（footer v12，含压缩方法名表） | v3 单文件 pak |
| 贴图格式 | `*-Android_ASTC.pak` | `PF_DXT5`（Windows） |
| 资源版本 | 3.6.0.186 | 3.6.0.122 |

四条：

1. 容器没问题。UE4.26 的 pak 读取器认 v3 pak，`mods/` 目录也能递归挂载。官方客户端自己就是这么加载的，自带 pak 都到 v12 这一代了，说明读取器还在用。
2. 逻辑没问题。反和谐的改动是 Lua 加 DataTable，跨平台。
3. 贴图有问题。立绘包是 DXT5，安卓端 cooked 的是 ASTC。只有部分 GPU（比如 Adreno 走 `EXT_texture_compression_s3tc`）运行时肯吃 DXT5，不认的话那张 CG 就是白图或者不显示，游戏不会崩。
4. 版本有风险。pak 是给 3.6.0.122 的，客户端是 3.6.0.186，`DT_StandByConfig_*` 和 DLC35 剧情这类数据表可能对不上。立绘那种纯按资产名覆盖的反而最稳。

---

## 5. 为什么整个包照搬没用

### 5.1 包名与证书不同

备份恢复是按包身份匹配的。`<上游分发包名>` 和 `com.seasun.snowbreak.google` 是两个不同的 App，恢复只会装出第二份客户端，碰不到现有那个。

### 5.2. 根本写不进去

目标目录是应用私有目录，只有它自己的 uid 写得进去：

```bash
# 数据在内部存储（不是 /sdcard/Android/data）
adb shell dumpsys package com.seasun.snowbreak.google | grep dataDir
#   dataDir=/data/user/0/com.seasun.snowbreak.google

adb shell run-as com.seasun.snowbreak.google   # 不可用：非 debuggable
adb shell "echo x > /storage/emulated/12/Android/data/com.seasun.snowbreak.google/x"   # Permission denied
```

- shell 在 user 12 上连 `/storage/emulated/12` 都写不了，分区存储加多用户隔离；
- `run-as` 要 `android:debuggable="true"`，客户端是 release 版；
- 没有 root，targetSdk 35 也回不到 `Android/obb/<pkg>/` 那种老路径。

### 5.3. 重打包就得换证书

动客户端本体（比如把 pak 塞进 `assets/main.obb.png`）就必须重签。原来那份装的是 `CN=MikuSB Local, OU=Client, O=Local, C=CN`，私钥在打包的人手里，构建脚本里写死的是他自己机器上的路径。

DN 能照抄，公钥抄不了。Android 验的是证书里的公钥，换了 key 就是新签名，覆盖安装直接 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`，只能先卸。

所以重打包不是做不到，是有代价：换签名意味着私有目录连那 26 GB 资源一起清空，装完得重新登录、重新下载。这条路实测走通了，步骤在 §7。

---

## 6. 想真塞进去，就这几条路

| 路线 | 做法 | 代价 | 风险 |
|---|---|---|---|
| A. 备份恢复（官服） | 按 §2 恢复这个包 | 2.4 GB 备份 + 1.4 GB 安装 + 首次启动 26 GB 资源；需要官服账号 | 低（独立安装，可与单机版共存） |
| B. 重打包（单机版） | 把 pak 注入 `assets/main.obb.png` 的 `Paks/mods/`，重新签名后卸载旧包再装 | 换签名必丢数据；2.6 GB 重打包 + 重下资源 | 中（没 root 时唯一不靠上游的路，已实测） |
| C. 服务端/清单注入 | 让客户端「自己下载」pak：劫持资源清单，追加 `mods/*.pak` 条目 | 需要 MikuSB 侧能改清单 + CDN/MITM 可控 | 高（研究性，清单校验未知） |
| D. root | 直接把 6 个 pak 拷进私有目录 | 一次性 | 低，但这个仓库的前提就是没 root |

A 和 D 都不用动客户端。既不想 root 又要在单机版上玩，就只剩 B 了。实测走的就是 B，步骤和结果都在 §7。

---

## 7. 实际动手：把 pak 塞进单机客户端

> 只写方法。APK、obb、pak 和它们解出来的东西，这里都没有。

### 7.1 先准备这些

- 目标：`com.seasun.snowbreak.google` 3.6.0.186，装在副用户（Android user 12）；
- 原始 `base.apk` 与已下载资源可从设备取出（`pm path --user 12`）；
- 自建 keystore（新 key，DN 可以照抄 `CN=MikuSB Local, OU=Client, O=Local, C=CN`）；
- 没有 root，写不进应用私有目录（§5.2），所以只能从 APK 本体下手。

### 7.2 步骤

1. 先取容器。`assets/main.obb.png` 本身就是个 ZIP（UE4 的 OBB），`Game/Content/Paks/` 下是本体 pak，它跟 APK 一起才算完整客户端。
2. 注入 pak。6 个 pak 原样放进 `Game/Content/Paks/mods/`，其余条目一个字节不动。不用重建 pak 索引，也别碰 `AssetRegistry` —— `_P` 后缀的 patch pak 就是靠挂载顺序覆盖同名资产的，原 MOD 能生效全靠这个（§3）。
3. 重写 ZIP。别用 7z 或者 `zip`，按 central directory 一条条重写：
   - 原签名文件全丢掉（`META-INF/*.SF`、`*.RSA`）；
   - 新的 `assets/main.obb.png` 用 stored 写，CRC 重算；
   - `extractNativeLibs=false` 要求 `lib/**/*.so` 也是 stored 且 4 KB 对齐，用 extra field 补 padding；
   - 总大小压在 4 GiB 以内，保持 zip32。长了 zip64 扩展有些安装器不认。
4. 签名：`apksigner sign --v2-signing-enabled true --v3-signing-enabled true`。
5. 安装。换了签名必须先 `pm uninstall`，旧包和数据一起清掉，然后再装。国产 ROM 有些会拦 `adb install`，实际是用该用户里的浏览器打开 `http://127.0.0.1:<port>/xxx.apk`，交给系统包安装器。
6. 登录。客户端 SDK 配置本来就指着 `127.0.0.1:21580`（见 [02-client-analysis.md](02-client-analysis.md)），登录这一步不需要 VPN 参与。没 GMS 的副用户里游客通道会 `ChannelApi.login` 空指针，所以得走邮箱登录。上游的 `AutoCreateUser` 会自动建号，填个合法邮箱加初始密码就行。
7. 资源。登录后客户端自己去官方 CDN 拉 `.../Android_ASTC/updates/manifest.json`，这次 `primeNeed` 2.19 GB、`downloadNeed` 27.4 GB、380 个文件。跟 pak 没关系，pak 在 obb 里，资源更新盖不到它。

### 7.3 跑出来什么样

- 安装：`signatures` 为 v3 方案、`installerPackageName` 指向系统包安装器，进程以该用户的 uid 身份运行；
- 登录：`game.xg.login.success`，本地服务端自动建号并接受长连接；
- pak 挂载：obb 内 `Paks/mods/` 下 6 个 pak 齐全（5 个小 pak + 1.06 GB 立绘 pak）；
- 效果核对与已知风险见 §7.4。

### 7.4 可能出问题的地方

| 现象 | 原因 | 处理 |
|---|---|---|
| 立绘 / CG 白图 | 立绘 pak 是 PC cooked（`PF_DXT5`），ASTC 客户端只在支持 S3TC 的 GPU 上有图 | 重打包时去掉 `illustration-*.pak`，其余 5 个照留 |
| 互动待机配置不生效或异常 | `DT_StandByConfig_*` 面向 3.6.0.122，客户端 3.6.0.186 | 同上，按需删对应 pak 重新打包 |
| 启动崩溃 | pak 与当前资源版本不兼容 | 同上，先只留 Lua 类 pak 做二分 |

换签名重装又是一次清数据。所以删哪个 pak、留哪个，最好在打第一个包之前就想清楚。

---

## 8. 几个随手能用的检查

仓库里有两个只读脚本，纯 Python，不用装依赖：

```bash
# 列出 .bak 里的包名、APK 与 f/ 落点，不解包
python scripts/miui-backup-list.py <file.bak> --filter Paks

# 读 pak 版本 / 挂载点 / 条目 / 贴图像素格式
python scripts/pak-inspect.py <file.pak> --formats
```

看看一台设备能不能直接放：

```bash
adb shell dumpsys package <pkg> | grep -E "dataDir|versionName"
adb shell run-as <pkg> true            # 报错就说明没有写入通道
adb shell pm list packages --user 12   # 确认目标用户
```

看看一个 pak 能不能给安卓用：

```bash
python scripts/pak-inspect.py <file.pak> --formats
# 只出现 PF_DXT* → PC 贴图，Android 大概率白图
# 出现 PF_ASTC_* → 手机端 cooked，正常
```

确认重打包后 pak 真进了 obb（不用解那 2.4 GB）：

```bash
python - <<'PY'
import zipfile
for i in zipfile.ZipFile("main.obb").infolist():
    if i.filename.endswith(".pak") and "mods/" in i.filename:
        print(i.filename, i.file_size)
PY
```

确认装上去的是不是自己签的那份：

```bash
apksigner verify --print-certs game_signed.apk   # 证书指纹
adb shell dumpsys package <pkg> | grep -E "signatures|installerPackageName|lastUpdateTime"
```

---

## 9. 最后总结一下

这包不是补丁，是「重签客户端 + 预置 pak」的整包分发，原样用只能靠系统备份恢复。

但它的资产覆盖方式完全能搬过来：pak 就是往 `Paks/mods/` 里丢文件，不动引擎也不动代码。没 root 的单机版走不通直接拷，走通的是重打包注入加换证书重装（§7）。

代价得提前认清。换签名就是卸载，卸载就是丢 26 GB 资源，所以「删哪个 pak」要在第一次打包之前定下来。6 个里只有 1 个是 PC 贴图，其余 5 个跨平台都能用。

原包那条路（A）也不是没价值：包名跟单机版不一样，两个能共存，互不影响。

## 10. 版权

客户端、资源、MOD 内容的版权归西山居和各 MOD 作者，这里一个文件都不发。

反和谐 MOD 一般来自社区（比如 Nexus Mods 上编号 994 那个整合包），用之前先看看原作者的许可。

所有改动只限个人本地环境，别拿去联机、商业分发，也别用来绕付费内容。

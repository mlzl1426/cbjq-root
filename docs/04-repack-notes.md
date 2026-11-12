# 04 · 改包和重签怎么做

不提供补丁和成品 APK，只写流程和约束。客户端请自备正版。

## 先判断要不要改

多数情况用不着。客户端已经把 SDK 地址指向 `127.0.0.1`、内置 CA 也对得上，原样装就行：

```bash
python scripts/check-client.py <客户端.apk> --ca <服务端根CA.pem>
```

`RESULT: OK` 就到这儿，按 [00-quickstart.md](00-quickstart.md) 上机。只有 `FAIL`（地址还指着远端私服，或者 CA 对不上）才需要往下走。

## 一条命令搞定

确认要改了，用脚本，别手工来：

```bash
python scripts/build-client.py 客户端.apk \
    --ca 服务端根CA.pem \
    --keystore my.jks --ks-alias miku --ks-pass 密码
```

它干四件事，其它条目一个字节不动：

1. `assets/sdk_config.properties` 里 `XgAuthUrl` / `SeasunAuthUrl` / `clientPushDataUrl` 改成 `http://127.0.0.1:<port>`。其它地址保持原样，不然资源下载也被指到本机就下不动了；
2. 把 `res/raw/` 下那个自定义 CA 换成你的服务端 CA。条目名不变，`network_security_config.xml` 不用动；
3. 重写 zip：stored 的 `.so` 按 4 KB 页对齐，其余 stored 条目 4 字节对齐，旧签名丢掉；
4. 用 `apksigner` 签 v1+v2+v3，签完自己验一遍。

产物 `客户端.local.apk` 直接能装。下面几节是实现细节和踩过的坑，手写或者排查的时候翻。

## 为什么必须改包

不是要改游戏逻辑。需要重打包的就三处，目的都是让客户端找得到本地服务端：

| 目标 | 位置 | 改动量 |
|---|---|---|
| SDK 地址指向本机 | `assets/sdk_config.properties` | 字符串替换 |
| 信任本地 CA | `res/raw/*.cer` | 整文件替换（`network_security_config.xml` 已预置槽位，不用改） |
| 可选：关闭上游自带的地址补丁 | `lib/arm64-v8a/liblocalpatch.so` 里写死的域名 | 等长替换，末尾补 `\x00` |

登录之后进不去那几个坑（代理残留、serverlist 格式、资源清单），全在配置和资源上，跟 dex 没关系，`classes*.dex` 不用动。见 [02-client-analysis.md](02-client-analysis.md)。

我一开始把「停在权限识别中」当成 Activity 回调链断裂，主张改 dex 绕过中转页。这个判断后来被实验推翻了：把上游补丁库关停、让 ACE 恢复原始状态，行为一模一样。所以别为这个问题去改 dex，白白多担签名和完整性校验的风险。

## 流程

```
1. 解包原 APK（就是个 zip）
2. 换上要改的文件（assets / res / 可选 so）
3. 动过 dex 的话，重算头里的 checksum（Adler-32）和 signature（SHA-1）
4. 删掉旧的 META-INF，旧签名对新内容已经无效
5. 重新对齐、重签
6. 卸载旧包，装新的
```

## 约束与坑

### 大包

1.5 GB 的包重打包，尽量保留原始压缩流：只换目标条目，其余原样复制。整个重新压一遍会让包体暴涨，见过 1.5 GB 变 2.8 GB 的。

### 原生库必须页对齐

`android:extractNativeLibs="false"` 的包，`.so` 是从 APK 里直接 `mmap` 的，数据偏移必须落在 4 KB 边界上。原包靠 local header 的 extra 字段凑，你重写 zip 时也得照做：往 extra 里塞个 `id=0` 的填充块，把数据顶到页边界。

不做的话报这个：

```
INSTALL_FAILED_INVALID_APK: Failed to extract native libraries, res=-2
```

`zipalign -p 4` 效果一样（`-p` 是页对齐，不是普通 4 字节），但它不认手写的 zip64 头。OBB 这类大包只能手写 zip，padding 得自己补。

### dex 校验（仅当确实改了 dex）

ART 会验每个 dex 头里的两样东西：

- `checksum`（Adler-32）
- `signature`（SHA-1）

改完就得把这两项重算，不然装的时候报 `INSTALL_FAILED_INVALID_APK`，或者运行时校验失败。有 `classes2.dex`、`classes3.dex` 的话，一个一个来。

### 签名

- `jarsigner` 只能出 v1（JAR）签名。Android 7+ 更认 v2/v3，但 v1 在多数设备上照样能装；
- `apksigner` 省事，能一次出 v1+v2+v3，但必须放在 zipalign 之后。先签再对齐会把签名搞坏；
- 重签之后跟商店版本的签名就不是一个了，覆盖安装必然失败，只能先卸载。

### 安装限制（部分国产 ROM）

有些国产 ROM（HyperOS / MIUI 之类）会拦 `adb install`，报 `INSTALL_FAILED_USER_RESTRICTED`。绕法是把包放进设备里，用系统安装器打开：

```bash
# 1) 下载/推送到设备可访问的 Download 目录（多用户设备注意 /storage/emulated/<user>/）
adb push app.apk /sdcard/Download/app.apk

# 2) 用系统包安装器打开（file:// URI），由安装器完成安装
adb shell am start -a android.intent.action.VIEW \
  -d "file:///sdcard/Download/app.apk" \
  -t "application/vnd.android.package-archive"

# 多用户（工作资料 / 隐私空间）需要指定 user
adb shell am start --user <user_id> -a android.intent.action.VIEW \
  -d "file:///storage/emulated/<user_id>/Download/app.apk" \
  -t "application/vnd.android.package-archive"
```

`file://` 指的路径必须是那个用户能读的。指到 `/data/local/tmp` 或者主用户目录一般会被拒，SELinux 把 `shell_data_file` 挡在安装器外面了。

### 资源目录

`Android/data/<pkg>/files/<version>` 是 26 GB 的资源目录，卸载就没了。只想换签名的话先备份、重装再拷回。拷回后客户端还提示要下载，一般是文件属主或权限不对，没 root 修不了，只能重下。

## 安全提醒

- 别在有正式账号的设备上动这些；
- 改包会关闭或绕过部分 SDK 和反外挂逻辑，等于改了客户端的信任边界；
- 别分发改好的包。那是版权作品加上被改过的安全逻辑，出事是分发的人担。

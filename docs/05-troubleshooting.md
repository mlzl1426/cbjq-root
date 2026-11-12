# 05 · 资源更新慢、看着像卡住

## 先说结论

更新慢跟 VPN、Wi-Fi、手机性能都没关系。是客户端在几个境外 CDN 域名之间来回切，其中某个节点特别慢、还老超时。等它自己切走，或者直接把慢节点屏掉。

不过「进度条不动」有三种情况：真慢、真卡、以及 UI 压根没在更新。判断依据只看磁盘增量和 tun 收包数，别看百分比，见文末那一节。

## 现场表现

- 进度条半天不动，30 秒才涨 13 MB 的样子；
- 百分比偶尔往回退，那是先缓存再校验；
- 客户端没崩，日志里全是重试。

## 分层排除

从内往外一层层排，每层都有个数能对照：

| 层 | 方法 | 正常值 | 异常含义 |
|---|---|---|---|
| 局域链路 | 手机/PC `ping` 网关 | 2–5 ms，0% 丢包 | Wi-Fi / 路由器问题 |
| 无线链路 | 设置里看 Wi-Fi 速率 / RSSI | 5 GHz、RSSI > -60 | 距离/干扰 |
| VPN 开销 | `top` 看 sing-box 进程 CPU | < 10% | 规则太复杂或栈不对 |
| 运营商→CDN | PC 上**不用 VPN** 直接 `curl -r` 同一 URL | 见下 | CDN 路径问题 |
| 本地宽带 | 从国内镜像下一份大文件 | 10 MB/s 以上 | 家宽本身慢 |

只要 PC 不挂 VPN 直连同一个 URL 也慢，那跟手机和 VPN 就没什么关系了。

## 资源 CDN 的几个域名

资源从几个域名来，客户端会轮着用，实测最快最慢差了三十倍：

| 域名形态 | 备注 |
|---|---|
| `snowbreak-dl.<cdn>` | 主域名，中等 |
| `snowbreak-dl-akm.<cdn>` | 某个海外 pop，特别容易超时，最慢 |
| `snowbreak-dl-aws.<cdn>` | 另一个海外 pop，单连接也快，多连接可跑满 |

客户端会按失败次数自己切。慢的时候日志里一般跟着这些：

```
UNKNOWN_IO_ERROR ×N
CONNECTION_TIMED_OUT ×N
HTTP_NOT_FOUND ×N
```

## 看日志

每次下载的结果都打在 `xgsdk` 这个 tag 下：

```bash
adb logcat -d | grep game.updateres | tail -20
```

关键字段：

| 字段 | 含义 |
|---|---|
| `source` | 本次命中的 CDN 域名 |
| `downloadsize` / `realsize` | 本次下载字节数 |
| `reason` | 失败原因（超时/IO 错误等） |
| `download` | 成功事件里带实际耗时 |

拿一次成功事件里的 `realsize` 除以耗时，真实速率就出来了，比看 UI 靠谱得多。

## 看整机速率

```bash
# 连续两次采样 /proc/net/dev，算 wlan0 rx 差值
adb shell "grep wlan0 /proc/net/dev"
```

有些机型读 tun 的 sysfs 会 `Permission denied`，那就用 wlan0 的 rx 近似。反正走 VPN 的流量最后也是从 wlan0 出去。

## 可选：把最慢的节点屏掉

确认某个域名稳定地慢，就在 sing-box 规则里给它加一条 `reject`，让客户端赶紧失败好切下一个：

```json
{"domain_suffix": ["<慢节点域名后缀>"], "action": "reject"}
```

代价是要重启 VPN，正在进行的下载会断。最好趁大版本更新前配好，别等卡住了临时改。

这条只适合确认稳定极慢的域名。排查时我临时用它验证过慢节点这个假设，后来 `-aws` 节点能跑到 9–13 MB/s，诊断规则就撤了，最终配置里没有任何 `reject`。

## 空间

完整资源二十多个 GB，更新前先看一眼剩多少：

```bash
adb shell df -h /data
```

空间不够的时候客户端要么静默失败，要么反复重下。

## 进度条停在 0%，其实在满速下

### 现象

在「資源下載」里勾一个语音包（中文配音 876.95 MB）下载，UI 就卡在「下載中：0%」不动。过一会儿弹窗自己消失了，但磁盘还在掉、tun 还在收包。回列表一看，条目已经是「已下載」。

### 实测数据

| 时刻 | 磁盘剩余 | tun0 入向累计 | 说明 |
|---|---|---|---|
| 13:43:36 | 41,278,256 KB | 31,690,383,295 B | 已点「下載」，UI 0% |
| 13:43–13:45 | 不变 | 不变 | 无流量、无写盘（约 2 分钟） |
| 13:46:07 | 40,860,152 KB | 32,137,144,053 B | 已开始下载 |
| 13:46:37 | 40,379,168 KB | 32,646,975,674 B | 传输中，弹窗已自行消失 |
| 13:47:08 | 40,379,144 KB | 32,646,983,222 B | 列表显示「已下載」 |

算下来磁盘少了 `899,112 KB`，差不多 878 MiB，跟包体 876.95 MB 对得上；tun 累计涨了约 956 MB，含 TLS 和重传开销；瞬时速率 9–13 MB/s。字节全传到位了，只有百分比没动。

### 为什么会这样

下载是游戏进程里 `libUE4.so` 自带的原生下载器干的。之前日志里每秒刷一条「后台监听 / DownloadTaskManager」，我以为是它，后来发现是同空间里那个「薄荷下载」`com.yfoo.mintdownloader` 打的，跟游戏没关系。

弹窗里的百分比走的是客户端自己的进度回调，客户端连本地服务端这个组合下，回调没正常回传也没渲染，所以 UI 永远是 0%，弹窗状态机还会提前收尾。这是显示问题，跟 VPN 规则、服务端转发都没关系。

翻了 `libUE4.so`（187 MB，stripped）和 `classes.dex`，可以确定这层回传根本不存在：

| Java 侧 `GameActivity` 里的 thunk | `UEDownloadManager` 里的实现 | `libUE4.so` 是否引用该 thunk 字符串 |
|---|---|---|
| `HttpFetch_Enqueue` | `enqueue(url, path, size, hash)`，`needDownloads += size` | **否** |
| `HttpFetch_GetStatus` | `getStatus()` | **否** |
| `HttpFetch_GetTotalDownloadSize` | `getTotalDownloaded()` = `completedSize + downloadingSize` | **否** |
| `HttpFetch_GetContentLength` | `getContentLength()`（只是当前文件总长） | 是 |
| `HttpFetch_GetDownloadResult` | `getDownloadResult()`（每个文件完成/出错的结果串） | 是 |
| `HttpFetch_StartOrResume` / `_Suspend` / `_Resume` / `_ClearAll` / `_AddAvailableFileServer` / `_ClearAvailableFileServer` / `_EnableOrDisableCheckMD5` / `_SetNotificationMsg` | 同名方法 | 是 |

也就是说，逐字节进度在 Java 层其实算得出来（`getTotalDownloaded` 除以总字节数），但原生代码从来不调。原生每次轮询只能拿到「当前文件总长度」和「某某文件已完成」这种字符串，所以百分比只能按整个文件跳。语音包正好是一个 876.95 MB 的整包，完成前是 0%，完成瞬间到 100%，跟实测完全对得上。

`fetch2` 那套通知栏进度本来也该看见，实际看不见。两个原因：应用 `targetSdk=35`，`POST_NOTIFICATION` 的 appops 是 `ignore`，通知被系统静了；另外 `classes.dex` 里除了 `GameActivity` 自己，没有别的类调 `UEDownloadManager.enqueue`，`libUE4.so` 也不调那个 thunk，队列一直是空的。这条通知路根本没跑起来过。

### 能不能修

- 修不了，也不值得修。百分比是 `libUE4.so` 算完自己渲染的，想让它逐字节跳就得改机器码，跟补丁、签名、多用户安装这一整套流程打架，收益太低。
- 想看进度，换个地方看：
  1. 开状态栏的实时网速。下载时一直显示 10 MB/s 上下，停了掉回几 KB/s，一眼就知道还在不在动。
     命令（加 `--user <id>` 指定副用户，也可以在设置 → 通知与控制中心 → 状态栏里手动开）：
     ```bash
     adb shell settings --user 12 put system status_bar_show_network_speed 1
     ```
     注意游戏全屏时状态栏是藏起来的，得从顶部往下拉一下；切后台就一直看得见。
  2. `bash scripts/watch-download.sh 10 877`，看磁盘和 tun 计数，带上包体大小就直接出百分比，这个最靠谱；
  3. 把语音包当成一次整包传输，大小已知（876.95 MB），拿瞬时速率估个剩余时间；
  4. 结束以列表条目变成「已下載」为准，别信百分比。

另外顺手把游戏的通知权限放开了（`appops set --user 12 com.seasun.snowbreak.google POST_NOTIFICATION allow`）。不过前面说了，原生代码从不往 Java 下载队列投任务，游戏自己不会发下载通知，放开只是排掉「被系统屏蔽」这个变量。

### 怎么处理

1. 别杀进程、别清游戏数据、也别反复点下载。重复点会打断正在传的那次。
2. 用脚本看客观指标：

```bash
bash scripts/watch-download.sh 10
```

   磁盘在掉、tun 在涨就是在下载。连着三次两个都不动，才值得怀疑。
3. 等条目变成「已下載」再进游戏。

### 顺便说一句：`準備更新` 停在 95% 也不是卡死

主资源更新还有一个看着像卡住的地方：`準備更新` 走到 95% 左右停住，`df` 不降、tun 不涨，但游戏主进程单核跑到 90%，161 个线程在转。那是本地逐文件校验，验完直接跳 100%。判断方法跟上面一样，看磁盘、tun、CPU，别看百分比。


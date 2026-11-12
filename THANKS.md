# 致谢与上游归属

这套客户端方案是站在别人肩膀上做的。下面这些项目的作者和贡献者，是它能跑通的前提，顺手点个 star 吧。

## 服务端：MikuLeaks / MikuSB

- 仓库：https://github.com/MikuLeaks/MikuSB
- 许可证：MIT
- 它是什么：C#/.NET 写的开源服务器模拟器（`SdkServer` / `GameServer` / `Proxy` / `Proto` / `TcpSharp`）
- 贡献者：
  - **Naruse** — https://github.com/DevilProMT
  - **Kei-Luna** — https://github.com/Kei-Luna

MikuSB 的源码和二进制这里一个都没有。服务端怎么部署、怎么编译，直接看它自己的仓库。

## 客户端补丁思路：Kei-Luna / MikuSB-Patch

- 仓库：https://github.com/Kei-Luna/MikuSB-Patch
- 干什么的：Windows PC 侧的注入补丁。hook `WS2_32` 的 `getaddrinfo` / `connect` / `WSAConnect`，把连接改到 `127.0.0.1`，顺便关掉 SSL 校验（`bVerifyPeer`）和 `WITH_XGSDK`。
- 启发在哪：把连接改到本机这件事，完全可以不碰客户端逻辑，只在网络层做。安卓上没法加载 Windows DLL，所以换成 VpnService 的规则重写，目标一样。

## 网络层：sing-box / SFA

- sing-box：https://github.com/SagerNet/sing-box
- SFA（Android 客户端）：https://github.com/SagerNet/sing-apk
- 这里只放配置文件，二进制一个不发。SFA 和 sing-box 各按自己的许可证走（GPLv3 之类）。

## MIT 许可声明（MikuSB）

```
MIT License

Copyright (c) MikuSB contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 致谢社区

还得谢谢最早把「手机单机」跑通的那批无名打包者。端口表、SDK 地址表跟 CA 槽位的玩法、pak 的挂载点，这三件事都是从他们的包里看出来的，这边就是照着这些重新做了一遍。作品本身没分发，名字也不点了，版权归他们。

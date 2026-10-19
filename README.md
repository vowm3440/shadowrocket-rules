# Shadowrocket 独立分流与去广告自动更新方案

首次交付构建日期：**2026-10-18，北京时间**。实际拉取了上游数据，生成完整规则，并做了静态验证。每个来源的获取时间、内容 SHA-256 和上游版本提示见 `manifest.json`。**今天构建不代表每个上游今天都维护过。**

本仓库为 **`vowm3440/shadowrocket-rules`**，默认分支 `main`。不包含代理节点、机场订阅密码或 MITM 证书私钥。

## 1. 在 Shadowrocket 使用远程配置

| 用途 | 远程地址 |
| --- | --- |
| 分流主配置 | https://raw.githubusercontent.com/vowm3440/shadowrocket-rules/main/routing.conf |
| 独立广告模块 | https://raw.githubusercontent.com/vowm3440/shadowrocket-rules/main/adblock.sgmodule |
| 广告列表（查阅用） | https://raw.githubusercontent.com/vowm3440/shadowrocket-rules/main/adblock.list |

1. 在 Shadowrocket 首页添加你已有的节点/机场订阅，选一个可用的默认节点。
2. 配置 → 右上角 `+` → 输入上面的主配置地址 → 下载 → 点文件 → **使用配置/编译配置**。
3. 首页选中可用节点（单节点也适用），再将“全局路由”选择 **配置**。r3 的 `ProxySelect` 默认使用首页所选节点；不用先等 Auto 测速。
4. 配置 → 模块 → `+` → 输入广告模块地址 → 下载并启用 → 重新编译配置。域名过滤不需要证书。
5. 在模块页关闭 `Independent-AdBlock`，即可关闭本方案全部去广告；主配置的分流继续工作。若还装了其他广告模块，它们仍会独立生效。
6. 知乎/微博的 HTTPS 路径与信息流过滤，需要按第 4 节在本机设置 MITM。**v2 更新及广告残留排查见 [`docs/adblock-v2.md`](docs/adblock-v2.md)**；不向本仓库上传 CA 私钥。

每天北京时间 **07:50** 由 GitHub Actions 调度更新，08:00 的 iOS 设置见 `docs/ios-0800.md`。源拉取或校验失败时不发布空规则。GitHub/iOS 的准点限制见第 5、6 节。

### 仓库维护

首次运行与手动刷新：打开本仓库 **Actions → Update Shadowrocket rules → Run workflow**。确保仓库允许工作流写入内容；受保护分支规则可能限制 bot 推送。

日常修改 `templates/`、`local/` 或 `sources.json`，工作流会重新生成全部产物。不要只修改生成的 `routing.conf` 或 `adblock.list`。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build.py --repository vowm3440/shadowrocket-rules --branch main
python3 scripts/validate.py
```

`settings.json` 已绑定当前仓库；`node_filter` 默认 `.*`，可筛选节点名称。`quic_block: false` 会在下次构建并更新模块后关闭 UDP/443 拦截。

## 2. 文件与解耦关系

| 文件 | 用途 |
| --- | --- |
| `routing.conf` | 完整主配置、加密 DNS、策略组与六层分流 |
| `adblock.sgmodule` | v2 独立模块：广告列表、UDP/443、知乎/微博广告路径与响应脚本、精确 MITM 主机 |
| `adblock.list` | 清洗、合并、去重并扣除白名单后的广告域名 |
| `rules/*.list` | Direct/Unbreak、AI、Telegram、流媒体、Apple/Microsoft、Proxy、LAN/CN 等分流子集 |
| `objects/<SHA256>.list` | 按内容寻址的子规则；生成配置实际引用这里，避免同一 URL 内容变化 |
| `scripts/domestic-ads.js` / `objects/<SHA256>.js` | 本地维护的原生响应过滤脚本及不可变发布副本 |
| `manifest.json` | 当前完整构建的版本、源哈希、规则数和输出文件哈希 |
| `whitelist-removed.tsv` | 本次剔除的白名单冲突广告规则，便于排查 |
| `local/*.list` | 持久维护本地补充规则与广告白名单 |
| `sources.json` | 所有真实上游地址及格式、最低条目数 |
| `scripts/build.py` | 并发拉取、格式校验、规则合并、白名单扣除、版本化输出 |
| `.github/workflows/update-rules.yml` | 北京时间每天 07:50 调度，校验成功后统一提交与推送 |
| `docs/ios-0800.md` | 08:00 个人自动化、URL Scheme、缓存与验收的详细步骤 |
| `docs/2026-10-18-snapshot.md` | 今天实际构建的统计与验证记录 |

## 3. 分流设计与实际取舍

主配置的六层顺序是：Direct/Unbreak 修正 → AI/Telegram/流媒体/Apple/Microsoft 专项 → 境外 Proxy/GFW 域名 → LAN/中国域名 → 中国 IP/GEOIP → `FINAL,ProxySelect,dns-failed`。DIRECT 使用内置策略，不重复创建同名组；`ProxySelect` 是自定义总代理，第一项 `PROXY` 是 Shadowrocket 内置的首页所选节点；Auto/Fallback 为可选模式，额外筛选设备节点。这样即使正则未发现节点、测速尚未完成或测速网址不可用，默认路径仍能使用手动导入的节点。自定义组不使用与内置 `PROXY` 近似的名称。AI 与流媒体另有手动出口组。

中国域名集合放在第四层，不放进第一层白名单，避免提前吞掉 AI 等专项规则。上游 Unbreak 中与 AI/流媒体等域名相交叠的条目会扣除；Unbreak 只保留精确域名/后缀，省略宽泛关键词与 UA 规则。**最终匹配还受 Shadowrocket 编译器的域名/IP 优先与 GeoIP 推断排序影响，不能把文本顺序理解为跨所有规则类型的绝对顺序。**

所有 IP 子条目统一带 `,no-resolve`，包含 IP 的主配置 `RULE-SET` 也带该参数。它的作用是**不为了判断 IP 规则额外触发域名解析**；不会修复已经污染的 DNS，也不阻止直连建立连接所需的正常解析。未被中国域名集覆盖的国内域名可能直接进入最终代理，这是坚持 `no-resolve` 的代价。

国内直连域名使用 AliDNS/DNSPod DoH，境外默认/备用 DNS 使用经默认代理的 Cloudflare/Google DoH；节点域名有单独的国内加密引导解析，国内 DoH 的引导 IP 在 `[Host]` 中固定。DoT 替代写法见主配置注释。没有把国内和国外 DNS 混在一组并发争抢结果，也没有主动设置明文备用 `system`。`#proxy` 以首页默认节点为准，不要误认为必定跟随自定义 `ProxySelect` 组。

`ipv6=false` 是偏兼容的初始值，**不是系统级防泄漏承诺**。IPv6-only/NAT64 网络、系统绕行流量和 App 自带 DoH/DoT 需要另外实测。`hijack-dns=:53` 仅处理进入隧道的传统 DNS。`tun-excluded-routes` 只旁路本地/保留网络，不旁路 Fake-IP 常用的 `198.18.0.0/15`；使用 Tailscale 时请注意 CGNAT 地址段 `100.64.0.0/10` 的交互。

## 4. 广告、QUIC 和 MITM

广告来源选用 anti-AD 与 blackmatrix7 的 AdvertisingLite 域名集，只取 `DOMAIN`/`DOMAIN-SUFFIX`，不导入宽泛广告关键词和共享广告 IP。相同条目以及被上级后缀覆盖的条目会合并。Loyalsoldier 用于境内外分流与中国 IP。全部源地址及各自许可见 `SOURCES.md`、`licenses/`。

模块规则优先于主配置，所以**主配置顶部的 Direct 白名单不能救回已经被模块拒绝的请求**。脚本先从广告列表移除 `local/ad-allow.list`、Direct/Unbreak 中的保护域名；如果广告后缀覆盖了受保护子域，也删除该广告后缀。新增白名单不会强制服务直连，而是恢复原来的分流策略。这个保守策略会允许部分统计请求，换取登录、推送、支付的兼容性。

用户指定的 UDP 规则需要改为 Shadowrocket 的正确端口键：

```ini
AND,((PROTOCOL,UDP),(DST-PORT,443)),REJECT
```

它让支持 TCP 回退的 HTTP/3 请求回到 HTTP/2/HTTP/1.1，方便路径级重写；**QUIC 并不会天然绕过域名/IP 规则**。全局阻断 UDP/443 可能降低连接速度，某些只支持 UDP 的功能可能失败。它也不阻断所有端口上的 QUIC。移除或关闭此条不会影响主配置的六层分流。

域名层无需安装证书。要启用模块中的 HTTPS 路径重写：

1. 点击正在使用的配置后面的 `ⓘ` → HTTPS 解密 → 证书 → 生成并安装 CA。
2. iOS 设置 → 通用 → VPN 与设备管理，安装描述文件；通用 → 关于本机 → 证书信任设置，信任该 CA。
3. 回到同一配置启用 HTTPS 解密。支持的版本可开启“通过 HTTP/2 进行 MITM”；它不等于 HTTP/3 解密。
4. 只使用模块列出的精确广告接口主机，保持 `hostname = %APPEND% ...`。不加 `*` 或整个银行/支付/Apple 登录/推送域名；检查其他已装模块是否扩大了解密范围。
5. CA/私钥仅保存在设备。远程配置重装可能重置本地解密设置；可按 Shadowrocket 的“证书模块”方法在本机单独保留证书，**不要提交到公开仓库**；否则更新后需在设备上重新选择已有证书。

这样能缩小 MITM 干预范围，但**不能保证网银/支付绝不风控**：VPN、出口 IP、设备状态也可能被检测。如果某个 App 有证书锁定，优先撤掉对应精确解密主机，保留域名广告过滤。

URL Rewrite 覆盖少数已知广告接口。`reject-dict` 返回空 JSON、`reject-200` 返回空 200、`reject` 拒绝请求；返回值必须符合客户端预期，不能保证所有版本不卡顿。v2 增加本仓库维护的 `scripts/domestic-ads.js`，对精确接口中的知乎/微博广告标记做响应过滤，通过 `objects/<SHA256>.js` 发布，不自动导入第三方脚本。脚本不改会员/账号，遇到新结构或异常保留原响应。MITM 解密是 HTTPS 重写和响应脚本生效的共同前提；更新主配置不等于更新模块。**本方案不承诺去掉 YouTube 原生 App 视频中插广告，也不承诺清除知乎/微博或所有国内 App 的全部广告。** 详细覆盖和排查见 `docs/adblock-v2.md`。

## 5. 每天 07:50 更新与缓存处理

工作流包含准确的 `50 23 * * *`，即 UTC 23:50，对应次日北京时间 07:50。它在默认分支执行，可手动触发，也会在源定义/模板/本地规则修改后执行。全部来源获取成功、格式正常并达到最低条数后，才生成完整结果；源失效、HTML 错误页、无效规则或验证失败均退出，不把空规则提交到仓库。最终一次 commit/push 发布主配置、模块及其所需对象。

脚本不执行上游代码，不把远程响应当 shell；只解析声明的规则类型。保留抓取哈希、获取时间、上游版本提示、跳过的 UA/URL 类型数量。`.cache` 仅供本地离线复现，工作流每次重新拉取。初次包内不放缓存，避免重复膨胀；完成首次在线构建后可用 `--offline` 复现。内容寻址对象不要随意删除：旧配置可能仍在引用。

Raw 分支地址可能受到数分钟 CDN 缓存影响，“07:50 到 08:00 有十分钟”**不是刷新保证**，也无法通过修改仓库文件来设置 GitHub Raw 的 HTTP 缓存响应头。`?t=时间戳` 和请求端 `Cache-Control: no-cache` 只能改善请求新鲜度，不能保证构建已完成。

本方案分两层处理：

1. **子规则不可变：**配置引用 `objects/<完整 SHA256>.list`，同一路径永不覆盖，旧版与新版不会在同一规则 URL 上争用缓存。稳定的 `rules/*.list` 与 `adblock.list` 便于人工查阅，运行配置实际引用内容对象。
2. **主配置锁定提交：**08:00 快捷指令先通过 GitHub API 取得默认分支的完整 commit SHA，再从 `raw.githubusercontent.com/vowm3440/shadowrocket-rules/<SHA>/manifest.json` 检查构建日期，然后从同一 SHA 导入 `routing.conf` 与所需模块。具体步骤见 `docs/ios-0800.md`。主配置自身的 `update-url` 仍是稳定分支 URL，普通后台更新是便利兜底，不具有这条快捷指令的版本确认能力。

GitHub 官方明确说明 schedule 可能排队、延迟甚至丢弃；非默认分支不按该计划运行，公开仓库长时间无活动也可能暂停 schedule。自建 cron/外部调度只能改善服务端触发，不能消除 iOS 执行限制。**不能承诺每天 08:00 一定已经生成并在手机上生效。**

## 6. iOS 08:00 的可落地范围

完整操作教程见 **`docs/ios-0800.md`**。支持的 Scheme 使用：

```text
安装/使用配置：shadowrocket://config/add/https://raw.githubusercontent.com/vowm3440/shadowrocket-rules/COMMIT_SHA/routing.conf
安装模块：shadowrocket://install?module=URL编码后的完整模块URL
更新节点订阅：shadowrocket://update-subs
```

其中 `update-subs` **不是规则更新接口**。没有查到可据此保证静默更新并编译所有配置/模块的公开 Scheme；本方案不编造 `update-config`/`update-rules`。

“快捷指令 → 自动化 → 特定时间 → 每天 08:00 → 立即运行”能安排当时尝试任务；锁屏、重启后未解锁、跨 App 打开 URL、导入确认、断网或系统调度都可能让实际应用延后。把 `autoclose=true` 加进 URL 也不会赋予后台权限或证明更新成功。**严谨交付是“08:00 尝试、校验版本、失败保留旧版、必要时提示手动完成”，不是无法验证的准点静默保证。**

## 7. 单个 VLESS/REALITY 节点与实机排查

2026-10-19 的 **r3** 改为默认直接使用首页所选节点，保留六层分流、加密 DNS 和独立广告模块。节点凭据继续只在设备中保存；公共 `routing.conf` 不包含节点服务器、UUID、REALITY 公钥或短 ID。

Karing/sing-box 的完整 JSON 不是 Shadowrocket 主配置，也不是可直接粘贴导入的单节点链接。请先将对应 VLESS 节点导入 Shadowrocket，再使用本仓库分流配置。对 **TCP + REALITY + Vision**，核对以下字段：

| 字段 | 设置 |
| --- | --- |
| 类型/传输 | VLESS；TCP/RAW（无 WebSocket/gRPC） |
| TLS/安全 | REALITY；保留原节点 SNI、公钥、短 ID |
| UUID | 与服务端一致 |
| Flow/XTLS | `xtls-rprx-vision`（Vision） |
| 指纹 | `chrome` |
| ALPN | 默认/留空，不强制单独的 `h3` |
| 允许不安全、Mux、代理转发/Proxy Pass | 初次连接时关闭或留空 |

这类节点的外层是 TCP；广告模块的 UDP/443 拦截不会直接拦截外层 TCP/443。更改分流配置无法自动修正首页已保存的错误节点参数。若同一节点在“全局路由 → 代理”也不能访问 HTTPS，需要检查节点字段、客户端与服务端版本和服务端可达性，不能只归因于分流规则。

当前环境不能直连任意外部 TCP 端点（返回 `Network is unreachable`），因此未验证用户节点的 REALITY 握手，也未操作用户 iPhone。配置编译和手机联网仍需按下列步骤实测。

### 实机验收与故障定位

1. 先仅启用主配置。检查节点、境内网站、ChatGPT/Claude/Gemini、Telegram 与各流媒体；在数据 → 代理日志中确认实际命中的策略。
2. 启用广告模块并编译。比较广告域名的拒绝记录；域名过滤不需要 MITM，只有精确 HTTPS 路径规则需要。
3. 逐个启用需要的解密主机，检查知乎/微博的对应广告接口。登录/支付/推送异常先停该模块验证，再把误杀域名加到广告白名单并重新构建。
4. APNs 不被广告集拦截，但 Telegram 后台通知是否及时还取决于 iOS 推送链路。若 APNs 直连异常，可实测把 Apple 组切至可用代理；不要解密 `push.apple.com`，也不要把更改隧道系统开关当通用保证。
5. 查看配置 → 编辑配置 → 规则集 URL，确认所有对象下载成功，然后使用/编译配置。只查看 Raw 文件日期不能证明手机已下载并编译。
6. 分别在解锁和锁屏状态下，将自动化临时设为两分钟后测试；确定真实行为后恢复 08:00。首次手动授权联网和打开 Shadowrocket。

已做的验证范围是 Python 解析、白名单/去重回归、输出哈希、IP 的 no-resolve、模板层级、重写/脚本引用和 11 组合成响应检查（需要 Node.js）。**没有连接到你的 iPhone，未做 Shadowrocket 真机编译、广告效果和锁屏自动化测试。**

## 8. 核实依据

- Shadowrocket 当前社区手册（非厂商官方）：https://github.com/LOWERTOP/Shadowrocket/wiki
- Shadowrocket 官方 App Store 更新记录：https://apps.apple.com/us/app/shadowrocket/id932747118
- 规则源与格式说明：https://github.com/blackmatrix7/ios_rule_script/tree/master/rule/Shadowrocket
- Loyalsoldier：https://github.com/Loyalsoldier/surge-rules
- anti-AD：https://github.com/privacy-protection-tools/anti-AD
- GitHub schedule 限制：https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- Apple 特定时间触发：https://support.apple.com/guide/shortcuts/apd932ff833f/ios
- Apple 个人自动化：https://support.apple.com/zh-cn/guide/shortcuts/apd602971e63/ios
- Apple 打开跨 App URL 会启动到前台：https://developer.apple.com/documentation/uikit/uiapplication/open(_:options:completionhandler:)

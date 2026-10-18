# vowm3440 远程配置部署

公开仓库： https://github.com/vowm3440/shadowrocket-rules
默认分支：`main`。

- 分流主配置：https://raw.githubusercontent.com/vowm3440/shadowrocket-rules/main/routing.conf
- 广告模块：https://raw.githubusercontent.com/vowm3440/shadowrocket-rules/main/adblock.sgmodule
- 广告列表：https://raw.githubusercontent.com/vowm3440/shadowrocket-rules/main/adblock.list

工作流调度：`50 23 * * *`，对应北京时间每天 07:50。
当前规则构建版本与源获取记录见根目录 `manifest.json`，GitHub Actions 执行结果在仓库 Actions 页面查看。

08:00 iOS 更新方式与无法保证锁屏准点完成的边界，见 `ios-0800.md`。

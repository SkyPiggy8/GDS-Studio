# 验证记录

日期：2026-10-10；本机 Windows 11 / Python 3.12.7 / PySide6 6.8.3。该记录描述本次实际执行结果。

- **72 项测试通过**：原有 63 项，加上向量去重与孔洞 / 拓扑 / D4 / 缩放；来源保留；未标定策略；Cell、连通、递归区域、路径面积化；超限与取消撤回；训练分组；图库到编辑器修正；后台进程；真实 PDF 渲染入口。
- 测试进程退出码 0；修复了 Qt 图层勾选期间销毁 tree item 的生命周期问题，并处理了应用退出时 Python MIME 数据释放顺序。
- 真实生成 `starter.gds`、`catalog.gds`、`line_space_sweep.gds`、`trace_result.gds`，附工程与 manifest；KLayout 独立回读摘要在 `examples/independent_verification.json`。
- `catalog.gds` 包含全部 41 类结构；`line_space_sweep.gds` 包含 20 个线宽/间距组合；`trace_result.gds` 对应示例输入图片，包含真实孔洞。
- Windows 原生 Qt 渲染截图：`examples/ui-preview.png` 与 `examples/image-import-preview.png`。人工检查了中文字形、面板和数值字段、图像覆盖对齐、孔洞、标定与导入状态。
- PyInstaller 目录桌面包启动退出码 0；`--self-check` 实际导出 47 个多边形、9 个 Cell、面积 66864 nm²，GDSTK 回读验证通过，并保存窗口截图。证据在源码目录 `userdata/packaged-check/desktop-check.json`。
- `pip check` 通过。GUI 依赖曾因新版 DLL 导入问题失败，已固定 Qt 6.8.3 并验证源码与桌面包入口。

v0.2 的额外验证：

- 真实公开论文预印本 Figure 4(a) 提取 31 个闭合轮廓与一个完整结构；保存裁剪、mask、工程、GDS 和回读 manifest。未标定、待审核；不是实际 3 nm PDK。
- 合成大文件 **217601688 字节 / 207.52 MiB / 3400000 个多边形 / 40 层 / 40 条文字备注**。生成 5.82 秒，层级索引 0.87 秒，ROI 读取和提取 1.16 秒。ROI 包含 100 个几何，10 个新样本 / 90 个尺寸重复。可复现 tools/large_layout_check.py，证据 userdata/large-check/report.json。
- 源码与 PyInstaller 发行版实际运行「后台索引 → 递归 ROI 提取 → 样本库分页渲染」，退出码均 0；发行版使用上述 207.52 MiB 文件。证据 userdata/library-packaged-check/library-check.json 与两个窗口截图。

未拿到用户真实大文件、检测程序输入规范或商业工艺 PDK，尚未完成这些输入上的集成验收。合成测试不保证复杂全芯片文件耗时；没有曝光 / 抗蚀剂 / 蚀刻 / CMP 仿真。

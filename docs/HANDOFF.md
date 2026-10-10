# 本地 agent 开发交接

## 入口

- 源码根目录即本文件上两级的 GDS，运行 `main.py`。
- 先读 README、ARCHITECTURE 与测试，禁止改变 nm/y-up 约定。
- `.venv` 为当前电脑的独立环境，不可把它当成可迁移的源码依赖。requirements 和锁定文件是安装入口。
- UI 使用 PySide6 **6.8.3**：当前电脑首次安装更新的 Qt 版本出现 DLL 入口加载问题，因此选择固定版本并测试。不要无理由更新到不同 Qt 版本。
- gdstk/shapely/OpenCV 均通过公开库接口使用，没有 fork 第三方源码。

## 保留的数据

- Pattern key、Shape.id、Layer/Datatype 与工程 version 必须稳定。
- 图像提取产生的物理标定要保留，不得根据图像像素猜测节点尺寸。
- 导出 manifest 的 patterns 列表与 GDS Cell 对应，是外部检测对接入口。
- 临时按 1 nm/px 导入的对象 metadata.calibrated=False；缩放可改变坐标，但不应自动标记标定成功。

## v0.2 样本库交接

阅读 SAMPLE_LIBRARY.md。library.py 管 SQLite，matching.py 管向量匹配，layout_source.py 管 KLayout 层级数据库，jobs.py 是可替换的后台进程入口，dataset.py 是数据集出口。现有编辑器可通过 add_library_shapes() 接收样本。默认按 Cell 定义，不展开阵列；递归 ROI 是显式选项。

当前已支持单多边形、连通、Cell 和 ROI 的逐层提取；精确与同形检索；论文 PDF 页裁剪；来源与审核；分层图谱与 mask 数据集。图库分页 80，提取默认上限 20000 几何 / 10000 样本。超限整批事务撤回。

测试包括 207.5 MiB / 340 万多边形 / 40 层合成文件索引和 ROI。未完成真实 foundry 文件验收。解析加载整个 KLayout 数据库到工作进程内存；不能称为流式解析。文字备注从独立 Cell 定义有界收集，不能称为所有实例的 ROI 标签索引。

KLayout 现在为运行依赖；当前 wheel GPL-3.0-or-later。构建时保留分发许可证、自有源码和上游源码归档，并备份旧桌面包的 userdata / examples / user_plugins。不要再排除 klayout。

## 编辑器当前边界

- 编辑画布最多 50000 多边形；有界遍历后展开。文件 ≥20 MiB 自动交给样本库后台索引。超大阵列应从样本库按区域提取。
- Undo 是完整快照；scene 按 ID 复用图元，只重建变化的几何，单个拖动期间也只更新相关 graphics item。大项目的历史序列化和列表刷新需要进一步优化。
- 图片是阈值轮廓，不是语义重建。截屏标注、遮挡和 SEM 纹理仍需 ROI 或人工修正。
- 比例尺已知才有物理标定；没有规则的结构只是测试几何。没有实际 3 nm DRC / OPC / CMP 求解器。
- 45° 浮点轮廓写入 0.1 nm 格点后会有量化误差；物理边缘位置不由此得到保证。
- 编辑画布不显示 GDS 标签，样本库保留有界文字来源备注；数组复制导出为对象 Cell 引用，不压缩成 AREF。隐藏层也导出。
- 参数化多层结构按主层+1生成辅助层；自由图形可重新分层。编辑锁定以主层对象为单位。

## 推荐的下一轮

先拿真实截图和实际检测程序的 GDS 输入规范做验收：坐标单位、Layer/Datatype、TOP Cell、是否需要图形合并、样本数量与命名。再扩充其真正需要的结构，不先编造完整 PDK。

若需要超多样本，优先实现增量命令和 Cell/AREF 重用。若需要更复杂论文图，优先独立颜色分层/分割 provider，保留用户标定和孔洞。

## 提交前

执行 `python -m pytest -q`，重新生成 examples，读取 GDS 并核对单位和空洞。用 Windows 实际窗口检查缩放、字段、快捷键、撤销与导出，不能只以 import 成功当成界面验收。

# 架构与扩展约定

## v0.2 样本管理扩展

主编辑器的 Document/Shape 与参数结构保持兼容。SampleWindow 为独立管理窗口：SQLite 样本库 → 分层分页图库 → 编辑器修正 → 再次入库。manager 的来源选择不改变当前编辑文档。

| 模块 | 职责 |
|---|---|
| library.py | schema v1，sources / samples / occurrences，事务、去重、出处和检索 |
| matching.py | 面积几何合并、保留孔洞、平移 / D4 / 等比例归一化指纹，向量 IoU 候选 |
| layout_source.py | KLayout 层级读取、Cell 索引、有限遍历、区域裁剪、路径面积化、同层连通合并 |
| jobs.py | multiprocessing spawn 独立进程，进度队列和取消事件 |
| library_window.py | 图库、来源 / Cell / 层选择、任务调度、PDF 页渲染和 TraceDialog 对接 |
| dataset.py | 每样本 PNG/GDS、逐层分页面图谱、来源清单、无泄漏分组 |

坐标为 nm / y-up。未标定的临时坐标 calibrated=False，不可当成测量尺寸。跨层可匹配；去重主键按 strict+Layer+Datatype+calibrated 分开。

后台提取只在整个任务成功后提交事务。超限或取消撤回本批。SQLite WAL 保留可读图库；每个进程独立创建连接，禁止传递连接或 Layout 对象。Queue 传递索引和进度，不传整个展平几何。

扩展入口：语义区域切分 provider；ANN / 边距候选索引；多层联合样本（当前逐层）；PDF 颜色分层 / OCR；增量大文件索引缓存；来源实例路径；外部检测工具层映射。

## 分层

| 模块 | 责任 | Qt 依赖 |
|---|---|---|
| `catalog.py` | Pattern/Parameter 注册、验证、参数生成器 | 无 |
| `geometry.py` | nm 几何、布尔、路径、偏置、方向规整 | 无 |
| `model.py` | Document、Shape、Layer，序列化与变换 | 无 |
| `io.py` | 原子工程写入、GDS 转换、层级导出和回读验证 | 无 |
| `tracing.py` | 图像阈值、层级轮廓、ROI、标定和孔洞 | 无 |
| `canvas.py` | Qt Graphics View 画布、绘图、选择与交互 | 有 |
| `image_dialog.py` | 图片标定、异步提取与覆盖预览 | 有 |
| `window.py` | 编辑命令、撤销、属性面板、菜单、项目流程 | 有 |
| `dialogs.py` / `sources.py` | 阵列/扫描/图层对话框与来源列表 | 有 / 无 |
| `app.py` / `style.py` | 启动、插件、异常日志、视觉样式 | 有 |

Geometry → Model → I/O 依赖方向不应反向引用 UI。未来可替换几何库、加入 C++ 算法模块或接本地 agent，而不改变工程语义。

## 核心协议

所有长度、位置与轮廓坐标为 nm，笛卡尔 y 向上；Qt 仅在画布适配处转换成 y 向下。角度为度。浮点几何在 GDS 输出时按 0.1 nm 量化。不可把 `nm` 坐标直接按 μm 写入库。

`Pattern.generate(params) -> list[list[[x,y],...]]`：返回非退化闭合多边形（末点不用重复起点），参数值需验证；可使用 GDSTK 布尔输出有孔的弱简单多边形。`Shape` 保留参数化语义或自由多边形，不同时把两者当成有效源。

`Shape.entries()` 返回 `(layer, datatype, world_polygons)`，几何已经应用 X/Y、角度、缩放与镜像。多层结构返回多条记录。导出与画布共同使用该接口，避免几何出现分歧。

`Document.to_dict()` 输出 `format=gds-studio, version=1, units=nm`；加载未知版本或缺失插件应给清晰错误，不能丢弃图形。

`metadata` 可承载 source_image、calibrated、nm_per_pixel、calibration_points_px、calibration_distance_nm、trace_roi_px、sweep、expanded_from、bias_nm。工程允许增加 JSON 兼容字段；不要写不可序列化 Python 对象。

## 命令与状态

编辑由 `MainWindow.mutate` 执行：保存 before → 修改模型 → 验证/提交 after → 推入 `DocumentCommand` → 更新 scene。Canvas 的连续拖动只在释放时提交一次命令；图像参数预览不写工程，确定导入时提交一次。Undo/redo 持有序列化快照，最多 80 个命令；适合中小规模研究样本，不是超大芯片数据库。

scene 按 ID 复用 graphics item，仅对几何/显示签名变化的对象重建路径；更改一个参数不会重建所有图元。后续性能优化可把完整历史快照替换成增量命令，图层/对象列表也改为局部更新；保持工程协议和 `entries()` 不变。参数面板读取模型而非 QGraphicsItem；scene 是显示适配器，不是保存真源。

## 插件

`user_plugins/*.py` 中非下划线开头文件启动时加载，调用 `register_patterns(register)`。参照 `_example.py`，去掉文件名前的下划线即可启用。插件为**受信任的本地 Python 代码**，启动即执行，不用于加载来自截图/工程的代码。注册失败会恢复之前 registry，并在 UI 提示。

插件协议：创建 `Pattern(key,name,category,description,effect,sources,parameters,builder)`，传给 register。key 要持久唯一。builder 返回 nm 多边形。来源可引用 `sources.py` ID。新多层生成器当前需要扩展 `Shape.entries()`；未来可增加 Pattern 的 layer resolver 协议，升级应保持单层生成器兼容。

## 持久化与输出

工程和 manifest 先写同目录临时文件，再替换。GDS 先写临时文件，回读检查面积与图层，再替换目标文件；manifest 单独原子写入，二者不构成双文件事务。外部 GDS 导入展开选择的顶层 Cell，转换其 unit；文字 Label 不导入。导出一对象一 Cell，TOP 引用各 Cell，不把数组复制优化为 AREF；方便 manifest 与对象对应。

## 后续可接入点

- 工艺配置：可新增 process profile，提供显式 Layer/Datatype 映射、尺寸上下限与约束；不要把节点名字变成通用规则。
- 图像语义：用独立 segmentation provider 提供 mask，再复用当前轮廓/孔洞/标定链。保持 preview 和导出同源。
- DRC：在 core service 上提供 violations，把错误映射到形状 ID 与顶点；真实规则来自用户工艺。
- OPC/光学：新增独立 simulation provider，有机器/胶/曝光配置和校准数据后才显示物理结果。
- 更复杂层级编辑：复用 layout_source adapter，在独立视图按可见 ROI 拉取图元和实例路径；当前编辑器仍只编辑提取后的中小规模样本。

## 验证

`tests/test_core.py` 对每种结构执行 GDSTK 导出与 **KLayout 独立回读**，核对 dbu、图层、面积、边界；另测孔洞、ROI、极性、单位转换、序列化、方向规整、布尔与偏置。

`tests/test_ui.py` 覆盖 Qt 创建、选择、参数调整、复制、undo/redo、顶点展开、旋转、多层、手绘工具及图片标定导入。`tools/generate_examples.py` 留下真实 GDS、工程、输入图片和独立回读证据。GUI 截图见 examples。

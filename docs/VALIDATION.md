# 测试记录

记录日期：2026-10-10。环境：Windows 11、Python 3.12.7、PySide6 6.8.3。

## 自动测试

72 项测试通过，进程退出码为 0。覆盖以下流程：

- 41 类结构的 GDS 导出，以及 KLayout 独立回读的单位、图层、面积和边界检查。
- 工程序列化、中文路径、孔洞、ROI、图像极性、方向规整、布尔运算和偏置。
- 尺寸、旋转镜像和同形匹配，重复来源保留，未标定样本处理。
- Cell、连通结构、递归区域提取、路径面积化、超限和取消时的事务撤回。
- Qt 放置、拖动、缩放、参数和顶点编辑、复制、图层、阵列、扫描及撤销重做。
- 图库到画布的修正流程、后台进程、PDF 页面渲染和数据集分组。

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pip check
```

## 示例与桌面版

`examples/` 中保存了 starter、catalog、line_space_sweep 和 trace_result 的工程、GDS 与 manifest。catalog 包含 41 类结构，参数扫描包含 20 个线宽/间距组合，图片示例包含孔洞。独立回读摘要见 `examples/independent_verification.json`。

论文示例从公开预印本 Figure 4(a) 提取了 31 个闭合轮廓，另保存一个完整结构样本，均为未标定、待审核。来源和处理参数见 [论文示例说明](PAPER_SAMPLES.md)。

PyInstaller 桌面版启动和退出正常。`--self-check` 导出 47 个多边形、9 个 Cell，面积为 66864 nm²，GDSTK 回读通过。源码和桌面版都跑过后台索引、递归 ROI 提取和图库渲染流程。界面截图放在 examples 中。

## 大文件测试

输入为合成矩形版图，不是实际工艺文件。

| 项目 | 结果 |
|---|---|
| 文件大小 | 217601688 字节，207.52 MiB |
| 多边形 | 3400000 个 |
| 图层 / 文字备注 | 40 层 / 40 条 |
| 生成耗时 | 5.82 秒 |
| 层级索引耗时 | 0.87 秒 |
| ROI 读取与提取耗时 | 1.16 秒 |
| ROI 几何 / 入库结果 | 100 个几何；10 个新样本、90 个重复 |

复现命令：

```powershell
.venv\Scripts\python.exe tools\large_layout_check.py
```

脚本会在 userdata/large-check 下生成约 208 MiB 的文件和报告。桌面版也使用这份文件检查过后台提取。结果取决于数据和运行环境，不能据此推算复杂全芯片版图的处理时间。

## 尚未覆盖

实际工艺大文件与检测程序的集成还需要更多数据。当前检查的是几何、文件格式和软件流程，不包含曝光、抗蚀剂、蚀刻或 CMP 的物理仿真。

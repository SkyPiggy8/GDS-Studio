# 第三方组件

使用公开接口。论文示例来自允许改编的 CC BY 4.0 预印本，署名、来源、裁剪范围和改动保留在 examples/paper-fig4a.gsproj 和 docs/PAPER_SAMPLES.md；没有打包论文全文。

| 组件 | 用途 | 许可 / 官方来源 |
|---|---|---|
| PySide6 / Qt 6 | Windows 桌面交互和绘制 | LGPLv3 / GPLv3 / 商业许可，https://www.qt.io/licensing/ |
| GDSTK | GDS、布尔、路径和偏置 | Boost Software License 1.0，https://github.com/heitzmann/gdstk |
| Shapely / GEOS | 多边形有效性检查 | Shapely BSD-3-Clause / GEOS LGPL，https://github.com/shapely/shapely |
| NumPy | 坐标计算 | BSD-3-Clause，https://numpy.org/ |
| OpenCV | 阈值、轮廓和简化 | Apache-2.0（当前 4.x），https://opencv.org/license/ |
| KLayout Python 0.30.12 | 大文件层级数据库、提取与独立验证 | 当前 wheel 元数据为 GPL-3.0-or-later，https://github.com/KLayout/klayout |
| PyInstaller | 打包工具 | GPL 带 bootloader exception，https://pyinstaller.org/ |

Qt 使用动态 DLL 链接。分发桌面包保留 DLL、其许可证和可替换动态库形式。运行依赖的分发许可全文由构建脚本从已安装 distribution 元数据复制到 `licenses/`；核查发现额外原生依赖时也应保留其声明。

GDS Studio 自有源文件继续按 LICENSE 中的 MIT 条款提供。包含 KLayout 的组合桌面发行版按 GPLv3 或后续版本分发，附 LICENSE-DISTRIBUTION.txt。桌面目录 source/ 含自有源码、测试与构建脚本；third_party_sources/ 含当前 KLayout 版本的上游源码归档和校验值。Qt 6.8.3 / PySide6 6.8.3 上游源码见 https://download.qt.io/archive/qt/6.8/6.8.3/ 与 https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/ 。没有对这些库作私有修改。

# 调研记录

查阅日期：2026-10-10。以下为实际查阅的原始论文、机构公开资料和官方文档。没有把公开网站当成完整 PDK；效应机制与具体测试几何用途区分说明。

## 阅读结果

1. 角部与线端：Mack 的光学研究帮助解释圆化、线端缩短与方孔成像；早期论文的数值不直接用于 3 nm。
2. EUV：imec 的 L/S 和孔阵列研究确定微桥、断线、缺孔和并孔等检测对照类型；剂量、胶、尺寸和节距共同影响窗口。
3. 图形转移：Tone reversal 论文说明轮廓与缺陷贯穿曝光、显影和蚀刻，不能只根据几何宣称工艺成功。
4. CMP：MIT 论文支持用线宽与局部密度构造测试样本，不提供当前节点的研磨预测参数。
5. 现代节点：TSMC N3 和 Samsung 3 nm GAA 的公开材料用于确认节点、结构差异，未获取商业设计规则。
6. 软件：PHIDL 参数化工作流、KLayout 数据库单位、GDSTK 布尔/文件协议、OpenCV 轮廓层级支持所选架构。

## 来源与用途

### Chris A. Mack · Corner Rounding and Line-end Shortening in Optical Lithography (2000)

论文：解释角部圆化、孔形状与线端缩短。早期光学研究，只借用效应机制，不移植尺寸。

[原始来源](https://www.lithoguru.com/scientist/litho_papers/2000_103_Corner%20Rounding%20and%20Line-end%20Shortening%20in%20OL.pdf)

### Peter De Bisschop · Stochastic effects in EUV lithography (2018)

论文元数据：EUV 随机效应研究。线条和接触孔缺陷对照由 imec 公开技术解读补充。

[原始来源](https://imec-publications.be/entities/publication/bcb41faf-d258-4974-9b0e-637a72e55f2a)

### Chris A. Mack · Metrics for stochastic scaling in EUV lithography (2019)

论文：讨论 LWR、LCDU 的随机变异指标；本软件只生成几何，不计算物理概率。

[原始来源](https://lithoguru.com/scientist/litho_papers/2019_Metrics%20for%20stochastic%20scaling%20in%20EUV.pdf)

### Impact of stochastic process variations on overlay mark fidelity towards the 5nm node (2017)

论文：套刻标记图形保真与工艺变化；示意标记需按实际量测流程另行设计。

[原始来源](https://lithoguru.com/scientist/litho_papers/2017_Overlay_Mark_Fidelity.pdf)

### MIT · Modeling of Pattern Dependencies in Abrasive-Free CMP (2001)

论文：线宽、图形密度和初始形貌影响 CMP。仅支持设置测试几何，未实现 CMP 模型。

[原始来源](https://mtlsites.mit.edu/researchgroups/Metrology/PAPERS/VMIC2001.pdf)

### F. Schleicher et al. · Tone reversal patterning for advanced technology nodes (2022)

论文：关注图形转移中的粗糙度与缺陷；不能只以曝光轮廓代表最终加工结果。

[原始来源](https://imec-publications.be/bitstreams/c5d23032-69e9-494b-9cce-03f5fcfa30e5/download)

### PHIDL: Python CAD layout and geometry creation for nanolithography (2021)

论文：参数化几何与脚本版图工作流。作为插件接口与参数结构的设计参考。

[原始来源](https://arxiv.org/abs/2103.01152)

### imec · Pushing EUV single-exposure limits (2018)

研究解读：L/S 微桥与断线、孔缺失与合并；SRAF 与 retargeting 的工艺窗口影响。

[原始来源](https://www.imec-int.com/en/imec-magazine/imec-magazine-march-2018/imec-pushes-the-limits-of-euv-lithography-single-exposure-for-future-logic-and-memory-applications)

### imec · Sailing along the stochastic cliffs (2019)

研究解读：随机缺陷与节距、剂量、胶材料相关。几何扫描不能代替实验窗口。

[原始来源](https://www.imec-int.com/en/imec-magazine/imec-magazine-july-2019/euv-lithography-sailing-along-the-stochastic-cliffs)

### imec · Single-patterning High-NA EUV milestones (2025)

研究公告：20 nm pitch、13 nm tip-to-tip 研究示例。仅说明测试结构意义，非 3 nm PDK 规则。

[原始来源](https://www.imec-int.com/en/press/imec-achieves-new-milestones-single-patterning-high-na-euv-lithography-both-damascene-and)

### imec · Printing 28nm Pitch Hexagonal Contact Arrays (2025)

论文元数据与摘要：交错接触孔阵列及图形转移后量测。库中的交错方孔是可调测试近似。

[原始来源](https://imec-publications.be/entities/publication/b9bb59cd-e1fa-4a1d-9bb1-51323e803060)

### ASML · Computational lithography

官方说明：模型通过机器与测试晶圆数据标定，再优化掩膜。手工锤头和 serif 属于测试几何。

[原始来源](https://www.asml.com/en/products/computational-lithography)

### IBM Research · Why we need EUV lithography (2023)

官方技术背景：EUV 曝光与多次图形化；节点名称不定义全部版图尺寸。

[原始来源](https://research.ibm.com/blog/what-is-euv-lithography)

### TSMC · 3nm Technology / FinFLEX

厂商背景：N3 系列与 FinFLEX。网页不提供可代用的完整设计规则。

[原始来源](https://www.tsmc.com/english/dedicatedFoundry/technology/logic/l_3nm)

### Samsung · 3nm GAA production (2022)

厂商背景：3 nm GAA 工艺与可变纳米片通道；与其他厂商结构不同。

[原始来源](https://news.samsung.com/global/samsung-begins-chip-production-using-3nm-process-technology-with-gaa-architecture)

### KLayout · Database API

官方文档：Cell、图层和数据库单位。用于独立 GDS 回读验证。

[原始来源](https://klayout.de/doc/programming/database_api.html)

### GDSTK · C++ / Python GDS toolkit

官方文档：GDS I/O、布尔、偏置和路径几何。软件使用库接口，不复制编辑器源码。

[原始来源](https://heitzmann.github.io/gdstk/)

### OpenCV · Contours hierarchy

官方文档：轮廓层级用于保留空洞；标注文字与比例尺需裁剪排除。

[原始来源](https://docs.opencv.org/4.x/d9/d8b/tutorial_py_contours_hierarchy.html)

## 形状对应关系

| 结构 | 类别 | 简短效应 / 用途 | 来源 ID |
|---|---|---|---|
| 矩形 | 基础几何 | 角部可能圆化；密度改变图形转移偏差。 | mack2000, asml |
| 孤立线 | 线条与端点 | 孤立与密集线的 CD 响应可不同。 | imec2018 |
| Line / Space | 线条与端点 | 关注 LER / LWR、微桥和断线。 | imec2018, de2018 |
| 密集 / 孤立对比 | 线条与端点 | 邻近图形影响 CD 与工艺窗口。 | imec2018, asml |
| Tip-to-Tip | 线条与端点 | 端部缩短和端点间距偏差。 | mack2000, imec2025 |
| Tip-to-Side | 线条与端点 | 可用于观察邻近效应与局部桥接。 | mack2000, asml |
| 交错线端 | 线条与端点 | 邻近环境不同，端部响应可能不一致。 | imec2018 |
| 锤头 Hammerhead | OPC 测试 | 用于探索端部补偿；尺寸需工艺标定。 | mack2000, asml |
| 狗骨 Dogbone | OPC 测试 | 可对比端部缩短与补偿后偏差。 | mack2000, asml |
| 角部 Serif | OPC 测试 | 测试角部补偿；不能替代模型 OPC。 | mack2000, asml |
| 辅助线 SRAF | OPC 测试 | 改善部分窗口；需核实辅助线不成像。 | imec2018 |
| L 型拐角 | 连接与拐角 | 外角圆化，内角与邻近结构耦合。 | mack2000 |
| U 型回折 | 连接与拐角 | 可观察内侧间隔与拐角偏差。 | mack2000, asml |
| T 型连接 | 连接与拐角 | 连接处局部成像与蚀刻偏差。 | asml |
| 十字连接 | 连接与拐角 | 局部密度与角部响应可区别于直线。 | asml, mack2000 |
| H 型连接 | 连接与拐角 | 测试窄桥连续性和内角图形保真。 | asml |
| Z 型 Jog | 连接与拐角 | 短段和角部容易出现边缘位置偏差。 | mack2000, asml |
| 蛇形线 | 连接与拐角 | 可用于连续性与断线检测样本。 | asml, de2018 |
| 阶梯线 | 连接与拐角 | 观察短边、密集拐角的轮廓偏差。 | mack2000 |
| 45° 斜线 | 非正交测试 | 方向依赖与栅格量化需单独评估。 | asml |
| 45° 倒角 | 非正交测试 | 与直角轮廓对比；工艺许可依赖 PDK。 | mack2000, asml |
| Y 型连接 | 非正交测试 | 观察分叉邻近效应与局部连通性。 | asml |
| 方形 Contact | 接触孔与阵列 | 成像可能圆化；关注缺孔与 CD。 | mack2000, imec2018 |
| Contact 阵列 | 接触孔与阵列 | 缺孔、孔合并和 LCDU。 | imec2018, de2018 |
| 交错孔阵列 | 接触孔与阵列 | 可比较不同邻近环境下的缺孔和合并。 | imec2018 |
| 长孔 Slot | 接触孔与阵列 | 窄方向分辨率与端部圆化值得关注。 | mack2000 |
| Via / 包围层 | 多层结构 | 关注套刻和包围裕量；需实际层映射。 | asml, imec2019 |
| 矩形环 | 检测测试 | 内外边缘便于检查轮廓与孔洞处理。 | mack2000 |
| 梳齿 | 检测测试 | 测试分支连通与间隔桥接。 | de2018, asml |
| 交指梳齿 | 检测测试 | 测试密集间隙、短路与连接保真。 | de2018 |
| 凹槽 Notch | 检测测试 | 窄槽可能闭合，内角可能圆化。 | mack2000 |
| 颈缩 Neck | 检测测试 | 测试局部颈缩与开路敏感性。 | de2018, asml |
| 微桥样本 | 缺陷对照 | 用于检测对照；不是随机缺陷模拟。 | imec2018, de2018 |
| 断线样本 | 缺陷对照 | 用于开路检测及 die-to-database 对照。 | imec2018, de2018 |
| 缺孔样本 | 缺陷对照 | 用于缺孔检测对照。 | imec2018, de2018 |
| 并孔样本 | 缺陷对照 | 用于孔合并和错误连通检测对照。 | imec2018, de2018 |
| Dummy Fill | 密度与套刻 | 用于密度对照；CMP 效应需实际模型。 | cmp2004 |
| 对准十字 | 密度与套刻 | 可用于坐标对齐；标记工艺需单独设计。 | asml |
| 游标 Vernier | 密度与套刻 | 帮助比较偏移；不等同设备级套刻量测。 | asml |
| Line / Cut | 多层结构 | 切割端点和套刻会影响目标线端位置。 | imec2018, imec2025 |
| Gate / Active 示意 | 多层结构 | 仅用于形状与层间位置测试，不代表晶体管 PDK。 | tsmc3, samsung3 |

形状对应的局部用途（例如 T/Y 分叉、梳齿和颈缩）是基于通用机制设计的测试推断；未声称原文证明本软件每个默认尺寸。De Bisschop 与 hex contact 的机构记录主要提供论文元数据/摘要，机制补充采用 imec 公开技术解读。网页抓取时间不作为论文发表年份。
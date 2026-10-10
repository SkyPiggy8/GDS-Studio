# 已提取的公开论文样本

来源：Duan, Xuan-Ming; Liang, Zi-Xin; Chen, Jing-Tao; Li, Wen-Hui; Zhou, Jing; Zhao, Yuan-Yuan. *Diffraction-limit-breaking digital projection lithography via multi-exposure strategies for high-density nanopatterning*. Research Square, posted 14 August 2025, v1. [DOI 与来源](https://doi.org/10.21203/rs.3.rs-7290332/v1)。

使用的是预印本，封面明确采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。后来发表的期刊版本采用不同许可；这里不从期刊版提取或分发改编图形。

提取范围：PDF 第 14 页（正文页码 13/28），Figure 4(a)，左上数字目标掩模。180 DPI 渲染图中的 ROI = [264,1131,210,210]，格式 x,y,width,height。裁掉标题与图轴，亮前景阈值 90，最小面积 12 px²，轮廓简化 0.7 px。得到 31 个闭合轮廓，另保存一个由这些轮廓组成的完整结构样本。

文件：examples/paper-fig4a-crop.png 是裁剪图；paper-fig4a-mask.png 是识别二值图；paper-fig4a.gsproj / .gds 是可编辑版图与回读验证结果。记录明确标识裁剪、阈值化和轮廓简化这些改动；没有分发论文全文。

所有轮廓都标为**未标定、待人工审核**，以临时坐标导入，不能作为真实物理尺寸。论文研究的是数字投影多次曝光，不是 3 nm foundry PDK；示例用来验证“公开论文图 → 轮廓 → 修正 → 样本库”的流程。

简短工艺备注：密集线间距与离焦会影响桥连；多次曝光分解和间距均匀性用于改善可印性。应用内参考信息只解释这些结构为何有收集价值，不替代曝光仿真或 DRC。

复现入口：`python tools/paper_sample.py 本地预印本.pdf`，使用 QtPdf。原样本由 Poppler 渲染，两个渲染器的抗锯齿略有区别，因此复现后需核对 crop 和 mask。工作目录的下载缓存不随源码包分发，用户可从上面 DOI 获取同一个 CC BY 4.0 版本。

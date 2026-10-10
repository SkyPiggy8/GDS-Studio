"""Reproduce the attributed, uncalibrated Fig. 4(a) sample from a local PDF.

Usage: python tools/paper_sample.py path/to/rs-7290332-v1.pdf
The input must be the CC BY 4.0 Research Square preprint, not the journal PDF.
No PDF is bundled. QtPdf rendering can slightly change antialiasing relative
to the original Poppler render; review the crop and generated mask.
"""
import argparse
from pathlib import Path
import cv2
import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtPdf import QPdfDocument
from gds_studio.tracing import TraceOptions,trace_image
from gds_studio.model import Document,Shape
from gds_studio.io import save_project,export_gds
from gds_studio.dataset import save_png


def main():
    parser=argparse.ArgumentParser();parser.add_argument("pdf",type=Path);parser.add_argument("--out",type=Path,default=Path("examples/paper-reproduced"));args=parser.parse_args()
    app=QGuiApplication.instance() or QGuiApplication([]);pdf=QPdfDocument()
    if pdf.load(str(args.pdf.resolve()))!=QPdfDocument.Error.None_:raise ValueError("无法打开本地 PDF")
    size=pdf.pagePointSize(13);image=pdf.render(13,QSize(round(size.width()*180/72),round(size.height()*180/72)))
    args.out.mkdir(parents=True,exist_ok=True);page=args.out/"page-14.png"
    if image.isNull() or not image.save(str(page)):raise ValueError("页面渲染失败")
    array=cv2.imdecode(np.frombuffer(page.read_bytes(),np.uint8),cv2.IMREAD_COLOR);crop=array[1131:1341,264:474]
    if crop.shape[:2]!=(210,210):raise ValueError("PDF 页面尺寸不同，请检查版本和裁剪坐标")
    save_png(args.out/"crop.png",crop);options=TraceOptions(threshold=90,dark=False,min_area=12,tolerance=.7,nm_per_pixel=1,calibrated=False)
    polygons,mask,report=trace_image(crop,options);save_png(args.out/"mask.png",mask)
    meta={"calibrated":False,"citation":"Duan, Liang, Chen, Li, Zhou, Zhao. Research Square preprint, 2025.","doi":"10.21203/rs.3.rs-7290332/v1","license":"CC BY 4.0","license_url":"https://creativecommons.org/licenses/by/4.0/","page":14,"figure":"4(a)","roi_px":[264,1131,210,210],"render_dpi":180,"renderer":"QtPdf","modifications":"cropped, thresholded, simplified; uncalibrated, unreviewed","node":"not a 3 nm process layout","trace_report":report}
    shapes=[Shape(name="论文 Fig4a 完整结构（未标定）",polygons=polygons,metadata=meta)]
    shapes += [Shape(name=f"论文 Fig4a 轮廓 {i+1}",polygons=[p],x=300+(i%4)*240,y=(i//4)*50,metadata={**meta,"contour_index":i}) for i,p in enumerate(polygons)]
    doc=Document(name="Fig4a · 未标定",shapes=shapes,metadata=meta);save_project(args.out/"sample.gsproj",doc);r=export_gds(args.out/"sample.gds",doc)
    print(f"Contours: {len(polygons)}, rejected: {report['rejected']}, GDS readback: {r['gds_readback_verified']}")


if __name__=="__main__":main()

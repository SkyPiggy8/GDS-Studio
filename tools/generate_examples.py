"""Generate actual reproducible demonstration artifacts, not screenshots as specs."""
import json
from pathlib import Path
import numpy as np
import cv2
import klayout.db as kdb
from gds_studio.catalog import REGISTRY
from gds_studio.model import Shape,Document,demo
from gds_studio.io import export_gds,save_project
from gds_studio.geometry import bounds
from gds_studio.tracing import TraceOptions,trace_image,trace_shapes


root=Path(__file__).resolve().parents[1];out=root/"examples";out.mkdir(exist_ok=True)
starter=demo();save_project(out/"starter.gsproj",starter);export_gds(out/"starter.gds",starter)
doc=Document(name="41 类结构总览")
for i,key in enumerate(REGISTRY):
    s=Shape.from_pattern(key);x0,y0,x1,y1=bounds(s.world_polygons());s.x=(i%6)*850-x0;s.y=(i//6)*600-y0
    s.metadata["catalog_key"]=key;doc.shapes.append(s)
doc.ensure_layers();save_project(out/"catalog.gsproj",doc);export_gds(out/"catalog.gds",doc)
sweep=Document(name="Line Space · 线宽与间距扫描")
for j,g in enumerate([8,12,16,24]):
    for i,w in enumerate([8,10,12,16,20]):
        s=Shape.from_pattern("line_space",x=i*280,y=j*300);s.params.update(width=w,gap=g,count=8);s.metadata["sweep"]={"width_nm":w,"gap_nm":g};sweep.shapes.append(s)
save_project(out/"line_space_sweep.gsproj",sweep);export_gds(out/"line_space_sweep.gds",sweep)
image=np.full((360,560,3),255,np.uint8)
cv2.rectangle(image,(35,40),(200,75),(0,0,0),-1);cv2.rectangle(image,(25,20),(50,95),(0,0,0),-1);cv2.rectangle(image,(185,20),(210,95),(0,0,0),-1)
for j in range(5):cv2.rectangle(image,(35,140+j*34),(230,151+j*34),(0,0,0),-1)
cv2.rectangle(image,(300,40),(510,270),(0,0,0),-1);cv2.rectangle(image,(330,70),(480,240),(255,255,255),-1)
cv2.imencode(".png",image)[1].tofile(out/"trace_input.png")
options=TraceOptions(nm_per_pixel=.5,calibrated=True,tolerance=.5);polys,_,report=trace_image(image,options)
traced=Document(name="标定截图轮廓",shapes=trace_shapes(polys,options,out/"trace_input.png",report));save_project(out/"trace_result.gsproj",traced);export_gds(out/"trace_result.gds",traced)
verification={}
for path in out.glob("*.gds"):
    layout=kdb.Layout();layout.read(str(path));verification[path.name]={"dbu_um":layout.dbu,"cells":layout.cells(),"top_cell":layout.top_cell().name,"layers":len(layout.layer_indices())}
(out/"independent_verification.json").write_text(json.dumps(verification,indent=2),encoding="utf-8")
print(f"Generated {len(verification)} verified GDS examples in {out}")

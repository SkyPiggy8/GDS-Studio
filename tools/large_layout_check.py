"""Synthetic large-file benchmark, explicit opt-in; not a foundry-layout claim."""
import json
import struct
import time
from pathlib import Path
import klayout.db as k
from gds_studio.layout_source import index_layout,extract_layout


def create(path,count=3400000):
    base=path.with_suffix(".template.gds");l=k.Layout();l.dbu=.001;c=l.create_cell("TOP")
    c.shapes(l.layer(1,0)).insert(k.Polygon(k.Box(0,0,20,40)))
    for layer in range(1,41):c.shapes(l.layer(layer,0)).insert(k.Text(f"L{layer}",k.Trans(0,0)))
    l.write(str(base));data=base.read_bytes();records=[];pos=0
    while pos<len(data):
        n,typ=struct.unpack_from(">HH",data,pos);records.append((typ,pos,n));pos+=n
    start=next(p for typ,p,n in records if typ==0x0800);end=next(p+n for typ,p,n in records if typ==0x1100 and p>start)
    def record(typ,payload=b""):return struct.pack(">HH",4+len(payload),typ)+payload
    with path.open("wb") as f:
        f.write(data[:start]);batch=[]
        for i in range(count):
            x=(i%2000)*100;y=(i//2000)*100;layer=i%40+1
            polygon=record(0x0800)+record(0x0D02,struct.pack(">h",layer))+record(0x0E02,struct.pack(">h",0))+record(0x1003,struct.pack(">10i",x,y,x+20,y,x+20,y+40,x,y+40,x,y))+record(0x1100)
            batch.append(polygon)
            if len(batch)==10000:f.write(b"".join(batch));batch=[]
        if batch:f.write(b"".join(batch))
        f.write(data[end:])


def main():
    root=Path(__file__).resolve().parents[1];out=root/"userdata"/"large-check";out.mkdir(parents=True,exist_ok=True);path=out/"synthetic-40layers.gds"
    t=time.perf_counter();create(path);generate=time.perf_counter()-t
    t=time.perf_counter();index=index_layout(path);index_time=time.perf_counter()-t
    t=time.perf_counter();r=extract_layout(path,out/"samples.sqlite",{"cells":["TOP"],"mode":"polygon","recursive":True,"roi":[0,0,1000,1000],"limit":1000});extract_time=time.perf_counter()-t
    report={"synthetic":True,"bytes":path.stat().st_size,"mb":path.stat().st_size/1048576,"input_polygons":3400000,"layers":len(index["layers"]),"cells":len(index["cells"]),"generation_seconds":generate,"index_seconds":index_time,"roi_extraction_seconds":extract_time,"roi_report":r,"limitations":"Synthetic rectangles + 40 text labels, not a real foundry layout; full-library extraction not benchmarked"}
    (out/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps(report))


if __name__=="__main__":main()

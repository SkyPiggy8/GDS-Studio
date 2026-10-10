"""Vector fingerprints, independent of source vertices and polygon fragmentation.

strict: translation invariant, 0.1 nm grid; congruent: also D4; same_shape:
also uniform scale, 1e-5 relative grid. D4 means 90-degree rotations/mirrors.
Approximate scores are explicitly not equivalence decisions.
"""
import hashlib
import json
import math
from shapely import make_valid, union_all, set_precision
from shapely.geometry import Polygon, GeometryCollection
from shapely.affinity import affine_transform, translate, scale


def polygon_parts(g):
    if g.geom_type == "Polygon":
        yield g
    elif hasattr(g, "geoms"):
        for part in g.geoms:
            yield from polygon_parts(part)


def geometry(polygons):
    parts=[]
    for points in polygons:
        if len(points)<3 or not all(math.isfinite(float(v)) for p in points for v in p):
            raise ValueError("无效轮廓坐标")
        # Remove floating-point noise from 90-degree transforms before union;
        # otherwise an intended shared edge can become a microscopic gap.
        parts.extend(polygon_parts(set_precision(make_valid(Polygon(points)),1e-7)))
    result=union_all(parts)
    if result.is_empty or result.area<=0:raise ValueError("样本没有有效面积")
    return result


D4=[(1,0,0,1), (0,-1,1,0), (-1,0,0,-1), (0,1,-1,0),
    (-1,0,0,1), (0,-1,-1,0), (1,0,0,-1), (0,1,1,0)]


def variants(g, mode):
    for a,b,d,e in (D4 if mode!="strict" else D4[:1]):
        v=affine_transform(g,[a,b,d,e,0,0]);x,y,r,t=v.bounds
        v=translate(v,-x,-y)
        if mode=="same_shape":
            f=1/max(r-x,t-y);v=scale(v,xfact=f,yfact=f,origin=(0,0))
        yield v


def ring_key(coords, step):
    pts=[(round(x/step),round(y/step)) for x,y in list(coords)[:-1]]
    pts=[p for i,p in enumerate(pts) if p!=pts[i-1]]
    while len(pts)>3:
        found=False
        for i,b in enumerate(pts):
            a,c=pts[i-1],pts[(i+1)%len(pts)]
            u,v=(b[0]-a[0],b[1]-a[1]),(c[0]-b[0],c[1]-b[1])
            if u[0]*v[1]==u[1]*v[0] and u[0]*v[0]+u[1]*v[1]>=0:
                pts.pop(i);found=True;break
        if not found:break
    def start(p):
        smallest=min(p)
        return min(tuple(p[i:]+p[:i]) for i,v in enumerate(p) if v==smallest)
    return min(start(pts),start(list(reversed(pts))))


def canonical(g,mode):
    step=1e-5 if mode=="same_shape" else .1
    candidates=[]
    for v in variants(g,mode):
        parts=[]
        for p in polygon_parts(v):
            parts.append((ring_key(p.exterior.coords,step),tuple(sorted(ring_key(h.coords,step) for h in p.interiors))))
        candidates.append(tuple(sorted(parts)))
    return min(candidates)


def fingerprints(polygons):
    g=geometry(polygons)
    result={m:hashlib.sha256(json.dumps(canonical(g,m),separators=(",",":")).encode()).hexdigest()
            for m in ("strict","congruent","same_shape")}
    x,y,r,t=g.bounds
    result.update(width=r-x,height=t-y,area=g.area,components=len(list(polygon_parts(g))),holes=sum(len(p.interiors) for p in polygon_parts(g)))
    return result


def similarity(a,b):
    """Best corner-aligned normalized vector IoU over D4; no learned model."""
    ga=next(variants(geometry(a),"same_shape"));gb=geometry(b)
    best=0.
    for v in variants(gb,"same_shape"):
        area=ga.union(v).area
        if area:best=max(best,ga.intersection(v).area/area)
    return best

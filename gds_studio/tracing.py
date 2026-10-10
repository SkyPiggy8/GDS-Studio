"""Deterministic raster trace. Keep holes; require explicit physical calibration."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from .geometry import boolean, clean, regularize
from .model import Shape


@dataclass
class TraceOptions:
    threshold: int = 150
    dark: bool = True
    min_area: float = 20
    tolerance: float = 1.5
    nm_per_pixel: float = 1.
    calibrated: bool = False
    constraint: str = "free"
    grid: float = 1.
    roi: tuple | None = None
    opening: int = 0


def read_image(path):
    raw=np.fromfile(str(path),dtype=np.uint8)
    img=cv2.imdecode(raw,cv2.IMREAD_COLOR)
    if img is None: raise ValueError("无法读取图片。支持 PNG / JPG / TIFF / BMP")
    if img.shape[0]*img.shape[1]>36_000_000: raise ValueError("图片超过 3600 万像素，请先裁剪")
    return img


def calibrated_scale(a,b,distance_nm):
    distance=float(np.linalg.norm(np.subtract(a,b)))
    if distance<1 or distance_nm<=0: raise ValueError("标定点距离至少 1 像素，实际距离必须大于 0")
    return float(distance_nm)/distance


def trace_image(image,options:TraceOptions):
    o=options
    if not np.isfinite(o.nm_per_pixel) or o.nm_per_pixel<=0: raise ValueError("标定比例无效")
    if o.tolerance<0 or o.min_area<0: raise ValueError("简化与去噪参数不可为负")
    x0=y0=0
    if o.roi:
        x,y,w,h=map(int,o.roi)
        if w<2 or h<2 or x<0 or y<0 or x+w>image.shape[1] or y+h>image.shape[0]:
            raise ValueError("裁剪区域无效")
        image=image[y:y+h,x:x+w]; x0=x; y0=y
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image
    _,mask=cv2.threshold(gray,o.threshold,255,cv2.THRESH_BINARY_INV if o.dark else cv2.THRESH_BINARY)
    if o.opening:
        mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((o.opening,o.opening),np.uint8))
    contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    polys=[]; rejected=0
    if hierarchy is None: return [],mask,{"count":0,"rejected":0}
    hierarchy=hierarchy[0]

    def contour_poly(c):
        pts=cv2.approxPolyDP(c,o.tolerance,True).reshape(-1,2).astype(float)
        # All trace geometry is relative to cropped image bottom left, in GDS y-up.
        pts[:,0]*=o.nm_per_pixel
        pts[:,1]=(image.shape[0]-1-pts[:,1])*o.nm_per_pixel
        if o.constraint!="free":
            return regularize(pts.tolist(),o.constraint,o.grid,max(.1,o.tolerance*o.nm_per_pixel))
        from .geometry import validate
        return validate(pts.tolist())

    for i,c in enumerate(contours):
        if hierarchy[i][3]!=-1 or cv2.contourArea(c)<o.min_area: continue
        try:
            hull=contour_poly(c); holes=[]; child=hierarchy[i][2]
            while child!=-1:
                # Preserve even small holes; min_area only filters foreground islands.
                if cv2.contourArea(contours[child])>.5: holes.append(contour_poly(contours[child]))
                child=hierarchy[child][0]
            polys.extend(boolean([hull],holes,"not") if holes else [hull])
        except ValueError: rejected+=1
    if len(polys)>10000: raise ValueError("识别轮廓超过 10000 个，请裁剪图形区或增加去噪面积")
    return polys,mask,{"count":len(polys),"rejected":rejected,"roi_origin_px":[x0,y0],"image_height_px":image.shape[0]}


def trace_shapes(polys,options,path="",report=None):
    return [Shape(name=f"图片轮廓 {i+1}",polygons=[p],metadata={"source_image":str(path),"calibrated":options.calibrated,"nm_per_pixel":options.nm_per_pixel,"trace_threshold":options.threshold,"trace_polarity":"dark" if options.dark else "light","trace_tolerance_px":options.tolerance,"trace_roi_px":options.roi,"trace_report":report or {}}) for i,p in enumerate(polys)]

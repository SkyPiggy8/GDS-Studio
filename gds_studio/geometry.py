"""UI-independent geometry. GDS-compatible simple contours, in nm."""
from __future__ import annotations

import math
import numpy as np
import gdstk
from shapely.geometry import Polygon

PRECISION = 0.1


def clean(points):
    result = []
    for p in points:
        p = [float(p[0]), float(p[1])]
        if not all(math.isfinite(v) for v in p):
            raise ValueError("坐标必须是有限数值")
        if not result or np.linalg.norm(np.subtract(p, result[-1])) > 1e-7:
            result.append(p)
    if len(result) > 1 and np.linalg.norm(np.subtract(result[0], result[-1])) < 1e-7:
        result.pop()
    # Remove redundant collinear vertices, while retaining the GDS hole seam.
    changed = True
    while changed and len(result) > 3:
        changed = False
        for i in range(len(result)):
            a, b, c = np.array(result[i-1]), np.array(result[i]), np.array(result[(i+1) % len(result)])
            u, v = b-a, c-b
            if abs(u[0]*v[1]-u[1]*v[0]) < 1e-7 and np.dot(u, v) >= 0:
                result.pop(i)
                changed = True
                break
    if len(result) < 3 or abs(gdstk.Polygon(result).area()) < 0.005:
        raise ValueError("轮廓需要至少三个顶点和非零面积")
    return result


def validate(points):
    p = clean(points)
    poly = Polygon(p)
    if not poly.is_valid:
        raise ValueError("轮廓有自交或重叠边，请调整顶点")
    return p


def rect(x, y, w, h):
    if w <= 0 or h <= 0:
        raise ValueError("宽度与高度必须大于 0")
    return [[x, y], [x+w, y], [x+w, y+h], [x, y+h]]


def boolean(a, b=(), operation="or"):
    if not a:
        return []
    result = gdstk.boolean([gdstk.Polygon(p) for p in a],
                          [gdstk.Polygon(p) for p in b], operation, precision=PRECISION)
    return [p.points.tolist() for p in result]


def stroke(points, width):
    if len(points) < 2 or width <= 0:
        raise ValueError("路径需要至少两个点，线宽必须大于 0")
    path = gdstk.FlexPath(points, width, joins="miter", ends="flush", tolerance=PRECISION)
    return boolean([p.points.tolist() for p in path.to_polygons()])


def bounds(polys):
    pts = np.vstack(polys) if polys else np.array([[0., 0.], [1., 1.]])
    return (*pts.min(axis=0), *pts.max(axis=0))


def transform(polys, x=0, y=0, angle=0, sx=1, sy=1, mirror=False):
    radians = math.radians(angle)
    matrix = np.array([[math.cos(radians), -math.sin(radians)],
                       [math.sin(radians), math.cos(radians)]])
    scale = np.array([-sx if mirror else sx, sy])
    return [((np.array(p)*scale) @ matrix.T + [x, y]).tolist() for p in polys]


def offset(polys, distance):
    return [p.points.tolist() for p in gdstk.offset([gdstk.Polygon(p) for p in polys],
                                                  distance, join="miter", precision=PRECISION, use_union=True)]


def constrain_segment(a, b, mode="orthogonal", grid=1.):
    """Snap the next vertex to a horizontal, vertical, or optionally 45° ray."""
    bx, by = round(b[0]/grid)*grid, round(b[1]/grid)*grid
    dx, dy = bx-a[0], by-a[1]
    if mode == "free":
        return [bx, by]
    directions = 8 if mode == "octilinear" else 4
    theta = round(math.atan2(dy, dx)/(2*math.pi/directions))*(2*math.pi/directions)
    ux, uy = math.cos(theta), math.sin(theta)
    distance = dx*ux+dy*uy
    if directions == 8 and abs(ux) > 0.1 and abs(uy) > 0.1:
        step = round(distance/math.sqrt(2)/grid)*grid
        return [a[0]+math.copysign(step, ux), a[1]+math.copysign(step, uy)]
    return [round((a[0]+distance*ux)/grid)*grid, round((a[1]+distance*uy)/grid)*grid]


def regularize(points, mode="orthogonal", grid=1., tolerance=2.):
    """Simplify an outline, constrain each segment, and close with valid edges."""
    import cv2
    pts = np.asarray(points, np.float32).reshape(-1, 1, 2)
    pts = cv2.approxPolyDP(pts, tolerance, True).reshape(-1, 2).tolist()
    if len(pts) < 3:
        raise ValueError("手绘范围太小，请绘制更完整的轮廓")
    result = [[round(pts[0][0]/grid)*grid, round(pts[0][1]/grid)*grid]]
    for p in pts[1:]:
        result.append(constrain_segment(result[-1], p, mode, grid))
    if mode != "free":
        a, b = result[-1], result[0]
        dx, dy = b[0]-a[0], b[1]-a[1]
        if abs(dx) > 1e-7 and abs(dy) > 1e-7:
            if mode != "octilinear" or abs(abs(dx)-abs(dy)) > 1e-7:
                # Try both axis-aligned closing routes; choose the valid one.
                for corner in ([b[0], a[1]], [a[0], b[1]]):
                    try:
                        return validate(result+[corner])
                    except ValueError:
                        pass
                raise ValueError("自动闭合产生交叉，请减少折返或改用多边形工具")
    return validate(result)

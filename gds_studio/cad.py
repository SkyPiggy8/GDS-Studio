"""Geometry operations used by the sketch tools. All coordinates are world nm."""
import math
from .geometry import bounds


def shape_bounds(shapes):
    return bounds([p for s in shapes for _, _, polys in s.entries() for p in polys])


def top_left(shapes):
    x0, _, _, y1 = shape_bounds(shapes)
    return float(x0), float(y1)


def move_top_left(shapes, x, y):
    """Translate a selection rigidly; Y is upwards, so top is maximum Y."""
    if not all(math.isfinite(v) for v in (x, y)):
        raise ValueError("目标坐标必须为有限数值")
    if not shapes:
        return
    ax, ay = top_left(shapes)
    for s in shapes:
        s.x += x - ax
        s.y += y - ay


def is_editable(doc, shape):
    return all(not doc.layer_info(l, d).locked for l, d, _ in shape.entries())

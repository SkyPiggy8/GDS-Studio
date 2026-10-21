"""Geometry operations used by the sketch tools. All coordinates are world nm."""
import math
import copy
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


def resolve(doc, ref):
    s=next((s for s in doc.shapes if s.id==ref['shape']),None)
    if s is None:raise ValueError("尺寸引用的对象已删除")
    entries=list(s.entries());entry=ref.get('entry',0)
    try:
        poly=entries[entry][2][ref['poly']]
        if len(poly)!=ref['count']:raise ValueError("轮廓已改变，请重新标注")
        i=ref['index'];a=poly[i]
        return s, a, poly[(i+1)%len(poly)] if ref['kind']=='edge' else a
    except IndexError:raise ValueError("尺寸引用已失效，请重新标注") from None


def dimension_points(doc, refs, mode='aligned'):
    """Return witness points and the unit direction in which the second moves."""
    _,a,b=resolve(doc,refs[0]);_,c,d=resolve(doc,refs[1])
    k1,k2=refs[0]['kind'],refs[1]['kind']
    def project(p,u,v):
        dx,dy=v[0]-u[0],v[1]-u[1];den=dx*dx+dy*dy
        if den<1e-12:raise ValueError("不能标注零长度边")
        t=((p[0]-u[0])*dx+(p[1]-u[1])*dy)/den
        return [u[0]+t*dx,u[1]+t*dy]
    if k1==k2=='edge':
        cross=(b[0]-a[0])*(d[1]-c[1])-(b[1]-a[1])*(d[0]-c[0])
        if abs(cross)>1e-6*max(1,math.dist(a,b)*math.dist(c,d)):
            raise ValueError("边间尺寸需要两条平行边；也可改选端点")
        c=[(c[0]+d[0])/2,(c[1]+d[1])/2];a=project(c,a,b)
    elif k1=='edge':a=project(c,a,b)
    elif k2=='edge':
        c=project(a,c,d)
    dx,dy=c[0]-a[0],c[1]-a[1]
    if k1==k2=='point' and mode=='horizontal':
        u=(1 if dx>=0 else -1,0);length=abs(dx)
    elif k1==k2=='point' and mode=='vertical':
        u=(0,1 if dy>=0 else -1);length=abs(dy)
    else:
        length=math.hypot(dx,dy)
        if length>1e-9:u=(dx/length,dy/length)
        elif k1=='edge' or k2=='edge':
            _,e,f=resolve(doc,refs[0] if k1=='edge' else refs[1]);n=math.dist(e,f)
            if n<1e-9:raise ValueError("不能标注零长度边")
            u=(-(f[1]-e[1])/n,(f[0]-e[0])/n)
        else:u=(1,0)
    return a,c,u,length


def drive_dimension(doc, refs, value, mode='aligned', whole=False):
    if not math.isfinite(value) or value<=0:raise ValueError("尺寸必须大于零")
    a,c,u,length=dimension_points(doc,refs,mode)
    s,_,_=resolve(doc,refs[1]);first,_,_=resolve(doc,refs[0])
    if not is_editable(doc,s):raise ValueError("目标图层已锁定")
    dx,dy=(value-length)*u[0],(value-length)*u[1]
    if abs(dx)+abs(dy)<1e-9:return
    if whole:
        if s.id==first.id:raise ValueError("同一对象内的尺寸请选择顶点 / 边编辑")
        s.x+=dx;s.y+=dy;return
    if len(list(s.entries()))>1 or refs[1].get('entry',0):
        raise ValueError("请先展开多图层结构，再编辑单层顶点 / 边")
    # Bake transforms atomically on a copy. Failed edits leave the original intact.
    candidate=copy.deepcopy(s);candidate.bake();r=refs[1]
    poly=candidate.polygons[r['poly']];indices=[r['index']]
    if r['kind']=='edge':indices.append((r['index']+1)%len(poly))
    moved_x,moved_y=vertex_groups(poly,indices,doc.constraint=='orthogonal')
    if first.id==s.id:
        fixed={refs[0]['index']}
        if refs[0]['kind']=='edge':fixed.add((refs[0]['index']+1)%refs[0]['count'])
        affected=(moved_x if abs(dx)>1e-9 else set()) | (moved_y if abs(dy)>1e-9 else set())
        if refs[0]['poly']==r['poly'] and fixed.intersection(affected):
            raise ValueError("两项引用共用顶点，无法保持第一项固定")
    for i in moved_x:poly[i][0]+=dx
    for i in moved_y:poly[i][1]+=dy
    from .geometry import validate
    for p in candidate.polygons:validate(p)
    # Keep vertex indices stable for associative annotations.
    for key in ('pattern','params','polygons','x','y','angle','sx','sy','mirror'):
        setattr(s,key,getattr(candidate,key))


def vertex_groups(poly, indices, orthogonal=True):
    """Propagate coordinates along connected vertical / horizontal sketch edges."""
    gx,gy=set(indices),set(indices)
    if orthogonal:
        for group,axis in ((gx,0),(gy,1)):
            changed=True
            while changed:
                changed=False
                for i in tuple(group):
                    for j in ((i-1)%len(poly),(i+1)%len(poly)):
                        if j not in group and abs(poly[i][axis]-poly[j][axis])<1e-7:
                            group.add(j);changed=True
    return gx,gy

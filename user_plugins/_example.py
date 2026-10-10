"""Rename to a filename without leading '_' to enable this trusted local plugin."""
from gds_studio.catalog import Pattern, Parameter
from gds_studio.geometry import rect, boolean


def register_patterns(register):
    def build(p):
        w,l=p["width"],p["length"]
        return boolean([rect(0,0,l,w),rect(0,0,w,l)])
    register(Pattern("custom_elbow","自定义等臂 L","自定义结构","演示本地结构扩展。","工艺响应需要实际标定。",(),
                     {"width":Parameter("线宽 · nm",12,.1,10000),"length":Parameter("长度 · nm",100,1,10000)},build))

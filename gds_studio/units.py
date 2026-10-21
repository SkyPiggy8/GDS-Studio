"""Display units only; model and GDS conversion continue to use nanometres."""
import math


def nice_step(target):
    power=10**math.floor(math.log10(max(target,1e-12)))
    return next(n*power for n in (1,2,5,10) if n*power>=target*(1-1e-12))


def format_length(nm,unit='auto',suffix=True):
    if unit=='auto':unit='um' if abs(nm)>=1000 else 'nm'
    value=nm/1000 if unit=='um' else nm
    text=f'{value:.4f}'.rstrip('0').rstrip('.')
    if text=='-0':text='0'
    return text+(' μm' if unit=='um' else ' nm') if suffix else text


SCALE_PRESETS_NM=(1e6,5e5,1e5,1e4,1e3,500,100,50,30,10)

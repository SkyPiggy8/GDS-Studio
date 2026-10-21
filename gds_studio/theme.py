"""Cool Morandi display palette. Geometry and saved layer colors are untouched."""
COLORS = {
    'window': '#E7ECEC', 'surface': '#F7F8F7', 'canvas': '#F0F3F2',
    'ruler': '#DFE6E7', 'ruler_corner': '#CCD7D9', 'grid': '#E0E7E6',
    'axis': '#ABBBC0', 'text': '#29373D', 'muted': '#62737A',
    'border': '#B9C7CA', 'accent': '#536D78', 'accent_soft': '#DCE5E8',
    'snap': '#607F75', 'outline': '#111518',
}
LAYER_COLORS = ('#91A7B0', '#A2B3AA', '#AAA8BC', '#91AAA5', '#ACB7C2')
LEGACY_LAYER_COLORS = dict(zip(
    ('#3285b5', '#d4973c', '#8b78b4', '#4b9c7b', '#ce6e69'), LAYER_COLORS))
LEGACY_LAYER_COLORS['#2f82b7'] = LAYER_COLORS[0]


def display_layer_color(color):
    """Restyle built-in legacy colors while respecting custom layer colors."""
    return LEGACY_LAYER_COLORS.get(color.lower(), color)

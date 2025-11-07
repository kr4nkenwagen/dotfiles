
import re
from colorsys import rgb_to_hls, hls_to_rgb

# === Utility functions ===

def hex_to_rgb(hex_color: str):
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex color."""
    return "#%02x%02x%02x" % rgb

def adjust_brightness(hex_color: str, factor: float):
    """Lighten (>1) or darken (<1) a color by a factor."""
    r, g, b = [x / 255 for x in hex_to_rgb(hex_color)]
    h, l, s = rgb_to_hls(r, g, b)
    l = max(0, min(1, l * factor))
    r, g, b = [int(x * 255) for x in hls_to_rgb(h, l, s)]
    return rgb_to_hex((r, g, b))

# === Core CSS functions ===

def load_colors():
    """Load CSS and extract color variables."""
    file_path = "/home/kr4nk/.config/qutebrowser/userstyles/all.css"
    with open(file_path, "r") as f:
        css = f.read()
    pattern = r"--([\w_]+):\s*(#[0-9A-Fa-f]{6});"
    colors = dict(re.findall(pattern, css))
    return css, colors

def save_colors(css: str, colors: dict):
    """Save updated color variables back to the CSS file."""
    file_path = "/home/kr4nk/.config/qutebrowser/userstyles/all.css"
    for var, hex_color in colors.items():
        css = re.sub(rf"--{var}:\s*#[0-9A-Fa-f]{{6}};", f"--{var}: {hex_color};", css)
    with open(file_path, "w") as f:
        f.write(css)

def list_colors(colors: dict):
    """Return all color variables as a formatted string."""
    return "\n".join(f"{var:15} {color}" for var, color in colors.items())

def edit_color(colors: dict, var: str, action: str, new_color: str = None, factor: float = None):
    """
    Modify a color variable.
    
    Parameters:
        colors (dict): dictionary of CSS color vars
        var (str): the variable name (e.g. "bg_default")
        action (str): 'new', 'lighten', or 'darken'
        new_color (str): optional, new hex color if action='new'
        factor (float): optional, brightness multiplier
    """
    if var not in colors:
        raise KeyError(f"Variable '{var}' not found in colors")

    if action == "new":
        if not new_color:
            raise ValueError("new_color must be provided when action='new'")
        colors[var] = new_color

    elif action in ("lighten", "darken"):
        if factor is None:
            factor = 1.2 if action == "lighten" else 0.8
        colors[var] = adjust_brightness(colors[var], factor)

    else:
        raise ValueError("action must be 'new', 'lighten', or 'darken'")

    return colors[var]


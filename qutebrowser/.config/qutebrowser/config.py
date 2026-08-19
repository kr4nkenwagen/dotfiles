import omarchy.draw
import os
import re
from qutebrowser.api import interceptor
from pathlib import Path

# Load autoconfig
config.load_autoconfig(False)

# ==========================================
# HELPER FUNCTIONS & STRICT HEX VALIDATION
# ==========================================
def clean_hex(val, fallback):
    """Ensure a string is a valid 6-digit hex color, otherwise return fallback."""
    if val and isinstance(val, str):
        match = re.search(r'#[0-9A-Fa-f]{6}', val)
        if match:
            return match.group(0)
    return fallback

def get_font():
    kitty_conf = os.path.expanduser("~/.config/kitty/kitty.conf")
    if os.path.isfile(kitty_conf):
        with open(kitty_conf, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("font_family"):
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        return parts[1].strip()
    return "monospace"

def load_colors():
    file_path = os.path.expanduser("~/.config/qutebrowser/userstyles/all.css")
    if not os.path.exists(file_path):
        return "", {}
    with open(file_path, "r", encoding="utf-8") as f:
        css = f.read()
    pattern = r"--([\w_]+):\s*(#[0-9A-Fa-f]{6});"
    colors = dict(re.findall(pattern, css))
    return css, colors

def save_colors(css: str, colors: dict):
    file_path = os.path.expanduser("~/.config/qutebrowser/userstyles/all.css")
    if not os.path.exists(file_path):
        return
    for var, hex_color in colors.items():
        valid_color = clean_hex(hex_color, None)
        if valid_color:
            css = re.sub(rf"--{var}:\s*#[0-9A-Fa-f]{{6}};", f"--{var}: {valid_color};", css)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(css)

def youtube_filter(info: interceptor.Request):
    url = info.request_url
    if url.host() == 'www.youtube.com' and url.path() == '/get_video_info' and '&adformat=' in url.query():
        info.block()

interceptor.register(youtube_filter)

# ==========================================
# FIND AND PARSE OMARCHY THEME FILE
# ==========================================
def find_omarchy_theme_file():
    candidates = [
        os.path.expanduser("~/.config/omarchy/current/theme/kitty.conf"),
        os.path.expanduser("~/.config/omarchy/current/colors.conf"),
        os.path.expanduser("~/.config/omarchy/current/theme/colors.conf"),
        os.path.expanduser("~/.config/omarchy/current/theme.conf"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    
    base_dir = os.path.expanduser("~/.config/omarchy/current")
    if os.path.exists(base_dir):
        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith((".conf", ".toml", ".ini", ".sh")):
                    return os.path.join(root, file)
    return None

theme_file_path = find_omarchy_theme_file()

foreground_color = None
background_color = None
selection_foreground_color = None
selection_background_color = None
colors = [None] * 16

if theme_file_path and os.path.isfile(theme_file_path):
    with open(theme_file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            hex_match = re.search(r'#[0-9A-Fa-f]{6}', line)
            if not hex_match:
                continue
            hex_val = hex_match.group(0)

            key_match = re.split(r'[\s=:]+', line)
            if not key_match:
                continue
            key = key_match[0].lower().lstrip('$')

            if key in ("foreground", "fg"):
                foreground_color = hex_val
            elif key in ("background", "bg"):
                background_color = hex_val
            elif key in ("selection_foreground", "select_fg"):
                selection_foreground_color = hex_val
            elif key in ("selection_background", "select_bg"):
                selection_background_color = hex_val
            elif key.startswith("color") and key[5:].isdigit():
                idx = int(key[5:])
                if 0 <= idx < 16:
                    colors[idx] = hex_val

def get_font_size():
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        config_path = Path(xdg_config) / "ghostty" / "config"
    else:
        config_path = Path("~/.config/ghostty/config").expanduser()

    pattern = re.compile(
        r"^\s*font-size\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*(?:#.*)?$", 
        re.MULTILINE
    )
    
    try:
        content = config_path.read_text(encoding="utf-8")
        matches = pattern.findall(content)
        if matches:
            val = float(matches[-1])
            return int(val) if val.is_integer() else val
        return 11
    except Exception:
        return 11
# Validate and apply fallbacks (Prioritizes explicit foreground colors)
bg_default = clean_hex(background_color, "#1e1e2e")
fg_default = clean_hex(foreground_color or colors[7] or colors[15], "#cdd6f4")
bg_selection = clean_hex(selection_background_color or colors[8], "#585b70")
fg_selection = clean_hex(selection_foreground_color or fg_default, "#ffffff")

bg_lighter = clean_hex(colors[0], "#181825")
fg_disabled = clean_hex(colors[8] or colors[15], "#6c7086")
bg_lightest = clean_hex(colors[6], "#89dceb")
fg_error = clean_hex(colors[1], "#f38ba8")
bg_hint = clean_hex(colors[0], "#11111b")
fg_matched_text = clean_hex(colors[10] or colors[2], "#a6e3a1")
bg_passthrough_mode = clean_hex(colors[13] or colors[5], "#f5c2e7")
bg_insert_mode = clean_hex(colors[14] or colors[4], "#89b4fa")
bg_warning = clean_hex(colors[11] or colors[3], "#f9e2af")

bg_transparent = bg_default[:7] + "00"

# Default qutebrowser settings
config.set('content.cookies.accept', 'all', 'chrome-devtools://*')
config.set('content.cookies.accept', 'all', 'devtools://*')
config.set('content.headers.accept_language', '', 'https://matchmaker.krunker.io/*')
config.set('content.headers.user_agent', 'Mozilla/5.0 ({os_info}; rv:136.0) Gecko/20100101 Firefox/139.0', 'https://accounts.google.com/*')
config.set('content.images', True, 'chrome-devtools://*')
config.set('content.images', True, 'devtools://*')
config.set('content.javascript.enabled', True, 'chrome-devtools://*')
config.set('content.javascript.enabled', True, 'devtools://*')
config.set('content.javascript.enabled', True, 'chrome://*/*')
config.set('content.javascript.enabled', True, 'qute://*/*')
config.set('content.local_content_can_access_remote_urls', True, 'file:///home/kr4nk/.local/share/qutebrowser/userscripts/*')
config.set('content.local_content_can_access_file_urls', False, 'file:///home/kr4nk/.local/share/qutebrowser/userscripts/*')



# User settings
c.qt.args = ['enable-gpu-rasterization', 'ignore-gpu-blocklist', 'enable-zero-copy']
c.url.start_pages = ['https://github.com/kr4nkenwagen']
c.url.default_page = 'https://github.com/kr4nkenwagen'
c.downloads.prevent_mixed_content = False
c.tabs.position = 'left'
c.window.transparent = True
c.colors.webpage.darkmode.enabled = True
c.content.blocking.method = 'both'
c.statusbar.show = 'in-mode'
c.tabs.show = 'never'
c.content.user_stylesheets = '~/.config/qutebrowser/userstyles/all.css'

# Fonts
font = f'{get_font_size()}pt "{get_font()}"'
c.fonts.statusbar = font
c.fonts.completion.category = font
c.fonts.completion.entry = font
c.fonts.contextmenu = font
c.fonts.hints = font
c.fonts.downloads = font
c.fonts.keyhint = font
c.fonts.messages.error = font
c.fonts.messages.warning = font
c.fonts.messages.info = font
c.fonts.prompts = font
c.fonts.tabs.selected = font
c.fonts.tabs.unselected = font
c.fonts.tooltip = font
c.fonts.debug_console = font

# Binds
config.bind('<Space>I', 'hint images tab')
config.bind('<Space>O', 'hint links fill :open -t -r {hint-url}')
config.bind('<Space>R', 'hint --rapid links window')
config.bind('<Space>Y', 'hint links yank-primary')
config.bind('<Space>y', 'hint links yank')
config.bind('<Space>t', 'hint inputs')
config.bind('<Space>r', 'hint --rapid links tab-bg')
config.bind('<Space>o', 'hint links fill :open {hint-url}')
config.bind('<Space>i', 'hint images')
config.bind('<Space>h', 'hint all hover')
config.bind('<Space>f', 'hint all tab-fg')
config.bind('<Space>d', 'hint links download')
config.bind('<Space>m', 'hint links spawn mpv {hint-url}')
config.bind('<Space>x', 'config-cycle statusbar.show always never;; config-cycle tabs.show always never')
config.bind('<Space>c', 'config-clear;; config-source ~/.config/qutebrowser/config.py')
config.bind('<Space>ba', 'bookmark-add')
config.bind('<Space>bd', 'bookmark-del {url}')
config.bind('<Space>bl', 'bookmark-list')
config.bind(';', 'cmd-set-text :')

# Update CSS userstyle
css, userstyle = load_colors()
if userstyle:
    userstyle["bg_default"] = bg_default
    userstyle["bg_lighter"] = bg_lighter
    userstyle["bg_selection"] = bg_selection
    userstyle["fg_disabled"] = fg_disabled
    userstyle["fg_default"] = fg_default
    userstyle["bg_lightest"] = bg_lightest
    userstyle["red"] = fg_error
    userstyle["orage"] = bg_hint
    userstyle["yellow"] = fg_matched_text
    userstyle["green"] = bg_passthrough_mode
    userstyle["blue"] = bg_insert_mode
    userstyle["teal"] = bg_warning
    userstyle["font"] = get_font()
    save_colors(css, userstyle)

# ==========================================
# FULL MENU & COMPLETION TEXT COLOR STYLING
# ==========================================

# Completion Menu (Dropdown list when typing commands/URLs)
c.colors.completion.fg = fg_default
c.colors.completion.odd.bg = bg_lighter
c.colors.completion.even.bg = bg_default

# Completion Headers / Categories ("History", "Bookmarks", etc.)
c.colors.completion.category.fg = fg_matched_text
c.colors.completion.category.bg = bg_default
c.colors.completion.category.border.top = bg_default
c.colors.completion.category.border.bottom = bg_default

# Selected Completion Row
c.colors.completion.item.selected.fg = fg_selection
c.colors.completion.item.selected.bg = bg_selection
c.colors.completion.item.selected.border.top = bg_selection
c.colors.completion.item.selected.border.bottom = bg_selection
c.colors.completion.item.selected.match.fg = fg_matched_text
c.colors.completion.match.fg = fg_matched_text

c.colors.completion.scrollbar.fg = fg_default
c.colors.completion.scrollbar.bg = bg_default

# Context Menu (Right-click menu)
c.colors.contextmenu.menu.bg = bg_default
c.colors.contextmenu.menu.fg = fg_default
c.colors.contextmenu.selected.bg = bg_selection
c.colors.contextmenu.selected.fg = fg_selection
c.colors.contextmenu.disabled.bg = bg_lighter
c.colors.contextmenu.disabled.fg = fg_disabled

# Webpages & Hints
c.colors.webpage.bg = bg_default
c.colors.hints.match.fg = fg_matched_text
c.colors.hints.bg = bg_hint
c.colors.hints.fg = fg_default

# Downloads
c.colors.downloads.bar.bg = bg_default
c.colors.downloads.start.fg = bg_default
c.colors.downloads.start.bg = bg_insert_mode
c.colors.downloads.stop.fg = bg_default
c.colors.downloads.stop.bg = bg_passthrough_mode
c.colors.downloads.error.fg = fg_error

# Key hints & Messages
c.colors.keyhint.fg = fg_default
c.colors.keyhint.suffix.fg = fg_default
c.colors.keyhint.bg = bg_default
c.colors.messages.error.fg = bg_default
c.colors.messages.error.bg = fg_error
c.colors.messages.error.border = fg_error
c.colors.messages.warning.fg = bg_default
c.colors.messages.warning.bg = bg_warning
c.colors.messages.warning.border = bg_warning
c.colors.messages.info.fg = fg_default
c.colors.messages.info.bg = bg_default
c.colors.messages.info.border = bg_default

# Prompts
c.colors.prompts.fg = fg_default
c.colors.prompts.border = bg_default
c.colors.prompts.bg = bg_default
c.colors.prompts.selected.fg = fg_selection
c.colors.prompts.selected.bg = bg_selection

# Statusbar
c.colors.statusbar.normal.fg = fg_default
c.colors.statusbar.normal.bg = bg_transparent
c.colors.statusbar.insert.fg = bg_default
c.colors.statusbar.insert.bg = bg_insert_mode
c.colors.statusbar.passthrough.fg = bg_default
c.colors.statusbar.passthrough.bg = bg_passthrough_mode
c.colors.statusbar.private.fg = bg_default
c.colors.statusbar.private.bg = bg_lighter
c.colors.statusbar.command.fg = fg_default
c.colors.statusbar.command.bg = bg_default
c.colors.statusbar.command.private.fg = fg_default
c.colors.statusbar.command.private.bg = bg_default
c.colors.statusbar.caret.fg = bg_default
c.colors.statusbar.caret.bg = bg_warning
c.colors.statusbar.caret.selection.fg = bg_default
c.colors.statusbar.caret.selection.bg = bg_insert_mode
c.colors.statusbar.progress.bg = bg_insert_mode
c.colors.statusbar.url.fg = fg_default
c.colors.statusbar.url.error.fg = fg_error
c.colors.statusbar.url.hover.fg = fg_default
c.colors.statusbar.url.success.http.fg = bg_passthrough_mode
c.colors.statusbar.url.success.https.fg = fg_matched_text
c.colors.statusbar.url.warn.fg = bg_warning

# Tabs
c.colors.tabs.bar.bg = bg_transparent
c.colors.tabs.indicator.start = bg_insert_mode
c.colors.tabs.indicator.stop = bg_passthrough_mode
c.colors.tabs.indicator.error = fg_error
c.colors.tabs.odd.fg = fg_default
c.colors.tabs.odd.bg = bg_lighter
c.colors.tabs.even.fg = fg_default
c.colors.tabs.even.bg = bg_default
c.colors.tabs.pinned.even.bg = bg_passthrough_mode
c.colors.tabs.pinned.even.fg = bg_lightest
c.colors.tabs.pinned.odd.bg = fg_matched_text
c.colors.tabs.pinned.odd.fg = bg_lightest
c.colors.tabs.pinned.selected.even.bg = bg_selection
c.colors.tabs.pinned.selected.even.fg = fg_selection
c.colors.tabs.pinned.selected.odd.bg = bg_selection
c.colors.tabs.pinned.selected.odd.fg = fg_selection
c.colors.tabs.selected.odd.fg = fg_selection
c.colors.tabs.selected.odd.bg = bg_selection
c.colors.tabs.selected.even.fg = fg_selection
c.colors.tabs.selected.even.bg = bg_selection
#

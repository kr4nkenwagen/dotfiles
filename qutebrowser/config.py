from qutebrowser.api import interceptor
# Change the argument to True to still load settings configured via autoconfig.yml
config.load_autoconfig(False)

def youtube_filter(info: interceptor.Request):
    url = info.request_url
    if url.host() == 'www.youtube.com' and url.path() == '/get_video_info' and '&adformat=' in url.query():
        info.block()

interceptor.register(youtube_filter)

#Default settings
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

#User setting
c.downloads.prevent_mixed_content = False
c.tabs.position = 'left'
c.window.transparent = True
c.colors.webpage.darkmode.enabled = True
c.content.blocking.method = 'both'
c.statusbar.show = 'never'
c.tabs.show = 'never'
c.content.user_stylesheets = '~/.config/qutebrowser/userstyles/all.css'
#c.content.autoplay = False

#fonts
font = '11pt "Arimo Nerd Font"' 
c.fonts.statusbar = font
c.fonts.completion.category = font
c.fonts.completion.entry = font
c.fonts.contextmenu= font
c.fonts.hints = font
c.fonts.downloads= font
c.fonts.keyhint = font
c.fonts.completion.entry = font
c.fonts.messages.error= font
c.fonts.messages.warning = font
c.fonts.messages.info = font
c.fonts.prompts = font
c.fonts.tabs.selected = font
c.fonts.tabs.unselected = font
c.fonts.tooltip = font
c.fonts.completion.entry = font
c.fonts.completion.entry = font
c.fonts.debug_console = font

#Binds
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
#config.bind('<Space>b', 'hint all tab-bg')
config.bind('<Space>m', 'hint links spawn mpv {hint-url}')
config.bind('<Space>x', 'config-cycle statusbar.show always never;; config-cycle tabs.show always never')
config.bind('<Space>c', 'config-clear;; config-source ~/.config/qutebrowser/config.py')
config.bind('<Space>ba','bookmark-add')
config.bind('<Space>bd','bookmark-del {url}')
config.bind('<Space>bl','bookmark-list')
config.bind(';', 'cmd-set-text :')

# Colors
bg_default = "#1a1b26"
bg_lighter = "#16161a"
bg_selection = "#33467c"
# "#545862"
fg_disabled = "#565c64"
fg_default = "#c0caf5"
# "#b6bdca"
bg_lightest = "#c0caf5"         # main shade lightest
fg_error = "#ff899d"            # red
# "#d19a66"                     # orange
bg_hint = "#faba4a"             # yellow
fg_matched_text = "#9fe044"     # green
bg_passthrough_mode = "#a4daff" # teal
bg_insert_mode = "#8db0ff"      # blue
bg_warning = "#c7a9ff"          # purple
# "#be5046"                     # dark red

c.colors.webpage.bg = bg_default
c.colors.hints.match.fg = fg_matched_text
c.colors.hints.bg = bg_hint 
c.colors.hints.fg = bg_selection 
c.colors.completion.fg = fg_default
c.colors.completion.odd.bg = bg_lighter
c.colors.completion.even.bg = bg_default
c.colors.completion.category.fg = bg_hint
c.colors.completion.category.bg = bg_default
c.colors.completion.category.border.top = bg_default
c.colors.completion.category.border.bottom = bg_default
c.colors.completion.item.selected.fg = fg_default
c.colors.completion.item.selected.bg = bg_selection
c.colors.completion.item.selected.border.top = bg_selection
c.colors.completion.item.selected.border.bottom = bg_selection
c.colors.completion.item.selected.match.fg = fg_matched_text
c.colors.completion.match.fg = fg_matched_text
c.colors.completion.scrollbar.fg = fg_default
c.colors.completion.scrollbar.bg = bg_default
c.colors.contextmenu.disabled.bg = bg_lighter
c.colors.contextmenu.disabled.fg = fg_disabled
c.colors.contextmenu.menu.bg = bg_default
c.colors.contextmenu.menu.fg =  fg_default
c.colors.contextmenu.selected.bg = bg_selection
c.colors.contextmenu.selected.fg = fg_default
c.colors.downloads.bar.bg = bg_default
c.colors.downloads.start.fg = bg_default
c.colors.downloads.start.bg = bg_insert_mode
c.colors.downloads.stop.fg = bg_default
c.colors.downloads.stop.bg = bg_passthrough_mode
c.colors.downloads.error.fg = fg_error
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
c.colors.prompts.fg = fg_default
c.colors.prompts.border = bg_default
c.colors.prompts.bg = bg_default
c.colors.prompts.selected.fg = fg_default
c.colors.statusbar.normal.fg = fg_matched_text
c.colors.statusbar.normal.bg = bg_default
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
c.colors.tabs.bar.bg = bg_default
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
c.colors.tabs.pinned.selected.even.fg = fg_default
c.colors.tabs.pinned.selected.odd.bg = bg_selection
c.colors.tabs.pinned.selected.odd.fg = fg_default
c.colors.tabs.selected.odd.fg = fg_default
c.colors.tabs.selected.odd.bg = bg_selection
c.colors.tabs.selected.even.fg = fg_default
c.colors.tabs.selected.even.bg = bg_selection

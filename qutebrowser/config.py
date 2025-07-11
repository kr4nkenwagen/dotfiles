# Change the argument to True to still load settings configured via autoconfig.yml
config.load_autoconfig(False)

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
c.tabs.show = 'never'
c.window.transparent = True
c.colors.webpage.darkmode.enabled = True
c.content.blocking.method = 'both'

#Binds
config.bind(';', 'cmd-set-text :')
config.bind("'I", 'hint images tab')
config.bind("'O", 'hint links fill :open -t -r {hint-url}')
config.bind("'R", 'hint --rapid links window')
config.bind("'Y", 'hint links yank-primary')
config.bind("'y", 'hint links yank')
config.bind("'t", 'hint inputs')
config.bind("'r", 'hint --rapid links tab-bg')
config.bind("'o", 'hint links fill :open {hint-url}')
config.bind("'i", 'hint images')
config.bind("'h", 'hint all hover')
config.bind("'f", 'hint all tab-fg')
config.bind("'d", 'hint links download')
config.bind("'b", 'hint all tab-bg')


# Colors
bg_default = "#16161e"
bg_lighter = "#0c0e14"
bg_selection = "#3e4451"
# "#545862"
fg_disabled = "#565c64"
fg_default = "#abb2bf"
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
c.colors.hints.fg = bg_default
c.colors.hints.bg = bg_hint
c.colors.hints.match.fg = fg_default
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
c.colors.webpage.bg = bg_default

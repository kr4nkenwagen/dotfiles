-- Floating TUIs (Super+Shift+… in bindings.lua) and dialogs, as on Omarchy and Sway.
o.window({ class = "^(TUI.float)$" }, { float = true, size = "60% 70%", center = true })
o.window({ class = "^(org.pulseaudio.pavucontrol)$" }, { float = true, size = "50% 60%", center = true })
o.window({ class = "^(xdg-desktop-portal-gtk)$" }, { float = true, center = true })

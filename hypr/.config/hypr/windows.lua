-- Override Omarchy's default-opacity rule (default/hypr/windows.lua:25).
-- The Omarchy default tags all windows and sets opacity = "0.985 0.96";
-- this later rule flips it back to fully opaque.
o.window({ tag = "default-opacity" }, { opacity = "1 1" })

-- youtube-mpv.lua: loaded by the mpv that k4-youtube starts (the player in the corner, the
-- Kestrel design's YouTubePip board). Each video that plays, from the queue too, goes in the
-- history with where it stopped (time, id, position, length; again every 15 s and when it ends);
-- k4's corners are drawn over the picture, grey, the accent while the pointer is on it with one
-- hint; when mpv quits its socket goes. A Jellyfin stream (k4-jellyfin plays in this player too) is
-- reported to the server instead: started, where it is every 15 s and on pause, stopped
-- (k4-jellyfin report), so Jellyfin's resume and "watched" follow you to the TV.
local home = os.getenv("HOME")
local dir = home .. "/.local/state/k4/youtube"
local log = dir .. "/history.log"
local sock = (os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/k4-youtube.sock"

local function id_of(path)
	return path:match("[?&]v=([%w_-]+)") or path:match("youtu%.be/([%w_-]+)") or path:match("/shorts/([%w_-]+)")
end

local jf = nil -- the Jellyfin item playing (its id), nil for YouTube and other links
local function jf_of(path) return path:match("/Videos/(%x+)/stream") end
local function report(what, at)
	if not jf then return end
	mp.command_native_async({ name = "subprocess", playback_only = false, capture_stdout = true,
		args = { home .. "/.local/bin/k4-jellyfin", "report", what, jf, tostring(math.floor(at or pos)), mp.get_property_bool("pause") and "1" or "0" } }, function() end)
end

local cur, pos, len = nil, 0, 0
local function save(at)
	if not cur then return end
	local f = io.open(log, "a")
	if f then f:write(string.format("%d\t%s\t%d\t%d\n", os.time(), cur, math.floor(at or pos), math.floor(len))); f:close() end
end

mp.observe_property("time-pos", "number", function(_, v) if v then pos = v end end)
mp.observe_property("duration", "number", function(_, v) if v then len = v end end)
mp.add_periodic_timer(15, function() if not mp.get_property_bool("pause") then save(); report("progress") end end)
mp.observe_property("pause", "bool", function() report("progress") end)

mp.register_event("file-loaded", function()
	jf = jf_of(mp.get_property("path", ""))
	report("start", mp.get_property_number("time-pos", 0))
	cur, pos, len = id_of(mp.get_property("path", "")), mp.get_property_number("time-pos", 0), mp.get_property_number("duration", 0)
	if not cur then return end
	save()
	-- a link played without a search: its title and channel, for the history
	local meta = io.open(dir .. "/meta.tsv", "a")
	if meta then
		local clean = function(s) return (s or ""):gsub("[\t\n\r]", " ") end
		meta:write(cur .. "\t" .. clean(mp.get_property("media-title")) .. "\t" .. clean(mp.get_property("metadata/by-key/uploader") or mp.get_property("metadata/by-key/artist")) .. "\t" .. math.floor(len) .. "\n")
		meta:close()
	end
end)

mp.register_event("end-file", function(e)
	report("stop", e.reason == "eof" and len or pos); jf = nil
	save(e.reason == "eof" and len or pos) -- (played to the end: watched)
	cur = nil
end)

mp.register_event("shutdown", function() os.remove(sock) end)

-- k4's corners: 12 px, 2 px, grey (#2A4650); the accent (#3DF5FF) and "Super+Alt+Y hides" on hover
local ov = mp.create_osd_overlay("ass-events")
local hover = false
local function corners()
	local w, h = mp.get_osd_size()
	if not w or w == 0 then return end
	ov.res_x, ov.res_y = w, h
	local c = hover and "FFF53D" or "50462A" -- (ASS colours are BGR)
	local a, t = 12, 2
	local function box(x, y, bw, bh) return string.format("m %d %d l %d %d l %d %d l %d %d ", x, y, x + bw, y, x + bw, y + bh, x, y + bh) end
	local d = box(0, 0, a, t) .. box(0, 0, t, a) .. box(w - a, 0, a, t) .. box(w - t, 0, t, a)
		.. box(0, h - t, a, t) .. box(0, h - a, t, a) .. box(w - a, h - t, a, t) .. box(w - t, h - a, t, a)
	local s = string.format("{\\an7\\pos(0,0)\\bord0\\shad0\\1c&H%s&\\p1}%s{\\p0}", c, d)
	if hover then
		s = s .. string.format("\n{\\an9\\pos(%d,10)\\fnJetBrains Mono\\fs10\\bord4\\3c&H0C0704&\\1c&HDED3A9&}Super+Alt+Y hides", w - 10)
	end
	ov.data = s
	ov:update()
end
mp.observe_property("osd-dimensions", "native", corners)
mp.observe_property("mouse-pos", "native", function(_, m)
	local h = m ~= nil and m.hover == true
	if h ~= hover then hover = h; corners() end
end)

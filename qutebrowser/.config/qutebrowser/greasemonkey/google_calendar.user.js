// ==UserScript==
// @name         Google Calendar: weekends, now-line, less clutter
// @description  Marks Calendar for userstyles/google.css (html[data-qb-site="gcal"]): Saturday and Sunday columns (data-qb-weekend), the current-time line (data-qb-now), promos found by their text.
// @match        https://calendar.google.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

// localStorage.qbDebug = 1 (:jseval -w main localStorage.qbDebug=1) logs what each rule found.
(function () {
    'use strict';
    // the tag for google.css: <html> may not exist yet at document-start, and the app may rewrite its attributes
    const tag = () => { const h = document.documentElement; if (h && h.dataset.qbSite !== 'gcal') h.dataset.qbSite = 'gcal'; return !!h; };
    if (!tag()) new MutationObserver((m, o) => { if (tag()) o.disconnect(); }).observe(document, { childList: true });
    document.addEventListener('DOMContentLoaded', () => { tag(); new MutationObserver(tag).observe(document.documentElement, { attributes: true, attributeFilter: ['data-qb-site'] }); });
    const debug = (() => { try { return localStorage.qbDebug === '1'; } catch (e) { return false; } })();

    // a day's key in Calendar's grid: (year - 1970) << 9 | month << 5 | day, month from 1
    const dateOf = (key) => new Date((key >> 9) + 1970, ((key >> 5) & 15) - 1, key & 31);
    const today = () => { const d = new Date(); return (d.getFullYear() - 1970) << 9 | (d.getMonth() + 1) << 5 | d.getDate(); };

    const PROMO = /^(try gemini|get booking pages|upgrade|try google workspace)\b/i;
    const isRed = (c) => { const m = /rgba?\((\d+), (\d+), (\d+)/.exec(c); return m && +m[1] > 180 && +m[2] < 110 && +m[3] < 110; };

    function sweep() {
        const n = { weekend: 0, now: 0, promo: 0 };
        for (const el of document.querySelectorAll('[data-datekey]')) {
            const key = +el.dataset.datekey;
            if (!key) continue;
            const dow = dateOf(key).getDay();
            const we = dow === 0 || dow === 6;
            for (const t of [el, el.closest('[role="columnheader"], [role="gridcell"]')]) {
                if (!t) continue;
                if (we) { t.dataset.qbWeekend = ''; n.weekend++; } else delete t.dataset.qbWeekend;
            }
        }
        // the now-line: a thin red bar (and its dot) inside today's column; its class is obfuscated
        for (const old of document.querySelectorAll('[data-qb-now]')) delete old.dataset.qbNow;
        for (const col of document.querySelectorAll(`[data-datekey="${today()}"]`)) {
            for (const el of col.querySelectorAll('div')) {
                const r = el.getBoundingClientRect();
                if (r.height > 0 && r.height <= 14 && r.width >= 8 && isRed(getComputedStyle(el).backgroundColor)) { el.dataset.qbNow = ''; n.now++; }
            }
        }
        for (const el of document.querySelectorAll('[role="button"], a, button')) {
            const t = (el.textContent || '').trim();
            if (t.length < 60 && PROMO.test(t) && !el.closest('[role="dialog"] [contenteditable]')) { el.dataset.qbHide = 'promo'; n.promo++; }
        }
        if (debug) console.log('[qb gcal]', JSON.stringify(n));
    }

    let pending = 0;
    const later = () => { if (!pending) pending = setTimeout(() => { pending = 0; sweep(); }, 250); };
    const start = () => {
        sweep();
        new MutationObserver(later).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-datekey'] });
        setInterval(sweep, 60000);   // the now-line moves
    };
    if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})();

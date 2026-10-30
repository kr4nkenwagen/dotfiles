// ==UserScript==
// @name         Gmail: less clutter
// @description  Marks Gmail for userstyles/google.css (html[data-qb-site="gmail"]) and hides what CSS can't select: promo banners by their text, ad rows in Promotions and Social.
// @match        https://mail.google.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

// localStorage.qbDebug = 1 (:jseval -w main localStorage.qbDebug=1) logs what each rule found.
(function () {
    'use strict';
    // the tag for google.css: <html> may not exist yet at document-start, and the app may rewrite its attributes
    const tag = () => { const h = document.documentElement; if (h && h.dataset.qbSite !== 'gmail') h.dataset.qbSite = 'gmail'; return !!h; };
    if (!tag()) new MutationObserver((m, o) => { if (tag()) o.disconnect(); }).observe(document, { childList: true });
    document.addEventListener('DOMContentLoaded', () => { tag(); new MutationObserver(tag).observe(document.documentElement, { attributes: true, attributeFilter: ['data-qb-site'] }); });
    const debug = (() => { try { return localStorage.qbDebug === '1'; } catch (e) { return false; } })();
    const found = {};
    const hide = (el, rule) => {
        if (!el || el.dataset.qbHide) return;
        el.dataset.qbHide = rule;
        found[rule] = (found[rule] || 0) + 1;
    };

    // banners and buttons selling something, never inside a message or the list
    const PROMO = /^(get the gmail app|upgrade( now| storage)?|try gemini|get google one|try google workspace|storage (is )?(almost )?full)\b/i;
    const ADLABEL = /^(ad|sponsored|annons|sponsrad)$/i;   // (Gmail in Swedish: Annons)

    function sweep() {
        for (const el of document.querySelectorAll('[role="alert"], [role="button"], a, [role="link"]')) {
            if (el.closest('.a3s, tr.zA, [role="listitem"], [contenteditable]')) continue;
            const t = (el.textContent || '').trim();
            if (t.length < 60 && PROMO.test(t)) hide(el.closest('[role="alert"]') || el, 'promo');
        }
        for (const row of document.querySelectorAll('tr.zA:not([data-qb-hide])')) {
            for (const s of row.querySelectorAll('span')) {
                if (s.children.length === 0 && ADLABEL.test((s.textContent || '').trim())) { hide(row, 'ad row'); break; }
            }
        }
        if (debug) console.log('[qb gmail]', JSON.stringify(found));
    }

    let pending = 0;
    const later = () => { if (!pending) pending = setTimeout(() => { pending = 0; sweep(); }, 250); };
    const start = () => { sweep(); new MutationObserver(later).observe(document.body, { childList: true, subtree: true }); };
    if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})();

/**
 * Premium Animal Hospital — Platform JS
 * Theme switcher, mobile sidebar, utilities
 */

(function () {
  'use strict';

  /* ── Theme ─────────────────────────────────────────────────── */

  const THEMES = ['medical', 'logo'];
  const THEME_KEY = 'pah_platform_theme';

  function getTheme() {
    return document.documentElement.dataset.theme || 'medical';
  }

  function applyTheme(theme) {
    if (!THEMES.includes(theme)) theme = 'medical';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);

    // Sync all toggle buttons
    document.querySelectorAll('[data-theme-btn]').forEach(btn => {
      btn.classList.toggle('current', btn.dataset.themeBtn === theme);
    });

    // Update hidden inputs in theme forms
    document.querySelectorAll('input[name="theme"]').forEach(inp => {
      if (inp.type === 'hidden') inp.value = theme;
    });
  }

  function initTheme() {
    // Priority: data-theme from server (set on html tag) → localStorage
    const serverTheme = document.documentElement.dataset.theme;
    const stored = localStorage.getItem(THEME_KEY);
    const theme = serverTheme || stored || 'medical';
    applyTheme(theme);
  }

  // Theme button clicks (quick switch without form submit)
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-theme-btn]');
    if (!btn) return;
    const theme = btn.dataset.themeBtn;
    applyTheme(theme);

    // Also POST to server to persist in session
    const form = document.getElementById('pf-theme-form');
    if (form) {
      form.querySelector('input[name="theme"]').value = theme;
      form.submit();
    }
  });

  /* ── Mobile sidebar ─────────────────────────────────────────── */

  function initSidebar() {
    const toggleBtn = document.getElementById('pf-sidebar-toggle');
    const sidebar   = document.getElementById('pf-sidebar');
    const overlay   = document.getElementById('pf-overlay');

    if (!toggleBtn || !sidebar) return;

    function open() {
      sidebar.classList.add('open');
      if (overlay) overlay.classList.add('show');
      document.body.style.overflow = 'hidden';
    }
    function close() {
      sidebar.classList.remove('open');
      if (overlay) overlay.classList.remove('show');
      document.body.style.overflow = '';
    }

    toggleBtn.addEventListener('click', function () {
      sidebar.classList.contains('open') ? close() : open();
    });

    if (overlay) overlay.addEventListener('click', close);

    // Close on ESC
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close();
    });
  }

  /* ── Flash message auto-dismiss ─────────────────────────────── */

  function initFlash() {
    document.querySelectorAll('.pf-flash[data-autodismiss]').forEach(function (el) {
      const delay = parseInt(el.dataset.autodismiss || '4000', 10);
      setTimeout(function () {
        el.style.transition = 'opacity .4s';
        el.style.opacity = '0';
        setTimeout(function () { el.remove(); }, 450);
      }, delay);
    });
  }

  /* ── CSRF auto-inject into every POST form ──────────────────── */

  function initCsrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta) return;
    const token = meta.content;
    document.addEventListener('submit', function (e) {
      const form = e.target;
      if (!form || form.method.toLowerCase() !== 'post') return;
      if (!form.querySelector('input[name="_csrf_token"]')) {
        const inp = document.createElement('input');
        inp.type  = 'hidden';
        inp.name  = '_csrf_token';
        inp.value = token;
        form.appendChild(inp);
      }
    }, true); // capture phase — fires before any inline onsubmit
  }

  /* ── Sidebar section collapse ──────────────────────────────── */

  function initSidebarCollapse() {
    const KEY = 'pah_sidebar_collapsed';
    // Load saved collapsed state
    let collapsed = {};
    try { collapsed = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e) {}

    document.querySelectorAll('.pf-nav-section[data-section]').forEach(function(section) {
      var name = section.dataset.section;
      if (collapsed[name]) section.classList.add('collapsed');

      var toggle = section.querySelector('.pf-nav-section-toggle');
      if (!toggle) return;
      toggle.addEventListener('click', function() {
        var isNowCollapsed = section.classList.toggle('collapsed');
        collapsed[name] = isNowCollapsed;
        try { localStorage.setItem(KEY, JSON.stringify(collapsed)); } catch(e) {}
      });
    });
  }

  /* ── Sidebar scroll persistence ─────────────────────────────── */

  function initSidebarScroll() {
    const sidebar = document.getElementById('pf-sidebar');
    if (!sidebar) return;
    const nav = sidebar.querySelector('.pf-nav') || sidebar;
    const KEY = 'pah_sidebar_scroll';

    // Restore saved position
    const saved = localStorage.getItem(KEY);
    if (saved) nav.scrollTop = parseInt(saved, 10);

    // Save on scroll (throttled)
    let ticking = false;
    nav.addEventListener('scroll', function () {
      if (!ticking) {
        requestAnimationFrame(function () {
          localStorage.setItem(KEY, nav.scrollTop);
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  /* ── Module card clicks ─────────────────────────────────────── */

  function initModuleCards() {
    document.querySelectorAll('.pf-module-card[data-href]').forEach(function (card) {
      card.addEventListener('click', function (e) {
        // Ignore if a button inside was clicked
        if (e.target.closest('a, button')) return;
        const href = card.dataset.href;
        const target = card.dataset.target || '_self';
        if (href) {
          if (target === '_blank') window.open(href, '_blank');
          else window.location.href = href;
        }
      });
    });
  }

  /* ── Language toggle ────────────────────────────────────────── */

  document.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-lang-btn]');
    if (!btn) return;
    const lang = btn.dataset.langBtn;
    localStorage.setItem('pah_lang', lang);
    // POST to server so current_lang updates server-side, then reload
    const csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/settings/lang';
    form.style.display = 'none';
    const addField = (name, val) => {
      const inp = document.createElement('input');
      inp.type = 'hidden'; inp.name = name; inp.value = val;
      form.appendChild(inp);
    };
    addField('lang', lang);
    addField('_csrf_token', csrf);
    addField('next', window.location.pathname + window.location.search);
    document.body.appendChild(form);
    form.submit();
  });

  /* ── Confirm dialogs ────────────────────────────────────────── */

  document.addEventListener('click', function (e) {
    const el = e.target.closest('[data-confirm]');
    if (!el) return;
    const msg = el.dataset.confirm || 'Are you sure?';
    if (!confirm(msg)) e.preventDefault();
  });

  /* ── Universal table sort + filter (every <table> on every page) ── */

  var PAH_TBL_STYLE_INJECTED = false;

  function _injectTableStyles() {
    if (PAH_TBL_STYLE_INJECTED) return;
    PAH_TBL_STYLE_INJECTED = true;
    var s = document.createElement('style');
    s.textContent = [
      /* sort cursor on all th */
      'table thead th.pah-sortable{cursor:pointer;user-select:none;white-space:nowrap}',
      'table thead th.pah-sortable:hover{opacity:.8}',
      'table thead th.pah-sort-asc::after{content:" ▲";font-size:.7em;opacity:.7}',
      'table thead th.pah-sort-desc::after{content:" ▼";font-size:.7em;opacity:.7}',
      /* filter box */
      '.pah-tbl-filter-wrap{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}',
      '.pah-tbl-filter{padding:6px 12px;border:1.5px solid var(--cl-border,#e2e8f0);border-radius:8px;',
      '  font-size:13px;background:var(--cl-bg,#fff);color:var(--cl-text,#1e293b);width:220px;outline:none}',
      '.pah-tbl-filter:focus{border-color:var(--cl-primary,#7c3aed)}',
      '.pah-tbl-count{font-size:12px;color:var(--cl-muted,#64748b)}',
    ].join('');
    document.head.appendChild(s);
  }

  function _wireTable(tbl) {
    if (tbl._pahWired) return;
    tbl._pahWired = true;

    var tbody = tbl.querySelector('tbody');
    if (!tbody) return;

    // ── Sort ───────────────────────────────────────────────────────
    var ths = Array.from(tbl.querySelectorAll('thead th'));
    var sortAsc = {};

    ths.forEach(function (th, colIdx) {
      var label = th.textContent.trim();
      if (!label || label === '#') return; // skip empty / row-number cols
      // skip pure-action columns (contain only buttons or icons)
      if (th.querySelector('button,a,input')) return;

      th.classList.add('pah-sortable');
      sortAsc[colIdx] = true;

      th.addEventListener('click', function () {
        // clear others
        ths.forEach(function (s, i) {
          s.classList.remove('pah-sort-asc', 'pah-sort-desc');
        });

        var asc = sortAsc[colIdx];
        th.classList.add(asc ? 'pah-sort-asc' : 'pah-sort-desc');
        sortAsc[colIdx] = !asc;

        var rows = Array.from(tbody.querySelectorAll('tr')).filter(function (r) {
          return r.cells.length > 1 && !r._pahHidden;
        });

        rows.sort(function (a, b) {
          var av = (a.cells[colIdx] ? a.cells[colIdx].textContent : '').trim();
          var bv = (b.cells[colIdx] ? b.cells[colIdx].textContent : '').trim();
          // try numeric
          var an = parseFloat(av.replace(/[^\d.\-]/g, ''));
          var bn = parseFloat(bv.replace(/[^\d.\-]/g, ''));
          if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
          // try date
          var ad = Date.parse(av), bd = Date.parse(bv);
          if (!isNaN(ad) && !isNaN(bd)) return asc ? ad - bd : bd - ad;
          return asc ? av.localeCompare(bv) : bv.localeCompare(av);
        });

        rows.forEach(function (r) { tbody.appendChild(r); });
        _updateCount(tbl);
      });
    });

    // ── Filter ─────────────────────────────────────────────────────
    // Find a sensible place to insert: before the table, or before its
    // nearest wrapping .pf-card / .table-wrap / parent div
    var anchor = tbl.closest('.pf-card, .table-wrap, .owners-table-wrap') || tbl.parentNode;

    var wrap = document.createElement('div');
    wrap.className = 'pah-tbl-filter-wrap';

    var inp = document.createElement('input');
    inp.type = 'search';
    inp.className = 'pah-tbl-filter';
    inp.placeholder = '🔍  Quick search this table…';
    inp.setAttribute('autocomplete', 'off');

    var counter = document.createElement('span');
    counter.className = 'pah-tbl-count';

    wrap.appendChild(inp);
    wrap.appendChild(counter);

    // Insert the filter bar just before the anchor element
    anchor.parentNode.insertBefore(wrap, anchor);

    var allRows = Array.from(tbody.querySelectorAll('tr'));

    function applyFilter() {
      var q = inp.value.trim().toLowerCase();
      var visible = 0;
      allRows.forEach(function (r) {
        var text = r.textContent.toLowerCase();
        var show = !q || text.includes(q);
        r.style.display = show ? '' : 'none';
        r._pahHidden = !show;
        if (show && r.cells.length > 1) visible++;
      });
      counter.textContent = q ? ('Showing ' + visible + ' of ' + allRows.length) : '';
    }

    inp.addEventListener('input', applyFilter);
    inp.addEventListener('search', applyFilter); // clear button on search input

    _updateCount(tbl);
  }

  function _updateCount(tbl) { /* no-op placeholder for future row counters */ }

  function initTableSort() {
    _injectTableStyles();
    // Target every table that has at least one header row — platform-wide
    document.querySelectorAll('table').forEach(function (tbl) {
      // skip tiny tables (modals, form-layout tables, etc.)
      var rows = tbl.querySelectorAll('tbody tr');
      if (rows.length === 0) return;
      // skip tables inside modals or print sections
      if (tbl.closest('.pf-modal-overlay, .invoice-print, [data-no-sort]')) return;
      _wireTable(tbl);
    });
  }

  /* ── Searchable select (owner / patient dropdowns) ──────────── */

  function initSearchableSelect() {
    // Apply to any select with id containing "ownerSel", "petSel",
    // or having the attribute data-searchable
    var selects = document.querySelectorAll(
      'select[id="ownerSel"], select[data-searchable]'
    );
    selects.forEach(function (sel) {
      if (sel.dataset.searchableInit) return; // already wired
      sel.dataset.searchableInit = '1';

      var wrapper = document.createElement('div');
      wrapper.style.cssText = 'position:relative';
      sel.parentNode.insertBefore(wrapper, sel);
      wrapper.appendChild(sel);

      var inp = document.createElement('input');
      inp.type = 'text';
      inp.placeholder = 'Type to search…';
      inp.className = sel.className;
      inp.style.marginBottom = '4px';
      wrapper.insertBefore(inp, sel);

      var allOpts = Array.from(sel.options).map(function (o) {
        return { text: o.text, value: o.value, el: o };
      });

      inp.addEventListener('input', function () {
        var q = inp.value.trim().toLowerCase();
        allOpts.forEach(function (o) {
          var match = !q || o.text.toLowerCase().includes(q);
          o.el.hidden = !match;
        });
        // auto-select first visible non-empty option when one match
        var visible = allOpts.filter(function (o) { return !o.el.hidden && o.value; });
        if (visible.length === 1) sel.value = visible[0].value;
      });

      // When select changes, update the input text
      sel.addEventListener('change', function () {
        var chosen = sel.options[sel.selectedIndex];
        if (chosen && chosen.value) inp.value = chosen.text;
      });

      // Clear filter when user clicks the select directly
      sel.addEventListener('focus', function () { inp.value = ''; allOpts.forEach(function (o) { o.el.hidden = false; }); });
    });
  }

  /* ── Tooltips (simple title-based) ─────────────────────────── */

  /* ── Init ───────────────────────────────────────────────────── */

  document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    initSidebar();
    initSidebarCollapse();
    initSidebarScroll();
    initCsrf();
    initFlash();
    initModuleCards();
    initTableSort();
    initSearchableSelect();

    // Restore lang direction
    const savedLang = localStorage.getItem('pah_lang');
    if (savedLang === 'ar') {
      document.documentElement.setAttribute('dir', 'rtl');
      document.documentElement.setAttribute('lang', 'ar');
    }
  });

  // Expose global API for inline scripts
  window.PAH = { applyTheme, getTheme };

})();

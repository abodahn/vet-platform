/**
 * Aleefy V3 — Core JavaScript
 * Premium Animal Hospital Platform
 *
 * Sections:
 *  1. Theme System
 *  2. Petsy Chatbot
 *  3. Offline Detection
 *  4. Toast System
 *  5. Mobile Sidebar
 *  6. Active Nav Item
 *  7. Page Transitions
 *  8. Form Enhancements
 *  9. Table Enhancements
 * 10. Search Enhancement
 * 11. Skeleton Loaders
 * 12. Copy to Clipboard
 * 13. Confirmation Dialogs
 * 14. Number Counter Animation
 */

(function () {
  'use strict';

  /* =========================================================
   * UTILITIES
   * ======================================================= */

  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(this, args); }, ms);
    };
  }

  function safeLocalGet(key, fallback) {
    try { var v = localStorage.getItem(key); return v !== null ? v : fallback; } catch (e) { return fallback; }
  }

  function safeLocalSet(key, val) {
    try { localStorage.setItem(key, val); } catch (e) { /* quota / private mode */ }
  }

  /* =========================================================
   * 1. THEME SYSTEM
   * ======================================================= */

  var THEME_KEY = 'al-theme';
  var THEME_TRANSITION_CLASS = 'v3-theme-transitioning';
  var themeTransitionTimer = null;

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    _updateThemeIcons(theme);
  }

  function _updateThemeIcons(theme) {
    var isDark = theme === 'dark';
    // Bootstrap Icon <i> elements — swap class names
    var biIds = ['v3-topbar-theme-icon', 'v3-sidebar-theme-icon'];
    biIds.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) {
        el.className = isDark ? 'bi bi-sun' : 'bi bi-moon-stars';
        el.setAttribute('title', isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode');
      }
    });
    // Sidebar label text (Day / Night)
    var lbl = document.getElementById('v3-sidebar-theme-label');
    if (lbl) lbl.textContent = isDark ? 'Day' : 'Night';
    // Also handle legacy text-based icons
    qsa('[data-v3-theme-icon], .v3-theme-icon').forEach(function (el) {
      el.textContent = isDark ? '☀️' : '🌙';
    });
  }

  function v3SetTheme(theme) {
    try {
      safeLocalSet(THEME_KEY, theme);
      // Add transitioning class to enable smooth CSS transition
      document.documentElement.classList.add(THEME_TRANSITION_CLASS);
      applyTheme(theme);
      if (themeTransitionTimer) clearTimeout(themeTransitionTimer);
      themeTransitionTimer = setTimeout(function () {
        document.documentElement.classList.remove(THEME_TRANSITION_CLASS);
      }, 400);
    } catch (e) {
      console.warn('[V3] Theme error:', e);
    }
  }

  function v3ToggleTheme() {
    var current = safeLocalGet(THEME_KEY, 'light');
    v3SetTheme(current === 'dark' ? 'light' : 'dark');
  }

  // Expose
  window.v3SetTheme = v3SetTheme;
  window.v3ToggleTheme = v3ToggleTheme;

  // Init on DOMContentLoaded (post-load logic; no-flash handled in <head>)
  document.addEventListener('DOMContentLoaded', function () {
    var saved = safeLocalGet(THEME_KEY, 'light');
    applyTheme(saved);
  });

  /* =========================================================
   * 4. TOAST SYSTEM  (defined before offline so offline can use it)
   * ======================================================= */

  var toastContainer = null;
  var activeToasts = [];
  var MAX_TOASTS = 4;

  var TOAST_COLORS = {
    success: '#22c55e',
    error:   '#ef4444',
    warning: '#f97316',
    info:    '#3b82f6'
  };

  var TOAST_ICONS = {
    success: '✓',
    error:   '✕',
    warning: '⚠',
    info:    'ℹ'
  };

  function _ensureToastContainer() {
    if (toastContainer && document.body.contains(toastContainer)) return;
    toastContainer = document.createElement('div');
    toastContainer.id = 'v3-toast-container';
    Object.assign(toastContainer.style, {
      position:      'fixed',
      top:           '16px',
      right:         '16px',
      zIndex:        '99999',
      display:       'flex',
      flexDirection: 'column',
      gap:           '8px',
      pointerEvents: 'none'
    });
    document.body.appendChild(toastContainer);
  }

  function v3ShowToast(msg, type, duration) {
    type = type || 'info';
    duration = (duration === undefined || duration === null) ? 3500 : duration;

    try {
      _ensureToastContainer();

      // Enforce FIFO max
      while (activeToasts.length >= MAX_TOASTS) {
        var oldest = activeToasts.shift();
        _dismissToast(oldest);
      }

      var color = TOAST_COLORS[type] || TOAST_COLORS.info;
      var icon  = TOAST_ICONS[type]  || TOAST_ICONS.info;

      var toast = document.createElement('div');
      toast.setAttribute('role', 'alert');
      Object.assign(toast.style, {
        background:    '#1e293b',
        color:         '#f1f5f9',
        borderLeft:    '4px solid ' + color,
        borderRadius:  '8px',
        padding:       '12px 16px',
        minWidth:      '260px',
        maxWidth:      '380px',
        boxShadow:     '0 4px 24px rgba(0,0,0,0.3)',
        display:       'flex',
        alignItems:    'flex-start',
        gap:           '10px',
        fontSize:      '14px',
        lineHeight:    '1.4',
        pointerEvents: 'all',
        cursor:        'pointer',
        transform:     'translateX(120%)',
        transition:    'transform 0.3s cubic-bezier(0.34,1.56,0.64,1), opacity 0.3s ease',
        opacity:       '0'
      });

      var iconEl = document.createElement('span');
      Object.assign(iconEl.style, {
        color:      color,
        fontWeight: 'bold',
        fontSize:   '16px',
        flexShrink: '0',
        marginTop:  '1px'
      });
      iconEl.textContent = icon;

      var textEl = document.createElement('span');
      textEl.style.flex = '1';
      textEl.textContent = msg;

      var closeEl = document.createElement('span');
      Object.assign(closeEl.style, {
        color:      '#94a3b8',
        cursor:     'pointer',
        flexShrink: '0',
        fontSize:   '16px',
        lineHeight: '1'
      });
      closeEl.textContent = '×';
      closeEl.addEventListener('click', function (e) {
        e.stopPropagation();
        _dismissToast(toast);
      });

      toast.appendChild(iconEl);
      toast.appendChild(textEl);
      toast.appendChild(closeEl);
      toastContainer.appendChild(toast);
      activeToasts.push(toast);

      // Slide in
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          toast.style.transform = 'translateX(0)';
          toast.style.opacity   = '1';
        });
      });

      // Click whole toast to dismiss
      toast.addEventListener('click', function () { _dismissToast(toast); });

      // Auto-dismiss
      if (duration > 0) {
        toast._dismissTimer = setTimeout(function () { _dismissToast(toast); }, duration);
      }
    } catch (e) {
      console.warn('[V3] Toast error:', e);
    }
  }

  function _dismissToast(toast) {
    if (!toast || !toast.parentNode) return;
    if (toast._dismissTimer) clearTimeout(toast._dismissTimer);
    toast.style.transform = 'translateX(120%)';
    toast.style.opacity   = '0';
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
      var idx = activeToasts.indexOf(toast);
      if (idx !== -1) activeToasts.splice(idx, 1);
    }, 350);
  }

  window.v3ShowToast = v3ShowToast;

  /* =========================================================
   * 3. OFFLINE DETECTION
   * ======================================================= */

  function _initOfflineDetection() {
    var banner = qs('#v3-offline-banner');

    function showOffline() {
      if (banner) {
        banner.style.display = 'flex';
        banner.removeAttribute('hidden');
      } else {
        // Create a fallback banner if not in HTML
        var b = document.createElement('div');
        b.id = 'v3-offline-banner';
        Object.assign(b.style, {
          position:       'fixed',
          top:            '0',
          left:           '0',
          right:          '0',
          zIndex:         '99998',
          background:     '#ef4444',
          color:          '#fff',
          padding:        '10px 20px',
          textAlign:      'center',
          fontSize:       '14px',
          fontWeight:     '600',
          display:        'flex',
          alignItems:     'center',
          justifyContent: 'center',
          gap:            '8px'
        });
        b.innerHTML = '<span>📡</span><span>You are offline. Some features may be unavailable.</span>';
        document.body.insertBefore(b, document.body.firstChild);
        banner = b;
      }
    }

    function hideOffline() {
      if (banner) {
        banner.style.display = 'none';
        banner.setAttribute('hidden', '');
      }
      v3ShowToast('Back online! Syncing...', 'success', 3000);
    }

    window.addEventListener('offline', showOffline);
    window.addEventListener('online',  hideOffline);

    // Set initial state
    if (!navigator.onLine) showOffline();
  }

  document.addEventListener('DOMContentLoaded', _initOfflineDetection);

  /* =========================================================
   * 2. PETSY CHATBOT
   * ======================================================= */

  var Petsy = (function () {
    var FAB_KEY   = 'petsy-pos';
    var STATE_KEY = 'petsy-state';
    var SRC_KEY   = 'petsy-src-loaded';

    var fab    = null;
    var panel  = null;
    var iframe = null;
    var state  = 'closed'; // 'open' | 'closed' | 'minimized'

    // Drag state
    var drag = {
      active:    false,
      startX:    0,
      startY:    0,
      origLeft:  0,
      origTop:   0,
      moved:     false,
      threshold: 6
    };

    // Support both IDs: base.html uses -global suffix; fallback to bare IDs
    function _getFab()   { return fab   || (fab   = qs('#petsy-fab-global') || qs('#petsy-fab')); }
    function _getPanel() { return panel || (panel = qs('#petsy-panel-global') || qs('#petsy-panel')); }
    function _getIframe(){ return iframe || (iframe = qs('#petsy-iframe')); }

    function _loadIframe() {
      var fr = _getIframe();
      if (!fr) return;
      var src = fr.getAttribute('data-src') || fr.getAttribute('src');
      if (!fr.src || fr.src === window.location.href || safeLocalGet(SRC_KEY, '') !== src) {
        if (fr.getAttribute('data-src')) {
          fr.src = fr.getAttribute('data-src');
          safeLocalSet(SRC_KEY, fr.src);
        }
      }
    }

    function _positionPanel() {
      var f = _getFab();
      var p = _getPanel();
      if (!f || !p) return;

      var fRect  = f.getBoundingClientRect();
      var vw     = window.innerWidth;
      var vh     = window.innerHeight;
      var pw     = p.offsetWidth  || 360;
      var ph     = p.offsetHeight || 520;

      // Prefer opening above-left of FAB
      var top  = fRect.top  - ph - 12;
      var left = fRect.left - pw + fRect.width;

      // Clamp to viewport
      if (top  < 10)       top  = Math.min(fRect.bottom + 12, vh - ph - 10);
      if (left < 10)       left = 10;
      if (left + pw > vw - 10) left = vw - pw - 10;
      if (top  + ph > vh - 10) top  = vh - ph - 10;
      if (top  < 10)       top  = 10;

      p.style.position = 'fixed';
      p.style.left     = left + 'px';
      p.style.top      = top  + 'px';
      p.style.zIndex   = '10000';
    }

    function petsyOpen() {
      var f = _getFab();
      var p = _getPanel();
      if (!p) return;

      _loadIframe();
      p.style.display  = 'flex';
      p.style.zIndex   = '10000';
      p.style.opacity  = '0';
      p.style.transform = 'scale(0.92) translateY(12px)';
      _positionPanel();

      requestAnimationFrame(function () {
        p.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
        p.style.opacity    = '1';
        p.style.transform  = 'scale(1) translateY(0)';
      });

      if (f) f.setAttribute('aria-expanded', 'true');
      state = 'open';
      safeLocalSet(STATE_KEY, 'open');
    }

    function petsyClose() {
      var f = _getFab();
      var p = _getPanel();
      if (!p) return;

      p.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
      p.style.opacity    = '0';
      p.style.transform  = 'scale(0.92) translateY(12px)';

      setTimeout(function () {
        p.style.display = 'none';
      }, 220);

      if (f) f.setAttribute('aria-expanded', 'false');
      state = 'closed';
      safeLocalSet(STATE_KEY, 'closed');
    }

    function petsyMinimize() {
      var f = _getFab();
      var p = _getPanel();
      if (!p) return;

      p.style.transition = 'opacity 0.2s ease, transform 0.25s ease';
      p.style.opacity    = '0';
      p.style.transform  = 'translateY(40px) scale(0.95)';

      setTimeout(function () {
        p.style.display = 'none';
      }, 250);

      if (f) f.setAttribute('aria-expanded', 'false');
      state = 'minimized';
      safeLocalSet(STATE_KEY, 'minimized');
    }

    function petsyToggle() {
      if (state === 'open') {
        // Do nothing if already open — per spec
        return;
      }
      petsyOpen();
    }

    // ---- Drag Logic ----

    function _clampFabToViewport(left, top) {
      var f = _getFab();
      if (!f) return { left: left, top: top };
      var fw = f.offsetWidth  || 56;
      var fh = f.offsetHeight || 56;
      var vw = window.innerWidth;
      var vh = window.innerHeight;
      return {
        left: Math.max(0, Math.min(left, vw - fw)),
        top:  Math.max(0, Math.min(top,  vh - fh))
      };
    }

    function _setFabPos(left, top) {
      var f = _getFab();
      if (!f) return;
      var clamped = _clampFabToViewport(left, top);
      f.style.left   = clamped.left + 'px';
      f.style.top    = clamped.top  + 'px';
      f.style.right  = 'auto';
      f.style.bottom = 'auto';
      f.style.position = 'fixed';
      safeLocalSet(FAB_KEY, JSON.stringify(clamped));
    }

    function _restoreFabPos() {
      var raw = safeLocalGet(FAB_KEY, null);
      if (!raw) return;
      try {
        var pos = JSON.parse(raw);
        _setFabPos(pos.left, pos.top);
      } catch (e) { /* ignore */ }
    }

    function _onMouseDown(e) {
      // Only primary button
      if (e.button !== 0) return;
      var f = _getFab();
      if (!f) return;
      var rect = f.getBoundingClientRect();
      drag.active   = true;
      drag.moved    = false;
      drag.startX   = e.clientX;
      drag.startY   = e.clientY;
      drag.origLeft = rect.left;
      drag.origTop  = rect.top;
      e.preventDefault();
    }

    function _onMouseMove(e) {
      if (!drag.active) return;
      var dx = e.clientX - drag.startX;
      var dy = e.clientY - drag.startY;
      if (Math.abs(dx) > drag.threshold || Math.abs(dy) > drag.threshold) {
        drag.moved = true;
      }
      if (drag.moved) {
        _setFabPos(drag.origLeft + dx, drag.origTop + dy);
        if (state === 'open') _positionPanel();
      }
    }

    function _onMouseUp(e) {
      if (!drag.active) return;
      drag.active = false;
      if (!drag.moved) {
        // Treat as click
        petsyToggle();
      }
    }

    function _onTouchStart(e) {
      var t = e.touches[0];
      var f = _getFab();
      if (!f) return;
      var rect = f.getBoundingClientRect();
      drag.active   = true;
      drag.moved    = false;
      drag.startX   = t.clientX;
      drag.startY   = t.clientY;
      drag.origLeft = rect.left;
      drag.origTop  = rect.top;
    }

    function _onTouchMove(e) {
      if (!drag.active) return;
      var t  = e.touches[0];
      var dx = t.clientX - drag.startX;
      var dy = t.clientY - drag.startY;
      if (Math.abs(dx) > drag.threshold || Math.abs(dy) > drag.threshold) {
        drag.moved = true;
        e.preventDefault(); // prevent scroll while dragging
      }
      if (drag.moved) {
        _setFabPos(drag.origLeft + dx, drag.origTop + dy);
        if (state === 'open') _positionPanel();
      }
    }

    function _onTouchEnd(e) {
      if (!drag.active) return;
      drag.active = false;
      if (!drag.moved) {
        petsyToggle();
      }
    }

    function _bindCloseButton() {
      var p = _getPanel();
      if (!p) return;
      var closeBtn = p.querySelector('[data-petsy-close]') || p.querySelector('.petsy-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          petsyClose();
        });
      }
    }

    function init() {
      var f = _getFab();
      if (!f) return; // Petsy not on this page

      // FAB z-index
      f.style.zIndex = '9999';
      f.style.position = 'fixed';
      f.style.cursor = 'grab';

      // Restore position
      _restoreFabPos();

      // Drag — mouse
      f.addEventListener('mousedown', _onMouseDown);
      document.addEventListener('mousemove', _onMouseMove);
      document.addEventListener('mouseup',   _onMouseUp);

      // Drag — touch
      f.addEventListener('touchstart', _onTouchStart, { passive: true });
      f.addEventListener('touchmove',  _onTouchMove,  { passive: false });
      f.addEventListener('touchend',   _onTouchEnd,   { passive: true });

      // Bind close button in panel
      _bindCloseButton();

      // Keyboard shortcuts
      document.addEventListener('keydown', function (e) {
        // Alt+P: toggle
        if (e.altKey && (e.key === 'p' || e.key === 'P')) {
          e.preventDefault();
          if (state === 'open') {
            petsyClose();
          } else {
            petsyOpen();
          }
        }
        // Escape: minimize if open
        if (e.key === 'Escape' && state === 'open') {
          petsyMinimize();
        }
      });

      // Restore state
      var savedState = safeLocalGet(STATE_KEY, 'closed');
      if (savedState === 'open') {
        // Small delay so layout is settled
        setTimeout(petsyOpen, 200);
      }
      // minimized / closed → just leave panel hidden (default)

      // Window resize: re-clamp FAB and reposition panel
      window.addEventListener('resize', debounce(function () {
        var raw = safeLocalGet(FAB_KEY, null);
        if (raw) {
          try {
            var pos = JSON.parse(raw);
            _setFabPos(pos.left, pos.top);
          } catch (e) { /* ignore */ }
        }
        if (state === 'open') _positionPanel();
      }, 150));
    }

    return {
      init:     init,
      open:     petsyOpen,
      close:    petsyClose,
      minimize: petsyMinimize,
      toggle:   petsyToggle
    };
  })();

  // Expose Petsy functions globally
  window.petsyOpen     = function () { Petsy.open(); };
  window.petsyClose    = function () { Petsy.close(); };
  window.petsyMinimize = function () { Petsy.minimize(); };
  window.petsyToggle   = function () { Petsy.toggle(); };

  document.addEventListener('DOMContentLoaded', function () { Petsy.init(); });

  /* =========================================================
   * 5. MOBILE SIDEBAR
   * ======================================================= */

  function _initMobileSidebar() {
    var toggleBtns = qsa('.v3-sidebar-toggle');
    var sidebar    = qs('.v3-sidebar') || qs('[data-v3-sidebar]');
    var backdrop   = qs('#v3-sidebar-backdrop');

    if (!toggleBtns.length && !sidebar) return;

    // Create backdrop if not in HTML
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'v3-sidebar-backdrop';
      Object.assign(backdrop.style, {
        display:    'none',
        position:   'fixed',
        inset:      '0',
        background: 'rgba(0,0,0,0.45)',
        zIndex:     '8998',
        transition: 'opacity 0.3s ease',
        opacity:    '0'
      });
      document.body.appendChild(backdrop);
    }

    function openSidebar() {
      document.body.classList.add('v3-sidebar-open');
      backdrop.style.display = 'block';
      requestAnimationFrame(function () {
        backdrop.style.opacity = '1';
      });
      if (sidebar) {
        sidebar.setAttribute('aria-hidden', 'false');
        // Focus first link for accessibility
        var first = sidebar.querySelector('a, button');
        if (first) setTimeout(function () { first.focus(); }, 300);
      }
    }

    function closeSidebar() {
      document.body.classList.remove('v3-sidebar-open');
      backdrop.style.opacity = '0';
      setTimeout(function () {
        backdrop.style.display = 'none';
      }, 300);
      if (sidebar) sidebar.setAttribute('aria-hidden', 'true');
    }

    toggleBtns.forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (document.body.classList.contains('v3-sidebar-open')) {
          closeSidebar();
        } else {
          openSidebar();
        }
      });
    });

    backdrop.addEventListener('click', closeSidebar);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && document.body.classList.contains('v3-sidebar-open')) {
        closeSidebar();
      }
    });
  }

  document.addEventListener('DOMContentLoaded', _initMobileSidebar);

  /* =========================================================
   * 6. ACTIVE NAV ITEM
   * ======================================================= */

  function _initActiveNav() {
    var current = window.location.pathname.replace(/\/$/, '') || '/';
    var navLinks = qsa('.v3-sidebar a[href], nav.v3-nav a[href]');
    var activeGroup = null;

    navLinks.forEach(function (link) {
      try {
        var href = link.getAttribute('href');
        if (!href || href === '#') return;

        var linkPath = new URL(href, window.location.origin).pathname.replace(/\/$/, '') || '/';

        var isActive = (current === linkPath) ||
                       (linkPath !== '/' && current.startsWith(linkPath));

        if (isActive) {
          link.classList.add('active');
          link.setAttribute('aria-current', 'page');

          // Remember the parent group so accordion can expand it
          var parent = link.closest('.v3-nav-group');
          if (parent) activeGroup = parent;
        }
      } catch (e) { /* ignore malformed URLs */ }
    });

    return activeGroup;
  }

  /* =========================================================
   * 6b. NAV ACCORDION (collapse / expand groups)
   * ======================================================= */

  var NAV_STATE_KEY = 'v3-nav-groups';

  function _initNavAccordion() {
    var activeGroup = _initActiveNav();
    var groups  = qsa('.v3-nav-group');
    if (!groups.length) return;

    // Restore saved state
    var savedRaw = safeLocalGet(NAV_STATE_KEY, null);
    var saved = {};
    try { if (savedRaw) saved = JSON.parse(savedRaw); } catch (e) { /* */ }

    groups.forEach(function (group) {
      var key = group.getAttribute('data-group') || group.dataset.group || '';
      var btn = group.querySelector('.v3-nav-toggle');

      // Determine initial collapsed state:
      // - active group is ALWAYS expanded
      // - otherwise use saved state (default: expanded)
      var isCollapsed = (group === activeGroup) ? false : (saved[key] === false);

      if (isCollapsed) {
        group.classList.add('collapsed');
        if (btn) btn.setAttribute('aria-expanded', 'false');
      } else {
        group.classList.remove('collapsed');
        if (btn) btn.setAttribute('aria-expanded', 'true');
      }

      // Click handler
      if (btn) {
        btn.addEventListener('click', function (e) {
          e.stopPropagation();
          var nowCollapsed = group.classList.toggle('collapsed');
          btn.setAttribute('aria-expanded', nowCollapsed ? 'false' : 'true');

          // Persist
          try {
            var st = {};
            try { st = JSON.parse(safeLocalGet(NAV_STATE_KEY, '{}')) || {}; } catch (_) { /* */ }
            st[key] = !nowCollapsed; // store 'true' = expanded
            safeLocalSet(NAV_STATE_KEY, JSON.stringify(st));
          } catch (_) { /* */ }
        });
      }
    });

    // Scroll sidebar to show active link
    var activeLink = qs('.v3-nav-item.active');
    if (activeLink) {
      setTimeout(function () {
        try { activeLink.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } catch (e) { /* */ }
      }, 100);
    }

    // Save sidebar scroll position between page loads
    var nav = qs('.v3-nav, #v3-nav');
    if (nav) {
      var scrollKey = 'v3-nav-scroll';
      var savedScroll = parseInt(safeLocalGet(scrollKey, '0'), 10) || 0;
      nav.scrollTop = savedScroll;
      nav.addEventListener('scroll', debounce(function () {
        safeLocalSet(scrollKey, nav.scrollTop);
      }, 200));
    }
  }

  document.addEventListener('DOMContentLoaded', _initNavAccordion);

  /* =========================================================
   * 7. PAGE TRANSITIONS
   * ======================================================= */

  function _initPageTransitions() {
    var content = qs('.v3-content, main.content, [data-v3-content]');
    if (!content) return;

    content.classList.add('v3-animate-in');

    // Stagger child cards
    var cards = qsa('.v3-card, .card, .v3-stat-card', content);
    cards.forEach(function (card, i) {
      card.style.animationDelay = (i * 60) + 'ms';
      card.classList.add('v3-card-stagger');
    });
  }

  document.addEventListener('DOMContentLoaded', _initPageTransitions);

  /* =========================================================
   * 8. FORM ENHANCEMENTS
   * ======================================================= */

  function _initForms() {
    // Auto-focus first input
    qsa('.v3-form').forEach(function (form) {
      var first = form.querySelector('input:not([type=hidden]):not([disabled]), textarea:not([disabled]), select:not([disabled])');
      if (first && !first.value) {
        try { first.focus(); } catch (e) { /* ignore */ }
      }

      // Password show/hide toggle
      qsa('input[type="password"]', form).forEach(function (input) {
        if (input.dataset.pwToggled) return;
        input.dataset.pwToggled = '1';

        var wrapper = document.createElement('div');
        wrapper.style.position = 'relative';
        wrapper.style.display  = 'block';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        var toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.setAttribute('aria-label', 'Show/hide password');
        toggle.setAttribute('tabindex', '-1');
        Object.assign(toggle.style, {
          position:   'absolute',
          right:      '10px',
          top:        '50%',
          transform:  'translateY(-50%)',
          background: 'none',
          border:     'none',
          cursor:     'pointer',
          padding:    '0',
          fontSize:   '18px',
          lineHeight: '1',
          color:      '#94a3b8'
        });
        toggle.textContent = '👁';
        wrapper.appendChild(toggle);

        toggle.addEventListener('click', function () {
          if (input.type === 'password') {
            input.type = 'text';
            toggle.textContent = '🙈';
          } else {
            input.type = 'password';
            toggle.textContent = '👁';
          }
          input.focus();
        });
      });

      // Validation feedback
      form.addEventListener('submit', function (e) {
        var invalid = qsa(':invalid', form);
        if (invalid.length) {
          e.preventDefault();
          invalid.forEach(function (field) {
            field.classList.add('v3-field-error');
            var errId = field.id + '-error';
            var existing = document.getElementById(errId);
            if (!existing) {
              var errDiv = document.createElement('div');
              errDiv.id = errId;
              errDiv.className = 'v3-error-msg';
              Object.assign(errDiv.style, {
                color:     '#ef4444',
                fontSize:  '12px',
                marginTop: '4px'
              });
              errDiv.textContent = field.validationMessage || 'This field is required.';
              field.parentNode.insertBefore(errDiv, field.nextSibling);
            }
            field.setAttribute('aria-describedby', errId);
          });
          // Focus first invalid
          invalid[0].focus();
        }
      });

      // Clear error on input
      form.addEventListener('input', function (e) {
        var t = e.target;
        if (t && t.classList.contains('v3-field-error')) {
          t.classList.remove('v3-field-error');
          var errDiv = document.getElementById(t.id + '-error');
          if (errDiv) errDiv.parentNode.removeChild(errDiv);
        }
      }, true);
    });
  }

  document.addEventListener('DOMContentLoaded', _initForms);

  /* =========================================================
   * 9. TABLE ENHANCEMENTS
   * ======================================================= */

  function _initTables() {
    qsa('.v3-table-wrap').forEach(function (wrap) {
      // Ensure horizontal scroll
      if (!wrap.style.overflowX) {
        wrap.style.overflowX = 'auto';
        wrap.style.WebkitOverflowScrolling = 'touch';
      }

      // Mobile card-view toggle button
      var table = wrap.querySelector('table');
      if (!table) return;

      // Add toggle button if not already present
      if (!wrap.previousElementSibling || !wrap.previousElementSibling.classList.contains('v3-table-view-toggle')) {
        var btnWrap = document.createElement('div');
        btnWrap.className = 'v3-table-view-toggle';
        Object.assign(btnWrap.style, {
          display:        'flex',
          justifyContent: 'flex-end',
          marginBottom:   '8px'
        });

        var viewBtn = document.createElement('button');
        viewBtn.type = 'button';
        viewBtn.className = 'v3-btn-sm';
        viewBtn.textContent = '⊞ Card View';
        Object.assign(viewBtn.style, {
          fontSize:     '12px',
          padding:      '4px 10px',
          borderRadius: '6px',
          border:       '1px solid #334155',
          background:   'transparent',
          cursor:       'pointer',
          color:        'inherit'
        });

        viewBtn.addEventListener('click', function () {
          var isCard = wrap.classList.toggle('v3-table-card-view');
          viewBtn.textContent = isCard ? '☰ Table View' : '⊞ Card View';
        });

        btnWrap.appendChild(viewBtn);
        wrap.parentNode.insertBefore(btnWrap, wrap);
      }
    });
  }

  document.addEventListener('DOMContentLoaded', _initTables);

  /* =========================================================
   * 10. SEARCH ENHANCEMENT
   * ======================================================= */

  function _initSearch() {
    qsa('.v3-search[data-search-target], input.v3-search[data-search-target]').forEach(function (input) {
      var targetSel = input.getAttribute('data-search-target');
      var table     = qs(targetSel);
      if (!table) return;

      var rows = null;

      function filterTable() {
        var term = input.value.trim().toLowerCase();
        if (!rows) rows = qsa('tbody tr', table);
        rows.forEach(function (row) {
          var text = row.textContent.toLowerCase();
          row.style.display = (!term || text.includes(term)) ? '' : 'none';
        });
        // Show no-results row if all hidden
        var visible = rows.filter(function (r) { return r.style.display !== 'none'; });
        var noResultsRow = table.querySelector('.v3-no-results-row');
        if (!visible.length && rows.length) {
          if (!noResultsRow) {
            var tr  = document.createElement('tr');
            tr.className = 'v3-no-results-row';
            var td  = document.createElement('td');
            var cols = table.querySelectorAll('thead th').length || 5;
            td.colSpan = cols;
            td.style.textAlign = 'center';
            td.style.padding   = '24px';
            td.style.color     = '#94a3b8';
            td.textContent     = 'No results found.';
            tr.appendChild(td);
            var tbody = table.querySelector('tbody');
            if (tbody) tbody.appendChild(tr);
          }
        } else if (noResultsRow) {
          noResultsRow.parentNode.removeChild(noResultsRow);
        }
      }

      input.addEventListener('input', debounce(filterTable, 220));
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { input.value = ''; filterTable(); }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', _initSearch);

  /* =========================================================
   * 11. SKELETON LOADERS
   * ======================================================= */

  var SKELETON_STYLE = [
    '.v3-skeleton{background:linear-gradient(90deg,#1e293b 25%,#334155 50%,#1e293b 75%);background-size:200% 100%;',
    'animation:v3-shimmer 1.4s infinite;border-radius:8px;}',
    '@keyframes v3-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}'
  ].join('');

  var _skeletonStyleInjected = false;
  function _injectSkeletonStyles() {
    if (_skeletonStyleInjected) return;
    _skeletonStyleInjected = true;
    var style = document.createElement('style');
    style.textContent = SKELETON_STYLE;
    document.head.appendChild(style);
  }

  function _makeSkeletonCard() {
    var card = document.createElement('div');
    Object.assign(card.style, {
      background:   '#1e293b',
      borderRadius: '12px',
      padding:      '20px',
      display:      'flex',
      flexDirection:'column',
      gap:          '12px'
    });
    [[40, '60%'], [16, '100%'], [16, '80%'], [16, '45%']].forEach(function (row) {
      var line = document.createElement('div');
      line.className = 'v3-skeleton';
      line.style.height = row[0] + 'px';
      line.style.width  = row[1];
      card.appendChild(line);
    });
    return card;
  }

  function _makeSkeletonRow() {
    var row = document.createElement('div');
    Object.assign(row.style, {
      display:       'flex',
      gap:           '12px',
      alignItems:    'center',
      padding:       '12px 0',
      borderBottom:  '1px solid #334155'
    });
    [40, 120, 180, 80].forEach(function (w) {
      var cell = document.createElement('div');
      cell.className = 'v3-skeleton';
      cell.style.height = '18px';
      cell.style.width  = w + 'px';
      cell.style.flexShrink = '0';
      row.appendChild(cell);
    });
    return row;
  }

  function v3ShowSkeleton(container, count, type) {
    if (!container) return;
    count = count || 3;
    type  = type  || 'card';
    _injectSkeletonStyles();
    container.setAttribute('data-skeleton-host', '1');
    // Clear existing skeletons
    v3HideSkeleton(container);
    var frag = document.createDocumentFragment();
    for (var i = 0; i < count; i++) {
      frag.appendChild(type === 'row' ? _makeSkeletonRow() : _makeSkeletonCard());
    }
    container.appendChild(frag);
  }

  function v3HideSkeleton(container) {
    if (!container) return;
    qsa('.v3-skeleton, [style*="v3-skeleton"]', container).forEach(function (el) {
      var parent = el.closest('[data-skeleton-host]') === container ? el.parentNode : null;
      if (parent && parent !== container) {
        container.removeChild(parent);
      } else {
        container.removeChild(el);
      }
    });
    // Simpler: remove all skeleton wrapper children
    var kids = Array.from(container.children);
    kids.forEach(function (kid) {
      if (kid.querySelector && kid.querySelector('.v3-skeleton')) {
        container.removeChild(kid);
      }
    });
  }

  window.v3ShowSkeleton = v3ShowSkeleton;
  window.v3HideSkeleton = v3HideSkeleton;

  /* =========================================================
   * 12. COPY TO CLIPBOARD
   * ======================================================= */

  function _initCopyToClipboard() {
    document.addEventListener('click', function (e) {
      var el = e.target.closest('[data-copy]');
      if (!el) return;
      var text = el.getAttribute('data-copy') || el.textContent.trim();
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            _showCopiedTooltip(el);
          }).catch(function () {
            _fallbackCopy(text, el);
          });
        } else {
          _fallbackCopy(text, el);
        }
      } catch (err) {
        console.warn('[V3] Copy error:', err);
      }
    });
  }

  function _fallbackCopy(text, el) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity  = '0';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
      _showCopiedTooltip(el);
    } catch (e) { /* */ }
    document.body.removeChild(ta);
  }

  function _showCopiedTooltip(el) {
    var existing = el.querySelector('.v3-copied-tip');
    if (existing) return;

    var tip = document.createElement('span');
    tip.className = 'v3-copied-tip';
    tip.textContent = 'Copied!';
    Object.assign(tip.style, {
      position:     'absolute',
      bottom:       'calc(100% + 6px)',
      left:         '50%',
      transform:    'translateX(-50%)',
      background:   '#22c55e',
      color:        '#fff',
      padding:      '3px 10px',
      borderRadius: '6px',
      fontSize:     '12px',
      whiteSpace:   'nowrap',
      pointerEvents:'none',
      zIndex:       '99999',
      animation:    'none'
    });

    var prevPos = el.style.position;
    if (!prevPos || prevPos === 'static') el.style.position = 'relative';
    el.appendChild(tip);

    setTimeout(function () {
      if (tip.parentNode) {
        tip.parentNode.removeChild(tip);
        if (!prevPos || prevPos === 'static') el.style.position = prevPos;
      }
    }, 1500);
  }

  document.addEventListener('DOMContentLoaded', _initCopyToClipboard);

  /* =========================================================
   * 13. CONFIRMATION DIALOGS
   * ======================================================= */

  function v3Confirm(message, onConfirm, title) {
    title = title || 'Are you sure?';

    // Ensure only one dialog at a time
    var existingOverlay = qs('#v3-confirm-overlay');
    if (existingOverlay) existingOverlay.parentNode.removeChild(existingOverlay);

    var overlay = document.createElement('div');
    overlay.id = 'v3-confirm-overlay';
    Object.assign(overlay.style, {
      position:       'fixed',
      inset:          '0',
      background:     'rgba(0,0,0,0.55)',
      zIndex:         '99997',
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'center',
      animation:      'v3-fadein 0.18s ease'
    });

    var dialog = document.createElement('div');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'v3-confirm-title');
    Object.assign(dialog.style, {
      background:   '#1e293b',
      borderRadius: '14px',
      padding:      '28px 32px',
      maxWidth:     '420px',
      width:        '90%',
      boxShadow:    '0 20px 60px rgba(0,0,0,0.5)',
      color:        '#f1f5f9'
    });

    var titleEl = document.createElement('h3');
    titleEl.id = 'v3-confirm-title';
    titleEl.textContent = title;
    Object.assign(titleEl.style, {
      margin:     '0 0 12px',
      fontSize:   '18px',
      fontWeight: '600'
    });

    var msgEl = document.createElement('p');
    msgEl.textContent = message;
    Object.assign(msgEl.style, {
      margin:     '0 0 24px',
      color:      '#94a3b8',
      lineHeight: '1.6'
    });

    var btnRow = document.createElement('div');
    Object.assign(btnRow.style, {
      display:        'flex',
      gap:            '12px',
      justifyContent: 'flex-end'
    });

    var cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.textContent = 'Cancel';
    Object.assign(cancelBtn.style, {
      padding:      '9px 20px',
      borderRadius: '8px',
      border:       '1px solid #334155',
      background:   'transparent',
      color:        '#94a3b8',
      cursor:       'pointer',
      fontSize:     '14px'
    });

    var confirmBtn = document.createElement('button');
    confirmBtn.type = 'button';
    confirmBtn.textContent = 'Confirm';
    Object.assign(confirmBtn.style, {
      padding:      '9px 20px',
      borderRadius: '8px',
      border:       'none',
      background:   '#ef4444',
      color:        '#fff',
      cursor:       'pointer',
      fontSize:     '14px',
      fontWeight:   '600'
    });

    function close() {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      document.removeEventListener('keydown', onKey);
    }

    cancelBtn.addEventListener('click', close);
    confirmBtn.addEventListener('click', function () {
      close();
      if (typeof onConfirm === 'function') onConfirm();
    });

    // Keyboard: Escape = cancel, Enter = confirm
    function onKey(e) {
      if (e.key === 'Escape')  { close(); }
      if (e.key === 'Enter')   { close(); if (typeof onConfirm === 'function') onConfirm(); }
    }
    document.addEventListener('keydown', onKey);

    // Click outside dialog = cancel
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });

    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(confirmBtn);
    dialog.appendChild(titleEl);
    dialog.appendChild(msgEl);
    dialog.appendChild(btnRow);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // Focus confirm button
    setTimeout(function () { confirmBtn.focus(); }, 50);

    return false; // always returns false synchronously
  }

  window.v3Confirm = v3Confirm;

  /* =========================================================
   * 14. NUMBER COUNTER ANIMATION
   * ======================================================= */

  function v3AnimateCount(el, target, duration) {
    if (!el) return;
    duration = duration || 1500;
    var start     = parseFloat(el.textContent.replace(/[^0-9.-]/g, '')) || 0;
    var startTime = null;
    var isFloat   = (target % 1 !== 0);
    var prefix    = (el.getAttribute('data-prefix') || '');
    var suffix    = (el.getAttribute('data-suffix') || '');

    function easeOutQuart(t) {
      return 1 - Math.pow(1 - t, 4);
    }

    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var elapsed  = timestamp - startTime;
      var progress = Math.min(elapsed / duration, 1);
      var eased    = easeOutQuart(progress);
      var current  = start + (target - start) * eased;
      el.textContent = prefix + (isFloat ? current.toFixed(2) : Math.round(current).toLocaleString()) + suffix;
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = prefix + (isFloat ? target.toFixed(2) : target.toLocaleString()) + suffix;
      }
    }

    requestAnimationFrame(step);
  }

  window.v3AnimateCount = v3AnimateCount;

  // Auto-animate KPI counters on page load using IntersectionObserver
  document.addEventListener('DOMContentLoaded', function () {
    var counters = qsa('[data-v3-count]');
    if (!counters.length) return;

    function animateCounter(el) {
      if (el.dataset.v3CountDone) return;
      el.dataset.v3CountDone = '1';
      var target   = parseFloat(el.getAttribute('data-v3-count')) || 0;
      var duration = parseInt(el.getAttribute('data-v3-count-duration'), 10) || 1500;
      v3AnimateCount(el, target, duration);
    }

    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateCounter(entry.target);
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.3 });
      counters.forEach(function (el) { io.observe(el); });
    } else {
      counters.forEach(animateCounter);
    }
  });

  /* =========================================================
   * INJECT GLOBAL CSS HELPERS
   * ======================================================= */

  document.addEventListener('DOMContentLoaded', function () {
    var style = document.createElement('style');
    style.id  = 'v3-runtime-styles';
    style.textContent = [
      /* Theme transition */
      '.v3-theme-transitioning *{transition:background-color 0.35s ease,color 0.35s ease,border-color 0.35s ease !important;}',

      /* Page transition */
      '.v3-animate-in{animation:v3-pageIn 0.4s ease both;}',
      '@keyframes v3-pageIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}',
      '.v3-card-stagger{animation:v3-pageIn 0.4s ease both;}',

      /* Sidebar mobile */
      '@media(max-width:768px){',
        '.v3-sidebar{transform:translateX(-100%);transition:transform 0.3s ease;position:fixed;top:0;left:0;height:100vh;z-index:8999;overflow-y:auto;}',
        'body.v3-sidebar-open .v3-sidebar{transform:translateX(0);}',
      '}',

      /* Confirm dialog fade */
      '@keyframes v3-fadein{from{opacity:0}to{opacity:1}}',

      /* Field error */
      '.v3-field-error{border-color:#ef4444 !important;box-shadow:0 0 0 2px rgba(239,68,68,0.2) !important;}',
      '.v3-error-msg{color:#ef4444;font-size:12px;margin-top:4px;}',

      /* Table card view */
      '.v3-table-card-view table thead{display:none;}',
      '.v3-table-card-view table tr{display:block;margin-bottom:12px;border:1px solid #334155;border-radius:10px;padding:12px;}',
      '.v3-table-card-view table td{display:flex;justify-content:space-between;padding:4px 8px;font-size:13px;}',
      '.v3-table-card-view table td::before{content:attr(data-label);font-weight:600;color:#94a3b8;margin-right:8px;}',

      /* Petsy panel default hidden */
      '#petsy-panel{display:none;flex-direction:column;}'
    ].join('\n');
    document.head.appendChild(style);
  });

  /* =========================================================
   * GLOBAL ERROR BOUNDARY
   * ======================================================= */
  window.addEventListener('error', function (e) {
    console.error('[V3] Uncaught error:', e.message, e.filename, e.lineno);
  });

  window.addEventListener('unhandledrejection', function (e) {
    console.warn('[V3] Unhandled promise rejection:', e.reason);
  });

})();

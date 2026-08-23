(function () {
  var overlay = null;
  var pending = null;
  var lastFocused = null;

  var STYLE = [
    '.ocloud-modal-overlay{position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.6);',
    '-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;',
    'opacity:0;pointer-events:none;transition:opacity .15s ease;}',
    '.ocloud-modal-overlay.visible{opacity:1;pointer-events:auto;}',
    '.ocloud-modal{background:var(--bg-card,#1e293b);border:1px solid var(--border-color,#334155);border-radius:14px;',
    'padding:22px;width:min(420px,90vw);box-shadow:0 24px 64px rgba(0,0,0,.45);',
    'transform:translateY(8px) scale(.98);transition:transform .15s ease;font-family:system-ui,-apple-system,sans-serif;}',
    '.ocloud-modal-overlay.visible .ocloud-modal{transform:none;}',
    '.ocloud-modal-title{margin:0 0 8px;font-size:1rem;font-weight:700;color:var(--text-primary,#f1f5f9);}',
    '.ocloud-modal-message{margin:0 0 14px;font-size:.85rem;line-height:1.5;color:var(--text-secondary,#94a3b8);',
    'word-break:break-word;white-space:pre-line;}',
    '.ocloud-modal-message:empty{display:none;margin:0;}',
    '.ocloud-modal-input{width:100%;padding:9px 12px;border:1px solid var(--border-color,#334155);border-radius:8px;',
    'background:rgba(128,128,128,.08);color:var(--text-primary,#f1f5f9);font-size:.9rem;font-family:inherit;',
    'outline:none;margin-bottom:16px;box-sizing:border-box;display:none;}',
    '.ocloud-modal-input:focus{border-color:var(--accent-cyan,#06b6d4);}',
    '.ocloud-modal-actions{display:flex;gap:8px;justify-content:flex-end;}',
    '.ocloud-modal-btn{padding:8px 16px;border-radius:8px;border:1px solid var(--border-color,#334155);',
    'background:transparent;color:var(--text-primary,#f1f5f9);cursor:pointer;font-size:.85rem;font-family:inherit;',
    'font-weight:600;transition:all .15s;}',
    '.ocloud-modal-btn:hover{border-color:var(--accent-cyan,#06b6d4);color:var(--accent-cyan,#06b6d4);}',
    '.ocloud-modal-btn-ok{background:var(--accent-cyan,#06b6d4);border-color:var(--accent-cyan,#06b6d4);color:#0f172a;}',
    '.ocloud-modal-btn-ok:hover{filter:brightness(1.12);color:#0f172a;}',
    '.ocloud-modal-btn-ok.danger{background:#f43f5e;border-color:#f43f5e;color:#fff;}',
    '.ocloud-modal-btn-ok.danger:hover{filter:brightness(1.12);color:#fff;}'
  ].join('');

  function el(cls) {
    return overlay.querySelector(cls);
  }

  function finish(value) {
    if (!pending) return;
    var resolve = pending;
    pending = null;
    document.removeEventListener('keydown', keyHandler, true);
    overlay.classList.remove('visible');
    if (lastFocused && document.contains(lastFocused)) {
      try { lastFocused.focus(); } catch (e) {}
    }
    lastFocused = null;
    resolve(value);
  }

  function keyHandler(e) {
    if (!pending) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      finish(null);
    } else if (e.key === 'Enter') {
      var t = e.target;
      if (t && (t.classList.contains('ocloud-modal-input') || t.classList.contains('ocloud-modal-btn'))) {
        if (t.classList.contains('ocloud-modal-cancel')) return;
        e.preventDefault();
        finish(el('.ocloud-modal-input').value);
      }
    }
  }

  function ensureDom() {
    if (overlay) return;
    var style = document.createElement('style');
    style.textContent = STYLE;
    document.head.appendChild(style);

    overlay = document.createElement('div');
    overlay.className = 'ocloud-modal-overlay';
    overlay.innerHTML =
      '<div class="ocloud-modal" role="dialog" aria-modal="true">' +
        '<h3 class="ocloud-modal-title"></h3>' +
        '<p class="ocloud-modal-message"></p>' +
        '<input type="text" class="ocloud-modal-input" spellcheck="false" autocomplete="off">' +
        '<div class="ocloud-modal-actions">' +
          '<button type="button" class="ocloud-modal-btn ocloud-modal-cancel"></button>' +
          '<button type="button" class="ocloud-modal-btn ocloud-modal-btn-ok"></button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    overlay.addEventListener('mousedown', function (e) {
      if (e.target === overlay) finish(null);
    });
    el('.ocloud-modal-cancel').addEventListener('click', function () { finish(null); });
    el('.ocloud-modal-btn-ok').addEventListener('click', function () {
      finish(el('.ocloud-modal-input').value);
    });
  }

  function open(cfg) {
    ensureDom();
    if (pending) return Promise.resolve(null);
    lastFocused = document.activeElement;

    el('.ocloud-modal-title').textContent = cfg.title || '';
    el('.ocloud-modal-message').textContent = cfg.message || '';
    var input = el('.ocloud-modal-input');
    var okBtn = el('.ocloud-modal-btn-ok');

    if (cfg.value !== null && cfg.value !== undefined) {
      input.style.display = 'block';
      input.value = cfg.value;
      input.placeholder = cfg.placeholder || '';
    } else {
      input.style.display = 'none';
      input.value = '';
    }
    okBtn.textContent = cfg.okText || 'OK';
    el('.ocloud-modal-cancel').textContent = cfg.cancelText || 'Cancel';
    okBtn.classList.toggle('danger', !!cfg.danger);

    overlay.classList.add('visible');
    document.addEventListener('keydown', keyHandler, true);
    if (cfg.value !== null && cfg.value !== undefined) {
      requestAnimationFrame(function () { input.focus(); });
    } else {
      requestAnimationFrame(function () { okBtn.focus(); });
    }

    return new Promise(function (resolve) { pending = resolve; });
  }

  window.showConfirm = function (opts) {
    opts = opts || {};
    return open({
      title: opts.title || 'Please Confirm',
      message: opts.message || '',
      okText: opts.okText || 'Confirm',
      cancelText: opts.cancelText || 'Cancel',
      danger: !!opts.danger,
      value: null
    }).then(function (v) { return v !== null; });
  };

  window.showPrompt = function (opts) {
    opts = opts || {};
    return open({
      title: opts.title || 'Input',
      message: opts.message || '',
      okText: opts.okText || 'OK',
      cancelText: opts.cancelText || 'Cancel',
      danger: !!opts.danger,
      placeholder: opts.placeholder || '',
      value: opts.value !== null && opts.value !== undefined ? String(opts.value) : ''
    });
  };
})();

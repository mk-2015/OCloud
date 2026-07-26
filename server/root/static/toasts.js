(function () {
  const container = document.createElement('div');
  container.id = 'toast-container';
  container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
  document.body.appendChild(container);

  const style = document.createElement('style');
  style.textContent = `
    .toast {
      padding: 12px 20px;
      border-radius: 10px;
      font-size: 0.9rem;
      font-weight: 500;
      color: #fff;
      backdrop-filter: blur(12px);
      pointer-events: auto;
      animation: toast-in 0.3s ease, toast-out 0.3s ease forwards;
      max-width: 360px;
      word-wrap: break-word;
      box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    }
    .toast-success { background: rgba(16, 185, 129, 0.9); }
    .toast-error { background: rgba(244, 63, 94, 0.9); }
    .toast-info { background: rgba(6, 182, 212, 0.9); }
    .toast-warn { background: rgba(245, 158, 11, 0.9); }
    @keyframes toast-in { from { opacity: 0; transform: translateX(40px); } to { opacity: 1; transform: translateX(0); } }
    @keyframes toast-out { from { opacity: 1; } to { opacity: 0; transform: translateY(-10px); } }
  `;
  document.head.appendChild(style);

  window.showToast = function (message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.animation = 'toast-out 0.3s ease forwards';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  };
})();

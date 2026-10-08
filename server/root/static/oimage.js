(function () {
  const fileInput = document.getElementById('fileInput');
  const btnOpenDisk = document.getElementById('btnOpenDisk');
  const btnImportOMedia = document.getElementById('btnImportOMedia');
  const btnRotateLeft = document.getElementById('btnRotateLeft');
  const btnRotateRight = document.getElementById('btnRotateRight');
  const btnZoomIn = document.getElementById('btnZoomIn');
  const btnZoomOut = document.getElementById('btnZoomOut');
  const btnReset = document.getElementById('btnReset');
  const btnDownload = document.getElementById('btnDownload');
  const chkDrawMode = document.getElementById('chkDrawMode');
  const colorPicker = document.getElementById('colorPicker');
  const brushSize = document.getElementById('brushSize');
  const canvas = document.getElementById('imageCanvas');
  const ctx = canvas.getContext('2d');

  let img = null;
  let rotation = 0; // degrees
  let userZoom = 1; // multiplier
  let baseScale = 1; // scale to fit viewport initially
  
  // Painting & History
  let isDrawing = false;
  let lastX = 0;
  let lastY = 0;
  let historyStack = [];
  let historyIndex = -1;

  function saveState() {
    // Save current canvas state
    historyStack = historyStack.slice(0, historyIndex + 1);
    historyStack.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
    historyIndex++;
  }

  function undo() {
    if (historyIndex > 0) {
      historyIndex--;
      ctx.putImageData(historyStack[historyIndex], 0, 0);
    }
  }

  function redo() {
    if (historyIndex < historyStack.length - 1) {
      historyIndex++;
      ctx.putImageData(historyStack[historyIndex], 0, 0);
    }
  }

  function computeBaseScale(w, h) {
    const maxW = Math.max(window.innerWidth - 160, 200);
    const maxH = Math.max(window.innerHeight - 220, 150);
    return Math.min(1, maxW / w, maxH / h);
  }

  function draw() {
    if (!img) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    const w = img.naturalWidth;
    const h = img.naturalHeight;
    const rot = ((rotation % 360) + 360) % 360;
    const effectiveScale = baseScale * userZoom;
    const drawW = (rot === 90 || rot === 270) ? h * effectiveScale : w * effectiveScale;
    const drawH = (rot === 90 || rot === 270) ? w * effectiveScale : h * effectiveScale;

    canvas.width = Math.round(drawW);
    canvas.height = Math.round(drawH);
    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((rotation * Math.PI) / 180);
    ctx.drawImage(img, - (w * effectiveScale) / 2, - (h * effectiveScale) / 2, w * effectiveScale, h * effectiveScale);
    ctx.restore();
  }

  function loadFile(file) {
    const url = URL.createObjectURL(file);
    const i = new Image();
    i.onload = function () {
      img = i;
      rotation = 0;
      userZoom = 1;
      baseScale = computeBaseScale(img.naturalWidth, img.naturalHeight);
      draw();
      saveState(); // Save initial state
      URL.revokeObjectURL(url);
    };
    i.src = url;
  }

  btnOpenDisk.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (ev) => {
    const f = ev.target.files && ev.target.files[0];
    if (f) loadFile(f);
    fileInput.value = '';
  });

  // Drawing Events
  canvas.addEventListener('mousedown', (e) => {
    if (!chkDrawMode.checked) return;
    isDrawing = true;
    const rect = canvas.getBoundingClientRect();
    lastX = e.clientX - rect.left;
    lastY = e.clientY - rect.top;
  });

  canvas.addEventListener('mousemove', (e) => {
    if (!isDrawing) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    ctx.strokeStyle = colorPicker.value;
    ctx.lineWidth = brushSize.value;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    ctx.stroke();
    
    lastX = x;
    lastY = y;
  });

  canvas.addEventListener('mouseup', () => {
    if (isDrawing) {
      isDrawing = false;
      saveState();
    }
  });

  canvas.addEventListener('mouseleave', () => {
    if (isDrawing) {
      isDrawing = false;
      saveState();
    }
  });

  // OMedia modal elements
  const omediaModal = document.getElementById('omediaModal');
  const omediaModalBody = document.getElementById('omediaModalBody');
  const omediaModalClose = document.getElementById('omediaModalClose');

  btnImportOMedia.addEventListener('click', openOMediaModal);
  omediaModalClose && omediaModalClose.addEventListener('click', closeOMediaModal);
  omediaModal && omediaModal.addEventListener('click', function (e) { if (e.target === omediaModal) closeOMediaModal(); });

  async function initUser() {
    try {
      const me = await fetch('/api/me');
      if (!me.ok) return;
      const meData = await me.json();
      window._ocloudUser = meData.username || meData.user;
    } catch (e) {
      // ignore
    }
  }

  function openOMediaModal() {
    if (!omediaModal) return;
    omediaModal.classList.add('active');
    omediaModal.setAttribute('aria-hidden', 'false');
    const grid = document.getElementById('omediaGrid');
    if (grid) grid.innerHTML = '<div class="empty-msg">Loading files...</div>';
    loadOMediaFiles();
  }

  function closeOMediaModal() {
    if (!omediaModal) return;
    omediaModal.classList.remove('active');
    omediaModal.setAttribute('aria-hidden', 'true');
  }

  async function loadOMediaFiles() {
    try {
      const username = window._ocloudUser;
      const grid = document.getElementById('omediaGrid');
      const search = document.getElementById('omediaSearch');
      if (!grid) return;
      grid.innerHTML = '<div class="empty-msg">Loading files...</div>';
      if (!username) {
        grid.innerHTML = '<div class="empty-msg">User not loaded</div>';
        return;
      }
      const res = await fetch('/api/omedia/lsfile/' + encodeURIComponent(username));
      if (!res.ok) throw new Error('Failed to list');
      const data = await res.json();
      const files = (data.files || data || []).filter(function (f) {
        const name = (f.name || f.filename || '').toLowerCase();
        return /\.(jpg|jpeg|png|gif|webp|svg|bmp|tiff)$/i.test(name);
      });
      if (files.length === 0) {
        grid.innerHTML = '<div class="empty-msg">No images found in OMedia</div>';
        return;
      }
      grid.innerHTML = '';

      files.forEach(function (f) {
        const fname = f.name || f.filename || '';
        const thumb = document.createElement('div');
        thumb.style.cursor = 'pointer';
        thumb.style.border = '1px solid rgba(128,128,128,0.12)';
        thumb.style.borderRadius = '8px';
        thumb.style.overflow = 'hidden';
        thumb.style.background = 'var(--bg-card)';
        thumb.style.padding = '6px';

        const imgEl = document.createElement('img');
        imgEl.alt = fname;
        imgEl.style.width = '100%';
        imgEl.style.height = '110px';
        imgEl.style.objectFit = 'cover';
        imgEl.style.display = 'block';
        imgEl.src = '/api/omedia/download/' + encodeURIComponent(username) + '/' + encodeURIComponent(fname);

        const label = document.createElement('div');
        label.style.padding = '6px 4px 0 4px';
        label.style.fontSize = '13px';
        label.style.color = 'var(--text-primary)';
        label.style.whiteSpace = 'nowrap';
        label.style.overflow = 'hidden';
        label.style.textOverflow = 'ellipsis';
        label.textContent = fname;

        thumb.appendChild(imgEl);
        thumb.appendChild(label);
        thumb.addEventListener('click', function () { importFromOMedia(fname); });
        grid.appendChild(thumb);
      });

      if (search) {
        search.value = '';
        search.oninput = function () {
          const q = (this.value || '').toLowerCase();
          Array.from(grid.children).forEach(function (c) {
            const txt = (c.querySelector('div') && c.querySelector('div').textContent) || '';
            c.style.display = txt.toLowerCase().includes(q) ? '' : 'none';
          });
        };
      }
    } catch (e) {
      const grid = document.getElementById('omediaGrid');
      if (grid) grid.innerHTML = '<div class="empty-msg">Failed to load OMedia files</div>';
    }
  }

  async function importFromOMedia(filename) {
    try {
      closeOMediaModal();
      const username = window._ocloudUser;
      const url = '/api/omedia/download/' + encodeURIComponent(username) + '/' + encodeURIComponent(filename);
      const res = await fetch(url);
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const file = new File([blob], filename, { type: blob.type });
      loadFile(file);
    } catch (e) {
      console.error('Import from OMedia failed', e);
      alert('Failed to import from OMedia: ' + e.message);
    }
  }

  // helpers used from other workspace scripts (escapeHTML/formatSize)
  function escapeHTML(s) { return (s || '').toString().replace(/[&<>'"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]; }); }
  function formatSize(n) { if (!n && n !== 0) return ''; if (n < 1024) return n + ' B'; if (n < 1024*1024) return (n/1024).toFixed(1)+' KB'; return (n/1024/1024).toFixed(1)+' MB'; }

  // initialize current user
  initUser();

  btnRotateLeft.addEventListener('click', () => {
    rotation = (rotation - 90) % 360;
    draw();
  });
  btnRotateRight.addEventListener('click', () => {
    rotation = (rotation + 90) % 360;
    draw();
  });

  btnZoomIn.addEventListener('click', () => {
    userZoom *= 1.1;
    draw();
  });
  btnZoomOut.addEventListener('click', () => {
    userZoom /= 1.1;
    draw();
  });

  btnReset.addEventListener('click', () => {
    if (!img) return;
    rotation = 0;
    userZoom = 1;
    baseScale = computeBaseScale(img.naturalWidth, img.naturalHeight);
    draw();
  });

  btnDownload.addEventListener('click', () => {
    if (!img) return;
    const mime = 'image/png';
    const data = canvas.toDataURL(mime);
    const a = document.createElement('a');
    a.href = data;
    a.download = (img.name || 'image') + '.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
  });

  // keyboard shortcuts
  window.addEventListener('keydown', (e) => {
    if (e.key === '+' || (e.key === '=' && e.shiftKey)) { userZoom *= 1.1; draw(); }
    if (e.key === '-') { userZoom /= 1.1; draw(); }
    if (e.key === 'ArrowLeft' && e.ctrlKey) { rotation = (rotation - 90) % 360; draw(); }
    if (e.key === 'ArrowRight' && e.ctrlKey) { rotation = (rotation + 90) % 360; draw(); }
    if (e.key === 'z' && e.ctrlKey) { undo(); }
    if (e.key === 'y' && e.ctrlKey) { redo(); }
  });

  // responsive: recompute baseScale on resize
  window.addEventListener('resize', () => {
    if (!img) return;
    baseScale = computeBaseScale(img.naturalWidth, img.naturalHeight);
    draw();
  });

  // init: clear canvas
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#0b1220';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
})();

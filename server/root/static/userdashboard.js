const status = document.getElementById('status');
const fileList = document.getElementById('fileList');
const uploadForm = document.getElementById('uploadForm');
const mkdirBtn = document.getElementById('mkdirBtn');
const logoutBtn = document.getElementById('logoutBtn');
const folderInput = document.getElementById('folderInput');
const shareForm = document.getElementById('shareForm');
const sharePath = document.getElementById('sharePath');
const shareForever = document.getElementById('shareForever');
const shareStatus = document.getElementById('shareStatus');
const shareResult = document.getElementById('shareResult');
const apiKeyLabel = document.getElementById('apiKeyLabel');
const createKeyBtn = document.getElementById('createKeyBtn');
const apiKeyResult = document.getElementById('apiKeyResult');
const apiKeyList = document.getElementById('apiKeyList');
let currentPath = '.';
let currentUser = null;

async function requireSession() {
  const response = await fetch('/api/me');
  if (!response.ok) {
    window.location.href = '/login.html';
    return null;
  }
  currentUser = await response.json();
  return currentUser;
}

async function loadFiles(path = currentPath) {
  const user = await requireSession();
  if (!user) return;
  currentPath = path;
  status.textContent = 'Loading files...';
  const response = await fetch(`/api/omedia/lsdir/${encodeURIComponent(user.username)}${path && path !== '.' ? `/${encodeURIComponent(path)}` : ''}`);
  const data = await response.json();
  fileList.innerHTML = '';

  const breadcrumb = document.createElement('div');
  breadcrumb.className = 'breadcrumb';
  breadcrumb.innerHTML = `<button class="link-btn" data-path=".">Home</button>`;
  if (data.path && data.path !== '.') {
    const parts = data.path.split('/');
    let build = '';
    parts.forEach((part, index) => {
      build = index === 0 ? part : `${build}/${part}`;
      breadcrumb.innerHTML += ` / <button class="link-btn" data-path="${escapeHTML(build)}">${escapeHTML(part)}</button>`;
    });
  }
  fileList.appendChild(breadcrumb);

  if (!data.entries.length) {
    fileList.innerHTML += '<p class="empty">No files yet.</p>';
    status.textContent = 'This folder is empty.';
    return;
  }

  const list = document.createElement('ul');
  data.entries.forEach((entry) => {
    const item = document.createElement('li');
    item.className = 'file-item';
    const isDir = entry.type === 'dir';
    const icon = isDir ? '📁' : '📄';
    item.innerHTML = `
      <div class="file-info ${isDir ? 'file-dir' : 'file-txt'}">
        <span class="file-icon">${icon}</span>
        <span class="file-name">${escapeHTML(entry.name)}</span>
      </div>
      <div class="file-actions">
        ${isDir ? `<button class="link-btn" data-enter="${escapeHTML(entry.path)}">Open</button>` : `<a href="/api/omedia/download/${encodeURIComponent(user.username)}/${encodeURIComponent(entry.path)}" target="_blank">Download</a>`}
        ${!isDir ? `<button class="link-btn btn-share" data-share="${escapeHTML(entry.path)}">Share</button>` : ''}
        <button data-name="${escapeHTML(entry.path)}" class="link-btn btn-delete">Delete</button>
      </div>
    `;
    list.appendChild(item);
  });
  fileList.appendChild(list);
  status.textContent = `Loaded ${data.entries.length} item(s).`;
}

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const user = await requireSession();
  if (!user) return;
  const fileInput = document.getElementById('file');
  if (!fileInput.files.length) {
    status.textContent = 'Choose a file first.';
    return;
  }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  const uploadTarget = currentPath && currentPath !== '.' ? currentPath : '';
  if (uploadTarget) formData.append('folder', uploadTarget);
  const response = await fetch(`/api/omedia/upload/${encodeURIComponent(user.username)}`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': getCsrfToken() },
    body: formData,
  });
  const data = await response.json();
  status.textContent = data.status || 'Uploaded';
  uploadForm.reset();
  loadFiles();
});

mkdirBtn.addEventListener('click', async () => {
  const user = await requireSession();
  if (!user) return;
  const name = folderInput.value.trim();
  if (!name) {
    status.textContent = 'Enter a folder name.';
    return;
  }
  const targetPath = currentPath && currentPath !== '.' ? `${currentPath}/${name}` : name;
  const response = await fetch(`/api/omedia/mkdir/${encodeURIComponent(user.username)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
    body: JSON.stringify({ path: targetPath }),
  });
  const data = await response.json();
  status.textContent = data.status || 'Folder created';
  loadFiles();
});

fileList.addEventListener('click', async (event) => {
  const button = event.target.closest('button');
  if (!button) return;

  if (button.hasAttribute('data-enter')) {
    const path = button.getAttribute('data-enter');
    loadFiles(path);
    return;
  }

  if (button.hasAttribute('data-path')) {
    const path = button.getAttribute('data-path');
    loadFiles(path);
    return;
  }

  if (button.hasAttribute('data-name')) {
    const user = await requireSession();
    if (!user) return;
    const name = button.getAttribute('data-name');
    const response = await fetch(`/api/omedia/delete/${encodeURIComponent(user.username)}/${encodeURIComponent(name)}`, {
      method: 'DELETE',
      headers: { 'X-CSRF-Token': getCsrfToken() },
    });
    if (response.ok) {
      status.textContent = 'Deleted.';
loadFiles();

async function loadApiKeys() {
  const response = await fetch('/api/omedia/apikeys');
  const data = await response.json();
  apiKeyList.innerHTML = '';
  if (!data.keys.length) {
    apiKeyList.innerHTML = '<p class="empty">No API keys.</p>';
    return;
  }
  const list = document.createElement('ul');
  data.keys.forEach((key) => {
    const item = document.createElement('li');
    item.className = 'file-item';
    item.innerHTML = `
      <div class="file-info">
        <span class="file-icon">&#x1f511;</span>
        <span class="file-name">${escapeHTML(key.label || 'unnamed')} <span style="font-size:0.75rem; color:var(--text-secondary);">(${key.last_used ? 'last used ' + escapeHTML(key.last_used) : 'never used'})</span></span>
      </div>
      <div class="file-actions">
        <button class="link-btn btn-delete" data-deletekey="${key.id}">Revoke</button>
      </div>
    `;
    list.appendChild(item);
  });
  apiKeyList.appendChild(list);
}

createKeyBtn.addEventListener('click', async () => {
  const label = apiKeyLabel.value.trim() || 'unnamed';
  const response = await fetch('/api/omedia/apikeys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
    body: JSON.stringify({ label })
  });
  const data = await response.json();
  if (response.ok) {
    apiKeyResult.textContent = `Key: ${data.key}`;
    apiKeyLabel.value = '';
    showToast('API key created', 'success');
    loadApiKeys();
  } else {
    apiKeyResult.textContent = data.detail || 'Failed to create key';
  }
});

apiKeyList.addEventListener('click', async (event) => {
  const button = event.target.closest('button');
  if (!button || !button.hasAttribute('data-deletekey')) return;
  const keyId = button.getAttribute('data-deletekey');
  const response = await fetch(`/api/omedia/apikeys/${keyId}`, { method: 'DELETE', headers: { 'X-CSRF-Token': getCsrfToken() } });
  if (response.ok) {
    showToast('API key revoked', 'success');
    loadApiKeys();
  }
});

loadApiKeys();
    }
  }

  if (button.hasAttribute('data-share')) {
    const filePath = button.getAttribute('data-share');
    sharePath.value = filePath;
    shareResult.innerHTML = '';
    shareStatus.textContent = '';
    shareForm.scrollIntoView({ behavior: 'smooth' });
  }
});

logoutBtn.addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() } });
  window.location.href = '/login.html';
});

shareForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const user = await requireSession();
  if (!user) return;
  const filepath = sharePath.value.trim();
  if (!filepath) {
    shareStatus.textContent = 'Enter a file path.';
    return;
  }
  shareStatus.textContent = 'Creating link...';
  shareResult.innerHTML = '';
  const response = await fetch('/api/fileshare/upload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
    body: JSON.stringify({ filepath, isforever: shareForever.checked }),
  });
  const data = await response.json();
  if (response.ok) {
    const link = window.location.origin + data.URL;
    shareStatus.textContent = 'Link created!';
    shareResult.innerHTML = `
      <div class="share-link-box">
        <input id="shareLink" type="text" value="${escapeHTML(link)}" readonly />
        <button class="btn btn-primary" onclick="navigator.clipboard.writeText(document.getElementById('shareLink').value).then(() => this.textContent = 'Copied!')">Copy</button>
      </div>
    `;
  } else {
    shareStatus.textContent = data.Reason || 'Failed to create link.';
  }
});

loadFiles();

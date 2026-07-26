const userList = document.getElementById('userList');
const fileList = document.getElementById('fileList');
const logoutBtn = document.getElementById('logoutBtn');
const auditLog = document.getElementById('auditLog');
const loadMoreAudit = document.getElementById('loadMoreAudit');
let currentUser = null;
let auditOffset = 0;

async function requireAdmin() {
  const response = await fetch('/api/me');
  if (!response.ok) {
    window.location.href = '/login.html';
    return null;
  }
  const data = await response.json();
  if (data.role !== 'admin') {
    window.location.href = '/omedia/userdashboard.html';
    return null;
  }
  currentUser = data;
  return data;
}

async function loadUsers() {
  const admin = await requireAdmin();
  if (!admin) return;
  const response = await fetch('/api/omedia/admin/users');
  const data = await response.json();
  userList.innerHTML = '';
  const list = document.createElement('ul');
  data.users.forEach((user) => {
    const item = document.createElement('li');
    item.className = 'file-item';
    item.innerHTML = `
      <div class="file-info file-user">
        <span class="file-icon">&#x1f464;</span>
        <span class="file-name">${escapeHTML(user.username)} <span style="font-size:0.75rem; color:var(--text-secondary);">(${escapeHTML(user.email)})</span></span>
      </div>
      <div class="file-actions">
        <button class="link-btn" data-view="${escapeHTML(user.username)}">View files</button>
        <button class="link-btn btn-delete" data-delete="${escapeHTML(user.username)}">Delete</button>
     </div>
    `;
    list.appendChild(item);
  });
  userList.appendChild(list);
}

async function loadFiles(username) {
  const response = await fetch(`/api/omedia/admin/files/${encodeURIComponent(username)}`);
  const data = await response.json();
  fileList.innerHTML = '';
  if (!data.entries.length) {
    fileList.innerHTML = '<p class="empty">No files found.</p>';
    return;
  }
  const list = document.createElement('ul');
  data.entries.forEach((entry) => {
    const item = document.createElement('li');
    item.className = 'file-item';
    const isDir = entry.type === 'dir';
    const icon = isDir ? '\u{1f4c1}' : '\u{1f4c4}';
    item.innerHTML = `
		<div class="file-info ${isDir ? 'file-dir' : 'file-txt'}">
			<span class="file-icon">${icon}</span>
			<span class="file-name">${escapeHTML(entry.name)} ${entry.type === 'file' ? `<span style="font-size:0.75rem; color:var(--text-secondary);">(${entry.size} bytes)</span>` : ''}</span>
		</div>
    `;
    list.appendChild(item);
  });
  fileList.appendChild(list);
}

userList.addEventListener('click', async (event) => {
  const button = event.target.closest('button');
  if (!button) return;
  const username = button.getAttribute('data-view') || button.getAttribute('data-delete');
  if (button.hasAttribute('data-view')) {
    loadFiles(username);
  } else if (button.hasAttribute('data-delete')) {
    const response = await fetch(`/api/admin/users/${encodeURIComponent(username)}`, { method: 'DELETE', headers: { 'X-CSRF-Token': getCsrfToken() } });
    if (response.ok) {
      showToast('User deleted', 'success');
      loadUsers();
      fileList.innerHTML = '<p class="empty">User deleted.</p>';
    }
  }
});

logoutBtn.addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() } });
  window.location.href = '/login.html';
});

async function loadAuditLogs(append = false) {
  if (!append) auditOffset = 0;
  const response = await fetch(`/api/omedia/admin/audit?limit=50&offset=${auditOffset}`);
  const data = await response.json();
  if (!append) auditLog.innerHTML = '';
  if (!data.logs.length && !append) {
    auditLog.innerHTML = '<p class="empty">No audit logs yet.</p>';
    loadMoreAudit.style.display = 'none';
    return;
  }
  const list = auditLog.querySelector('ul') || document.createElement('ul');
  if (!append) auditLog.appendChild(list);
  data.logs.forEach((log) => {
    const item = document.createElement('li');
    item.className = 'file-item';
    item.style.flexDirection = 'column';
    item.style.alignItems = 'flex-start';
    item.style.gap = '4px';
    item.innerHTML = `
      <div style="display:flex; justify-content:space-between; width:100%;">
        <span style="font-weight:600; color:var(--accent-cyan);">${escapeHTML(log.action)}</span>
        <span style="font-size:0.75rem; color:var(--text-muted);">${escapeHTML(log.timestamp)}</span>
      </div>
      <div style="font-size:0.85rem; color:var(--text-secondary);">
        ${log.username ? 'User: ' + escapeHTML(log.username) : ''}${log.detail ? ' | ' + escapeHTML(log.detail) : ''}${log.ip ? ' | IP: ' + escapeHTML(log.ip) : ''}
      </div>
    `;
    list.appendChild(item);
  });
  auditOffset += data.logs.length;
  loadMoreAudit.style.display = auditOffset < data.total ? 'inline-block' : 'none';
}

loadMoreAudit.addEventListener('click', () => loadAuditLogs(true));

loadUsers();
loadAuditLogs();

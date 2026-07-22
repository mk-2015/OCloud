const userList = document.getElementById('userList');
const fileList = document.getElementById('fileList');
const logoutBtn = document.getElementById('logoutBtn');
let currentUser = null;

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

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
        <span class="file-icon">👤</span>
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
    const icon = isDir ? '📁' : '📄';
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
      loadUsers();
      fileList.innerHTML = '<p class="empty">User deleted.</p>';
    }
  }
});

logoutBtn.addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() } });
  window.location.href = '/login.html';
});

loadUsers();

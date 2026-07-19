const usernameInput = document.getElementById('username');
const loadBtn = document.getElementById('loadBtn');
const uploadForm = document.getElementById('uploadForm');
const fileList = document.getElementById('fileList');
const status = document.getElementById('status');

async function loadFiles() {
  const username = usernameInput.value.trim();
  if (!username) {
    status.textContent = 'Enter a username to view files.';
    return;
  }

  status.textContent = 'Loading files...';
  const response = await fetch(`/api/omedia/lsdir/${encodeURIComponent(username)}`);
  const data = await response.json();
  fileList.innerHTML = '';

  if (!data.entries.length) {
    fileList.innerHTML = '<p class="empty">No files yet.</p>';
    status.textContent = 'No files found for this user.';
    return;
  }

  const list = document.createElement('ul');
  data.entries.forEach((file) => {
    const item = document.createElement('li');
    item.className = 'file-item';
    item.innerHTML = `
      <span>${file.name}</span>
      <div class="file-actions">
        <a href="/api/omedia/download/${encodeURIComponent(username)}/${encodeURIComponent(file.path)}" target="_blank">Download</a>
        <button data-name="${file.name}" class="link-btn">Delete</button>
      </div>
    `;
    list.appendChild(item);
  });
  fileList.appendChild(list);
  status.textContent = `Loaded ${data.entries.length} file(s).`;
}

loadBtn.addEventListener('click', loadFiles);
usernameInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    loadFiles();
  }
});

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const username = usernameInput.value.trim();
  const folder = document.getElementById('folder').value.trim();
  const fileInput = document.getElementById('file');
  const formData = new FormData();

  if (!username || !fileInput.files.length) {
    status.textContent = 'Enter a username and choose a file.';
    return;
  }

  formData.append('file', fileInput.files[0]);
  if (folder) formData.append('folder', folder);

  status.textContent = 'Uploading...';
  const response = await fetch(`/api/omedia/upload/${encodeURIComponent(username)}`, {
    method: 'POST',
    body: formData,
  });
  const data = await response.json();
  status.textContent = data.status || 'Upload complete';
  uploadForm.reset();
  loadFiles();
});

fileList.addEventListener('click', async (event) => {
  if (event.target.matches('button[data-name]')) {
    const username = usernameInput.value.trim();
    const name = event.target.getAttribute('data-name');
    const response = await fetch(`/api/omedia/delete/${encodeURIComponent(username)}/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
    if (response.ok) {
      status.textContent = 'File deleted.';
      loadFiles();
    } else {
      status.textContent = 'Deletion failed.';
    }
  }
});

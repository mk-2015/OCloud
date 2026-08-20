// Local State
let socket = null;
let selectedTargetUser = null;
let selectedFiles = []; // Array of relative file paths selected
let pendingConnectionsPayload = null;

// File Picker Modal State
let currentFolderPath = '.';
let activeDirectoryEntries = [];
let tempSelectedFilePath = null;

// DOM Elements
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const btnConnect = document.getElementById('btnConnect');
const btnDisconnect = document.getElementById('btnDisconnect');
const userList = document.getElementById('userList');
const userCount = document.getElementById('userCount');
const selectedTargetDisplay = document.getElementById('selectedTargetDisplay');
const filePreview = document.getElementById('filePreview');
const btnSend = document.getElementById('btnSend');

const transferModal = document.getElementById('transferModal');
const transferContainer = document.getElementById('transferContainer');

const filePickerModal = document.getElementById('filePickerModal');
const pickerBreadcrumb = document.getElementById('pickerBreadcrumb');
const pickerList = document.getElementById('pickerList');

// -------------------------------------------------------------
// Network Management
// -------------------------------------------------------------

async function networkConnect() {
    try {
        const res = await fetch('/api/konnect/network-connect', { method: 'POST' });
        if (!res.ok) throw new Error('Failed to announce connection');

        statusDot.classList.add('connected');
        statusText.innerText = 'Connected';
        btnConnect.disabled = true;
        btnDisconnect.disabled = false;

        initWebSocket();
        fetchUserList();
    } catch (err) {
        alert('Connect Error: ' + err.message);
    }
}

async function networkDisconnect() {
    try {
        await fetch('/api/konnect/network-disconnect', { method: 'POST' });
        if (socket) socket.close();

        statusDot.classList.remove('connected');
        statusText.innerText = 'Disconnected';
        btnConnect.disabled = false;
        btnDisconnect.disabled = true;

        userList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 10px;">Connect to view active network peers.</div>';
        userCount.innerText = '0';
        selectTarget(null);
    } catch (err) {
        console.error('Disconnect error:', err);
    }
}

async function fetchUserList() {
    if (!statusDot.classList.contains('connected')) return;

    try {
        const res = await fetch('/api/konnect/list-connected');
        const users = await res.json();
        
        userCount.innerText = users.length;
        userList.innerHTML = '';

        users.forEach(entry => {
            const div = document.createElement('div');
            div.className = `user-item ${selectedTargetUser === entry.user ? 'selected' : ''}`;
            div.innerHTML = `
                <span>${entry.user}</span>
                <span class="user-tag">Online</span>
            `;
            div.onclick = () => selectTarget(entry.user);
            userList.appendChild(div);
        });
    } catch (err) {
        console.error('Failed to update peer list:', err);
    }
}

function selectTarget(username) {
    selectedTargetUser = username;
    if (username) {
        selectedTargetDisplay.innerHTML = `Target Peer: <strong>${username}</strong>`;
    } else {
        selectedTargetDisplay.innerHTML = `Target Peer: <strong>None Selected</strong> (Click a peer from the list)`;
    }
    updateSendButtonState();
    fetchUserList();
}

// -------------------------------------------------------------
// OMedia Directory Browser & File Picker Modal
// -------------------------------------------------------------

async function openFilePickerModal() {
    currentFolderPath = '.';
    tempSelectedFilePath = null;
    filePickerModal.classList.add('active');
    await loadDirectoryContents(currentFolderPath);
}

function closeFilePickerModal() {
    filePickerModal.classList.remove('active');
    tempSelectedFilePath = null;
}

async function loadDirectoryContents(path) {
    try {
        const meRes = await fetch('/api/me');
        if (!meRes.ok) throw new Error('Failed to resolve current session user');
        const meData = await meRes.json();
        const username = meData.username;

        const res = await fetch(`/api/omedia/list/${encodeURIComponent(username)}?path=${encodeURIComponent(path)}`);
        if (!res.ok) throw new Error('Failed to load directory files');
        const data = await res.json();

        activeDirectoryEntries = data.entries || (Array.isArray(data) ? data : []);
        currentFolderPath = path;
        pickerBreadcrumb.innerText = `Path: ${currentFolderPath}`;
        renderPickerList();
    } catch (err) {
        alert('Directory Error: ' + err.message);
    }
}

function renderPickerList() {
    pickerList.innerHTML = '';

    // "Up" level navigation if not in root
    if (currentFolderPath !== '.' && currentFolderPath !== '') {
        const upDiv = document.createElement('div');
        upDiv.className = 'picker-item';
        upDiv.innerHTML = `<span>📁 <strong>.. (Parent Directory)</strong></span>`;
        upDiv.onclick = () => {
            const parts = currentFolderPath.split('/');
            parts.pop();
            const parentPath = parts.length > 0 ? parts.join('/') : '.';
            loadDirectoryContents(parentPath || '.');
        };
        pickerList.appendChild(upDiv);
    }

    if (activeDirectoryEntries.length === 0) {
        pickerList.innerHTML += `<div style="padding: 15px; color: var(--text-muted); font-size: 0.85rem;">Folder is empty.</div>`;
        return;
    }

    activeDirectoryEntries.forEach(item => {
        const div = document.createElement('div');
        const isSelected = tempSelectedFilePath === item.path;
        div.className = `picker-item ${isSelected ? 'selected' : ''}`;

        if (item.type === 'dir') {
            div.innerHTML = `<span>📁 ${item.name}</span> <span style="opacity:0.5; font-size:0.75rem;">Directory</span>`;
            div.onclick = () => loadDirectoryContents(item.path);
        } else {
            const sizeKB = item.size ? `${Math.round(item.size / 1024)} KB` : '';
            div.innerHTML = `<span>📄 ${item.name}</span> <span style="opacity:0.5; font-size:0.75rem;">${sizeKB}</span>`;
            div.onclick = () => {
                tempSelectedFilePath = item.path;
                renderPickerList();
            };
        }

        pickerList.appendChild(div);
    });
}

function confirmFileSelection() {
    if (!tempSelectedFilePath) {
        alert('Please click to select a file.');
        return;
    }

    if (!selectedFiles.includes(tempSelectedFilePath)) {
        selectedFiles.push(tempSelectedFilePath);
        renderSelectedFileChips();
    }

    closeFilePickerModal();
}

function renderSelectedFileChips() {
    filePreview.innerHTML = '';
    selectedFiles.forEach((filePath, idx) => {
        const chip = document.createElement('div');
        chip.className = 'file-chip';
        chip.innerHTML = `
            📄 ${filePath} 
            <span class="remove-btn" onclick="removeSelectedFile(${idx})">×</span>
        `;
        filePreview.appendChild(chip);
    });
    updateSendButtonState();
}

function removeSelectedFile(index) {
    selectedFiles.splice(index, 1);
    renderSelectedFileChips();
}

function updateSendButtonState() {
    btnSend.disabled = !(selectedTargetUser && selectedFiles.length > 0);
}

async function sendFiles() {
    if (!selectedTargetUser || selectedFiles.length === 0) return;

    try {
        const res = await fetch('/api/konnect/send-file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                to_user: selectedTargetUser,
                files: selectedFiles
            })
        });

        const data = await res.json();
        if (res.ok) {
            alert(`Success: ${data.message}`);
            selectedFiles = [];
            renderSelectedFileChips();
        } else {
            alert(`Error: ${data.detail}`);
        }
    } catch (err) {
        alert('Send Error: ' + err.message);
    }
}

// -------------------------------------------------------------
// WebSocket Handshake (Incoming File Stream Protocol)
// -------------------------------------------------------------

function initWebSocket() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    if (socket) {
        socket.onclose = null;
        socket.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('omedia_token') || '';
    socket = new WebSocket(`${protocol}//${window.location.host}/api/konnect/recieve-file?token=${encodeURIComponent(token)}`);

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (Object.keys(data).some(k => k.startsWith('connection-'))) {
            pendingConnectionsPayload = data;
            renderIncomingOffers(data);
        } else if (data.status === 'processed') {
            console.log('Transfers processed:', data.copied);
        }
    };

    socket.onclose = (event) => {
        console.log(`WebSocket closed: code=${event.code}, reason=${event.reason}, wasClean=${event.wasClean}`);
        socket = null;
        if (statusDot.classList.contains('connected')) {
            setTimeout(initWebSocket, 3000);
        }
    };

    socket.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
}

window.addEventListener('beforeunload', () => {
    if (socket) {
        socket.onclose = null;
        socket.close();
    }
});

async function renderIncomingOffers(offers) {
    transferContainer.innerHTML = '';

    let omediaDirs = [];
    try {
        const meRes = await fetch('/api/me');
        if (meRes.ok) {
            const meData = await meRes.json();
            const username = meData.username;
            
            const res = await fetch(`/api/omedia/list/${encodeURIComponent(username)}?path=.`);
            if (res.ok) {
                const data = await res.json();
                const items = data.entries || (Array.isArray(data) ? data : []);
                omediaDirs = items.filter(item => item.type === 'dir');
            }
        }
    } catch (e) {
        console.error('Failed to fetch OMedia directories:', e);
    }

    Object.entries(offers).forEach(([key, offer]) => {
        const card = document.createElement('div');
        card.className = 'transfer-card';
        
        const filesList = offer.file.map(f => `<li>${f.file}</li>`).join('');
        const dirOptions = omediaDirs.map(d => `<option value="${d.path}">${d.name}</option>`).join('');
        
        card.innerHTML = `
            <header>
                <span>From: ${offer.user}</span>
                <input type="checkbox" id="chk-${key}" checked>
            </header>
            <ul style="padding-left: 18px; margin-top: 5px; color: var(--text-muted);">
                ${filesList}
            </ul>
            <div style="margin-top: 10px;">
                <label style="font-size: 0.75rem;">Save Destination Folder (Storage):</label>
                <select id="sel-${key}" style="width: 100%; margin-top: 4px; padding: 4px; background: #161b22; color: #fff; border: 1px solid var(--border-color); border-radius: 4px;">
                    <option value="">Default (Root Storage)</option>
                    ${dirOptions}
                </select>
            </div>
        `;
        transferContainer.appendChild(card);
    });

    transferModal.classList.add('active');
}

function respondToTransfers(acceptAll) {
    if (!pendingConnectionsPayload || !socket) return;

    let responseLines = [];

    Object.keys(pendingConnectionsPayload).forEach(key => {
        const chk = document.getElementById(`chk-${key}`);
        const sel = document.getElementById(`sel-${key}`);
        const isAccepted = acceptAll && chk && chk.checked;
        
        const dest = sel ? sel.value : "";
        responseLines.push(`${isAccepted ? 'OK' : 'NO'} ${key} ${dest}`);
    });

    socket.send(responseLines.join('\n'));

    pendingConnectionsPayload = null;
    transferModal.classList.remove('active');
}
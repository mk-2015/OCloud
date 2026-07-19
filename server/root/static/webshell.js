const statusDot = document.getElementById('statusDot');
const logoutBtn = document.getElementById('logoutBtn');
const terminalEl = document.getElementById('terminal');

const term = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
    theme: {
        background: '#0a0e17',
        foreground: '#e2e8f0',
        cursor: '#06b6d4',
        cursorAccent: '#0a0e17',
        selectionBackground: 'rgba(6, 182, 212, 0.3)',
        black: '#1e293b',
        red: '#f43f5e',
        green: '#10b981',
        yellow: '#f59e0b',
        blue: '#3b82f6',
        magenta: '#8b5cf6',
        cyan: '#06b6d4',
        white: '#f1f5f9',
        brightBlack: '#475569',
        brightRed: '#fb7185',
        brightGreen: '#34d399',
        brightYellow: '#fbbf24',
        brightBlue: '#60a5fa',
        brightMagenta: '#a78bfa',
        brightCyan: '#22d3ee',
        brightWhite: '#f8fafc',
    },
});

const fitAddon = new FitAddon.FitAddon();
term.loadAddon(fitAddon);
term.open(terminalEl);

let ws = null;
let fitting = false;

function doFit() {
    if (fitting) return;
    fitting = true;
    fitAddon.fit();
    fitting = false;
}

function sendResize() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(`\x1b[${term.rows};${term.cols}R`);
    }
}

function fitAndResize() {
    doFit();
    sendResize();
}

function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('omedia_token') || '';
    ws = new WebSocket(`${proto}//${location.host}/api/webshell/ws?token=${encodeURIComponent(token)}`);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
        statusDot.classList.add('connected');
        fitAndResize();
    };

    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
            term.write(new Uint8Array(event.data));
        } else {
            term.write(event.data);
        }
    };

    ws.onclose = (e) => {
        statusDot.classList.remove('connected');
        ws = null;
        term.write(`\r\n\x1b[31m[Connection closed: ${e.code}]\x1b[0m\r\n`);
        setTimeout(connect, 3000);
    };

    ws.onerror = () => {
        statusDot.classList.remove('connected');
    };
}

term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(data);
    }
});

window.addEventListener('resize', fitAndResize);

logoutBtn.addEventListener('click', async () => {
    if (ws) ws.close();
    localStorage.removeItem('omedia_token');
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/login.html';
});

(async () => {
    const res = await fetch('/api/me');
    if (!res.ok) {
        window.location.href = '/login.html';
        return;
    }
    const user = await res.json();
    if (user.role !== 'admin') {
        window.location.href = '/omedia/userdashboard.html';
        return;
    }
    connect();
})();

const CIRCUMFERENCE = 2 * Math.PI * 52;
const REFRESH_MS = 3000;

const cpuFill = document.getElementById('cpuFill');
const memFill = document.getElementById('memFill');
const diskFill = document.getElementById('diskFill');
const swapFill = document.getElementById('swapFill');

const cpuPercent = document.getElementById('cpuPercent');
const memPercent = document.getElementById('memPercent');
const diskPercent = document.getElementById('diskPercent');
const swapPercent = document.getElementById('swapPercent');

const cpuDetail = document.getElementById('cpuDetail');
const memDetail = document.getElementById('memDetail');
const diskDetail = document.getElementById('diskDetail');
const swapDetail = document.getElementById('swapDetail');

const systemInfo = document.getElementById('systemInfo');
const uptimeInfo = document.getElementById('uptimeInfo');
const networkInfo = document.getElementById('networkInfo');
const diskInfoEl = document.getElementById('diskInfo');
const procBody = document.getElementById('procBody');
const systemBadge = document.getElementById('systemBadge');
const logoutBtn = document.getElementById('logoutBtn');

function escapeHTML(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

[cpuFill, memFill, diskFill, swapFill].forEach(c => {
    c.style.strokeDasharray = CIRCUMFERENCE;
    c.style.strokeDashoffset = CIRCUMFERENCE;
});

function setGauge(fillEl, pctEl, pct) {
    const offset = CIRCUMFERENCE - (pct / 100) * CIRCUMFERENCE;
    fillEl.style.strokeDashoffset = offset;
    pctEl.textContent = Math.round(pct) + '%';
    fillEl.classList.remove('warn', 'danger');
    if (pct >= 90) fillEl.classList.add('danger');
    else if (pct >= 70) fillEl.classList.add('warn');
}

function row(label, value) {
    return `<div class="info-row"><span class="label">${escapeHTML(String(label))}</span><span class="value">${escapeHTML(String(value))}</span></div>`;
}

async function requireSession() {
    const res = await fetch('/api/me');
    if (!res.ok) {
        window.location.href = '/login.html';
        return null;
    }
    const user = await res.json();
    if (user.role !== 'admin') {
        window.location.href = '/omedia/userdashboard.html';
        return null;
    }
    return user;
}

async function refresh() {
    const user = await requireSession();
    if (!user) return;

    try {
        const [statsRes, procRes, diskRes, netRes] = await Promise.all([
            fetch('/api/monitord/stats'),
            fetch('/api/monitord/processes'),
            fetch('/api/monitord/disks'),
            fetch('/api/monitord/network'),
        ]);

        if (!statsRes.ok) return;

        const stats = await statsRes.json();
        const procs = await procRes.json();
        const disks = await diskRes.json();
        const net = await netRes.json();

        setGauge(cpuFill, cpuPercent, stats.cpu.percent);
        cpuDetail.textContent = `${stats.cpu.count} cores${stats.cpu.freq_current ? ' @ ' + stats.cpu.freq_current + ' MHz' : ''}`;

        setGauge(memFill, memPercent, stats.memory.percent);
        memDetail.textContent = `${stats.memory.used_fmt} / ${stats.memory.total_fmt}`;

        setGauge(diskFill, diskPercent, stats.disk.percent);
        diskDetail.textContent = `${stats.disk.used_fmt} / ${stats.disk.total_fmt}`;

        setGauge(swapFill, swapPercent, stats.swap.percent);
        swapDetail.textContent = `${stats.swap.used_fmt} / ${stats.swap.total_fmt}`;

        const sys = stats.system;
        systemBadge.textContent = `${sys.os} ${sys.arch}`;
        systemInfo.innerHTML =
            row('Hostname', sys.hostname) +
            row('OS', `${sys.os} ${sys.os_release}`) +
            row('Arch', sys.arch) +
            row('Python', sys.python);

        const u = stats.uptime;
        uptimeInfo.innerHTML =
            row('Uptime', `${u.days}d ${u.hours}h ${u.minutes}m`) +
            row('Booted', new Date(u.boot_time * 1000).toLocaleString());

        const netStats = stats.network;
        networkInfo.innerHTML =
            row('Sent', netStats.bytes_sent_fmt) +
            row('Received', netStats.bytes_recv_fmt) +
            row('Interfaces', net.interfaces.length);

        diskInfoEl.innerHTML = disks.disks.map(d =>
            row(`${d.mountpoint}`, `${d.used_fmt} / ${d.total_fmt} (${d.percent}%)`)
        ).join('');

        procBody.innerHTML = procs.processes.map(p =>
            `<tr><td>${escapeHTML(String(p.pid))}</td><td>${escapeHTML(p.name)}</td><td>${escapeHTML(p.user)}</td><td>${escapeHTML(String(p.cpu))}</td><td>${escapeHTML(String(p.mem))}</td><td>${escapeHTML(p.status)}</td></tr>`
        ).join('');
    } catch (e) {
        console.error('Monitor refresh failed:', e);
    }
}

logoutBtn.addEventListener('click', async () => {
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/login.html';
});

refresh();
setInterval(refresh, REFRESH_MS);

document.addEventListener('DOMContentLoaded', () => {
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
    const diskInfo = document.getElementById('diskInfo');
    const procBody = document.getElementById('procBody');
    const systemBadge = document.getElementById('systemBadge');

    function updateGauge(fill, percentEl, detailEl, percent, detailText) {
        if (!fill || !percentEl) return;
        const radius = fill.r.baseVal.value;
        const circumference = radius * 2 * Math.PI;
        const offset = circumference - (percent / 100) * circumference;
        fill.style.strokeDasharray = `${circumference} ${circumference}`;
        fill.style.strokeDashoffset = offset;
        percentEl.textContent = `${Math.round(percent)}%`;
        if (detailEl) detailEl.textContent = detailText;
    }

    // Connect to websocket for stats
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/monitor`);

    ws.onmessage = (event) => {
        try {
            const stats = JSON.parse(event.data);
            
            // Update Gauges
            updateGauge(cpuFill, cpuPercent, cpuDetail, stats.cpu.percent, `${stats.cpu.count} cores @ ${stats.cpu.freq_current || '?'}MHz`);
            updateGauge(memFill, memPercent, memDetail, stats.memory.percent, `${stats.memory.used_fmt} / ${stats.memory.total_fmt}`);
            updateGauge(diskFill, diskPercent, diskDetail, stats.disk.percent, `${stats.disk.used_fmt} / ${stats.disk.total_fmt}`);
            updateGauge(swapFill, swapPercent, swapDetail, stats.swap.percent, `${stats.swap.used_fmt} / ${stats.swap.total_fmt}`);

            // Update Info (Use escapeHTML to prevent XSS)
            systemInfo.innerHTML = `
                <div class="info-row"><span class="label">OS</span><span class="value">${escapeHTML(stats.system.os)} ${escapeHTML(stats.system.os_release)}</span></div>
                <div class="info-row"><span class="label">Hostname</span><span class="value">${escapeHTML(stats.system.hostname)}</span></div>
                <div class="info-row"><span class="label">Arch</span><span class="value">${escapeHTML(stats.system.arch)}</span></div>
            `;
            
            uptimeInfo.innerHTML = `
                <div class="info-row"><span class="label">Days</span><span class="value">${stats.uptime.days}</span></div>
                <div class="info-row"><span class="label">Hours</span><span class="value">${stats.uptime.hours}</span></div>
                <div class="info-row"><span class="label">Minutes</span><span class="value">${stats.uptime.minutes}</span></div>
            `;

            networkInfo.innerHTML = `
                <div class="info-row"><span class="label">Sent</span><span class="value">${escapeHTML(stats.network.bytes_sent_fmt)}</span></div>
                <div class="info-row"><span class="label">Received</span><span class="value">${escapeHTML(stats.network.bytes_recv_fmt)}</span></div>
            `;

            diskInfo.innerHTML = `
                <div class="info-row"><span class="label">Used</span><span class="value">${escapeHTML(stats.disk.used_fmt)}</span></div>
                <div class="info-row"><span class="label">Free</span><span class="value">${escapeHTML(stats.disk.free_fmt)}</span></div>
                <div class="info-row"><span class="label">Total</span><span class="value">${escapeHTML(stats.disk.total_fmt)}</span></div>
            `;
            
            systemBadge.textContent = 'Live';
        } catch (e) {
            console.error('Failed to parse stats', e);
        }
    };
    
    ws.onerror = (e) => {
        showToast('Monitoring connection error', 'error');
    };
    
    ws.onclose = () => {
        systemBadge.textContent = 'Disconnected';
        showToast('Monitoring disconnected', 'warn');
    };

    // Fetch processes periodically
    async function fetchProcesses() {
        try {
            const res = await fetch('/api/monitord/processes');
            if (!res.ok) throw new Error('Failed to fetch');
            const data = await res.json();
            procBody.innerHTML = data.processes.map(p => `
                <tr>
                    <td>${escapeHTML(p.pid.toString())}</td>
                    <td>${escapeHTML(p.name)}</td>
                    <td>${escapeHTML(p.user)}</td>
                    <td>${escapeHTML(p.cpu.toString())}%</td>
                    <td>${escapeHTML(p.mem.toString())}%</td>
                    <td>${escapeHTML(p.status)}</td>
                </tr>
            `).join('');
        } catch (e) {
            console.error('Failed to fetch processes', e);
        } finally {
            setTimeout(fetchProcesses, 5000);
        }
    }
    
    fetchProcesses();
});

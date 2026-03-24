/**
 * status.js — Crawler status page.
 * - Shows list of crawlers if no ID in URL
 * - Shows detail view with live logs if ID present
 * - Polls for updates (like long-polling but simpler)
 */

const API = '';
let currentCrawlId = null;
let pollInterval = null;

// Detect crawl_id from URL path: /status/<crawl_id>
const pathParts = window.location.pathname.split('/');
if (pathParts.length >= 3 && pathParts[2]) {
    currentCrawlId = pathParts[2];
    showDetail(currentCrawlId);
} else {
    loadCrawlerList();
}

// ── List View ──
async function loadCrawlerList() {
    try {
        const res = await fetch(`${API}/api/crawl`);
        const jobs = await res.json();
        const tbody = document.getElementById('crawler-list');

        if (!jobs.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No crawlers yet.</td></tr>';
            return;
        }

        tbody.innerHTML = jobs.map(job => `
            <tr style="cursor:pointer;" onclick="window.location='/status/${job.id || job.crawl_id}'">
                <td style="font-family:monospace; font-size:0.8rem;">${(job.id || job.crawl_id).substring(0, 20)}...</td>
                <td><a href="/status/${job.id || job.crawl_id}">${job.origin}</a></td>
                <td><span class="badge badge-${job.status}">${job.status}</span></td>
                <td>${job.pages_crawled || 0}</td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Error loading crawler list:', err);
    }
}

// ── Detail View ──
async function showDetail(crawlId) {
    document.getElementById('pick-crawler').style.display = 'none';
    document.getElementById('crawler-detail').style.display = 'block';

    // Initial load
    await updateDetail(crawlId);

    // Poll every 2 seconds for live updates
    pollInterval = setInterval(() => updateDetail(crawlId), 2000);
}

async function updateDetail(crawlId) {
    try {
        const res = await fetch(`${API}/api/crawl/${crawlId}`);
        if (!res.ok) {
            document.getElementById('detail-status').textContent = 'Not Found';
            if (pollInterval) clearInterval(pollInterval);
            return;
        }

        const data = await res.json();

        // Update stats
        document.getElementById('detail-status').textContent = data.status || '-';
        document.getElementById('detail-status').style.color =
            data.status === 'running' ? 'var(--accent)' :
            data.status === 'completed' ? 'var(--success)' :
            data.status === 'error' ? 'var(--danger)' : 'var(--warn)';

        document.getElementById('detail-pages').textContent = data.pages_crawled || 0;
        document.getElementById('detail-queue').textContent = data.queue_size || 0;
        document.getElementById('detail-depth').textContent = data.max_depth || '-';
        renderBackPressure(data);

        // Info table
        document.getElementById('detail-id').textContent = crawlId;
        document.getElementById('detail-origin').innerHTML = `<a href="${data.origin}" target="_blank">${data.origin}</a>`;
        document.getElementById('detail-hitrate').textContent = `${data.hit_rate || '-'} req/sec`;
        document.getElementById('detail-maxurls').textContent = data.max_urls || '-';
        document.getElementById('detail-maxqueue').textContent = data.max_queue || '-';
        document.getElementById('detail-queueusage').textContent = formatQueueUsage(data.queue_size, data.max_queue);

        // Control buttons
        renderControlButtons(crawlId, data.status);

        // Logs
        if (data.logs && data.logs.length) {
            const logBox = document.getElementById('log-box');
            logBox.innerHTML = data.logs.map(log => {
                const cls = log.level === 'error' ? 'error' : log.level === 'warn' ? 'warn' : '';
                return `<div class="log-entry ${cls}">${log.message}</div>`;
            }).join('');
            // Auto-scroll to bottom
            logBox.scrollTop = logBox.scrollHeight;
        }

        // Stop polling if crawl is done
        if (['completed', 'error', 'stopped'].includes(data.status) && pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    } catch (err) {
        console.error('Error updating detail:', err);
    }
}

function formatQueueUsage(queueSize, maxQueue) {
    const size = queueSize || 0;
    const capacity = maxQueue || 0;
    if (!capacity) return `${size}`;
    const pct = Math.round((size / capacity) * 100);
    return `${size} / ${capacity} (${pct}%)`;
}

function renderBackPressure(data) {
    const el = document.getElementById('detail-pressure');
    const queueSize = data.queue_size || 0;
    const maxQueue = data.max_queue || 0;

    if (!maxQueue) {
        el.textContent = 'Unknown';
        el.style.color = 'var(--text)';
        return;
    }

    const pct = Math.round((queueSize / maxQueue) * 100);
    let label = 'Low';
    let color = 'var(--success)';

    if (pct >= 90) {
        label = 'High';
        color = 'var(--danger)';
    } else if (pct >= 60) {
        label = 'Medium';
        color = 'var(--warn)';
    }

    el.textContent = `${label} (${pct}%)`;
    el.style.color = color;
}

function renderControlButtons(crawlId, status) {
    const container = document.getElementById('control-buttons');
    let html = '';

    if (status === 'running') {
        html += `<button class="btn btn-sm btn-primary" onclick="controlCrawler('${crawlId}', 'pause')">Pause</button>`;
        html += `<button class="btn btn-sm btn-danger" onclick="controlCrawler('${crawlId}', 'stop')">Stop</button>`;
    } else if (status === 'paused') {
        html += `<button class="btn btn-sm btn-primary" onclick="controlCrawler('${crawlId}', 'resume')">Resume</button>`;
        html += `<button class="btn btn-sm btn-danger" onclick="controlCrawler('${crawlId}', 'stop')">Stop</button>`;
    } else if (status === 'stopped') {
        html += `<button class="btn btn-sm btn-primary" onclick="controlCrawler('${crawlId}', 'resume')">Resume</button>`;
    }

    html += `<a href="/" class="btn btn-sm" style="background:var(--surface2); color:var(--text);">New Crawl</a>`;
    container.innerHTML = html;
}

async function controlCrawler(crawlId, action) {
    try {
        const res = await fetch(`${API}/api/crawl/${crawlId}/${action}`, { method: 'POST' });
        const data = await res.json();
        if (data.error) {
            alert(data.error);
        } else if (action === 'resume' && !pollInterval) {
            // Restart polling only on successful resume
            pollInterval = setInterval(() => updateDetail(crawlId), 2000);
        }
        await updateDetail(crawlId);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

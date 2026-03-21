/**
 * crawler.js — Handles the main crawler page.
 * - Submit new crawl jobs
 * - Display stats
 * - Show recent jobs table
 */

const API = '';  // same origin

// ── Start Crawl ──
document.getElementById('crawl-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Starting...';

    try {
        const res = await fetch(`${API}/api/crawl`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                origin: document.getElementById('origin').value.trim(),
                max_depth: parseInt(document.getElementById('max_depth').value),
                hit_rate: parseFloat(document.getElementById('hit_rate').value),
                max_urls: parseInt(document.getElementById('max_urls').value),
                max_queue: parseInt(document.getElementById('max_queue').value),
            }),
        });

        const data = await res.json();
        if (res.ok) {
            // Redirect to status page
            window.location.href = `/status/${data.crawl_id}`;
        } else {
            alert(data.error || 'Failed to start crawl');
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Start Crawl';
    }
});

// ── Load Stats & Jobs ──
async function loadDashboard() {
    try {
        // Stats
        const statsRes = await fetch(`${API}/api/stats`);
        const stats = await statsRes.json();
        document.getElementById('stat-jobs').textContent = stats.total_jobs || 0;
        document.getElementById('stat-pages').textContent = stats.total_pages || 0;
        document.getElementById('stat-words').textContent = stats.total_words || 0;
        document.getElementById('stat-active').textContent = stats.active_crawlers || 0;

        // Jobs
        const jobsRes = await fetch(`${API}/api/crawl`);
        const jobs = await jobsRes.json();
        renderJobs(jobs);
    } catch (err) {
        console.error('Dashboard load error:', err);
    }
}

function renderJobs(jobs) {
    const tbody = document.getElementById('jobs-table');
    if (!jobs.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No crawl jobs yet. Start one above!</td></tr>';
        return;
    }

    tbody.innerHTML = jobs.map(job => {
        const status = job.status || 'unknown';
        const origin = job.origin || '';
        const shortOrigin = origin.length > 50 ? origin.substring(0, 50) + '...' : origin;

        return `
            <tr>
                <td><a href="/status/${job.id || job.crawl_id}" title="${origin}">${shortOrigin}</a></td>
                <td>${job.max_depth}</td>
                <td>${job.pages_crawled || 0}</td>
                <td><span class="badge badge-${status}">${status}</span></td>
                <td>
                    <a href="/status/${job.id || job.crawl_id}" class="btn btn-sm btn-primary">View</a>
                </td>
            </tr>
        `;
    }).join('');
}

// ── Clear All Data ──
async function clearAllData() {
    if (!confirm('Are you sure? This will delete ALL crawl jobs, pages, and search index.')) return;
    try {
        const res = await fetch(`${API}/api/clear`, { method: 'POST' });
        const data = await res.json();
        alert(data.message || 'All data cleared');
        loadDashboard();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// Load on page ready, then refresh every 3 seconds
loadDashboard();
setInterval(loadDashboard, 3000);

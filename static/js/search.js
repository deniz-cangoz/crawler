/**
 * search.js — Search page.
 * - Submit search queries
 * - Display results as (relevant_url, origin_url, depth) triples
 * - Pagination
 */

const API = '';
const PAGE_SIZE = 20;
let currentOffset = 0;
let currentQuery = '';
let totalResults = 0;

document.getElementById('search-form').addEventListener('submit', (e) => {
    e.preventDefault();
    currentQuery = document.getElementById('query').value.trim();
    currentOffset = 0;
    updateSearchUrl();
    doSearch();
});

function buildSearchUrl(includeFormat = false) {
    const sort = document.getElementById('sort').value;
    const params = new URLSearchParams();
    params.set('query', currentQuery);
    params.set('sortBy', sort);
    if (currentOffset > 0) {
        params.set('offset', String(currentOffset));
    }
    if (includeFormat) {
        params.set('format', 'json');
        params.set('limit', String(PAGE_SIZE));
    }
    return `${API}/search?${params.toString()}`;
}

function updateSearchUrl() {
    if (!currentQuery) return;
    window.history.replaceState({}, '', buildSearchUrl(false));
}

async function doSearch() {
    if (!currentQuery) return;

    const resultsDiv = document.getElementById('search-results');
    resultsDiv.innerHTML = '<div class="empty-state"><span class="spinner"></span> Searching...</div>';

    try {
        const res = await fetch(buildSearchUrl(true), {
            headers: {
                'Accept': 'application/json',
            },
        });
        const data = await res.json();

        if (data.error) {
            resultsDiv.innerHTML = `<div class="empty-state">${data.error}</div>`;
            return;
        }

        totalResults = data.total_results || 0;

        // Info bar
        const infoDiv = document.getElementById('search-info');
        infoDiv.style.display = 'block';
        document.getElementById('result-count').textContent =
            `${totalResults} result${totalResults !== 1 ? 's' : ''} found`;
        document.getElementById('query-words').textContent =
            data.query_words ? `Words: ${data.query_words.join(', ')}` : '';

        // Results
        if (!data.results || !data.results.length) {
            resultsDiv.innerHTML = '<div class="empty-state">No results found. Try different keywords.</div>';
            document.getElementById('pagination').style.display = 'none';
            return;
        }

        resultsDiv.innerHTML = data.results.map(r => `
            <div class="result-item">
                <a href="${r.relevant_url}" target="_blank" class="result-url">${r.relevant_url}</a>
                <div class="result-meta">
                    <span>Origin: <a href="${r.origin_url}" target="_blank">${truncate(r.origin_url, 60)}</a></span>
                    <span>Depth: ${r.depth}</span>
                    <span>Relevance Score: ${r.relevance_score ?? r.score}</span>
                    ${r.matched_words ? `<span>Matched: ${r.matched_words.join(', ')}</span>` : ''}
                </div>
            </div>
        `).join('');

        // Pagination
        const pagination = document.getElementById('pagination');
        if (totalResults > PAGE_SIZE) {
            pagination.style.display = 'block';
            const page = Math.floor(currentOffset / PAGE_SIZE) + 1;
            const totalPages = Math.ceil(totalResults / PAGE_SIZE);
            document.getElementById('page-info').textContent = `Page ${page} of ${totalPages}`;
            document.getElementById('prev-btn').disabled = currentOffset === 0;
            document.getElementById('next-btn').disabled = currentOffset + PAGE_SIZE >= totalResults;
        } else {
            pagination.style.display = 'none';
        }

    } catch (err) {
        resultsDiv.innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
    }
}

function changePage(direction) {
    currentOffset += direction * PAGE_SIZE;
    if (currentOffset < 0) currentOffset = 0;
    updateSearchUrl();
    doSearch();
}

function truncate(str, max) {
    return str.length > max ? str.substring(0, max) + '...' : str;
}

// "I'm Feeling Lucky" — pick a random indexed word
async function feelingLucky() {
    try {
        const res = await fetch(`${API}/api/search/random`);
        const data = await res.json();
        if (data.word) {
            document.getElementById('query').value = data.word;
            currentQuery = data.word;
            currentOffset = 0;
            updateSearchUrl();
            doSearch();
        } else {
            alert(data.error || 'No indexed words yet. Run a crawl first!');
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// Restore search state from URL
const urlParams = new URLSearchParams(window.location.search);
const queryFromUrl = urlParams.get('query') || urlParams.get('q');
const sortFromUrl = urlParams.get('sortBy') || urlParams.get('sort');
const offsetFromUrl = parseInt(urlParams.get('offset') || '0', 10);

if (sortFromUrl) {
    document.getElementById('sort').value = sortFromUrl;
}

if (queryFromUrl) {
    document.getElementById('query').value = queryFromUrl;
    currentQuery = queryFromUrl;
    currentOffset = Number.isNaN(offsetFromUrl) ? 0 : Math.max(0, offsetFromUrl);
    doSearch();
}

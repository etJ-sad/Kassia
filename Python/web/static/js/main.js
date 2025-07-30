import { apiGet, apiPost } from './api.js';
import { WebSocketManager } from './websocket.js';
import { renderJobs, setupEventListeners } from './ui.js';
import { JobLogViewer } from './job-logs.js';

async function loadJobs() {
    try {
        const jobs = await apiGet('/api/jobs');
        renderJobs(jobs);
    } catch (err) {
        console.error('Failed to load jobs', err);
    }
}

const wsScheme = location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocketManager(`${wsScheme}://${location.host}/ws`);
ws.onMessage(msg => {
    if (msg.type === 'jobs_updated') {
        loadJobs();
    }
});

setupEventListeners(loadJobs);
loadJobs();

// expose log viewer class for other modules
window.JobLogViewer = JobLogViewer;

export function renderJobs(jobs) {
    const list = document.getElementById('jobsList');
    if (!list) return;
    if (!jobs.length) {
        list.innerHTML = `<p style="text-align:center;padding:40px;">No jobs found</p>`;
        return;
    }
    list.innerHTML = `<ul class="job-list">${jobs.map(j => `<li>${j.job_id} - ${j.status}</li>`).join('')}</ul>`;
}

export function setupEventListeners(refresh) {
    const btn = document.querySelector('button[onclick="refreshJobs()"]');
    if (btn) {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            refresh();
        });
    }
}

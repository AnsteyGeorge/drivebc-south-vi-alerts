async function fetchDashboard() {
  try {
    const res = await fetch('/api/dashboard');
    if (!res.ok) throw new Error('Network error');
    return await res.json();
  } catch (err) {
    console.error('Failed to fetch dashboard:', err);
    return null;
  }
}

function setStatusBar(data) {
  const pill = document.getElementById('status-pill');
  const msg = document.getElementById('status-message');
  const last = document.getElementById('last-check');
  const next = document.getElementById('next-check');

  if (!data) {
    pill.textContent = 'OFFLINE';
    pill.className = 'pill pill-red';
    msg.textContent = 'Dashboard cannot reach monitor data';
    last.textContent = '—';
    next.textContent = '—';
    return;
  }

  let pillClass = 'pill pill-gray';
  let pillLabel = 'UNKNOWN';

  switch (data.status_color) {
    case 'green':
      pillClass = 'pill pill-green';
      pillLabel = 'HEALTHY';
      break;
    case 'amber':
      pillClass = 'pill pill-amber';
      pillLabel = 'DEGRADED';
      break;
    case 'red':
      pillClass = 'pill pill-red';
      pillLabel = 'ATTENTION';
      break;
  }

  pill.className = pillClass;
  pill.textContent = pillLabel;
  msg.textContent = data.status_message || 'Status unavailable';
  last.textContent = data.last_check ? new Date(data.last_check).toLocaleString() : '—';
  next.textContent = data.next_check ? new Date(data.next_check).toLocaleString() : '—';
}

function renderIncidents(data) {
  const strip = document.getElementById('incident-strip');
  const badge = document.getElementById('incident-count-badge');

  strip.innerHTML = '';
  const incidents = data ? data.live_incidents || [] : [];
  badge.textContent = incidents.length;

  if (!incidents.length) {
    strip.classList.add('empty-state');
    strip.innerHTML = `
      <div class="empty-message">
        <div class="empty-icon">✓</div>
        <div class="empty-text">
          <h3>No active commute disruptions detected</h3>
          <p>System is monitoring your South Island corridors in real time.</p>
        </div>
      </div>
    `;
    return;
  }

  strip.classList.remove('empty-state');

  incidents.forEach((inc) => {
    const risk = inc.risk ?? 0;
    let chipLabel = inc.incident_type || 'incident';
    chipLabel = chipLabel.replace(/_/g, ' ').toUpperCase();

    const card = document.createElement('div');
    card.className = 'incident-card high-risk';

    card.innerHTML = `
      <div class="incident-header">
        <div class="incident-title">${inc.camera}</div>
        <div class="incident-chip">${chipLabel}</div>
      </div>
      <div class="incident-body">
        <div class="incident-risk">${risk.toFixed(0)}</div>
        <div class="incident-meta">
          <div>Hwy ${inc.highway}</div>
          <div>${new Date(inc.timestamp).toLocaleTimeString()}</div>
        </div>
      </div>
    `;

    strip.appendChild(card);
  });
}

function riskClass(risk) {
  if (risk == null) return 'risk-none';
  if (risk < 30) return 'risk-low';
  if (risk < 70) return 'risk-medium';
  return 'risk-high';
}

function renderCameras(data) {
  const grid = document.getElementById('camera-grid');
  const badge = document.getElementById('camera-count-badge');
  grid.innerHTML = '';

  const cams = data ? data.cameras || [] : [];
  badge.textContent = cams.length;

  cams.forEach((cam) => {
    const card = document.createElement('div');
    card.className = 'camera-card';

    const risk = cam.last_risk;
    const riskLabel = risk == null ? '—' : risk.toFixed(0);
    const riskCls = riskClass(risk);
    const ts = cam.last_timestamp ? new Date(cam.last_timestamp).toLocaleTimeString() : '—';
    const imgSrc = cam.image_url || '';

    card.innerHTML = `
      <div class="camera-header">
        <div class="camera-name">${cam.name}</div>
        <div class="camera-highway">Hwy ${cam.highway}</div>
      </div>
      <div class="camera-thumbnail">
        ${
          imgSrc
            ? `<img src="${imgSrc}" alt="${cam.name}" />`
            : '<span style="font-size:0.8rem;color:var(--text-muted);">No image URL</span>'
        }
      </div>
      <div class="camera-metrics">
        <div class="camera-risk-label">Risk</div>
        <div class="camera-risk-value ${riskCls}">${riskLabel}</div>
      </div>
      <div class="camera-metrics">
        <div>Last update</div>
        <div style="font-variant-numeric: tabular-nums;">${ts}</div>
      </div>
    `;
    grid.appendChild(card);
  });
}

async function refreshDashboard() {
  const data = await fetchDashboard();
  setStatusBar(data);
  renderIncidents(data);
  renderCameras(data);
}

document.addEventListener('DOMContentLoaded', () => {
  refreshDashboard();
  setInterval(refreshDashboard, 20000);
});

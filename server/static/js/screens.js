/**
 * RaspiDeck — Displays / Screens Module
 * Handles pairing, telemetry, status metrics, display settings, and remote OTA updates.
 */

// --- SCREENS & OTA VERSION DATA FETCHING ---
async function fetchPlayerVersion() {
  try {
    const data = await api('/api/system/player-version');
    if (data && data.manifest) {
      state.playerManifest = data.manifest;
      state.serverPlayerVersion = data.manifest.version;
    }
  } catch (e) {
    console.error('Failed to fetch player release manifest:', e);
  }
}

async function fetchScreensSilent() {
  await fetchPlayerVersion();
  const data = await api('/api/screens');
  if (!data) return;
  state.screens = data;
  renderScreens();
  updateScreenStats();
}

async function fetchScreens() {
  await fetchPlayerVersion();
  const data = await api('/api/screens');
  if (!data) return;
  state.screens = data;
  renderScreens();
  updateScreenStats();
}

function updateScreenStats() {
  const paired = state.screens.filter(s => s.is_paired);
  const unpaired = state.screens.filter(s => !s.is_paired);
  const onlineCount = paired.filter(s => isScreenOnline(s.last_seen)).length;
  const offlineCount = paired.length - onlineCount;

  const onlineEl = document.getElementById('stat-screens-online');
  if (onlineEl) onlineEl.textContent = `${onlineCount} Online`;

  const totalEl = document.getElementById('stat-screens-total');
  if (totalEl) totalEl.textContent = `Dari ${paired.length} Layar Terpasang`;

  const offlineEl = document.getElementById('stat-screens-offline');
  if (offlineEl) {
    offlineEl.textContent = `${offlineCount} Offline`;
    if (offlineCount > 0) {
      offlineEl.className = 'fw-bold fs-2 text-truncate text-danger';
    } else {
      offlineEl.className = 'fw-bold fs-2 text-truncate text-secondary';
    }
  }

  const pendingEl = document.getElementById('stat-screens-pending');
  if (pendingEl) {
    pendingEl.textContent = `${unpaired.length} Layar`;
    if (unpaired.length > 0) {
      pendingEl.className = 'fw-bold fs-2 text-truncate text-warning';
    } else {
      pendingEl.className = 'fw-bold fs-2 text-truncate text-secondary';
    }
  }

  const badgeEl = document.getElementById('nav-badge-screens');
  if (badgeEl) badgeEl.textContent = onlineCount;

  const latestTime = state.screens.reduce((acc, s) => {
    if (!s.last_seen) return acc;
    const t = new Date(s.last_seen).getTime();
    return t > acc ? t : acc;
  }, 0);
  const syncEl = document.getElementById('stat-last-sync');
  if (syncEl) {
    syncEl.textContent = latestTime > 0 ? format24Time(latestTime) : '--:--:--';
  }

  // Update OTA Batch Button & Banner
  const targetVer = state.serverPlayerVersion;
  const outdatedScreens = paired.filter(s => targetVer && s.app_version && s.app_version !== targetVer);
  const batchBtn = document.getElementById('btn-batch-update');
  const batchCountEl = document.getElementById('batch-update-count');
  if (batchBtn && batchCountEl) {
    batchCountEl.textContent = outdatedScreens.length;
    if (outdatedScreens.length > 0) {
      batchBtn.classList.remove('d-none');
    } else {
      batchBtn.classList.add('d-none');
    }
  }

  const otaAlertContainer = document.getElementById('ota-update-alert-container');
  if (otaAlertContainer) {
    if (outdatedScreens.length > 0) {
      otaAlertContainer.innerHTML = `
        <div class="alert alert-info d-flex align-items-center justify-content-between p-3 rounded-3 shadow-sm border-0" role="alert">
          <div class="d-flex align-items-center gap-3">
            <span class="avatar bg-primary text-white rounded-3 flex-shrink-0">
              <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2" /><path d="M7 11l5 5l5 -5" /><path d="M12 4l0 12" /></svg>
            </span>
            <div>
              <h4 class="alert-title mb-1 fw-bold">Pembaruan Player Tersedia &bull; Versi ${escapeHtml(targetVer)}</h4>
              <div class="text-secondary small">${outdatedScreens.length} layar display saat ini menjalankan versi lama dan dapat diperbarui secara Over-The-Air.</div>
            </div>
          </div>
          <button class="btn btn-primary px-3 d-flex align-items-center gap-1" onclick="openBatchUpdateModal()">
            <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2" /><path d="M7 11l5 5l5 -5" /><path d="M12 4l0 12" /></svg>
            Perbarui Semua Layar (${outdatedScreens.length})
          </button>
        </div>
      `;
    } else {
      otaAlertContainer.innerHTML = '';
    }
  }
}

function isScreenOnline(lastSeenIso) {
  if (!lastSeenIso) return false;
  const diffSec = (Date.now() - new Date(lastSeenIso).getTime()) / 1000;
  return diffSec < 45; // 45s threshold (Pi heartbeats every 10s)
}

function parseScreenMetrics(s) {
  const online = isScreenOnline(s.last_seen);
  let sys = {};
  try {
    sys = typeof s.system_info === 'object' ? (s.system_info || {}) : JSON.parse(s.system_info || '{}');
  } catch(e){}

  let settings = { volume: 100, rotation: 'normal', heartbeat_interval: 10, screen_power: 'on' };
  try {
    if (s.settings) {
      settings = { ...settings, ...(typeof s.settings === 'object' ? s.settings : JSON.parse(s.settings)) };
    }
  } catch(e){}

  const appVersion = s.app_version || '2.0';
  const updateStatus = s.update_status || 'idle';
  const targetVersion = state.serverPlayerVersion || '2.1.0';
  const isOutdated = Boolean(appVersion && targetVersion && appVersion !== targetVersion);
  const isUpdating = ['pending', 'downloading', 'applying', 'restarting', 'verifying'].includes(updateStatus);

  const model = sys.model || 'Raspberry Pi Terminal';
  const temp = sys.temp != null ? `${sys.temp}°C` : '--';
  const tempVal = sys.temp != null ? sys.temp : 0;
  const tempColor = tempVal > 75 ? 'danger' : (tempVal > 60 ? 'warning' : 'success');

  const memPercent = sys.mem?.percent || 0;
  const diskPercent = sys.disk?.percent || 0;
  const hdmiStatus = sys.display?.hdmi || 'unknown';
  const hdmiColor = hdmiStatus === 'connected' ? 'success' : 'secondary';
  const resolution = sys.display?.resolution || 'Unknown';
  const playingTitle = sys.playing || 'Standby / Idle Loop';
  const playingType = sys.media_type || 'image';
  const assignedPlaylist = state.playlists.find(p => p.id === s.playlist_id);

  return {
    online,
    sys,
    settings,
    appVersion,
    updateStatus,
    targetVersion,
    isOutdated,
    isUpdating,
    model,
    temp,
    tempVal,
    tempColor,
    memPercent,
    diskPercent,
    hdmiStatus,
    hdmiColor,
    resolution,
    playingTitle,
    playingType,
    assignedPlaylist
  };
}

// --- RENDER SCREENS & UNPAIRED BANNER ---
function renderScreens() {
  const unpairedDiv = document.getElementById('unpaired-container');
  const grid = document.getElementById('screens-grid');
  if (!grid) return;
  const search = (document.getElementById('screens-search')?.value || '').toLowerCase().trim();

  const unpaired = state.screens.filter(s => !s.is_paired);
  const paired = state.screens.filter(s => s.is_paired);

  // Render Unpaired Callout Banner
  if (unpairedDiv) {
    if (unpaired.length > 0) {
      unpairedDiv.innerHTML = unpaired.map(s => {
        let sysInfoObj = {};
        try { sysInfoObj = JSON.parse(s.system_info || '{}'); } catch(e){}
        const model = sysInfoObj.model || 'Raspberry Pi Terminal';
        return `
          <div class="unpaired-alert-banner d-flex align-items-center justify-content-between p-3 rounded-3 mb-3 flex-wrap gap-3" role="alert">
            <div class="d-flex align-items-center gap-3">
              <span class="avatar avatar-md banner-icon rounded-3 flex-shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none">
                  <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                  <path d="M12 9v2m0 4v.01" />
                  <path d="M5 19h14a2 2 0 0 0 1.84 -2.75l-7.1 -12.25a2 2 0 0 0 -3.5 0l-7.1 12.25a2 2 0 0 0 1.75 2.75" />
                </svg>
              </span>
              <div>
                <h4 class="banner-title mb-1 fw-bold">New Display Pending Approval &bull; ${escapeHtml(model)}</h4>
                <div class="banner-sub small">IP: ${s.ip_address || 'Unknown'} &bull; Discovered ${formatRelativeTime(s.last_seen)}</div>
              </div>
            </div>
            <div class="d-flex align-items-center gap-2 flex-wrap">
              <div>
                <div class="pairing-code-badge">${s.pairing_code || '------'}</div>
              </div>
              <button class="btn btn-approve px-3 d-inline-flex align-items-center gap-1" onclick="quickPairModal('${s.id}', '${s.pairing_code}')">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="18" height="18" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" fill="none">
                  <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                  <path d="M5 12l5 5l10 -10" />
                </svg>
                Approve &amp; Name Screen
              </button>
              <button class="btn btn-dismiss px-3" title="Dismiss pairing request" onclick="confirmDeleteScreenById('${s.id}')">
                Dismiss
              </button>
            </div>
          </div>
        `;
      }).join('');
    } else {
      unpairedDiv.innerHTML = '';
    }
  }

  // Filter Paired Screens
  const filtered = paired.filter(s =>
    (s.name || '').toLowerCase().includes(search) ||
    (s.ip_address || '').toLowerCase().includes(search)
  );

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="col-12">
        <div class="card border-dashed p-5 text-center">
          <div class="text-secondary mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="48" height="48" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" fill="none">
              <rect x="2" y="3" width="20" height="14" rx="2"></rect>
              <line x1="8" y1="21" x2="16" y2="21"></line>
              <line x1="12" y1="17" x2="12" y2="21"></line>
            </svg>
          </div>
          <h3 class="fw-bold mb-1">No paired display terminals found</h3>
          <p class="text-secondary small mb-3">Power on your Raspberry Pi player at outlet, or pair a terminal using its pairing code.</p>
          <div>
            <button class="btn btn-primary btn-sm" onclick="openManualPairModal()">Pair Display by Code</button>
          </div>
        </div>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(s => {
    const m = parseScreenMetrics(s);
    const displayIp = (m.sys && m.sys.local_ip && !m.sys.local_ip.includes(':')) ? m.sys.local_ip : (s.ip_address || '127.0.0.1');

    let versionBadge = `<span class="badge bg-secondary-lt font-monospace flex-shrink-0" title="Versi Player">v${escapeHtml(m.appVersion)}</span>`;
    if (m.isUpdating) {
      versionBadge = `<span class="badge bg-warning-lt text-warning font-monospace cursor-pointer flex-shrink-0" onclick="openUpdateScreenModalById('${s.id}')" title="Status: ${escapeHtml(m.updateStatus)}"><span class="spinner-border spinner-border-sm me-1"></span> ${escapeHtml(m.updateStatus)}</span>`;
    } else if (m.isOutdated) {
      versionBadge = `<a href="#" class="badge bg-yellow-lt text-warning font-monospace text-decoration-none d-inline-flex align-items-center gap-1 flex-shrink-0" title="Pembaruan OTA v${escapeHtml(m.targetVersion)} tersedia" onclick="event.preventDefault(); openUpdateScreenModalById('${s.id}')"><svg xmlns="http://www.w3.org/2000/svg" class="icon icon-inline m-0" width="11" height="11" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2"/><path d="M7 11l5 5l5 -5"/><path d="M12 4l0 12"/></svg>v${escapeHtml(m.appVersion)} <span class="badge bg-warning text-dark px-1 py-0" style="font-size:0.62rem; font-weight:700;">Upd</span></a>`;
    } else {
      versionBadge = `<span class="badge bg-success-lt font-monospace flex-shrink-0" title="Versi terbaru">v${escapeHtml(m.appVersion)}</span>`;
    }

    return `
      <div class="col-md-6 col-xl-4">
        <div class="card h-100 shadow-sm screen-player-card">
          <!-- CARD HEADER -->
          <div class="card-header d-flex align-items-center justify-content-between py-2 px-3 gap-2">
            <div class="d-flex align-items-center gap-2 min-w-0 flex-grow-1" style="overflow: hidden;">
              <span class="status-dot status-dot-animated flex-shrink-0 ${m.online ? 'status-green status-dot-pulse' : 'status-red status-dot-pulse-red'}" title="${m.online ? 'Online' : 'Offline / Mati'}"></span>
              <div class="min-w-0 flex-grow-1" style="overflow: hidden;">
                <h3 class="card-title fw-bold mb-0 text-truncate" style="max-width: 140px;" title="${escapeHtml(s.name || s.id)}">${escapeHtml(s.name || s.id)}</h3>
                <div class="text-secondary small font-monospace text-truncate" style="max-width: 140px; font-size: 0.72rem;" title="${escapeHtml(displayIp)}">${escapeHtml(displayIp)}</div>
              </div>
            </div>
            <div class="d-flex align-items-center gap-1 flex-shrink-0">
              ${versionBadge}
              <div class="dropdown position-relative">
                <button class="btn btn-icon btn-ghost-secondary rounded-circle" type="button" onclick="toggleScreenDropdown(event)" aria-label="Screen options">
                  <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="20" height="20" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none">
                    <circle cx="12" cy="12" r="1"></circle>
                    <circle cx="12" cy="19" r="1"></circle>
                    <circle cx="12" cy="5" r="1"></circle>
                  </svg>
                </button>
                <div class="dropdown-menu dropdown-menu-end shadow-sm">
                  <a class="dropdown-item text-primary fw-medium" href="#" onclick="openScreenSettingsModalById('${s.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon dropdown-item-icon text-primary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><circle cx="12" cy="12" r="9"></circle><path d="M12 8v4l3 3"></path></svg>
                    Display Settings (Volume, Rotasi)
                  </a>
                  <a class="dropdown-item ${m.isOutdated ? 'text-warning fw-bold' : ''}" href="#" onclick="openUpdateScreenModalById('${s.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon dropdown-item-icon ${m.isOutdated ? 'text-warning' : 'text-secondary'}" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2" /><path d="M7 11l5 5l5 -5" /><path d="M12 4l0 12" /></svg>
                    Pembaruan Software (OTA)
                  </a>
                  <a class="dropdown-item" href="#" onclick="openScreenDetailsModalById('${s.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon dropdown-item-icon text-secondary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><rect x="3" y="4" width="18" height="12" rx="1"></rect><line x1="7" y1="20" x2="17" y2="20"></line><line x1="9" y1="16" x2="9" y2="20"></line><line x1="15" y1="16" x2="15" y2="20"></line><path d="M7 10h2l2 3l2 -6l1 3h3"></path></svg>
                    Device Diagnostics & Info
                  </a>
                  <a class="dropdown-item text-primary" href="#" onclick="restartScreenById('${s.id}', '${escapeHtml(s.name || s.id)}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon dropdown-item-icon text-primary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4" /><path d="M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4" /></svg>
                    Restart Player
                  </a>
                  <a class="dropdown-item" href="#" onclick="pingScreenById('${s.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon dropdown-item-icon text-info" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path d="M3 12h4l3 8l4 -16l3 8h4"></path></svg>
                    Ping & Test Connection
                  </a>
                  <a class="dropdown-item" href="#" onclick="openChangePlaylistModalById('${s.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon dropdown-item-icon text-purple" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><circle cx="14" cy="17" r="3"></circle><path d="M17 17v-10h4"></path><path d="M13 5h-10"></path><path d="M9 9h-6"></path><path d="M7 13h-4"></path></svg>
                    Assign / Change Playlist
                  </a>
                  <a class="dropdown-item" href="#" onclick="openRenameModalById('${s.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon dropdown-item-icon text-secondary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path d="M4 20h4l10.5 -10.5a1.5 1.5 0 0 0 -5 -5l-10.5 10.5v4"></path></svg>
                    Rename Display
                  </a>
                  <div class="dropdown-divider"></div>
                  <a class="dropdown-item text-warning" href="#" onclick="confirmUnpairScreenById('${s.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon dropdown-item-icon text-warning" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path d="M17 7l-10 10"></path><path d="M8 7l4 -4a3.5 3.5 0 0 1 5 5l-1.5 1.5"></path><path d="M16 17l-4 4a3.5 3.5 0 0 1 -5 -5l1.5 -1.5"></path></svg>
                    Unpair Screen (Re-pair)
                  </a>
                  <a class="dropdown-item text-danger" href="#" onclick="confirmDeleteScreenById('${s.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon dropdown-item-icon text-danger" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><line x1="4" y1="7" x2="20" y2="7"></line><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line><path d="M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12"></path><path d="M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3"></path></svg>
                    Remove Display
                  </a>
                </div>
              </div>
            </div>
          </div>

          <!-- CARD BODY -->
          <div class="card-body p-3 d-flex flex-column gap-2">
            <!-- Hardware & Display Info Strip -->
            <div class="d-flex align-items-center justify-content-between p-2 rounded-2 bg-body-tertiary border small">
              <div class="d-flex align-items-center gap-2 text-truncate me-2" title="${escapeHtml(m.model)}">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-inline text-secondary flex-shrink-0" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><rect x="3" y="4" width="18" height="12" rx="1"></rect><line x1="7" y1="20" x2="17" y2="20"></line><line x1="9" y1="16" x2="9" y2="20"></line><line x1="15" y1="16" x2="15" y2="20"></line></svg>
                <span class="text-secondary text-truncate fw-medium" style="font-size: 0.78rem;">${escapeHtml(m.model)}</span>
              </div>
              <div class="d-flex align-items-center gap-1 flex-shrink-0">
                <span class="badge bg-${m.hdmiColor}-lt text-uppercase font-monospace" style="font-size: 0.7rem;">HDMI ${m.hdmiStatus}</span>
                <span class="badge ${m.settings.screen_power === 'on' ? 'bg-success-lt' : 'bg-secondary-lt'} text-uppercase font-monospace" style="font-size: 0.7rem;">
                  ${m.settings.screen_power === 'on' ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>

            <!-- Now Playing Widget -->
            <div class="now-playing-card is-${m.playingType === 'video' ? 'video' : (m.playingType === 'image' ? 'image' : 'idle')}">
              <div class="d-flex align-items-center justify-content-between mb-1.5">
                <div class="d-flex align-items-center gap-2">
                  ${m.online && m.playingTitle !== 'Standby / Idle Loop' ? `
                    <span class="equalizer-anim" title="Aktif Diputar">
                      <span class="equalizer-bar" style="background-color: var(--tblr-${m.playingType === 'video' ? 'danger' : 'primary'});"></span>
                      <span class="equalizer-bar" style="background-color: var(--tblr-${m.playingType === 'video' ? 'danger' : 'primary'});"></span>
                      <span class="equalizer-bar" style="background-color: var(--tblr-${m.playingType === 'video' ? 'danger' : 'primary'});"></span>
                    </span>
                  ` : `
                    <span class="status-dot ${m.online ? 'status-blue' : 'status-secondary'}"></span>
                  `}
                  <span class="text-uppercase fw-bold text-secondary tracking-wider" style="font-size: 0.7rem; letter-spacing: 0.05em;">Sedang Diputar</span>
                </div>
                <span class="badge bg-${m.playingType === 'video' ? 'danger' : (m.playingType === 'image' ? 'info' : 'secondary')}-lt text-uppercase font-monospace" style="font-size: 0.7rem;">
                  ${m.playingType}
                </span>
              </div>

              <div class="min-w-0">
                <div class="fw-bold text-truncate text-body mb-1" style="font-size: 0.875rem;" title="${escapeHtml(m.playingTitle)}">
                  ${escapeHtml(m.playingTitle)}
                </div>
                <div class="text-secondary small d-flex align-items-center gap-2 font-monospace" style="font-size: 0.72rem;">
                  <span>${m.resolution}</span>
                  <span>&bull;</span>
                  <span>${formatRelativeTime(s.last_seen)}</span>
                </div>
              </div>
            </div>

            <!-- 3-Column Compact Telemetry Widget -->
            <div class="row g-2 text-center">
              <div class="col-4">
                <div class="mini-telemetry-card h-100 d-flex flex-column justify-content-between">
                  <div class="mini-telemetry-label">CPU Temp</div>
                  <div class="mini-telemetry-val text-${m.tempColor}">${m.temp}</div>
                  <div class="progress progress-xs">
                    <div class="progress-bar bg-${m.tempColor}" style="width: ${Math.min(m.tempVal, 100)}%"></div>
                  </div>
                </div>
              </div>
              <div class="col-4">
                <div class="mini-telemetry-card h-100 d-flex flex-column justify-content-between">
                  <div class="mini-telemetry-label">RAM</div>
                  <div class="mini-telemetry-val text-primary">${m.memPercent}%</div>
                  <div class="progress progress-xs">
                    <div class="progress-bar bg-primary" style="width: ${m.memPercent}%"></div>
                  </div>
                </div>
              </div>
              <div class="col-4">
                <div class="mini-telemetry-card h-100 d-flex flex-column justify-content-between">
                  <div class="mini-telemetry-label">Storage</div>
                  <div class="mini-telemetry-val text-azure">${m.diskPercent}%</div>
                  <div class="progress progress-xs">
                    <div class="progress-bar bg-azure" style="width: ${m.diskPercent}%"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- FOOTER: ASSIGNED PLAYLIST -->
          <div class="card-footer bg-transparent border-top p-3 mt-auto">
            <div class="d-flex align-items-center justify-content-between mb-1">
              <label class="form-label small fw-semibold text-secondary mb-0">Assigned Playlist</label>
              ${m.assignedPlaylist ? `<span class="badge bg-purple-lt small">${m.assignedPlaylist.items ? m.assignedPlaylist.items.length : 0} item</span>` : '<span class="badge bg-secondary-lt small">Kosong</span>'}
            </div>
            <div class="input-group input-group-sm">
              <select class="form-select form-select-sm" id="select-pl-${s.id}">
                <option value="">-- Tidak Ada Playlist --</option>
                ${state.playlists.map(p => `
                  <option value="${p.id}" ${s.playlist_id === p.id ? 'selected' : ''}>${escapeHtml(p.name)} (${p.items ? p.items.length : 0} item)</option>
                `).join('')}
              </select>
              <button class="btn btn-sm btn-primary" onclick="assignPlaylist('${s.id}', document.getElementById('select-pl-${s.id}').value, '${escapeHtml(s.name || s.id)}')">
                Simpan
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// --- DROPDOWN TOGGLE FOR DYNAMIC CONTENT ---
function toggleScreenDropdown(event) {
  event.preventDefault();
  event.stopPropagation();
  const btn = event.currentTarget;
  const container = btn.closest('.dropdown');
  const menu = container ? container.querySelector('.dropdown-menu') : null;
  if (!menu) return;

  const wasOpen = menu.classList.contains('show');

  // Close all other open dropdowns first
  document.querySelectorAll('.dropdown-menu.show').forEach(m => {
    m.classList.remove('show');
  });

  if (!wasOpen) {
    menu.classList.add('show');
    menu.style.position = 'absolute';
    menu.style.top = '100%';
    menu.style.right = '0';
    menu.style.left = 'auto';
    menu.style.zIndex = '1060';
  }
}

// Close dropdowns when clicking outside or clicking any dropdown item
document.addEventListener('click', function(e) {
  if (!e.target.closest('.dropdown') || e.target.closest('.dropdown-item')) {
    document.querySelectorAll('.dropdown-menu.show').forEach(m => m.classList.remove('show'));
  }
});

// Close dropdown on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.dropdown-menu.show').forEach(m => m.classList.remove('show'));
  }
});

// --- SCREEN MODALS & ACTIONS ---

// Modal: Quick Pair
function quickPairModal(screenId, pairingCode) {
  openModal(`
    <div class="modal-header">
      <h5 class="modal-title fw-bold">Pair New Screen Terminal</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <div class="mb-3 text-center">
        <span class="text-secondary small d-block mb-1">Terminal Pairing Code</span>
        <div class="pairing-code-badge d-inline-block">${pairingCode || '------'}</div>
      </div>
      <div class="mb-3">
        <label class="form-label required">Display Name / Outlet Location</label>
        <input type="text" id="modal-pair-name" class="form-control" placeholder="e.g., Outlet Jakarta - Main Lobby TV" autofocus>
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-primary" onclick="submitQuickPair('${screenId}')">Approve & Connect Display</button>
    </div>
  `);
}

async function submitQuickPair(screenId) {
  const name = document.getElementById('modal-pair-name')?.value.trim();
  const res = await api(`/api/screens/${screenId}/pair`, {
    method: 'POST',
    body: { name: name || undefined }
  });
  if (res && res.success) {
    closeModal();
    showToast('Layar berhasil disetujui dan terhubung', 'success');
    fetchScreens();
  }
}

// Modal: Manual Pair by Code
function openManualPairModal() {
  openModal(`
    <div class="modal-header">
      <h5 class="modal-title fw-bold">Pair Display by Code</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <p class="text-secondary small mb-3">
        Enter the 6-character pairing code currently shown on your Raspberry Pi television screen.
      </p>
      <div class="mb-3">
        <label class="form-label required">6-Digit Pairing Code</label>
        <input type="text" id="manual-pair-code" class="form-control form-control-lg text-uppercase fw-bold text-center letter-spacing-2" maxlength="6" placeholder="e.g. 7A8B9C">
      </div>
      <div class="mb-3">
        <label class="form-label">Display Name / Outlet Location</label>
        <input type="text" id="manual-pair-name" class="form-control" placeholder="e.g. Outlet Surabaya - Cashier TV">
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-primary" onclick="submitManualPair()">Verify & Connect</button>
    </div>
  `);
}

async function submitManualPair() {
  const code = document.getElementById('manual-pair-code')?.value.trim().toUpperCase();
  const name = document.getElementById('manual-pair-name')?.value.trim();
  if (!code || code.length < 4) {
    showToast('Masukkan kode pairing yang valid', 'warning');
    return;
  }
  const match = state.screens.find(s => s.pairing_code && s.pairing_code.toUpperCase() === code);
  if (!match) {
    showToast('Tidak ditemukan layar dengan kode: ' + code, 'danger');
    return;
  }
  const res = await api(`/api/screens/${match.id}/pair`, {
    method: 'POST',
    body: { name: name || undefined }
  });
  if (res && res.success) {
    closeModal();
    showToast('Layar berhasil dipasangkan', 'success');
    fetchScreens();
  }
}

// Modal: Rename Screen
function openRenameModalById(screenId) {
  const s = state.screens.find(x => x.id === screenId);
  if (!s) return;
  openRenameModal(s.id, s.name || s.id);
}

function openRenameModal(screenId, currentName) {
  openModal(`
    <div class="modal-header">
      <h5 class="modal-title fw-bold">Rename Display Terminal</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <div class="mb-3">
        <label class="form-label required">Display Name</label>
        <input type="text" id="modal-rename-val" class="form-control" value="${escapeHtml(currentName)}">
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-primary" onclick="submitRenameScreen('${screenId}')">Save Changes</button>
    </div>
  `);
}

async function submitRenameScreen(screenId) {
  const name = document.getElementById('modal-rename-val')?.value.trim();
  if (!name) return;
  await api(`/api/screens/${screenId}`, { method: 'PATCH', body: { name } });
  closeModal();
  showToast('Nama layar berhasil diubah', 'success');
  fetchScreens();
}

// Modal: Delete Screen
function confirmDeleteScreenById(screenId) {
  const s = state.screens.find(x => x.id === screenId);
  if (!s) return;
  confirmDeleteScreen(s.id, s.name || s.id);
}

function confirmDeleteScreen(screenId, screenName) {
  openModal(`
    <div class="modal-header">
      <h5 class="modal-title text-danger fw-bold">Remove Display Terminal</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <p class="text-secondary mb-0">
        Are you sure you want to remove <strong>${escapeHtml(screenName)}</strong>? The Raspberry Pi will return to unpaired mode and need a new pairing code to reconnect.
      </p>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-danger" onclick="submitDeleteScreen('${screenId}')">Remove Screen</button>
    </div>
  `);
}

async function submitDeleteScreen(screenId) {
  await api(`/api/screens/${screenId}`, { method: 'DELETE' });
  closeModal();
  showToast('Layar berhasil dihapus dari sistem', 'info');
  fetchScreens();
}

// Assign Playlist
async function assignPlaylist(screenId, playlistId, screenName = '') {
  const res = await api(`/api/screens/${screenId}`, {
    method: 'PATCH',
    body: { playlist_id: playlistId || null }
  });
  if (res && res.success) {
    const targetName = screenName ? ` untuk "${screenName}"` : '';
    showToast(`Playlist berhasil disimpan${targetName}`, 'success');
    fetchScreens();
  } else {
    showToast(res ? res.error : 'Gagal menyimpan playlist', 'danger');
  }
}

// Skip Screen Current Media
async function skipScreenMedia(screenId, screenName = '') {
  const btn = document.getElementById(`btn-skip-${screenId}`);
  let originalHtml = '';
  if (btn) {
    originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status"></span> Skip...`;
  }

  try {
    const res = await api(`/api/screens/${screenId}/skip`, { method: 'POST' });
    if (res && res.success) {
      showToast(res.message || `Perintah Skip berhasil dikirim ke ${screenName || 'player'}.`, 'success');
      setTimeout(fetchScreens, 1500);
    } else {
      showToast(res ? res.error : 'Gagal mengirim perintah Skip', 'danger');
    }
  } catch (err) {
    showToast('Koneksi ke server gagal', 'danger');
  } finally {
    if (btn) {
      btn.innerHTML = originalHtml;
      btn.disabled = false;
    }
  }
}

// Modal: Screen Details / Diagnostics
function openScreenDetailsModalById(screenId) {
  const s = state.screens.find(x => x.id === screenId);
  if (!s) return;
  const m = parseScreenMetrics(s);
  const displayIp = (m.sys && m.sys.local_ip && !m.sys.local_ip.includes(':')) ? m.sys.local_ip : (s.ip_address || '127.0.0.1');

  openModal(`
    <div class="modal-header">
      <div>
        <div class="d-flex align-items-center gap-2">
          <h5 class="modal-title fw-bold mb-0">${escapeHtml(s.name || s.id)}</h5>
          <span class="badge bg-${m.online ? 'success' : 'danger'}-lt text-uppercase">${m.online ? 'ONLINE' : 'OFFLINE'}</span>
        </div>
        <div class="text-secondary small mt-1">Terminal Hardware Diagnostics & Status Report</div>
      </div>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <!-- Network & Device Identity -->
      <div class="row g-3 mb-3">
        <div class="col-sm-6">
          <div class="card card-sm bg-body-tertiary border">
            <div class="card-body p-3">
              <div class="text-secondary small fw-bold text-uppercase mb-1">Device Hardware ID</div>
              <div class="d-flex align-items-center justify-content-between gap-2">
                <code class="fw-bold fs-5 text-body text-truncate d-block flex-grow-1 min-w-0" title="${escapeHtml(s.id)}">${escapeHtml(s.id)}</code>
                <button class="btn btn-sm btn-icon btn-ghost-secondary flex-shrink-0" title="Copy Hardware ID" onclick="copyToClipboard('${escapeHtml(s.id)}')">
                  <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><rect x="8" y="8" width="12" height="12" rx="2"></rect><path d="M16 8v-2a2 2 0 0 0 -2 -2h-8a2 2 0 0 0 -2 2v8a2 2 0 0 0 2 2h2"></path></svg>
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="col-sm-6">
          <div class="card card-sm bg-body-tertiary border">
            <div class="card-body p-3">
              <div class="text-secondary small fw-bold text-uppercase mb-1">Terminal IP Address</div>
              <div class="d-flex align-items-center justify-content-between gap-2">
                <div class="min-w-0 flex-grow-1" style="overflow: hidden;">
                  <span class="fw-bold fs-5 text-body font-monospace text-truncate d-block" title="${escapeHtml(displayIp)}" style="letter-spacing: -0.3px;">${escapeHtml(displayIp)}</span>
                  ${(s.ip_address && s.ip_address !== displayIp) ? `<div class="text-secondary small font-monospace text-truncate" style="font-size: 0.72rem;" title="IPv6: ${escapeHtml(s.ip_address)}">IPv6: ${escapeHtml(s.ip_address)}</div>` : ''}
                </div>
                <div class="d-flex gap-1 flex-shrink-0">
                  <button class="btn btn-sm btn-icon btn-ghost-secondary" title="Copy IP" onclick="copyToClipboard('${escapeHtml(displayIp)}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><rect x="8" y="8" width="12" height="12" rx="2"></rect><path d="M16 8v-2a2 2 0 0 0 -2 -2h-8a2 2 0 0 0 -2 2v8a2 2 0 0 0 2 2h2"></path></svg>
                  </button>
                  <button class="btn btn-sm btn-outline-info" onclick="pingScreenById('${s.id}')">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="14" height="14" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path d="M3 12h4l3 8l4 -16l3 8h4"></path></svg>
                    Ping
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Hardware Model & Display Resolution -->
      <div class="card border mb-3">
        <div class="card-header py-2 bg-body-tertiary">
          <div class="card-title fs-5 fw-bold mb-0">Hardware & Video Output</div>
        </div>
        <div class="card-body p-3">
          <div class="row g-3">
            <div class="col-sm-6">
              <div class="text-secondary small">Hardware Model</div>
              <div class="fw-medium text-body">${escapeHtml(m.model)}</div>
            </div>
            <div class="col-sm-3">
              <div class="text-secondary small">Display Resolution</div>
              <div class="fw-medium text-body">${m.resolution}</div>
            </div>
            <div class="col-sm-3">
              <div class="text-secondary small">HDMI Output</div>
              <span class="badge bg-${m.hdmiColor}-lt text-uppercase">HDMI ${m.hdmiStatus}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Realtime Telemetry -->
      <div class="card border mb-3">
        <div class="card-header py-2 bg-body-tertiary">
          <div class="card-title fs-5 fw-bold mb-0">System Telemetry & Resource Health</div>
        </div>
        <div class="card-body p-3">
          <!-- CPU Temp -->
          <div class="mb-3">
            <div class="d-flex justify-content-between small mb-1">
              <span class="text-secondary fw-medium">CPU Core Temperature</span>
              <span class="badge bg-${m.tempColor}-lt fw-bold">${m.temp}</span>
            </div>
            <div class="progress progress-sm">
              <div class="progress-bar bg-${m.tempColor}" style="width: ${Math.min(m.tempVal, 100)}%"></div>
            </div>
          </div>
          <!-- RAM -->
          <div class="mb-3">
            <div class="d-flex justify-content-between small mb-1">
              <span class="text-secondary fw-medium">RAM Memory Utilization</span>
              <span class="fw-bold text-body">${m.sys.mem ? `${m.sys.mem.used_mb}MB / ${m.sys.mem.total_mb}MB (${m.memPercent}%)` : '--'}</span>
            </div>
            <div class="progress progress-sm">
              <div class="progress-bar bg-primary" style="width: ${m.memPercent}%"></div>
            </div>
          </div>
          <!-- Storage -->
          <div>
            <div class="d-flex justify-content-between small mb-1">
              <span class="text-secondary fw-medium">MicroSD Disk Storage</span>
              <span class="fw-bold text-body">${m.sys.disk ? `${m.sys.disk.used_gb}GB / ${m.sys.disk.total_gb}GB (${m.diskPercent}%)` : '--'}</span>
            </div>
            <div class="progress progress-sm">
              <div class="progress-bar bg-azure" style="width: ${m.diskPercent}%"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Playback & Sync Information -->
      <div class="card border">
        <div class="card-header py-2 bg-body-tertiary d-flex justify-content-between align-items-center">
          <div class="card-title fs-5 fw-bold mb-0">Playback & Sync State</div>
          <button class="btn btn-sm btn-outline-purple" onclick="closeModal(); openChangePlaylistModalById('${s.id}')">
            Change Playlist
          </button>
        </div>
        <div class="card-body p-3">
          <div class="row g-3">
            <div class="col-sm-6">
              <div class="text-secondary small">Assigned Playlist</div>
              <div class="fw-bold text-purple">${escapeHtml(m.assignedPlaylist?.name || 'No Playlist (Standby)')}</div>
            </div>
            <div class="col-sm-6">
              <div class="text-secondary small">Last Heartbeat Seen</div>
              <div class="fw-medium">${s.last_seen ? `${formatRelativeTime(s.last_seen)} (${format24Time(s.last_seen)})` : 'Never'}</div>
            </div>
            <div class="col-12">
              <div class="text-secondary small">Currently Playing Asset</div>
              <div class="p-2 rounded bg-body-tertiary border d-flex align-items-center gap-2 mt-1">
                <span class="badge bg-${m.playingType === 'video' ? 'danger' : 'info'}-lt text-uppercase">${m.playingType}</span>
                <span class="fw-medium text-truncate">${escapeHtml(m.playingTitle)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Hardware Settings & Software Version -->
      <div class="card border mt-3">
        <div class="card-header py-2 bg-body-tertiary d-flex justify-content-between align-items-center">
          <div class="card-title fs-5 fw-bold mb-0">Display Settings & Software Version</div>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-primary" onclick="closeModal(); openScreenSettingsModalById('${s.id}')">
              Edit Settings
            </button>
            <button class="btn btn-sm ${m.isOutdated ? 'btn-warning' : 'btn-outline-secondary'}" onclick="closeModal(); openUpdateScreenModalById('${s.id}')">
              ${m.isOutdated ? 'Update OTA Available' : 'OTA Details'}
            </button>
          </div>
        </div>
        <div class="card-body p-3">
          <div class="row g-3">
            <div class="col-sm-3">
              <div class="text-secondary small mb-1">Audio Volume</div>
              <div><span class="badge ${m.settings.volume === 0 ? 'bg-secondary-lt border border-secondary-subtle text-secondary' : 'bg-blue-lt border border-blue-subtle text-primary'} font-monospace fw-bold fs-5 px-2.5 py-1">${m.settings.volume}%</span></div>
            </div>
            <div class="col-sm-3">
              <div class="text-secondary small mb-1">Screen Rotation</div>
              <div><span class="badge bg-secondary-lt border border-secondary-subtle text-secondary font-monospace fw-bold fs-5 px-2.5 py-1 text-uppercase">${escapeHtml(m.settings.rotation)}</span></div>
            </div>
            <div class="col-sm-3">
              <div class="text-secondary small mb-1">Polling Interval</div>
              <div><span class="badge bg-secondary-lt border border-secondary-subtle text-secondary font-monospace fw-bold fs-5 px-2.5 py-1">${m.settings.heartbeat_interval || 10}s</span></div>
            </div>
            <div class="col-sm-3">
              <div class="text-secondary small mb-1">Software Version</div>
              <div><span class="badge ${m.isOutdated ? 'bg-warning-lt border border-warning-subtle text-warning' : 'bg-success-lt border border-success-subtle text-success'} font-monospace fw-bold fs-5 px-2.5 py-1">v${escapeHtml(m.appVersion)}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="modal-footer d-flex justify-content-between">
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-outline-primary d-flex align-items-center gap-1" onclick="closeModal(); restartScreenById('${s.id}', '${escapeHtml(s.name || s.id)}')">
          <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-inline" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4" /><path d="M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4" /></svg>
          Restart Player
        </button>
        <button class="btn btn-sm btn-outline-secondary" onclick="closeModal(); openRenameModalById('${s.id}')">Rename</button>
        <button class="btn btn-sm btn-outline-warning" onclick="closeModal(); confirmUnpairScreenById('${s.id}')">Unpair Screen</button>
      </div>
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Close</button>
    </div>
  `, 'modal-lg');
}

// Modal: Change Playlist Assignment
function openChangePlaylistModalById(screenId) {
  const s = state.screens.find(x => x.id === screenId);
  if (!s) return;

  openModal(`
    <div class="modal-header">
      <h5 class="modal-title fw-bold">Assign Playlist Loop</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <div class="mb-3">
        <label class="form-label text-secondary small mb-1">Target Display Terminal</label>
        <div class="fw-bold fs-4">${escapeHtml(s.name || s.id)} <span class="text-secondary small font-monospace">(${s.ip_address || '127.0.0.1'})</span></div>
      </div>
      <div class="mb-3">
        <label class="form-label required">Select Playlist Loop</label>
        <select id="modal-select-playlist" class="form-select">
          <option value="" ${!s.playlist_id ? 'selected' : ''}>-- Standby Screen (No Playlist) --</option>
          ${state.playlists.map(p => `
            <option value="${p.id}" ${s.playlist_id === p.id ? 'selected' : ''}>
              ${escapeHtml(p.name)} (${(p.items || []).length} assets, Version ${p.version || 1})
            </option>
          `).join('')}
        </select>
        <div class="form-text">Changing the playlist will take effect on the Raspberry Pi on its next poll cycle (within 10s).</div>
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-purple text-white" onclick="submitChangePlaylist('${s.id}')">Save Assignment</button>
    </div>
  `);
}

async function submitChangePlaylist(screenId) {
  const plId = document.getElementById('modal-select-playlist')?.value;
  await assignPlaylist(screenId, plId);
  closeModal();
}

// Action: Ping Screen
async function pingScreenById(screenId) {
  const s = state.screens.find(x => x.id === screenId);
  const name = s ? (s.name || s.id) : screenId;
  showToast(`Menguji koneksi ke "${name}"...`, 'info');
  const res = await api(`/api/screens/${screenId}/ping`, { method: 'POST' });
  if (res && res.success) {
    if (res.is_online) {
      const pingText = res.latency_ms ? ` • Ping ${res.latency_ms}ms` : '';
      const heartbeatText = res.last_seen_seconds != null ? ` • Terlihat ${res.last_seen_seconds}d lalu` : '';
      showToast(`Layar "${name}" (${res.ip}) ONLINE${pingText}${heartbeatText}`, 'success');
    } else {
      const lastSeenText = res.last_seen_seconds != null ? ` • Terakhir terlihat ${Math.round(res.last_seen_seconds)}d lalu` : '';
      showToast(`Layar "${name}" (${res.ip}) OFFLINE${lastSeenText}`, 'warning');
    }
  } else {
    showToast(`Gagal menguji koneksi ke "${name}"`, 'danger');
  }
}

// Action: Restart / Reboot Screen Modal
function restartScreenById(screenId, screenName) {
  const s = state.screens.find(x => x.id === screenId);
  const name = screenName || (s ? (s.name || s.id) : screenId);

  openModal(`
    <div class="modal-header">
      <h5 class="modal-title fw-bold text-primary d-flex align-items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="22" height="22" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none">
          <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
          <path d="M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4" />
          <path d="M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4" />
        </svg>
        Restart Client Player
      </h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <p class="text-secondary mb-3">
        Pilih jenis restart untuk terminal display <strong>${escapeHtml(name)}</strong>:
      </p>
      <div class="list-group mb-3">
        <label class="list-group-item d-flex gap-3 align-items-center cursor-pointer">
          <input class="form-check-input flex-shrink-0" type="radio" name="restartType" value="restart" checked>
          <span>
            <strong class="d-block text-body">Restart Aplikasi Player (Direkomendasikan)</strong>
            <small class="text-secondary">Memuat ulang service player & antarmuka GUI secara instan tanpa reboot OS (~3-5 detik).</small>
          </span>
        </label>
        <label class="list-group-item d-flex gap-3 align-items-center cursor-pointer">
          <input class="form-check-input flex-shrink-0" type="radio" name="restartType" value="reboot">
          <span>
            <strong class="d-block text-body">Reboot Perangkat (Full Reboot Pi)</strong>
            <small class="text-secondary">Memulai ulang seluruh sistem operasi Raspberry Pi dari awal (~30-40 detik).</small>
          </span>
        </label>
      </div>
      <div class="alert alert-info py-2 px-3 small mb-0 d-flex align-items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-inline flex-shrink-0" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><circle cx="12" cy="12" r="9"></circle><line x1="12" y1="8" x2="12.01" y2="8"></line><polyline points="11 12 12 12 12 16 13 16"></polyline></svg>
        <span>Perintah akan dieksekusi otomatis oleh player pada siklus sinkronisasi berikutnya (&le; 5-10 detik).</span>
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Batal</button>
      <button type="button" class="btn btn-primary d-flex align-items-center gap-1" id="btn-submit-restart" onclick="submitRestartScreen('${screenId}')">
        <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none">
          <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
          <path d="M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4" />
          <path d="M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4" />
        </svg>
        Kirim Perintah Restart
      </button>
    </div>
  `);
}

async function submitRestartScreen(screenId) {
  const selected = document.querySelector('input[name="restartType"]:checked')?.value || 'restart';
  const btn = document.getElementById('btn-submit-restart');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Mengirim...';
  }
  try {
    const res = await api(`/api/screens/${screenId}/command`, {
      method: 'POST',
      body: { command: selected }
    });
    closeModal();
    if (res && res.success) {
      showToast(res.message || 'Perintah restart berhasil dikirim ke player', 'success');
      fetchScreens();
    } else {
      showToast(res ? res.error : 'Gagal mengirim perintah restart', 'danger');
    }
  } catch (err) {
    closeModal();
    showToast('Koneksi ke server gagal', 'danger');
  }
}

// Modal: Unpair Screen
function confirmUnpairScreenById(screenId) {
  const s = state.screens.find(x => x.id === screenId);
  if (!s) return;

  openModal(`
    <div class="modal-header">
      <h5 class="modal-title text-warning fw-bold">Unpair Display Terminal</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <p class="text-secondary mb-2">
        Are you sure you want to disconnect terminal <strong>${escapeHtml(s.name || s.id)}</strong> (${s.ip_address || '127.0.0.1'})?
      </p>
      <div class="alert alert-warning mb-0 small">
        <svg xmlns="http://www.w3.org/2000/svg" class="icon alert-icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path d="M12 9v4"></path><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z"></path><path d="M12 16h.01"></path></svg>
        The Raspberry Pi player will stop video playback and display a brand new 6-digit pairing code on the TV screen. You can pair it again at any time.
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-warning" onclick="submitUnpairScreen('${s.id}')">Unpair Terminal</button>
    </div>
  `);
}

async function submitUnpairScreen(screenId) {
  const res = await api(`/api/screens/${screenId}/unpair`, { method: 'POST' });
  closeModal();
  if (res && res.success) {
    showToast(`Layar diputuskan. Kode pairing baru: ${res.pairing_code}`, 'warning');
    fetchScreens();
  }
}

// --- MODAL: PER-DISPLAY HARDWARE SETTINGS ---
window.updateVolumeSliderDisplay = function(val) {
  const badge = document.getElementById('val-volume-display');
  const iconSpan = document.getElementById('volume-icon-indicator');
  if (!badge) return;
  const v = parseInt(val, 10);
  if (v === 0) {
    badge.className = 'badge bg-secondary-lt border border-secondary-subtle text-secondary font-monospace px-2.5 py-1 fw-bold';
    badge.textContent = '0% (Mute)';
    if (iconSpan) {
      iconSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="icon text-secondary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><line x1="16" y1="9" x2="22" y2="15" /><line x1="22" y1="9" x2="16" y2="15" /><path d="M6 15h-2a1 1 0 0 1 -1 -1v-4a1 1 0 0 1 1 -1h2l3.5 -4.5a.8 .8 0 0 1 1.5 .5v16a.8 .8 0 0 1 -1.5 .5l-3.5 -4.5" /></svg>`;
    }
  } else if (v < 50) {
    badge.className = 'badge bg-blue-lt border border-blue-subtle text-primary font-monospace px-2.5 py-1 fw-bold';
    badge.textContent = v + '%';
    if (iconSpan) {
      iconSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="icon text-primary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M15 8a5 5 0 0 1 0 8" /><path d="M6 15h-2a1 1 0 0 1 -1 -1v-4a1 1 0 0 1 1 -1h2l3.5 -4.5a.8 .8 0 0 1 1.5 .5v16a.8 .8 0 0 1 -1.5 .5l-3.5 -4.5" /></svg>`;
    }
  } else {
    badge.className = 'badge bg-blue-lt border border-blue-subtle text-primary font-monospace px-2.5 py-1 fw-bold';
    badge.textContent = v + '%';
    if (iconSpan) {
      iconSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="icon text-primary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M15 8a5 5 0 0 1 0 8" /><path d="M17.7 5a9 9 0 0 1 0 14" /><path d="M6 15h-2a1 1 0 0 1 -1 -1v-4a1 1 0 0 1 1 -1h2l3.5 -4.5a.8 .8 0 0 1 1.5 .5v16a.8 .8 0 0 1 -1.5 .5l-3.5 -4.5" /></svg>`;
    }
  }
};

function openScreenSettingsModalById(screenId) {
  const s = state.screens.find(x => x.id === screenId);
  if (!s) return;
  const m = parseScreenMetrics(s);

  openModal(`
    <div class="modal-header">
      <div>
        <h5 class="modal-title fw-bold mb-0">Pengaturan Display &bull; ${escapeHtml(s.name || s.id)}</h5>
        <div class="text-secondary small mt-1">Konfigurasi hardware individual untuk terminal ini (disinkronkan via heartbeat).</div>
      </div>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <!-- Volume Slider -->
      <div class="card bg-body-tertiary border mb-3">
        <div class="card-body p-3">
          <div class="d-flex align-items-center justify-content-between mb-2">
            <label class="form-label fw-bold mb-0 d-flex align-items-center gap-2">
              <span id="volume-icon-indicator" class="d-inline-flex align-items-center">
                ${m.settings.volume === 0
                  ? `<svg xmlns="http://www.w3.org/2000/svg" class="icon text-secondary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><line x1="16" y1="9" x2="22" y2="15" /><line x1="22" y1="9" x2="16" y2="15" /><path d="M6 15h-2a1 1 0 0 1 -1 -1v-4a1 1 0 0 1 1 -1h2l3.5 -4.5a.8 .8 0 0 1 1.5 .5v16a.8 .8 0 0 1 -1.5 .5l-3.5 -4.5" /></svg>`
                  : `<svg xmlns="http://www.w3.org/2000/svg" class="icon text-primary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M15 8a5 5 0 0 1 0 8" />${m.settings.volume > 50 ? '<path d="M17.7 5a9 9 0 0 1 0 14" />' : ''}<path d="M6 15h-2a1 1 0 0 1 -1 -1v-4a1 1 0 0 1 1 -1h2l3.5 -4.5a.8 .8 0 0 1 1.5 .5v16a.8 .8 0 0 1 -1.5 .5l-3.5 -4.5" /></svg>`
                }
              </span>
              Volume Audio Hardware (ALSA)
            </label>
            <span class="badge ${m.settings.volume === 0 ? 'bg-secondary-lt border border-secondary-subtle text-secondary' : 'bg-blue-lt border border-blue-subtle text-primary'} font-monospace px-2.5 py-1 fw-bold" style="font-size: 0.95rem; letter-spacing: 0.3px;" id="val-volume-display">${m.settings.volume === 0 ? '0% (Mute)' : m.settings.volume + '%'}</span>
          </div>
          <input type="range" class="form-range" id="input-volume" min="0" max="100" step="5" value="${m.settings.volume}" oninput="updateVolumeSliderDisplay(this.value)">
          <div class="d-flex justify-content-between text-secondary small mt-1" style="font-size: 0.78rem;">
            <span>0% (Mute)</span>
            <span>50%</span>
            <span>100% (Maksimal)</span>
          </div>
        </div>
      </div>

      <!-- Screen Orientation -->
      <div class="card bg-body-tertiary border mb-3">
        <div class="card-body p-3">
          <label class="form-label fw-bold mb-2 d-flex align-items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="icon text-primary" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><rect x="4" y="4" width="16" height="16" rx="2" /><line x1="8" y1="4" x2="8" y2="20" /></svg>
            Orientasi / Rotasi Layar Monitor
          </label>
          <div class="row g-2">
            <div class="col-6">
              <label class="form-selectgroup-item w-100">
                <input type="radio" name="input_rotation" value="normal" class="form-selectgroup-input" ${m.settings.rotation === 'normal' ? 'checked' : ''}>
                <div class="form-selectgroup-label text-start p-2">
                  <div class="fw-bold">Horizontal (0°)</div>
                  <div class="text-secondary small">Landscape standar TV</div>
                </div>
              </label>
            </div>
            <div class="col-6">
              <label class="form-selectgroup-item w-100">
                <input type="radio" name="input_rotation" value="right" class="form-selectgroup-input" ${m.settings.rotation === 'right' ? 'checked' : ''}>
                <div class="form-selectgroup-label text-start p-2">
                  <div class="fw-bold">Vertikal (90°)</div>
                  <div class="text-secondary small">Portrait Kanan / Standing</div>
                </div>
              </label>
            </div>
            <div class="col-6">
              <label class="form-selectgroup-item w-100">
                <input type="radio" name="input_rotation" value="inverted" class="form-selectgroup-input" ${m.settings.rotation === 'inverted' ? 'checked' : ''}>
                <div class="form-selectgroup-label text-start p-2">
                  <div class="fw-bold">Terbalik (180°)</div>
                  <div class="text-secondary small">Landscape Terbalik</div>
                </div>
              </label>
            </div>
            <div class="col-6">
              <label class="form-selectgroup-item w-100">
                <input type="radio" name="input_rotation" value="left" class="form-selectgroup-input" ${m.settings.rotation === 'left' ? 'checked' : ''}>
                <div class="form-selectgroup-label text-start p-2">
                  <div class="fw-bold">Vertikal Kiri (270°)</div>
                  <div class="text-secondary small">Portrait Kiri / Standing</div>
                </div>
              </label>
            </div>
          </div>
          <div class="form-text mt-2 small text-secondary">Rotasi dieksekusi secara instan via xrandr tanpa perlu me-reboot Raspberry Pi.</div>
        </div>
      </div>

      <!-- Heartbeat Interval & Power Mode -->
      <div class="row g-3 mb-2">
        <div class="col-sm-6">
          <div class="card bg-body-tertiary border h-100">
            <div class="card-body p-3">
              <label class="form-label fw-bold mb-1">Interval Polling Heartbeat</label>
              <div class="input-group">
                <input type="number" id="input-interval" class="form-control" min="5" max="120" value="${m.settings.heartbeat_interval || 10}">
                <span class="input-group-text">Detik</span>
              </div>
              <div class="form-text small text-secondary">Frekuensi telemetri ke server (default: 10 detik).</div>
            </div>
          </div>
        </div>
        <div class="col-sm-6">
          <div class="card bg-body-tertiary border h-100">
            <div class="card-body p-3">
              <label class="form-label fw-bold mb-1">Status Sinyal Layar (DPMS)</label>
              <select id="input-screen-power" class="form-select">
                <option value="on" ${m.settings.screen_power === 'on' ? 'selected' : ''}>Aktif (Display ON)</option>
                <option value="off" ${m.settings.screen_power === 'off' ? 'selected' : ''}>Standby / Layar Mati (DPMS OFF)</option>
              </select>
              <div class="form-text small text-secondary">Matikan sinyal display untuk hemat daya.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Batal</button>
      <button type="button" class="btn btn-primary" id="btn-save-settings" onclick="submitScreenSettings('${s.id}')">Simpan Pengaturan</button>
    </div>
  `, 'modal-lg');
}

async function submitScreenSettings(screenId) {
  const volume = parseInt(document.getElementById('input-volume')?.value || '100', 10);
  const rotation = document.querySelector('input[name="input_rotation"]:checked')?.value || 'normal';
  const heartbeat_interval = parseInt(document.getElementById('input-interval')?.value || '10', 10);
  const screen_power = document.getElementById('input-screen-power')?.value || 'on';

  const btn = document.getElementById('btn-save-settings');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Menyimpan...';
  }

  const res = await api(`/api/screens/${screenId}/settings`, {
    method: 'PATCH',
    body: { volume, rotation, heartbeat_interval, screen_power }
  });

  closeModal();
  if (res && res.success) {
    showToast(res.message || 'Pengaturan display berhasil disimpan.', 'success');
    fetchScreens();
  } else {
    showToast(res ? res.error : 'Gagal menyimpan pengaturan display', 'danger');
  }
}

// --- MODAL: OTA SOFTWARE UPDATE ---
function openUpdateScreenModalById(screenId) {
  const s = state.screens.find(x => x.id === screenId);
  if (!s) return;
  const m = parseScreenMetrics(s);
  const manifest = state.playerManifest || {};

  let logsHtml = '<div class="text-secondary small p-3 text-center">Belum ada riwayat update untuk display ini.</div>';
  try {
    const logs = typeof s.last_update_log === 'object' ? s.last_update_log : JSON.parse(s.last_update_log || '[]');
    if (logs && logs.length > 0) {
      logsHtml = `
        <div class="table-responsive">
          <table class="table table-vcenter card-table table-sm small mb-0">
            <thead>
              <tr class="text-secondary">
                <th style="width: 110px;">WAKTU</th>
                <th style="width: 120px;">TARGET VERSI</th>
                <th style="width: 120px;">STATUS</th>
                <th>DETAIL</th>
              </tr>
            </thead>
            <tbody>
              ${logs.map(l => {
                const sLower = String(l.status || '').toLowerCase();
                let badgeClass = 'bg-secondary-lt text-secondary';
                let statusText = (l.status || 'IDLE').toUpperCase();
                let spinner = '';

                if (sLower === 'success') {
                  badgeClass = 'bg-success-lt text-success fw-bold';
                  statusText = 'SUKSES';
                } else if (sLower === 'pending') {
                  badgeClass = 'bg-warning-lt text-warning fw-bold';
                  statusText = 'DIPROSES';
                } else if (sLower === 'downloading') {
                  badgeClass = 'bg-info-lt text-info fw-bold';
                  statusText = 'MENGUNDUH';
                  spinner = '<span class="spinner-border spinner-border-sm me-1"></span>';
                } else if (sLower === 'applying') {
                  badgeClass = 'bg-primary-lt text-primary fw-bold';
                  statusText = 'MEMASANG';
                  spinner = '<span class="spinner-border spinner-border-sm me-1"></span>';
                } else if (sLower === 'restarting') {
                  badgeClass = 'bg-secondary-lt text-secondary fw-bold';
                  statusText = 'RESTARTING';
                } else if (sLower.startsWith('failed')) {
                  badgeClass = 'bg-danger-lt text-danger fw-bold';
                  statusText = 'GAGAL';
                }

                let detailText = l.detail || '';
                if (!detailText) {
                  if (l.action === 'trigger_ota') detailText = 'Pembaruan dijadwalkan oleh admin';
                  else detailText = '-';
                }

                return `
                  <tr>
                    <td class="text-secondary text-nowrap">${formatRelativeTime(l.timestamp)}</td>
                    <td><span class="badge bg-secondary-lt font-monospace">v${escapeHtml(l.target_version || l.version || '-')}</span></td>
                    <td><span class="badge ${badgeClass}">${spinner}${escapeHtml(statusText)}</span></td>
                    <td class="text-body small text-truncate" style="max-width:280px;" title="${escapeHtml(detailText)}">${escapeHtml(detailText)}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      `;
    }
  } catch(e) {}

  openModal(`
    <div class="modal-header py-3">
      <div>
        <h5 class="modal-title fw-bold mb-0">Pembaruan Software (OTA) &bull; ${escapeHtml(s.name || s.id)}</h5>
        <div class="text-secondary small mt-1">Sistem pembaruan over-the-air aman dengan atomic symlink swap & rollback.</div>
      </div>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body p-3">
      <!-- Version Comparison Card -->
      <div class="row g-3 mb-3">
        <div class="col-sm-6">
          <div class="card bg-body-tertiary border text-center p-3 h-100 justify-content-center">
            <div class="text-secondary small text-uppercase fw-bold mb-1">Versi Player Saat Ini</div>
            <div class="fs-1 fw-bold text-body font-monospace">v${escapeHtml(m.appVersion)}</div>
            <div class="mt-2">
              <span class="badge ${m.online ? 'bg-success-lt text-success' : 'bg-danger-lt text-danger'}">${m.online ? 'ONLINE' : 'OFFLINE'}</span>
            </div>
          </div>
        </div>
        <div class="col-sm-6">
          <div class="card bg-body-tertiary border text-center p-3 h-100 justify-content-center">
            <div class="text-secondary small text-uppercase fw-bold mb-1">Versi Rilis Server</div>
            <div class="fs-1 fw-bold text-primary font-monospace">v${escapeHtml(m.targetVersion)}</div>
            <div class="mt-2">
              <span class="badge ${m.isOutdated ? 'bg-yellow-lt text-warning' : 'bg-success-lt text-success'}">${m.isOutdated ? 'UPDATE TERSEDIA' : 'VERSI TERBARU'}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Current Update Status Alert if updating -->
      ${m.isUpdating ? `
        <div class="alert alert-warning d-flex align-items-center gap-2 p-3 mb-3" role="alert">
          <div class="spinner-border spinner-border-sm text-warning" role="status"></div>
          <div>
            <strong>Update sedang berlangsung:</strong> Status saat ini adalah <code>${escapeHtml(m.updateStatus)}</code>.
            Player sedang memproses pengunduhan, verifikasi, atau restart.
          </div>
        </div>
      ` : ''}

      <!-- Package Manifest Details -->
      <div class="card border mb-3">
        <div class="card-header py-2 bg-body-tertiary d-flex justify-content-between align-items-center">
          <div class="card-title fs-5 fw-bold mb-0">Informasi Paket Pembaruan Server</div>
          <span class="badge bg-primary-lt font-monospace">v${escapeHtml(manifest.version || m.targetVersion)}</span>
        </div>
        <div class="card-body p-3">
          <div class="row g-3 small">
            <div class="col-sm-6 d-flex justify-content-between border-bottom pb-2">
              <span class="text-secondary">Nama Arsip:</span>
              <code class="text-body">${escapeHtml(manifest.filename || 'raspideck-player.tar.gz')}</code>
            </div>
            <div class="col-sm-6 d-flex justify-content-between border-bottom pb-2">
              <span class="text-secondary">Ukuran Paket:</span>
              <span class="fw-semibold text-body">${manifest.size_bytes ? (manifest.size_bytes / 1024).toFixed(1) + ' KB' : 'N/A'}</span>
            </div>
            <div class="col-sm-6 d-flex justify-content-between">
              <span class="text-secondary">Kebutuhan Disk:</span>
              <span class="fw-semibold text-body">&ge; ${manifest.min_free_space_mb || 30} MB</span>
            </div>
            <div class="col-sm-6 d-flex justify-content-between">
              <span class="text-secondary">Checksum SHA-256:</span>
              <code class="font-monospace text-body" title="${escapeHtml(manifest.sha256 || '')}">${manifest.sha256 ? manifest.sha256.substring(0, 16) + '...' : 'N/A'}</code>
            </div>
          </div>
        </div>
      </div>

      <!-- Audit History -->
      <div class="card border">
        <div class="card-header py-2 bg-body-tertiary">
          <div class="card-title fs-5 fw-bold mb-0">Riwayat Audit Pembaruan</div>
        </div>
        <div class="card-body p-0">
          ${logsHtml}
        </div>
      </div>
    </div>
    <div class="modal-footer d-flex justify-content-between align-items-center py-2 px-3">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Tutup</button>
      <div>
        ${m.isUpdating ? `
          <button type="button" class="btn btn-warning d-flex align-items-center gap-1" disabled>
            <span class="spinner-border spinner-border-sm me-1"></span>
            Sedang Memperbarui...
          </button>
        ` : (m.isOutdated ? `
          <button type="button" class="btn btn-primary d-flex align-items-center gap-1" id="btn-trigger-update" onclick="submitScreenUpdate('${s.id}')">
            <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2" /><path d="M7 11l5 5l5 -5" /><path d="M12 4l0 12" /></svg>
            Perbarui ke v${m.targetVersion}
          </button>
        ` : `
          <div class="d-flex align-items-center gap-2">
            <span class="badge bg-success-lt text-success d-flex align-items-center gap-1 py-2 px-3">
              <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-inline" width="16" height="16" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" fill="none"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M5 12l5 5l10 -10" /></svg>
              Sudah Versi Terbaru
            </span>
            <button type="button" class="btn btn-sm btn-outline-secondary" id="btn-trigger-update" onclick="submitScreenUpdate('${s.id}')" title="Pasang ulang versi ini">
              Install Ulang
            </button>
          </div>
        `)}
      </div>
    </div>
  `, 'modal-lg');
}

async function submitScreenUpdate(screenId) {
  const btn = document.getElementById('btn-trigger-update');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Mengirim...';
  }
  const res = await api(`/api/screens/${screenId}/update`, { method: 'POST' });
  closeModal();
  if (res && res.success) {
    showToast(res.message || 'Pembaruan OTA berhasil dijadwalkan.', 'success');
    fetchScreens();
  } else {
    showToast(res ? res.error : 'Gagal menjadwalkan pembaruan OTA', 'danger');
  }
}

// --- MODAL: BATCH OTA UPDATE ---
function openBatchUpdateModal() {
  const targetVer = state.serverPlayerVersion;
  const outdatedScreens = state.screens.filter(s => s.is_paired && targetVer && s.app_version && s.app_version !== targetVer);

  openModal(`
    <div class="modal-header">
      <h5 class="modal-title fw-bold text-primary">Pembaruan Massal Software Player (OTA)</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <p class="text-secondary mb-3">
        Terdapat <strong>${outdatedScreens.length} layar display</strong> yang saat ini menjalankan versi lama dan akan diperbarui ke versi <strong>v${escapeHtml(targetVer)}</strong>:
      </p>
      <div class="list-group mb-3" style="max-height: 250px; overflow-y:auto;">
        ${outdatedScreens.map(s => `
          <div class="list-group-item d-flex justify-content-between align-items-center py-2">
            <div>
              <div class="fw-bold">${escapeHtml(s.name || s.id)}</div>
              <div class="text-secondary small font-monospace">${s.ip_address || '127.0.0.1'}</div>
            </div>
            <div class="d-flex align-items-center gap-2">
              <span class="badge bg-secondary-lt">v${escapeHtml(s.app_version || '2.0')}</span>
              &rarr;
              <span class="badge bg-primary text-white">v${escapeHtml(targetVer)}</span>
            </div>
          </div>
        `).join('')}
      </div>
      <div class="alert alert-info py-2 px-3 small mb-0">
        Perintah pembaruan akan dieksekusi otomatis oleh masing-masing Raspberry Pi saat siklus heartbeat berikutnya. Video playback akan di-pause sejenak saat proses atomic swap berlangsung.
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Batal</button>
      <button type="button" class="btn btn-primary" id="btn-submit-batch-update" onclick="submitBatchUpdate()">
        Konfirmasi Perbarui Semua (${outdatedScreens.length} Layar)
      </button>
    </div>
  `);
}

async function submitBatchUpdate() {
  const btn = document.getElementById('btn-submit-batch-update');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Memproses...';
  }
  const res = await api('/api/screens/update-all', { method: 'POST' });
  closeModal();
  if (res && res.success) {
    showToast(res.message || 'Pembaruan massal berhasil dijadwalkan.', 'success');
    fetchScreens();
  } else {
    showToast(res ? res.error : 'Gagal menjadwalkan pembaruan massal', 'danger');
  }
}


/**
 * RaspiDeck — Playlists Module
 * Handles loop management, scheduling, item reordering, and video duration synchronization.
 */

// --- PLAYLISTS DATA FETCHING ---
async function fetchPlaylists() {
  const data = await api('/api/playlists');
  if (!data) return;
  state.playlists = data;
  renderPlaylists();
  const statEl = document.getElementById('stat-playlists-count');
  if (statEl) statEl.textContent = `${state.playlists.length} Loops`;
  const badgeEl = document.getElementById('nav-badge-playlists');
  if (badgeEl) badgeEl.textContent = state.playlists.length;
}

// --- RENDER PLAYLISTS GRID ---
function renderPlaylists() {
  const grid = document.getElementById('playlists-grid');
  if (!grid) return;
  const search = (document.getElementById('playlists-search')?.value || '').toLowerCase().trim();

  const filtered = state.playlists.filter(p =>
    (p.name || '').toLowerCase().includes(search)
  );

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="col-12">
        <div class="card border-dashed p-5 text-center">
          <div class="text-secondary mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="48" height="48" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" fill="none">
              <circle cx="14" cy="17" r="3" />
              <path d="M17 17v-10h4" />
              <path d="M13 5h-10" />
              <path d="M9 9h-6" />
              <path d="M7 13h-4" />
            </svg>
          </div>
          <h3 class="fw-bold mb-1">No playlists created yet</h3>
          <p class="text-secondary small mb-3">Create a playlist loop to assign to your Raspberry Pi screen terminals.</p>
          <div>
            <button class="btn btn-purple text-white btn-sm" onclick="openCreatePlaylistModal()">Create New Playlist</button>
          </div>
        </div>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(p => {
    const items = p.items || [];
    const totalDuration = items.reduce((acc, it) => acc + (parseInt(it.duration) || 10), 0);
    const assignedCount = state.screens.filter(s => s.playlist_id === p.id).length;

    return `
      <div class="col-md-6 col-xl-4">
        <div class="card h-100 shadow-sm border-0">
          <div class="card-header d-flex align-items-center justify-content-between py-3">
            <div class="d-flex align-items-center gap-2">
              <span class="avatar avatar-sm bg-purple-lt text-purple rounded-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none">
                  <circle cx="14" cy="17" r="3" />
                  <path d="M17 17v-10h4" />
                  <path d="M13 5h-10" />
                </svg>
              </span>
              <div>
                <h3 class="card-title fw-bold mb-0 text-truncate" style="max-width: 180px;">${escapeHtml(p.name)}</h3>
                <div class="text-secondary small">Version ${p.version || 1} &bull; ${items.length} assets</div>
              </div>
            </div>
            <span class="badge bg-primary-lt">${assignedCount} Screen${assignedCount === 1 ? '' : 's'}</span>
          </div>

          <div class="card-body py-3 d-flex flex-column justify-content-between">
            <div>
              <div class="d-flex justify-content-between small text-secondary mb-2">
                <span>Total Loop Duration:</span>
                <span class="fw-bold text-body">${totalDuration} seconds</span>
              </div>
              <div class="d-flex justify-content-between align-items-center small text-secondary mb-2">
                <span>Waktu Tayang:</span>
                ${p.schedule_enabled ? `
                  <span class="badge bg-green-lt fw-bold font-monospace">🕒 ${escapeHtml(p.start_time || '00:00')} - ${escapeHtml(p.end_time || '23:59')}</span>
                ` : `
                  <span class="badge bg-secondary-lt">🕒 Selalu Aktif</span>
                `}
              </div>

              <!-- Sequence Preview Strip -->
              <div class="small text-secondary mb-1">Rotation Order:</div>
              <div class="d-flex flex-wrap gap-1 mb-3" style="min-height: 32px;">
                ${items.length === 0 ? '<span class="text-secondary small fst-italic">No items in playlist</span>' : ''}
                ${items.slice(0, 6).map((it, idx) => {
                  const m = state.media.find(x => x.id === it.media_id);
                  const title = it.original_name || m?.original_name || it.filename || `Item ${idx+1}`;
                  const isVid = m?.media_type === 'video' || it.media_type === 'video';
                  return `
                    <div class="playlist-pill-item" title="${escapeHtml(title)} (${it.duration}s)">
                      <span class="badge bg-${isVid ? 'danger' : 'info'} p-1 rounded-circle"></span>
                      <span class="text-truncate">${escapeHtml(title)}</span>
                      <span class="text-secondary fw-bold ms-auto">${it.duration}s</span>
                    </div>
                  `;
                }).join('')}
                ${items.length > 6 ? `<span class="badge bg-secondary-lt align-self-center">+${items.length - 6} more</span>` : ''}
              </div>
            </div>

            <div class="d-flex gap-2 pt-3 border-top mt-3">
              <button class="btn btn-sm btn-outline-primary flex-grow-1" onclick="openEditPlaylistModal('${p.id}')">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path d="M4 20h4l10.5 -10.5a1.5 1.5 0 0 0 -5 -5l-10.5 10.5v4"></path></svg>
                Edit Loop Items
              </button>
              <button class="btn btn-sm btn-outline-danger btn-icon" title="Delete playlist" onclick="confirmDeletePlaylistById('${p.id}')">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><line x1="4" y1="7" x2="20" y2="7"></line><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line><path d="M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12"></path><path d="M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3"></path></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// --- MODAL: CREATE PLAYLIST ---
function openCreatePlaylistModal() {
  openModal(`
    <div class="modal-header">
      <h5 class="modal-title fw-bold">Create New Playlist Loop</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <div class="mb-3">
        <label class="form-label required">Playlist Name</label>
        <input type="text" id="new-playlist-name" class="form-control" placeholder="e.g., Morning Promo Menu 2026">
      </div>

      <div class="card bg-body-tertiary border mb-2">
        <div class="card-body p-3">
          <div class="d-flex align-items-center justify-content-between">
            <div class="fw-bold small d-flex align-items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" class="icon text-purple" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><circle cx="12" cy="12" r="9"></circle><polyline points="12 7 12 12 15 15"></polyline></svg>
              Atur Waktu Pemutaran
            </div>
            <div class="form-check form-switch m-0">
              <input class="form-check-input" type="checkbox" id="new-pl-schedule-enabled" onchange="toggleNewScheduleBox()">
            </div>
          </div>
          <div id="new-pl-schedule-box" class="mt-2 pt-2 border-top d-none">
            <div class="row g-2 mb-2">
              <div class="col-6">
                <label class="form-label small fw-bold mb-1">Jam Mulai</label>
                <div class="input-group input-group-sm">
                  <span class="input-group-text text-secondary bg-body-tertiary px-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon m-0" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><circle cx="12" cy="12" r="9"></circle><polyline points="12 7 12 12 15 15"></polyline></svg>
                  </span>
                  <input type="text" id="new-pl-start-time" class="form-control form-control-sm font-monospace" value="08:00" placeholder="08:00" maxlength="5" oninput="mask24HourTime(this)" onblur="validate24HourTime(this, '08:00')" list="time-24h-presets">
                </div>
              </div>
              <div class="col-6">
                <label class="form-label small fw-bold mb-1">Jam Selesai</label>
                <div class="input-group input-group-sm">
                  <span class="input-group-text text-secondary bg-body-tertiary px-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon m-0" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><circle cx="12" cy="12" r="9"></circle><polyline points="12 7 12 12 15 15"></polyline></svg>
                  </span>
                  <input type="text" id="new-pl-end-time" class="form-control form-control-sm font-monospace" value="22:00" placeholder="22:00" maxlength="5" oninput="mask24HourTime(this)" onblur="validate24HourTime(this, '22:00')" list="time-24h-presets">
                </div>
              </div>
            </div>
            <div>
              <label class="form-label small fw-bold mb-1">Hari Tayang</label>
              <div class="d-flex flex-wrap gap-2">
                <label class="form-check form-check-inline m-0"><input class="form-check-input new-pl-day-cb" type="checkbox" value="mon" checked><span class="form-check-label small ms-1">Sen</span></label>
                <label class="form-check form-check-inline m-0"><input class="form-check-input new-pl-day-cb" type="checkbox" value="tue" checked><span class="form-check-label small ms-1">Sel</span></label>
                <label class="form-check form-check-inline m-0"><input class="form-check-input new-pl-day-cb" type="checkbox" value="wed" checked><span class="form-check-label small ms-1">Rab</span></label>
                <label class="form-check form-check-inline m-0"><input class="form-check-input new-pl-day-cb" type="checkbox" value="thu" checked><span class="form-check-label small ms-1">Kam</span></label>
                <label class="form-check form-check-inline m-0"><input class="form-check-input new-pl-day-cb" type="checkbox" value="fri" checked><span class="form-check-label small ms-1">Jum</span></label>
                <label class="form-check form-check-inline m-0"><input class="form-check-input new-pl-day-cb" type="checkbox" value="sat" checked><span class="form-check-label small ms-1">Sab</span></label>
                <label class="form-check form-check-inline m-0"><input class="form-check-input new-pl-day-cb" type="checkbox" value="sun" checked><span class="form-check-label small ms-1">Min</span></label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-purple text-white" onclick="submitCreatePlaylist()">Create Playlist</button>
    </div>
  `);
}

function toggleNewScheduleBox() {
  const isChecked = document.getElementById('new-pl-schedule-enabled')?.checked;
  const box = document.getElementById('new-pl-schedule-box');
  if (box) box.classList.toggle('d-none', !isChecked);
}

async function submitCreatePlaylist() {
  const name = document.getElementById('new-playlist-name')?.value.trim();
  if (!name) {
    showToast('Masukkan nama playlist terlebih dahulu', 'warning');
    return;
  }
  const scheduleEnabled = document.getElementById('new-pl-schedule-enabled')?.checked || false;
  const startTime = document.getElementById('new-pl-start-time')?.value || '00:00';
  const endTime = document.getElementById('new-pl-end-time')?.value || '23:59';
  const dayCheckboxes = document.querySelectorAll('.new-pl-day-cb:checked');
  const scheduleDays = Array.from(dayCheckboxes).map(cb => cb.value);

  const res = await api('/api/playlists', {
    method: 'POST',
    body: {
      name,
      items: [],
      schedule_enabled: scheduleEnabled,
      start_time: startTime,
      end_time: endTime,
      schedule_days: scheduleDays
    }
  });
  if (res && res.success) {
    closeModal();
    showToast('Playlist berhasil dibuat', 'success');
    await fetchPlaylists();
    openEditPlaylistModal(res.id);
  }
}

// --- MODAL: EDIT PLAYLIST ITEMS ---
let currentEditPlaylistId = null;
let currentEditItems = [];

function openEditPlaylistModal(playlistId) {
  currentEditPlaylistId = playlistId;
  const p = state.playlists.find(x => x.id === playlistId);
  if (!p) return;
  currentEditItems = structuredClone(p.items || []);

  // Auto-detect and sync real durations and original names
  currentEditItems.forEach((it, idx) => {
    const m = state.media.find(x => x.id === it.media_id);
    if (m && !it.original_name && m.original_name) {
      it.original_name = m.original_name;
    }
    if (m && (m.media_type === 'video' || it.media_type === 'video') && (!it.duration || it.duration === 10)) {
      if (typeof getMediaDuration === 'function') {
        getMediaDuration(m).then(dur => {
          if (dur && dur !== 10 && it.duration === 10) {
            it.duration = dur;
            const input = document.getElementById(`item-dur-${idx}`);
            if (input) input.value = dur;
            const hint = document.getElementById(`item-dur-hint-${idx}`);
            if (hint && typeof formatDurationTime === 'function') hint.textContent = formatDurationTime(dur);
          }
        });
      }
    }
  });

  openModal(`
    <div class="modal-header">
      <div>
        <h5 class="modal-title fw-bold">Edit Playlist: ${escapeHtml(p.name)}</h5>
        <div class="text-secondary small">Reorder items, set image display durations, or add new media.</div>
      </div>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <div class="mb-3">
        <label class="form-label required">Playlist Name</label>
        <input type="text" id="edit-pl-name" class="form-control" value="${escapeHtml(p.name)}">
      </div>

      <!-- Schedule Settings Box -->
      <div class="card bg-body-tertiary border mb-3">
        <div class="card-body p-3">
          <div class="d-flex align-items-center justify-content-between">
            <div class="fw-bold small d-flex align-items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" class="icon text-purple" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><circle cx="12" cy="12" r="9"></circle><polyline points="12 7 12 12 15 15"></polyline></svg>
              Atur Waktu Pemutaran
            </div>
            <div class="form-check form-switch m-0">
              <input class="form-check-input" type="checkbox" id="edit-pl-schedule-enabled" ${p.schedule_enabled ? 'checked' : ''} onchange="toggleEditScheduleBox()">
            </div>
          </div>

          <div id="edit-pl-schedule-box" class="mt-3 pt-2 border-top ${p.schedule_enabled ? '' : 'd-none'}">
            <div class="row g-2 mb-2">
              <div class="col-6">
                <label class="form-label small fw-bold mb-1">Jam Mulai</label>
                <div class="input-group input-group-sm">
                  <span class="input-group-text text-secondary bg-body-tertiary px-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon m-0" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><circle cx="12" cy="12" r="9"></circle><polyline points="12 7 12 12 15 15"></polyline></svg>
                  </span>
                  <input type="text" id="edit-pl-start-time" class="form-control form-control-sm font-monospace" value="${escapeHtml(p.start_time || '08:00')}" placeholder="08:00" maxlength="5" oninput="mask24HourTime(this)" onblur="validate24HourTime(this, '08:00')" list="time-24h-presets">
                </div>
              </div>
              <div class="col-6">
                <label class="form-label small fw-bold mb-1">Jam Selesai</label>
                <div class="input-group input-group-sm">
                  <span class="input-group-text text-secondary bg-body-tertiary px-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon m-0" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><circle cx="12" cy="12" r="9"></circle><polyline points="12 7 12 12 15 15"></polyline></svg>
                  </span>
                  <input type="text" id="edit-pl-end-time" class="form-control form-control-sm font-monospace" value="${escapeHtml(p.end_time || '22:00')}" placeholder="22:00" maxlength="5" oninput="mask24HourTime(this)" onblur="validate24HourTime(this, '22:00')" list="time-24h-presets">
                </div>
              </div>
            </div>

            <div>
              <label class="form-label small fw-bold mb-1">Hari Tayang</label>
              <div class="d-flex flex-wrap gap-2">
                ${[
                  ['mon', 'Sen'],
                  ['tue', 'Sel'],
                  ['wed', 'Rab'],
                  ['thu', 'Kam'],
                  ['fri', 'Jum'],
                  ['sat', 'Sab'],
                  ['sun', 'Min']
                ].map(([code, label]) => {
                  const checked = (!p.schedule_days || p.schedule_days.includes(code)) ? 'checked' : '';
                  return `
                    <label class="form-check form-check-inline m-0">
                      <input class="form-check-input edit-pl-day-cb" type="checkbox" value="${code}" ${checked}>
                      <span class="form-check-label small ms-1">${label}</span>
                    </label>
                  `;
                }).join('')}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Items Sequence List -->
      <div class="mb-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <label class="form-label fw-bold mb-0">Rotation Items (<span id="playlist-items-count">${currentEditItems.length}</span>)</label>
          <button class="btn btn-sm btn-outline-primary" onclick="showAddMediaSelector()">
            <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            Add Media Item
          </button>
        </div>

        <!-- Media selection picker (hidden by default) -->
        <div id="media-picker-box" class="p-3 bg-body-tertiary rounded-3 border mb-3 d-none">
          <div class="fw-bold small mb-2">Pilih media dari library untuk ditambahkan:</div>
          <div class="d-flex flex-wrap gap-2 mb-2">
            <select id="select-add-media-id" class="form-select form-select-sm" style="flex: 1; min-width: 200px;" onchange="onAddMediaSelectChange()">
              ${state.media.map(m => `
                <option value="${m.id}">${escapeHtml(m.original_name)} (${m.media_type === 'video' ? '🎬 Video' : '🖼️ Gambar'})</option>
              `).join('')}
            </select>
            <div class="input-group input-group-sm" style="width: 125px; flex-shrink: 0;">
              <input type="number" id="input-add-duration" class="form-control form-control-sm text-end font-monospace" placeholder="Durasi" value="10" min="1" max="7200">
              <span class="input-group-text">detik</span>
            </div>
            <button type="button" class="btn btn-sm btn-success px-3" onclick="appendItemToPlaylist()">Add</button>
          </div>
          <div class="small text-secondary" id="add-media-duration-hint">
            ⏱️ Durasi video akan otomatis disesuaikan dengan panjang video.
          </div>
        </div>

        <div class="list-group list-group-flush border rounded-2" id="playlist-items-list" style="max-height: 280px; overflow-y: auto;">
          <!-- Items rendered by renderPlaylistItemsList() -->
        </div>
      </div>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-primary" onclick="submitEditPlaylist()">Save Playlist Changes</button>
    </div>
  `, 'modal-lg');

  renderPlaylistItemsList();
}

function toggleEditScheduleBox() {
  const isChecked = document.getElementById('edit-pl-schedule-enabled')?.checked;
  const box = document.getElementById('edit-pl-schedule-box');
  if (box) box.classList.toggle('d-none', !isChecked);
}

function renderPlaylistItemsList() {
  const container = document.getElementById('playlist-items-list');
  const countEl = document.getElementById('playlist-items-count');
  if (countEl) countEl.textContent = currentEditItems.length;
  if (!container) return;

  if (currentEditItems.length === 0) {
    container.innerHTML = '<div class="p-3 text-secondary text-center small">No items in playlist. Click "Add Media Item" above.</div>';
    return;
  }

  container.innerHTML = currentEditItems.map((it, idx) => {
    const m = state.media.find(x => x.id === it.media_id);
    const title = it.original_name || m?.original_name || it.filename || `Item ${idx+1}`;
    const isVideo = m?.media_type === 'video' || it.media_type === 'video';
    const formattedDuration = typeof formatDurationTime === 'function' ? formatDurationTime(it.duration || 10) : `${it.duration || 10}s`;

    return `
      <div class="list-group-item d-flex align-items-center justify-content-between p-2">
        <div class="d-flex align-items-center gap-2 text-truncate" style="max-width: 270px;">
          <span class="badge bg-secondary-lt fw-bold">${idx + 1}</span>
          <span class="badge bg-${isVideo ? 'danger' : 'info'}-lt text-uppercase">${isVideo ? 'VID' : 'IMG'}</span>
          <div class="text-truncate">
            <span class="text-truncate small fw-medium d-block" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
            ${isVideo ? `<span class="text-secondary font-monospace" style="font-size: 0.72rem;" id="item-dur-hint-${idx}">${formattedDuration}</span>` : ''}
          </div>
        </div>
        <div class="d-flex align-items-center gap-1">
          <div class="input-group input-group-sm" style="width: 105px;">
            <input type="number" id="item-dur-${idx}" class="form-control form-control-sm text-end font-monospace" value="${it.duration || 10}" min="1" max="7200" onchange="updateItemDuration(${idx}, this.value)">
            <span class="input-group-text">s</span>
          </div>
          ${isVideo ? `
            <button type="button" class="btn btn-sm btn-ghost-secondary btn-icon" title="Sesuaikan otomatis dengan panjang video asli" onclick="syncItemVideoDuration(${idx})">
              <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="15" height="15" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path d="M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4" /><path d="M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4" /></svg>
            </button>
          ` : ''}
          <div class="btn-group btn-group-sm ms-1">
            <button type="button" class="btn btn-ghost-secondary btn-icon" title="Move Up" ${idx === 0 ? 'disabled' : ''} onclick="movePlaylistItem(${idx}, -1)">
              <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><polyline points="6 15 12 9 18 15"></polyline></svg>
            </button>
            <button type="button" class="btn btn-ghost-secondary btn-icon" title="Move Down" ${idx === currentEditItems.length - 1 ? 'disabled' : ''} onclick="movePlaylistItem(${idx}, 1)">
              <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </button>
            <button type="button" class="btn btn-ghost-danger btn-icon" title="Remove" onclick="removePlaylistItem(${idx})">
              <svg xmlns="http://www.w3.org/2000/svg" class="icon text-danger" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function showAddMediaSelector() {
  const box = document.getElementById('media-picker-box');
  if (box) {
    const isHidden = box.classList.contains('d-none');
    box.classList.toggle('d-none');
    if (isHidden) {
      await onAddMediaSelectChange();
    }
  }
}

async function onAddMediaSelectChange() {
  const select = document.getElementById('select-add-media-id');
  const durInput = document.getElementById('input-add-duration');
  const hint = document.getElementById('add-media-duration-hint');
  if (!select || !durInput) return;

  const m = state.media.find(x => x.id === select.value);
  if (!m) return;

  if (m.media_type === 'video') {
    durInput.value = '...';
    durInput.disabled = true;
    if (hint) hint.innerHTML = '<span class="spinner-border spinner-border-sm text-primary me-1"></span> Mendeteksi durasi video...';
    const dur = typeof getMediaDuration === 'function' ? await getMediaDuration(m) : 10;
    durInput.disabled = false;
    durInput.value = dur;
    const formatted = typeof formatDurationTime === 'function' ? formatDurationTime(dur) : `${dur}s`;
    if (hint) hint.innerHTML = `🎬 Durasi asli video: <strong>${dur} detik</strong> (${formatted})`;
  } else {
    durInput.disabled = false;
    durInput.value = 10;
    if (hint) hint.innerHTML = '🖼️ Durasi tayang gambar: 10 detik (dapat disesuaikan)';
  }
}

async function appendItemToPlaylist() {
  const select = document.getElementById('select-add-media-id');
  const mediaId = select?.value;
  const m = state.media.find(x => x.id === mediaId);
  if (!m) return;

  let duration = parseInt(document.getElementById('input-add-duration')?.value);
  if (isNaN(duration) || duration <= 0) {
    duration = typeof getMediaDuration === 'function' ? await getMediaDuration(m) : 10;
  }

  currentEditItems.push({
    media_id: m.id,
    filename: m.filename,
    original_name: m.original_name,
    duration: duration,
    media_type: m.media_type
  });
  renderPlaylistItemsList();
  const box = document.getElementById('media-picker-box');
  if (box) box.classList.add('d-none');
}

async function syncItemVideoDuration(idx) {
  const it = currentEditItems[idx];
  if (!it) return;
  const m = state.media.find(x => x.id === it.media_id);
  if (!m) return;
  showToast(`Mendeteksi durasi ${m.original_name}...`, 'info');
  const dur = typeof getMediaDuration === 'function' ? await getMediaDuration(m) : 10;
  it.duration = dur;
  renderPlaylistItemsList();
  const formatted = typeof formatDurationTime === 'function' ? formatDurationTime(dur) : `${dur}s`;
  showToast(`Durasi ${m.original_name} disesuaikan ke ${dur} detik (${formatted})`, 'success');
}

function updateItemDuration(idx, val) {
  if (currentEditItems[idx]) {
    const d = parseInt(val) || 10;
    currentEditItems[idx].duration = d;
    const hint = document.getElementById(`item-dur-hint-${idx}`);
    if (hint && typeof formatDurationTime === 'function') hint.textContent = formatDurationTime(d);
  }
}

function movePlaylistItem(idx, direction) {
  const target = idx + direction;
  if (target < 0 || target >= currentEditItems.length) return;
  const temp = currentEditItems[idx];
  currentEditItems[idx] = currentEditItems[target];
  currentEditItems[target] = temp;
  renderPlaylistItemsList();
}

function removePlaylistItem(idx) {
  currentEditItems.splice(idx, 1);
  renderPlaylistItemsList();
}

async function submitEditPlaylist() {
  if (!currentEditPlaylistId) return;
  const name = document.getElementById('edit-pl-name')?.value.trim();
  const scheduleEnabled = document.getElementById('edit-pl-schedule-enabled')?.checked || false;
  const startTime = document.getElementById('edit-pl-start-time')?.value || '00:00';
  const endTime = document.getElementById('edit-pl-end-time')?.value || '23:59';
  const dayCheckboxes = document.querySelectorAll('.edit-pl-day-cb:checked');
  const scheduleDays = Array.from(dayCheckboxes).map(cb => cb.value);

  const res = await api(`/api/playlists/${currentEditPlaylistId}`, {
    method: 'PUT',
    body: {
      name: name || undefined,
      items: currentEditItems,
      schedule_enabled: scheduleEnabled,
      start_time: startTime,
      end_time: endTime,
      schedule_days: scheduleDays
    }
  });
  if (res && res.success) {
    closeModal();
    showToast('Playlist berhasil diperbarui', 'success');
    fetchPlaylists();
  }
}

// --- MODAL: DELETE PLAYLIST ---
function confirmDeletePlaylistById(playlistId) {
  const p = state.playlists.find(x => x.id === playlistId);
  if (!p) return;
  confirmDeletePlaylist(p.id, p.name);
}

function confirmDeletePlaylist(playlistId, playlistName) {
  openModal(`
    <div class="modal-header">
      <h5 class="modal-title text-danger fw-bold">Delete Playlist</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <p class="text-secondary mb-0">
        Are you sure you want to delete playlist <strong>${escapeHtml(playlistName)}</strong>? Screens currently playing this loop will fallback to cached or waiting display.
      </p>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-danger" onclick="submitDeletePlaylist('${playlistId}')">Delete Playlist</button>
    </div>
  `);
}

async function submitDeletePlaylist(playlistId) {
  await api(`/api/playlists/${playlistId}`, { method: 'DELETE' });
  closeModal();
  showToast('Playlist berhasil dihapus', 'info');
  fetchPlaylists();
}

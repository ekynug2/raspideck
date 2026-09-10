/**
 * RaspiDeck — Media Library Module
 * Handles media browsing, Google Drive-style file uploads, video metadata detection, and previews.
 */

// --- DURATION CACHE & HELPERS ---
const mediaDurationCache = {};

function getMediaDuration(media) {
  if (!media) return Promise.resolve(10);
  if (media.media_type !== 'video') return Promise.resolve(10);
  if (media.duration && media.duration > 0) return Promise.resolve(media.duration);
  if (mediaDurationCache[media.id]) return Promise.resolve(mediaDurationCache[media.id]);

  return new Promise((resolve) => {
    const v = document.createElement('video');
    v.preload = 'metadata';
    v.src = `/media/${encodeURIComponent(media.filename)}`;

    const timeout = setTimeout(() => {
      resolve(10);
    }, 6000);

    v.onloadedmetadata = () => {
      clearTimeout(timeout);
      const dur = Math.round(v.duration);
      if (dur && dur > 0 && !isNaN(dur) && isFinite(dur)) {
        mediaDurationCache[media.id] = dur;
        media.duration = dur;
        resolve(dur);
      } else {
        resolve(10);
      }
    };

    v.onerror = () => {
      clearTimeout(timeout);
      resolve(10);
    };
  });
}

function formatDurationTime(seconds) {
  const s = parseInt(seconds) || 0;
  if (s < 60) return `${s}s`;
  const mins = Math.floor(s / 60);
  const remSecs = s % 60;
  return `${mins}m ${remSecs > 0 ? remSecs + 's' : ''}`;
}

// --- MEDIA DATA FETCHING ---
async function fetchMedia() {
  const data = await api('/api/media');
  if (!data) return;
  state.media = data;
  renderMedia();
  updateMediaStats();
  if (typeof renderPlaylists === 'function' && state.playlists && state.playlists.length > 0) {
    renderPlaylists();
  }
  // Background pre-fetch video durations
  state.media.forEach(m => {
    if (m.media_type === 'video') {
      getMediaDuration(m);
    }
  });
}

function updateMediaStats() {
  const totalBytes = state.media.reduce((acc, m) => acc + (m.size || 0), 0);
  const totalMb = (totalBytes / (1024 * 1024)).toFixed(1);
  const storageEl = document.getElementById('stat-media-storage');
  if (storageEl) storageEl.textContent = `${totalMb} MB`;
  const assetsEl = document.getElementById('stat-media-assets');
  if (assetsEl) assetsEl.textContent = `${state.media.length} Uploaded Assets`;
  const badgeEl = document.getElementById('nav-badge-media');
  if (badgeEl) badgeEl.textContent = state.media.length;
}

function setMediaFilter(filter) {
  state.mediaFilter = filter;
  document.querySelectorAll('#filter-media-all, #filter-media-video, #filter-media-image').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById(`filter-media-${filter}`);
  if (activeBtn) activeBtn.classList.add('active');
  renderMedia();
}

// --- RENDER MEDIA GRID ---
function renderMedia() {
  const grid = document.getElementById('media-grid');
  if (!grid) return;
  const search = (document.getElementById('media-search')?.value || '').toLowerCase().trim();

  let filtered = state.media;
  if (state.mediaFilter !== 'all') {
    filtered = filtered.filter(m => m.media_type === state.mediaFilter);
  }
  if (search) {
    filtered = filtered.filter(m => (m.original_name || m.filename || '').toLowerCase().includes(search));
  }

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="col-12">
        <div class="card border-dashed p-5 text-center">
          <div class="text-secondary mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="48" height="48" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" fill="none">
              <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
              <rect x="4" y="4" width="16" height="16" rx="3" />
              <path d="M4 15l4 -4a3 5 0 0 1 3 0l5 5" />
              <path d="M14 14l1 -1a3 5 0 0 1 3 0l2 2" />
            </svg>
          </div>
          <h3 class="fw-bold mb-1">No media files found</h3>
          <p class="text-secondary small">Drag and drop images or videos above to upload signage assets.</p>
        </div>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(m => {
    const isVideo = m.media_type === 'video';
    const sizeMb = ((m.size || 0) / (1024 * 1024)).toFixed(2);
    const mediaUrl = `/media/${encodeURIComponent(m.filename)}`;
    const thumbUrl = m.thumbnail_url || (isVideo ? `/media/thumbnails/${encodeURIComponent(m.id)}.jpg` : mediaUrl);

    return `
      <div class="col-sm-6 col-md-4 col-xl-3">
        <div class="card h-100 shadow-sm border-0 position-relative">
          <!-- Thumbnail Preview -->
          ${isVideo ? `
            <div class="media-card-video-wrapper position-relative" style="cursor:pointer;" onclick="openMediaPreviewById('${m.id}')">
              <img src="${thumbUrl}" class="media-card-img w-100" alt="${escapeHtml(m.original_name)}" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.classList.remove('d-none');">
              <div class="media-card-video-placeholder d-none w-100">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-lg" width="48" height="48" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" fill="none">
                  <circle cx="12" cy="12" r="9" />
                  <polygon points="10 8 16 12 10 16 10 8" fill="currentColor" />
                </svg>
              </div>
              <div class="video-play-overlay">
                <div class="video-play-btn">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><polygon points="8 5 19 12 8 19 8 5" /></svg>
                </div>
              </div>
              <span class="badge bg-danger position-absolute top-0 start-0 m-2 shadow-sm">VIDEO</span>
            </div>
          ` : `
            <div class="position-relative overflow-hidden" style="cursor:pointer; height: 160px; border-top-left-radius: var(--tblr-border-radius); border-top-right-radius: var(--tblr-border-radius);" onclick="openMediaPreviewById('${m.id}')">
              <img src="${mediaUrl}" class="media-card-img w-100" alt="${escapeHtml(m.original_name)}" loading="lazy">
              <span class="badge bg-info position-absolute top-0 start-0 m-2 shadow-sm">IMAGE</span>
            </div>
          `}

          <!-- Card Body -->
          <div class="card-body p-3 d-flex flex-column justify-content-between">
            <div class="mb-2">
              <div class="fw-bold text-truncate mb-1" title="${escapeHtml(m.original_name)}">${escapeHtml(m.original_name)}</div>
              <div class="text-secondary small">${sizeMb} MB &bull; ${formatRelativeTime(m.created_at)}</div>
            </div>

            <div class="d-flex gap-1 pt-2 border-top">
              <button class="btn btn-sm btn-ghost-secondary flex-grow-1" onclick="openMediaPreviewById('${m.id}')">
                Preview
              </button>
              <button class="btn btn-sm btn-icon btn-ghost-secondary" title="Copy URL" onclick="copyToClipboard('${window.location.origin}${mediaUrl}')">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><rect x="8" y="8" width="12" height="12" rx="2"></rect><path d="M16 8v-2a2 2 0 0 0 -2 -2h-8a2 2 0 0 0 -2 2v8a2 2 0 0 0 2 2h2"></path></svg>
              </button>
              <button class="btn btn-sm btn-icon btn-ghost-danger" title="Delete media" onclick="confirmDeleteMediaById('${m.id}')">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon text-danger" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><line x1="4" y1="7" x2="20" y2="7"></line><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line><path d="M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12"></path><path d="M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3"></path></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// --- UPLOAD DROPZONE LOGIC ---
function initDropzone() {
  const zone = document.getElementById('upload-zone');
  if (!zone) return;

  ['dragenter', 'dragover'].forEach(name => {
    zone.addEventListener(name, (e) => {
      e.preventDefault();
      zone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    zone.addEventListener(name, (e) => {
      e.preventDefault();
      zone.classList.remove('dragover');
    });
  });

  zone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      uploadFiles(e.dataTransfer.files);
    }
  });
}

function handleFileSelect(e) {
  if (e.target.files && e.target.files.length > 0) {
    uploadFiles(e.target.files);
    e.target.value = '';
  }
}

// --- UPLOAD PROGRESS PANEL LOGIC (Google Drive style) ---
let uploadQueue = [];
let uploadActiveCount = 0;
let uploadTotalCount = 0;
let uploadDoneCount = 0;
let panelCollapsed = false;
let autoCloseUploadTimer = null;

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
  return (bytes / 1073741824).toFixed(2) + ' GB';
}

function showUploadPanel() {
  if (autoCloseUploadTimer) {
    clearTimeout(autoCloseUploadTimer);
    autoCloseUploadTimer = null;
  }
  const panel = document.getElementById('upload-progress-panel');
  if (panel) {
    panel.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    panel.style.opacity = '1';
    panel.style.transform = 'translateY(0)';
    panel.classList.add('active');
    panel.style.setProperty('display', 'flex', 'important');
  }
}

function closeUploadPanel() {
  if (autoCloseUploadTimer) {
    clearTimeout(autoCloseUploadTimer);
    autoCloseUploadTimer = null;
  }
  const panel = document.getElementById('upload-progress-panel');
  if (panel) {
    panel.classList.remove('active');
    panel.style.setProperty('display', 'none', 'important');
    panel.style.opacity = '1';
    panel.style.transform = 'translateY(0)';
    const body = document.getElementById('upload-panel-body');
    if (body) body.innerHTML = '';
  }
  uploadQueue = [];
  uploadActiveCount = 0;
  uploadTotalCount = 0;
  uploadDoneCount = 0;
}

function toggleUploadPanel() {
  panelCollapsed = !panelCollapsed;
  const body = document.getElementById('upload-panel-body');
  const btn = document.getElementById('upload-panel-toggle-btn');
  if (panelCollapsed) {
    if (body) body.classList.add('collapsed');
    if (btn) btn.innerHTML = '&#x2b;';
  } else {
    if (body) body.classList.remove('collapsed');
    if (btn) btn.innerHTML = '&#x2212;';
  }
}

function updatePanelTitle() {
  const title = document.getElementById('upload-panel-title');
  if (!title) return;
  if (uploadDoneCount >= uploadTotalCount) {
    title.textContent = `${uploadDoneCount} upload${uploadDoneCount > 1 ? 's' : ''} complete`;
  } else {
    title.textContent = `Uploading ${uploadDoneCount + 1} of ${uploadTotalCount}...`;
  }
}

function isVideoFile(name) {
  return /\.(mp4|mkv|webm|avi|mov)$/i.test(name);
}

function createFileRow(file, index) {
  const isVid = isVideoFile(file.name);
  const iconClass = isVid ? 'video' : 'image';
  const iconSvg = isVid
    ? `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><rect x="4" y="4" width="16" height="16" rx="2" /><line x1="8" y1="4" x2="8" y2="20" /><line x1="16" y1="4" x2="16" y2="20" /><line x1="4" y1="8" x2="8" y2="8" /><line x1="4" y1="16" x2="8" y2="16" /></svg>`
    : `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><rect x="4" y="4" width="16" height="16" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg>`;
  return `
    <div class="upload-file-item" id="upload-item-${index}">
      <div class="upload-file-icon ${iconClass}">${iconSvg}</div>
      <div class="upload-file-info">
        <div class="upload-file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</div>
        <div class="upload-file-meta">
          <span id="upload-meta-${index}">${formatFileSize(file.size)} — Waiting...</span>
        </div>
        <div class="upload-file-progress">
          <div class="upload-file-progress-bar" id="upload-bar-${index}"></div>
        </div>
      </div>
      <div class="upload-file-status" id="upload-status-${index}">
        <div class="spinner"></div>
      </div>
    </div>
  `;
}

function uploadSingleFile(file, index) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);
    const startTime = Date.now();

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        const bar = document.getElementById(`upload-bar-${index}`);
        const meta = document.getElementById(`upload-meta-${index}`);
        if (bar) bar.style.width = pct + '%';

        // Calculate speed
        const elapsed = (Date.now() - startTime) / 1000;
        const speed = elapsed > 0 ? e.loaded / elapsed : 0;
        const remaining = speed > 0 ? (e.total - e.loaded) / speed : 0;

        if (meta) {
          meta.textContent = `${formatFileSize(e.loaded)} / ${formatFileSize(e.total)} — ${pct}% · ${formatFileSize(speed)}/s`;
          if (remaining > 0 && pct < 100) {
            const mins = Math.floor(remaining / 60);
            const secs = Math.round(remaining % 60);
            meta.textContent += ` · ${mins > 0 ? mins + 'm ' : ''}${secs}s left`;
          }
        }
      }
    });

    xhr.addEventListener('load', () => {
      const bar = document.getElementById(`upload-bar-${index}`);
      const meta = document.getElementById(`upload-meta-${index}`);
      const status = document.getElementById(`upload-status-${index}`);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

      if (xhr.status >= 200 && xhr.status < 300) {
        if (bar) { bar.style.width = '100%'; bar.classList.add('done'); }
        if (meta) meta.textContent = `${formatFileSize(file.size)} — Done in ${elapsed}s`;
        if (status) status.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tblr-green)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
      } else {
        if (bar) { bar.style.width = '100%'; bar.classList.add('error'); }
        if (meta) meta.textContent = `Upload failed (${xhr.status})`;
        if (status) status.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tblr-danger)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
      }
      uploadDoneCount++;
      updatePanelTitle();
      resolve();
    });

    xhr.addEventListener('error', () => {
      const bar = document.getElementById(`upload-bar-${index}`);
      const meta = document.getElementById(`upload-meta-${index}`);
      const status = document.getElementById(`upload-status-${index}`);
      if (bar) { bar.style.width = '100%'; bar.classList.add('error'); }
      if (meta) meta.textContent = 'Network error';
      if (status) status.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tblr-danger)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
      uploadDoneCount++;
      updatePanelTitle();
      resolve();
    });

    xhr.open('POST', '/api/media');
    xhr.send(formData);

    // Update meta to "Uploading"
    const meta = document.getElementById(`upload-meta-${index}`);
    if (meta) meta.textContent = `${formatFileSize(file.size)} — Starting...`;
  });
}

async function uploadFiles(files) {
  const fileList = Array.from(files);
  if (fileList.length === 0) return;

  // Reset & show panel
  uploadTotalCount = fileList.length;
  uploadDoneCount = 0;
  panelCollapsed = false;
  const panelBody = document.getElementById('upload-panel-body');
  if (panelBody) {
    panelBody.classList.remove('collapsed');
    panelBody.innerHTML = '';
    fileList.forEach((file, i) => {
      panelBody.innerHTML += createFileRow(file, i);
    });
  }
  const toggleBtn = document.getElementById('upload-panel-toggle-btn');
  if (toggleBtn) toggleBtn.innerHTML = '&#x2212;';

  showUploadPanel();
  updatePanelTitle();

  // Upload files sequentially
  for (let i = 0; i < fileList.length; i++) {
    await uploadSingleFile(fileList[i], i);
  }

  // Refresh media library
  fetchMedia();
  showToast(`${uploadDoneCount} file${uploadDoneCount > 1 ? 's' : ''} uploaded`, 'success');

  // Auto-hide upload panel automatically 3.5s after completion
  if (autoCloseUploadTimer) clearTimeout(autoCloseUploadTimer);
  autoCloseUploadTimer = setTimeout(() => {
    const panel = document.getElementById('upload-progress-panel');
    if (panel && uploadDoneCount >= uploadTotalCount) {
      panel.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      panel.style.opacity = '0';
      panel.style.transform = 'translateY(12px)';
      setTimeout(() => {
        closeUploadPanel();
      }, 400);
    }
  }, 3500);
}

// --- MEDIA MODALS ---

// Modal: Preview Media
function openMediaPreviewById(mediaId) {
  const m = state.media.find(x => x.id === mediaId);
  if (!m) return;
  const mediaUrl = `/media/${encodeURIComponent(m.filename)}`;
  previewMediaModal(mediaUrl, m.original_name, m.media_type);
}

function previewMediaModal(url, filename, type) {
  const isVideo = type === 'video';
  openModal(`
    <div class="modal-header">
      <h5 class="modal-title fw-bold text-truncate" style="max-width:400px;">${escapeHtml(filename)}</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body p-3 text-center bg-black d-flex align-items-center justify-content-center" style="min-height: 380px; max-height: 75vh; overflow: hidden;">
      ${isVideo ? `
        <video src="${url}" controls autoplay playsinline loop style="max-width:100%; max-height:70vh; width:auto; height:auto; object-fit:contain; display:block; margin:0 auto; background:#000; border-radius: 4px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);"></video>
      ` : `
        <img src="${url}" style="max-width:100%; max-height:70vh; width:auto; height:auto; object-fit:contain; display:block; margin:0 auto;" alt="${escapeHtml(filename)}">
      `}
    </div>
    <div class="modal-footer d-flex justify-content-between">
      <a href="${url}" target="_blank" download class="btn btn-sm btn-outline-secondary">
        <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none"><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2"></path><polyline points="7 11 12 16 17 11"></polyline><line x1="12" y1="4" x2="12" y2="16"></line></svg>
        Download File
      </a>
      <button type="button" class="btn btn-sm btn-secondary" onclick="closeModal()">Close Preview</button>
    </div>
  `, 'modal-lg');
}

// Modal: Delete Media
function confirmDeleteMediaById(mediaId) {
  const m = state.media.find(x => x.id === mediaId);
  if (!m) return;
  confirmDeleteMedia(m.id, m.original_name);
}

function confirmDeleteMedia(mediaId, filename) {
  openModal(`
    <div class="modal-header">
      <h5 class="modal-title text-danger fw-bold">Delete Media Asset</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body">
      <p class="text-secondary mb-0">
        Are you sure you want to permanently delete <strong>${escapeHtml(filename)}</strong>? It will also be removed from disk.
      </p>
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn btn-danger" onclick="submitDeleteMedia('${mediaId}')">Delete Asset</button>
    </div>
  `);
}

async function submitDeleteMedia(mediaId) {
  await api(`/api/media/${mediaId}`, { method: 'DELETE' });
  closeModal();
  showToast('Media file deleted', 'info');
  fetchMedia();
}

// Modal: Preview Boot Splash
function openSplashPreviewModal(e) {
  if (e) e.preventDefault();
  openModal(`
    <div class="modal-header">
      <h5 class="modal-title fw-bold">Raspberry Pi Boot Splash Preview</h5>
      <button type="button" class="btn-close" onclick="closeModal()"></button>
    </div>
    <div class="modal-body p-0 bg-black text-center">
      <img src="/preview-splash" style="max-width:100%; max-height:65vh;" alt="Boot Splash" onerror="this.src=''; this.alt='Splash not generated yet. Run python player/generate_splash.py.'">
    </div>
    <div class="modal-footer">
      <button type="button" class="btn btn-secondary" onclick="closeModal()">Close</button>
    </div>
  `, 'modal-lg');
}

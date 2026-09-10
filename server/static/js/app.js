/**
 * RaspiDeck — Core Application State, API, Modals, & Utilities
 */

// --- APP STATE ---
const state = {
  screens: [],
  playlists: [],
  media: [],
  activeTab: 'screens',
  mediaFilter: 'all',
  pollingInterval: null
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
  initThemeIcons();
  if (typeof initDropzone === 'function') initDropzone();
  await Promise.all([
    typeof fetchScreens === 'function' ? fetchScreens() : Promise.resolve(),
    typeof fetchMedia === 'function' ? fetchMedia() : Promise.resolve()
  ]);
  if (typeof fetchPlaylists === 'function') await fetchPlaylists();
  startSilentPolling();
});

// --- THEME MANAGEMENT (DARK / LIGHT) ---
function initThemeIcons() {
  const current = document.body.getAttribute("data-bs-theme") || "dark";
  const iconDark = document.getElementById("theme-icon-dark");
  const iconLight = document.getElementById("theme-icon-light");
  if (!iconDark || !iconLight) return;
  if (current === "dark") {
    iconDark.classList.remove("d-none");
    iconLight.classList.add("d-none");
  } else {
    iconDark.classList.add("d-none");
    iconLight.classList.remove("d-none");
  }
}

function toggleTheme() {
  const current = document.body.getAttribute("data-bs-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";
  document.body.setAttribute("data-bs-theme", next);
  localStorage.setItem("tablerTheme", next);
  initThemeIcons();
  showToast(`Switched to ${next} theme`, 'info');
}

// --- NAVIGATION TABS ---
function switchTab(tabId, e) {
  if (e) e.preventDefault();
  state.activeTab = tabId;

  document.querySelectorAll('#main-nav-tabs .nav-link').forEach(link => {
    link.classList.remove('active');
    if (link.getAttribute('href') === `#${tabId}`) {
      link.classList.add('active');
    }
  });

  document.querySelectorAll('.tab-view-panel').forEach(panel => {
    panel.classList.add('d-none');
  });

  const target = document.getElementById(`view-${tabId}`);
  if (target) target.classList.remove('d-none');
}

// --- API HELPER ---
async function api(endpoint, options = {}) {
  try {
    const fetchOptions = {
      method: options.method || 'GET',
      headers: {}
    };
    if (options.body && !(options.body instanceof FormData)) {
      fetchOptions.headers['Content-Type'] = 'application/json';
      fetchOptions.body = JSON.stringify(options.body);
    } else if (options.body instanceof FormData) {
      fetchOptions.body = options.body;
    }

    const res = await fetch(endpoint, fetchOptions);
    if (res.status === 401) {
      window.location.href = '/login';
      return null;
    }
    return await res.json();
  } catch (err) {
    console.error('API Error:', err);
    showToast('Connection error to signage server', 'danger');
    return null;
  }
}

// --- POLLING & SYNC ---
function startSilentPolling() {
  if (state.pollingInterval) clearInterval(state.pollingInterval);
  state.pollingInterval = setInterval(() => {
    if (typeof fetchScreensSilent === 'function') fetchScreensSilent();
  }, 5000);
}

async function handleManualSync(btn) {
  const icon = document.getElementById('sync-icon');
  if (icon) icon.style.animation = 'spin 0.8s linear infinite';
  await Promise.all([
    typeof fetchScreens === 'function' ? fetchScreens() : Promise.resolve(),
    typeof fetchMedia === 'function' ? fetchMedia() : Promise.resolve()
  ]);
  if (typeof fetchPlaylists === 'function') await fetchPlaylists();
  if (icon) icon.style.animation = '';
  showToast('Displays and playlists synchronized', 'success');
}

// --- ACTIONS & BASE MODALS ---
function getModalInstance() {
  const modalEl = document.getElementById('mainModal');
  if (!modalEl) return null;
  const ModalClass = (window.bootstrap && window.bootstrap.Modal) || (window.tabler && window.tabler.Modal);
  if (!ModalClass) return null;
  try {
    return ModalClass.getOrCreateInstance ? ModalClass.getOrCreateInstance(modalEl) : (ModalClass.getInstance(modalEl) || new ModalClass(modalEl, { backdrop: true, keyboard: true }));
  } catch (e) {
    return null;
  }
}

function openModal(contentHtml, dialogSize = '') {
  const modalEl = document.getElementById('mainModal');
  const dialog = document.getElementById('mainModalDialog');
  if (dialog) dialog.className = 'modal-dialog modal-dialog-centered ' + dialogSize;
  const contentEl = document.getElementById('mainModalContent');
  if (contentEl) contentEl.innerHTML = contentHtml;

  try {
    const instance = getModalInstance();
    if (instance) {
      instance.show();
      return;
    }
  } catch (err) {
    console.warn('Bootstrap modal instance show failed:', err);
  }

  // Fallback if JS modal instance is unavailable
  if (modalEl) {
    modalEl.classList.add('show');
    modalEl.style.display = 'block';
    document.body.classList.add('modal-open');
    let backdrop = document.getElementById('custom-modal-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'custom-modal-backdrop';
      backdrop.className = 'modal-backdrop fade show';
      backdrop.onclick = closeModal;
      document.body.appendChild(backdrop);
    }
  }
}

function closeModal() {
  const modalEl = document.getElementById('mainModal');
  const video = modalEl?.querySelector('video');
  if (video) {
    try { video.pause(); video.src = ''; } catch(e){}
  }
  try {
    const instance = getModalInstance();
    if (instance) instance.hide();
  } catch (e) {}

  if (modalEl) {
    modalEl.classList.remove('show');
    modalEl.style.display = 'none';
    document.body.classList.remove('modal-open');
  }
  const customBackdrop = document.getElementById('custom-modal-backdrop');
  if (customBackdrop) customBackdrop.remove();
  document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
  const contentEl = document.getElementById('mainModalContent');
  if (contentEl) contentEl.innerHTML = '';
}

document.addEventListener('DOMContentLoaded', () => {
  const modalEl = document.getElementById('mainModal');
  if (modalEl) {
    modalEl.addEventListener('hidden.bs.modal', () => {
      const video = modalEl.querySelector('video');
      if (video) {
        try { video.pause(); video.src = ''; } catch(e){}
      }
      const contentEl = document.getElementById('mainModalContent');
      if (contentEl) contentEl.innerHTML = '';
    });
  }
});

// --- UTILITIES ---
function copyToClipboard(text) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast('Link copied to clipboard', 'info');
  }).catch(() => {
    showToast('Failed to copy to clipboard', 'warning');
  });
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `alert alert-${type} alert-important alert-dismissible toast-item mb-0 fade show`;
  toast.setAttribute('role', 'alert');
  toast.innerHTML = `
    <div class="d-flex align-items-center">
      <div class="flex-grow-1 small fw-medium">${escapeHtml(message)}</div>
      <button type="button" class="btn-close ms-2" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

function formatRelativeTime(isoStr) {
  if (!isoStr) return 'never';
  const diffSec = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (diffSec < 15) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  return `${Math.floor(diffHour / 24)}d ago`;
}

function format24Time(dateOrIso, includeSeconds = true) {
  if (!dateOrIso) return '-';
  const d = typeof dateOrIso === 'object' ? dateOrIso : new Date(dateOrIso);
  if (isNaN(d.getTime())) return '-';
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  if (!includeSeconds) return `${h}:${m}`;
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function mask24HourTime(input) {
  let val = input.value.replace(/[^0-9]/g, '');
  if (val.length > 4) val = val.slice(0, 4);
  if (val.length >= 3) {
    val = val.slice(0, 2) + ':' + val.slice(2);
  }
  input.value = val;
}

function validate24HourTime(input, defaultVal = '00:00') {
  let val = input.value.trim();
  if (!val) {
    input.value = defaultVal;
    return;
  }
  const parts = val.split(':');
  if (parts.length === 2) {
    let h = parseInt(parts[0], 10);
    let m = parseInt(parts[1], 10);
    if (!isNaN(h) && !isNaN(m)) {
      if (h < 0) h = 0;
      if (h > 23) h = 23;
      if (m < 0) m = 0;
      if (m > 59) m = 59;
      input.value = String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
      return;
    }
  } else if (parts.length === 1 && val.length <= 2) {
    let h = parseInt(val, 10);
    if (!isNaN(h)) {
      if (h < 0) h = 0;
      if (h > 23) h = 23;
      input.value = String(h).padStart(2, '0') + ':00';
      return;
    }
  }
  input.value = defaultVal;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

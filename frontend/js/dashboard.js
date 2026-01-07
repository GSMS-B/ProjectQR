/**
 * QRSecure - Dashboard JavaScript
 * Handles all dashboard functionality
 */

// State
let qrCodes = [];
let currentShortCode = null;
let timelineChart = null;
let devicesChart = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication
    const isAuth = await QRSecureAuth.requireAuth();
    if (!isAuth) return;

    // Setup navigation
    setupNavigation();

    // Setup forms
    setupForms();

    // Setup logout
    document.getElementById('logoutBtn').addEventListener('click', (e) => {
        e.preventDefault();
        QRSecureAuth.logout();
    });

    // Load initial data
    await loadQrCodes();
    updateOverviewStats();

    // Check URL params for redirect after create
    const params = new URLSearchParams(window.location.search);
    if (params.get('code')) {
        showSection('qrcodes');
    }
});

// Navigation
function setupNavigation() {
    document.querySelectorAll('.sidebar-nav-item[data-section]').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;
            showSection(section);
        });
    });
}

function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('main > section').forEach(s => s.style.display = 'none');

    // Show requested section
    const section = document.getElementById(`${sectionName}-section`);
    if (section) section.style.display = 'block';

    // Update nav active state
    document.querySelectorAll('.sidebar-nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.section === sectionName);
    });

    // Load section-specific data
    if (sectionName === 'analytics') {
        populateAnalyticsDropdown();
    }
}

// API Helpers
async function apiRequest(endpoint, options = {}) {
    const response = await fetch(endpoint, {
        ...options,
        headers: {
            ...QRSecureAuth.getAuthHeaders(),
            ...options.headers
        }
    });

    if (response.status === 401) {
        QRSecureAuth.logout();
        return null;
    }

    return response;
}

// Load QR Codes
async function loadQrCodes() {
    try {
        const response = await apiRequest('/api/qr/list');

        if (!response || !response.ok) {
            console.error('Failed to load QR codes');
            return;
        }

        const data = await response.json();
        qrCodes = data.qr_codes || [];

        renderQrCodesList();
        renderRecentQrCodes();

    } catch (error) {
        console.error('Error loading QR codes:', error);
    }
}

function renderQrCodesList() {
    const container = document.getElementById('qrCodesList');

    if (qrCodes.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 60px;">
                <p style="color: var(--text-muted); font-size: 1.125rem; margin-bottom: 16px;">No QR codes yet</p>
                <button class="btn btn-primary" onclick="showSection('create')">Create Your First QR Code</button>
            </div>
        `;
        return;
    }

    container.innerHTML = qrCodes.map(qr => `
        <div class="qr-card">
            <div class="qr-card-header">
                <span class="qr-card-title">${qr.custom_title || qr.short_code}</span>
                <span class="qr-card-status ${qr.is_active ? 'active' : 'inactive'}">
                    ${qr.is_active ? 'Active' : 'Inactive'}
                </span>
            </div>
            
            <img src="${qr.qr_image_url}" alt="QR Code" class="qr-card-image" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22120%22 height=%22120%22><rect fill=%22%23333%22 width=%22120%22 height=%22120%22/><text x=%2260%22 y=%2260%22 text-anchor=%22middle%22 fill=%22%23666%22>QR</text></svg>'">
            
            <p class="qr-card-url" title="${qr.destination}">${qr.destination}</p>
            
            <div class="qr-card-stats">
                <div class="qr-card-stat">
                    <div class="qr-card-stat-value">${qr.total_scans}</div>
                    <div class="qr-card-stat-label">Scans</div>
                </div>
                <div class="qr-card-stat">
                    <div class="qr-card-stat-value">${formatDate(qr.created_at)}</div>
                    <div class="qr-card-stat-label">Created</div>
                </div>
            </div>
            
            <div class="qr-card-actions">
                <button class="btn btn-sm btn-secondary" onclick="openEditModal('${qr.short_code}')">Edit</button>
                <a href="${qr.qr_image_url}" download="qr_${qr.short_code}.png" class="btn btn-sm btn-secondary">Download</a>
                <button class="btn btn-sm btn-secondary" onclick="viewAnalytics('${qr.short_code}')" style="display: flex; align-items: center; justify-content: center;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="20" x2="18" y2="10"></line>
                        <line x1="12" y1="20" x2="12" y2="4"></line>
                        <line x1="6" y1="20" x2="6" y2="14"></line>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

function renderRecentQrCodes() {
    const container = document.getElementById('recentQrCodes');
    const recent = qrCodes.slice(0, 5);

    if (recent.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted);">No QR codes yet. Create your first one!</p>';
        return;
    }

    container.innerHTML = `
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="border-bottom: 1px solid var(--border);">
                    <th style="text-align: left; padding: 12px 0; color: var(--text-muted); font-weight: 500;">Name</th>
                    <th style="text-align: left; padding: 12px 0; color: var(--text-muted); font-weight: 500;">Destination</th>
                    <th style="text-align: center; padding: 12px 0; color: var(--text-muted); font-weight: 500;">Scans</th>
                    <th style="text-align: right; padding: 12px 0; color: var(--text-muted); font-weight: 500;">Actions</th>
                </tr>
            </thead>
            <tbody>
                ${recent.map(qr => `
                    <tr style="border-bottom: 1px solid var(--border);">
                        <td style="padding: 16px 0;">${qr.custom_title || qr.short_code}</td>
                        <td style="padding: 16px 0; color: var(--text-muted); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${qr.destination}</td>
                        <td style="padding: 16px 0; text-align: center; color: var(--primary); font-weight: 600;">${qr.total_scans}</td>
                        <td style="padding: 16px 0; text-align: right;">
                            <button class="btn btn-sm btn-ghost" onclick="viewAnalytics('${qr.short_code}')">View</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function updateOverviewStats() {
    document.getElementById('totalQrCodes').textContent = qrCodes.length;
    document.getElementById('totalScans').textContent = qrCodes.reduce((sum, qr) => sum + qr.total_scans, 0);
    document.getElementById('activeQr').textContent = qrCodes.filter(qr => qr.is_active).length;
    // Scans today would need API call, using placeholder
    document.getElementById('scansToday').textContent = '-';
}

// Forms
function setupForms() {
    // Create QR Form
    document.getElementById('createQrForm').addEventListener('submit', handleCreateQr);

    // Edit QR Form
    document.getElementById('editQrForm').addEventListener('submit', handleEditQr);

    // Analytics dropdown
    document.getElementById('analyticsQrSelect').addEventListener('change', (e) => {
        if (e.target.value) {
            loadAnalytics(e.target.value);
        }
    });
}

async function handleCreateQr(e) {
    e.preventDefault();

    const url = document.getElementById('createUrl').value;
    const customTitle = document.getElementById('createTitle').value;
    const showPreview = document.getElementById('showPreview').checked;
    const analyticsEnabled = document.getElementById('enableAnalytics').checked;
    const qrColor = document.getElementById('qrColor').value;
    const qrBgColor = document.getElementById('qrBgColor').value;
    const expirationDays = document.getElementById('expirationDays').value;

    const body = {
        url,
        show_preview: showPreview,
        analytics_enabled: analyticsEnabled,
        qr_color: qrColor,
        qr_background: qrBgColor
    };

    if (customTitle) body.custom_title = customTitle;
    if (expirationDays) body.expiration_days = parseInt(expirationDays);

    try {
        const response = await apiRequest('/api/qr/create', {
            method: 'POST',
            body: JSON.stringify(body)
        });

        if (!response) return;

        const data = await response.json();

        if (response.ok) {
            // Show result and hide placeholder
            document.getElementById('qrResult').style.display = 'block';
            document.getElementById('qrPlaceholder').style.display = 'none';
            document.getElementById('qrImage').src = data.qr_image_url;
            document.getElementById('shortUrl').textContent = data.short_url;
            document.getElementById('downloadBtn').href = `/api/qr/${data.short_code}/download`;

            // Store for copy function
            currentShortCode = data.short_code;

            // Reload QR codes list
            await loadQrCodes();
            updateOverviewStats();

            // Reset form
            document.getElementById('createQrForm').reset();
        } else {
            showToast(data.detail || 'Error creating QR code', 'error');
        }
    } catch (error) {
        console.error('Create QR error:', error);
        showToast('Error creating QR code. Please try again.', 'error');
    }
}

async function handleEditQr(e) {
    e.preventDefault();

    const shortCode = document.getElementById('editShortCode').value;
    const url = document.getElementById('editUrl').value;
    const customTitle = document.getElementById('editTitle').value;
    const showPreview = document.getElementById('editShowPreview').checked;
    const analyticsEnabled = document.getElementById('editAnalytics').checked;

    const body = {
        url,
        show_preview: showPreview,
        analytics_enabled: analyticsEnabled
    };

    if (customTitle !== undefined) body.custom_title = customTitle;

    try {
        const response = await apiRequest(`/api/qr/${shortCode}`, {
            method: 'PUT',
            body: JSON.stringify(body)
        });

        if (!response) return;

        if (response.ok) {
            closeEditModal();
            await loadQrCodes();
            showToast('QR code updated successfully!', 'success');
        } else {
            const data = await response.json();
            showToast(data.detail || 'Error updating QR code', 'error');
        }
    } catch (error) {
        console.error('Edit QR error:', error);
        showToast('Error updating QR code. Please try again.', 'error');
    }
}

// Edit Modal
function openEditModal(shortCode) {
    const qr = qrCodes.find(q => q.short_code === shortCode);
    if (!qr) return;

    document.getElementById('editShortCode').value = shortCode;
    document.getElementById('editUrl').value = qr.destination;
    document.getElementById('editTitle').value = qr.custom_title || '';
    document.getElementById('editShowPreview').checked = qr.show_preview;
    document.getElementById('editAnalytics').checked = qr.analytics_enabled;

    document.getElementById('editModal').classList.add('active');
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
}

// Analytics
function populateAnalyticsDropdown() {
    const select = document.getElementById('analyticsQrSelect');
    select.innerHTML = '<option value="">Select a QR Code</option>' +
        qrCodes.map(qr => `<option value="${qr.short_code}">${qr.custom_title || qr.short_code}</option>`).join('');
}

function viewAnalytics(shortCode) {
    showSection('analytics');
    document.getElementById('analyticsQrSelect').value = shortCode;
    loadAnalytics(shortCode);
}

async function loadAnalytics(shortCode) {
    try {
        const response = await apiRequest(`/api/analytics/${shortCode}?days=30`);

        if (!response || !response.ok) {
            console.error('Failed to load analytics');
            return;
        }

        const data = await response.json();

        document.getElementById('analyticsPlaceholder').style.display = 'none';
        document.getElementById('analyticsContent').style.display = 'block';

        // Render timeline chart
        renderTimelineChart(data.timeline);

        // Render devices chart
        renderDevicesChart(data.devices);

        // Render locations list
        renderLocationsList(data.top_countries);

        // Render recent scans
        renderRecentScans(data.recent_scans);

    } catch (error) {
        console.error('Analytics error:', error);
    }
}

function renderTimelineChart(timeline) {
    const ctx = document.getElementById('timelineChart').getContext('2d');

    if (timelineChart) {
        timelineChart.destroy();
    }

    timelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: timeline.map(t => t.date),
            datasets: [{
                label: 'Scans',
                data: timeline.map(t => t.count),
                borderColor: '#FF6B2C',
                backgroundColor: 'rgba(255, 107, 44, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(0,0,0,0.05)' },
                    ticks: { color: '#666666', font: { family: "'JetBrains Mono', monospace" } }
                },
                y: {
                    grid: { color: 'rgba(0,0,0,0.05)' },
                    ticks: { color: '#666666', font: { family: "'JetBrains Mono', monospace" } },
                    beginAtZero: true
                }
            }
        }
    });
}

function renderDevicesChart(devices) {
    const ctx = document.getElementById('devicesChart').getContext('2d');

    if (devicesChart) {
        devicesChart.destroy();
    }

    const labels = Object.keys(devices);
    const values = Object.values(devices);

    devicesChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: ['#FF6B2C', '#1a1a1a', '#666666', '#10b981', '#f59e0b']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#666666',
                        font: { family: "'JetBrains Mono', monospace" }
                    }
                }
            }
        }
    });
}

function renderLocationsList(countries) {
    const container = document.getElementById('locationsList');

    if (!countries || countries.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted);">No location data yet</p>';
        return;
    }

    container.innerHTML = countries.slice(0, 10).map(([country, count], i) => `
        <div style="display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--border);">
            <span>${i + 1}. ${country}</span>
            <span style="color: var(--primary); font-weight: 600;">${count}</span>
        </div>
    `).join('');
}

function renderRecentScans(scans) {
    const container = document.getElementById('recentScansTable');

    if (!scans || scans.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted);">No scans yet</p>';
        return;
    }

    container.innerHTML = `
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="border-bottom: 1px solid var(--border);">
                    <th style="text-align: left; padding: 12px 0; color: var(--text-muted);">Time</th>
                    <th style="text-align: left; padding: 12px 0; color: var(--text-muted);">Location</th>
                    <th style="text-align: left; padding: 12px 0; color: var(--text-muted);">Device</th>
                    <th style="text-align: left; padding: 12px 0; color: var(--text-muted);">Browser</th>
                </tr>
            </thead>
            <tbody>
                ${scans.map(scan => `
                    <tr style="border-bottom: 1px solid var(--border);">
                        <td style="padding: 12px 0;">${formatDateTime(scan.scanned_at)}</td>
                        <td style="padding: 12px 0;">${scan.city || 'Unknown'}, ${scan.country || 'Unknown'}</td>
                        <td style="padding: 12px 0;">${scan.device || 'Unknown'}</td>
                        <td style="padding: 12px 0;">${scan.browser || 'Unknown'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Utilities
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatDateTime(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function copyToClipboard() {
    const qr = qrCodes.find(q => q.short_code === currentShortCode);
    if (qr) {
        navigator.clipboard.writeText(qr.short_url);
        showToast('URL copied to clipboard!', 'success');
    }
}

// Toast Notification System
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="#FF6B2C" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>
    `;

    container.appendChild(toast);

    // Auto remove after 4 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 4000);
}

// Mobile Sidebar Toggle
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

// Make functions globally available
window.showSection = showSection;
window.openEditModal = openEditModal;
window.closeEditModal = closeEditModal;
window.viewAnalytics = viewAnalytics;
window.copyToClipboard = copyToClipboard;
window.showToast = showToast;
window.toggleSidebar = toggleSidebar;

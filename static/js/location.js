/**
 * Hydria - Client-Side Geolocation & Interactive Helpers
 * Pure Vanilla JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    initGeolocation();
    initImagePreview();
    initVoteButtons();
});

/**
 * Automatically detects location using browser's navigator.geolocation API
 */
function initGeolocation() {
    const statusBox = document.getElementById('location-status');
    const latInput = document.getElementById('latitude-input');
    const lonInput = document.getElementById('longitude-input');
    const manualContainer = document.getElementById('manual-location-container');
    const manualLatInput = document.getElementById('manual-lat-input');
    const manualLonInput = document.getElementById('manual-lon-input');
    const toggleManualBtn = document.getElementById('toggle-manual-loc-btn');
    const confirmManualBtn = document.getElementById('confirm-manual-coords-btn');

    if (!statusBox || !latInput || !lonInput) {
        return; // Not on the report page
    }

    // Toggle manual coordinates container
    if (toggleManualBtn && manualContainer) {
        toggleManualBtn.addEventListener('click', () => {
            const isHidden = manualContainer.style.display === 'none';
            manualContainer.style.display = isHidden ? 'block' : 'none';
            toggleManualBtn.textContent = isHidden ? 'Hide Manual Entry' : 'Manual Coordinates';
        });
    }

    // Apply manual coordinates button
    if (confirmManualBtn) {
        confirmManualBtn.addEventListener('click', () => {
            const latVal = parseFloat(manualLatInput.value);
            const lonVal = parseFloat(manualLonInput.value);
            if (isNaN(latVal) || isNaN(lonVal)) {
                alert("Please enter valid numeric latitude and longitude coordinates.");
                return;
            }
            showLocationSuccess(latVal.toFixed(6), lonVal.toFixed(6), 'Manual Entry');
            if (manualContainer) {
                manualContainer.style.display = 'none';
            }
            if (toggleManualBtn) {
                toggleManualBtn.textContent = 'Manual Coordinates';
            }
        });
    }

    // Helper: update UI on successful location acquisition or manual entry
    window.showLocationSuccess = function(lat, lon, label) {
        latInput.value = lat;
        lonInput.value = lon;
        if (manualLatInput) manualLatInput.value = lat;
        if (manualLonInput) manualLonInput.value = lon;

        statusBox.className = 'location-box location-detected';
        statusBox.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;">
                <div>
                    <div style="font-weight: 700; color: #166534; display: flex; align-items: center; gap: 0.4rem;">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#166534" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                        <span>Location Confirmed (${label || 'Browser GPS'})</span>
                    </div>
                    <div style="font-size: 0.88rem; color: #15803d; margin-top: 0.2rem;">
                        <strong>Latitude:</strong> ${lat}° N &nbsp;|&nbsp; <strong>Longitude:</strong> ${lon}° E
                    </div>
                </div>
                <div style="display: flex; gap: 0.5rem;">
                    <button type="button" id="change-location-btn" class="btn btn-secondary btn-sm" style="padding: 0.35rem 0.75rem; font-size: 0.82rem;">
                        Change
                    </button>
                    <button type="button" id="refresh-gps-btn" class="btn btn-secondary btn-sm" style="padding: 0.35rem 0.75rem; font-size: 0.82rem;" title="Re-detect GPS">
                        Update GPS
                    </button>
                </div>
            </div>
        `;

        const changeBtn = document.getElementById('change-location-btn');
        if (changeBtn && manualContainer) {
            changeBtn.addEventListener('click', () => {
                manualContainer.style.display = 'block';
                if (toggleManualBtn) toggleManualBtn.textContent = 'Hide Manual Entry';
            });
        }

        const refreshGpsBtn = document.getElementById('refresh-gps-btn');
        if (refreshGpsBtn) {
            refreshGpsBtn.addEventListener('click', detectLocation);
        }
    };

    // Helper: global preset helper
    window.applyPresetLocation = function(lat, lon, label) {
        showLocationSuccess(Number(lat).toFixed(6), Number(lon).toFixed(6), label);
        if (manualContainer) {
            manualContainer.style.display = 'none';
        }
        if (toggleManualBtn) {
            toggleManualBtn.textContent = 'Manual Coordinates';
        }
    };

    function detectLocation() {
        if (!navigator.geolocation) {
            showLocationError("Your browser does not support automatic geolocation. Please enter coordinates manually below.");
            return;
        }

        statusBox.className = 'location-box';
        statusBox.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.6rem;">
                <span class="location-pulse-dot"></span>
                <span style="font-size: 0.92rem; color: var(--text-secondary);">Detecting your location...</span>
            </div>
        `;

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude.toFixed(6);
                const lon = position.coords.longitude.toFixed(6);
                showLocationSuccess(lat, lon, 'Device GPS');
            },
            (error) => {
                let errorMsg = "Please allow location access or enter coordinates manually below.";
                if (error.code === error.PERMISSION_DENIED) {
                    errorMsg = "Location permission was denied in your browser. You can enter coordinates manually or choose a preset below.";
                } else if (error.code === error.POSITION_UNAVAILABLE) {
                    errorMsg = "Location information is currently unavailable. Enter coordinates manually below.";
                } else if (error.code === error.TIMEOUT) {
                    errorMsg = "Location detection timed out. Please enter coordinates manually or retry.";
                }

                showLocationError(errorMsg);
            },
            {
                enableHighAccuracy: true,
                timeout: 8000,
                maximumAge: 60000
            }
        );
    }

    function showLocationError(errorMsg) {
        statusBox.className = 'location-box location-error';
        statusBox.innerHTML = `
            <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap;">
                <div>
                    <div style="font-weight: 700; color: #991b1b; margin-bottom: 0.2rem;">Location could not be detected</div>
                    <div style="font-size: 0.88rem; color: #b91c1c; line-height: 1.4;">${errorMsg}</div>
                </div>
                <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                    <button type="button" id="retry-location-btn-inner" class="btn btn-secondary btn-sm" style="padding: 0.35rem 0.75rem; font-size: 0.82rem; display: inline-flex; align-items: center; gap: 0.35rem;">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="23 4 23 10 17 10"/>
                            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                        </svg>
                        <span>Retry</span>
                    </button>
                    <button type="button" id="open-manual-btn-inner" class="btn btn-primary btn-sm" style="padding: 0.35rem 0.75rem; font-size: 0.82rem;">
                        Enter Manually
                    </button>
                </div>
            </div>
        `;

        // Automatically open manual input container when error occurs so user isn't stuck
        if (manualContainer) {
            manualContainer.style.display = 'block';
            if (toggleManualBtn) toggleManualBtn.textContent = 'Hide Manual Entry';
        }

        const retryInner = document.getElementById('retry-location-btn-inner');
        if (retryInner) {
            retryInner.addEventListener('click', detectLocation);
        }

        const openManualInner = document.getElementById('open-manual-btn-inner');
        if (openManualInner && manualContainer) {
            openManualInner.addEventListener('click', () => {
                manualContainer.style.display = 'block';
                if (manualLatInput) manualLatInput.focus();
            });
        }
    }

    // If coordinates already present, display confirmed state immediately
    if (latInput.value && lonInput.value) {
        showLocationSuccess(latInput.value, lonInput.value, 'Saved Coordinates');
    } else {
        detectLocation();
    }
}

/**
 * Handles image selection and displays an instant image preview
 */
function initImagePreview() {
    const fileInput = document.getElementById('image-input');
    const previewContainer = document.getElementById('preview-container');
    const previewImg = document.getElementById('image-preview');

    if (!fileInput || !previewContainer || !previewImg) {
        return;
    }

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) {
            // Check file size (5MB)
            if (file.size > 5 * 1024 * 1024) {
                alert("File size exceeds 5 MB. Please select a smaller photo.");
                fileInput.value = '';
                previewContainer.style.display = 'none';
                return;
            }

            const reader = new FileReader();
            reader.onload = (e) => {
                previewImg.src = e.target.result;
                previewContainer.style.display = 'block';
            };
            reader.readAsDataURL(file);
        } else {
            previewContainer.style.display = 'none';
        }
    });
}

/**
 * Enables smooth voting ("I observed this too") via AJAX
 */
function initVoteButtons() {
    const voteForms = document.querySelectorAll('.vote-form-ajax');
    voteForms.forEach((form) => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const actionUrl = form.action;
            const submitBtn = form.querySelector('.btn-vote');
            const voteCountDisplay = form.querySelector('.vote-count');

            try {
                const response = await fetch(actionUrl, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (response.redirected) {
                    window.location.href = response.url;
                    return;
                }

                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        if (submitBtn) {
                            submitBtn.innerHTML = data.label;
                            if (data.voted) {
                                submitBtn.classList.add('voted');
                            } else {
                                submitBtn.classList.remove('voted');
                            }
                        }
                        if (voteCountDisplay) {
                            voteCountDisplay.textContent = data.total_votes;
                        }
                    }
                } else if (response.status === 401) {
                    window.location.href = '/login';
                }
            } catch (err) {
                // If fetch fails, fall back to native form submission
                form.submit();
            }
        });
    });
}

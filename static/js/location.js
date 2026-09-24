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
    const retryBtn = document.getElementById('retry-location-btn');

    if (!statusBox || !latInput || !lonInput) {
        return; // Not on the report page
    }

    function detectLocation() {
        if (!navigator.geolocation) {
            statusBox.className = 'location-box location-error';
            statusBox.innerHTML = `
                <div style="font-weight: 600; margin-bottom: 0.25rem;">Location not supported</div>
                <div style="font-size: 0.9rem;">Your browser does not support automatic geolocation.</div>
            `;
            return;
        }

        statusBox.className = 'location-box';
        statusBox.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span class="spinner" style="font-size: 1.2rem;">⏳</span>
                <span>Detecting your location...</span>
            </div>
        `;

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude.toFixed(6);
                const lon = position.coords.longitude.toFixed(6);
                latInput.value = lat;
                lonInput.value = lon;

                statusBox.className = 'location-box location-detected';
                statusBox.innerHTML = `
                    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem;">
                        <div>
                            <div style="font-weight: 700; color: #166534; margin-bottom: 0.2rem;">✓ Location detected</div>
                            <div style="font-size: 0.9rem; color: #15803d;">
                                <strong>Latitude:</strong> ${lat} &nbsp;|&nbsp; <strong>Longitude:</strong> ${lon}
                            </div>
                        </div>
                        <button type="button" id="refresh-location-btn" class="btn btn-secondary" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;">
                            Update
                        </button>
                    </div>
                `;

                // Add refresh listener
                const refreshBtn = document.getElementById('refresh-location-btn');
                if (refreshBtn) {
                    refreshBtn.addEventListener('click', detectLocation);
                }
            },
            (error) => {
                let errorMsg = "Please enable location permission and try again.";
                if (error.code === error.PERMISSION_DENIED) {
                    errorMsg = "Location permission was denied. Please allow location access in your browser settings to continue.";
                } else if (error.code === error.POSITION_UNAVAILABLE) {
                    errorMsg = "Location information is currently unavailable.";
                } else if (error.code === error.TIMEOUT) {
                    errorMsg = "Location detection timed out.";
                }

                statusBox.className = 'location-box location-error';
                statusBox.innerHTML = `
                    <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap;">
                        <div>
                            <div style="font-weight: 700; color: #991b1b; margin-bottom: 0.2rem;">Location could not be detected</div>
                            <div style="font-size: 0.9rem; color: #b91c1c;">${errorMsg}</div>
                        </div>
                        <button type="button" id="retry-location-btn-inner" class="btn btn-secondary" style="padding: 0.4rem 0.85rem; font-size: 0.85rem;">
                            🔄 Retry Location
                        </button>
                    </div>
                `;

                const retryInner = document.getElementById('retry-location-btn-inner');
                if (retryInner) {
                    retryInner.addEventListener('click', detectLocation);
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000
            }
        );
    }

    // Run automatically on page open if coordinates not already present
    if (!latInput.value || !lonInput.value) {
        detectLocation();
    }

    if (retryBtn) {
        retryBtn.addEventListener('click', detectLocation);
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

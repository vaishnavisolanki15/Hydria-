/**
 * Hydria - Client-Side Interactive Location Tracer, Autocomplete & Map Helpers
 * Pure Vanilla JavaScript with Leaflet.js integration
 */

document.addEventListener('DOMContentLoaded', () => {
    initGeolocation();
    initImagePreview();
    initVoteButtons();
});

/**
 * Initializes the Interactive Leaflet Map, Live Search Autocomplete, and Geolocation
 */
function initGeolocation() {
    const mapElement = document.getElementById('location-map');
    const latInput = document.getElementById('latitude-input');
    const lonInput = document.getElementById('longitude-input');
    const searchInput = document.getElementById('manual-address-input');
    const searchBtn = document.getElementById('search-address-btn');
    const clearBtn = document.getElementById('loc-clear-btn');
    const gpsBtn = document.getElementById('btn-locate-gps');
    const dropdown = document.getElementById('autocomplete-dropdown');
    const feedback = document.getElementById('address-search-feedback');
    const statusChip = document.getElementById('loc-status-chip');
    const statusText = document.getElementById('loc-status-text');
    const verifiedCard = document.getElementById('loc-verified-card');
    const verifiedTitle = document.getElementById('loc-verified-title');
    const valLat = document.getElementById('val-lat');
    const valLon = document.getElementById('val-lon');
    const recenterBtn = document.getElementById('btn-recenter-map');
    const waterBodyNameInput = document.getElementById('water_body_name');
    const waterBodyTypeInput = document.getElementById('water_body_type');
    const toggleExactCoordsBtn = document.getElementById('toggle-exact-coords-btn');
    const exactCoordsDrawer = document.getElementById('exact-coords-drawer');
    const coordsArrow = document.getElementById('coords-arrow');
    const manualLatInput = document.getElementById('manual-lat-input');
    const manualLonInput = document.getElementById('manual-lon-input');
    const confirmManualCoordsBtn = document.getElementById('confirm-manual-coords-btn');
    const reportForm = document.getElementById('report-form');

    if (!mapElement || !latInput || !lonInput) {
        return; // Not on the report page
    }

    let map = null;
    let marker = null;
    let debounceTimer = null;
    let activeSuggestionIndex = -1;
    let currentSuggestions = [];

    // Custom animated map pin icon
    const customPinIcon = (typeof L !== 'undefined') ? L.divIcon({
        className: 'custom-map-pin',
        html: '<div class="custom-pin-pulse"></div>',
        iconSize: [22, 22],
        iconAnchor: [11, 11]
    }) : null;

    // -------------------------------------------------------------
    // 1. Initialize Leaflet Map
    // -------------------------------------------------------------
    try {
        if (typeof L !== 'undefined') {
            const initialLat = parseFloat(latInput.value) || 22.7196;
            const initialLon = parseFloat(lonInput.value) || 75.8577;
            const initialZoom = (latInput.value && lonInput.value) ? 14 : 5;

            map = L.map('location-map', {
                zoomControl: true,
                scrollWheelZoom: false
            }).setView([initialLat, initialLon], initialZoom);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'
            }).addTo(map);

            // User clicks anywhere on the map to pinpoint water body location
            map.on('click', (e) => {
                const clickedLat = e.latlng.lat;
                const clickedLon = e.latlng.lng;
                traceLocation(clickedLat, clickedLon, null, false);
                reverseGeocodeLocation(clickedLat, clickedLon);
            });

            // Re-render map tiles correctly if container size changes
            setTimeout(() => {
                map.invalidateSize();
            }, 300);
        }
    } catch (e) {
        console.warn('Map initialization failed:', e);
    }

    // -------------------------------------------------------------
    // 2. Core Location Tracing Function
    // -------------------------------------------------------------
    function traceLocation(lat, lon, displayName, autoZoom = true, rawName = null) {
        const numLat = parseFloat(lat);
        const numLon = parseFloat(lon);
        if (isNaN(numLat) || isNaN(numLon)) return;

        const formattedLat = numLat.toFixed(6);
        const formattedLon = numLon.toFixed(6);

        // Update hidden inputs submitted with form
        latInput.value = formattedLat;
        lonInput.value = formattedLon;

        // Update manual direct coordinate inputs
        if (manualLatInput) manualLatInput.value = formattedLat;
        if (manualLonInput) manualLonInput.value = formattedLon;

        // Update map marker
        if (map && typeof L !== 'undefined') {
            if (marker) {
                marker.setLatLng([numLat, numLon]);
            } else {
                marker = L.marker([numLat, numLon], {
                    icon: customPinIcon,
                    draggable: true
                }).addTo(map);

                // Dragging the marker updates coordinates & triggers reverse geocode
                marker.on('dragend', () => {
                    const pos = marker.getLatLng();
                    traceLocation(pos.lat, pos.lng, null, false);
                    reverseGeocodeLocation(pos.lat, pos.lng);
                });
            }

            if (autoZoom) {
                map.flyTo([numLat, numLon], 15, {
                    animate: true,
                    duration: 1.2
                });
            }
        }

        // Update UI status chip
        if (statusChip && statusText) {
            statusChip.className = 'loc-status-chip traced';
            statusText.textContent = '✓ Location Traced';
        }

        // Update verified confirmation card
        if (verifiedCard && verifiedTitle && valLat && valLon) {
            verifiedCard.style.display = 'flex';
            verifiedTitle.textContent = displayName || `Traced Water Body (${numLat.toFixed(4)}°, ${numLon.toFixed(4)}°)`;
            valLat.textContent = `${formattedLat}° N`;
            valLon.textContent = `${formattedLon}° E`;
        }

        // Hide feedback alert if previously shown
        hideFeedback();

        // Intelligently infer water body name and type if empty
        const titleToCheck = (rawName || displayName || (searchInput ? searchInput.value : '')).toLowerCase();
        if (waterBodyNameInput && !waterBodyNameInput.value.trim() && rawName) {
            waterBodyNameInput.value = rawName;
        }

        if (waterBodyTypeInput && (!waterBodyTypeInput.value || waterBodyTypeInput.value === '')) {
            if (titleToCheck.includes('lake') || titleToCheck.includes('tal') || titleToCheck.includes('sagar')) {
                waterBodyTypeInput.value = 'Lake';
            } else if (titleToCheck.includes('river') || titleToCheck.includes('nadi') || titleToCheck.includes('ganga') || titleToCheck.includes('yamuna')) {
                waterBodyTypeInput.value = 'River';
            } else if (titleToCheck.includes('pond') || titleToCheck.includes('pokhar') || titleToCheck.includes('kund')) {
                waterBodyTypeInput.value = 'Pond';
            } else if (titleToCheck.includes('canal') || titleToCheck.includes('drain')) {
                waterBodyTypeInput.value = 'Canal';
            } else if (titleToCheck.includes('stream') || titleToCheck.includes('nala')) {
                waterBodyTypeInput.value = 'Stream';
            }
        }
    }

    // Expose traceLocation for global pill clicks
    window.traceLocationOnMap = traceLocation;

    // -------------------------------------------------------------
    // 3. Reverse Geocoding (Lat/Lon -> Readable Place Name)
    // -------------------------------------------------------------
    function reverseGeocodeLocation(lat, lon) {
        fetch(`/api/geocode/reverse?lat=${lat}&lon=${lon}`)
            .then(res => res.json())
            .then(data => {
                if (data && data.success && data.display_name) {
                    if (verifiedTitle) {
                        verifiedTitle.textContent = data.display_name;
                    }
                    if (searchInput && (!searchInput.value || searchInput.value.startsWith('Pinned Location'))) {
                        searchInput.value = data.display_name;
                        if (clearBtn) clearBtn.style.display = 'block';
                    }
                }
            })
            .catch(err => {
                console.warn('Reverse geocode error:', err);
            });
    }

    // -------------------------------------------------------------
    // 4. Autocomplete Search Dropdown (Search-as-you-type)
    // -------------------------------------------------------------
    if (searchInput && dropdown) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();

            if (clearBtn) {
                clearBtn.style.display = query ? 'block' : 'none';
            }

            if (query.length < 2) {
                closeAutocomplete();
                return;
            }

            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                fetchSuggestions(query);
            }, 250);
        });

        // Keyboard navigation for autocomplete list
        searchInput.addEventListener('keydown', (e) => {
            if (!dropdown || dropdown.style.display === 'none') {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    executeSearch(searchInput.value.trim());
                }
                return;
            }

            const items = dropdown.querySelectorAll('.loc-autocomplete-item');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeSuggestionIndex = (activeSuggestionIndex + 1) % items.length;
                updateActiveSuggestion(items);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeSuggestionIndex = (activeSuggestionIndex - 1 + items.length) % items.length;
                updateActiveSuggestion(items);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (activeSuggestionIndex >= 0 && items[activeSuggestionIndex]) {
                    items[activeSuggestionIndex].click();
                } else {
                    executeSearch(searchInput.value.trim());
                }
            } else if (e.key === 'Escape') {
                closeAutocomplete();
            }
        });

        // Clear button click
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                searchInput.value = '';
                clearBtn.style.display = 'none';
                closeAutocomplete();
                searchInput.focus();
            });
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                closeAutocomplete();
            }
        });
    }

    function fetchSuggestions(query) {
        if (statusChip && statusText) {
            statusChip.className = 'loc-status-chip tracing';
            statusText.textContent = 'Searching places...';
        }

        fetch(`/api/geocode/suggest?q=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(data => {
                if (statusChip && statusText && (!latInput.value || !lonInput.value)) {
                    statusChip.className = 'loc-status-chip untraced';
                    statusText.textContent = 'Location Not Traced';
                }

                if (data && data.success && data.results && data.results.length > 0) {
                    currentSuggestions = data.results;
                    renderAutocompleteDropdown(data.results);
                } else {
                    closeAutocomplete();
                }
            })
            .catch(err => {
                console.warn('Autocomplete fetch failed:', err);
                closeAutocomplete();
            });
    }

    function renderAutocompleteDropdown(results) {
        if (!dropdown) return;
        dropdown.innerHTML = '';
        activeSuggestionIndex = -1;

        results.forEach((item, index) => {
            const row = document.createElement('div');
            row.className = 'loc-autocomplete-item';
            row.dataset.index = index;

            const icon = item.is_water ? '🌊' : '📍';
            const badgeText = item.is_water ? 'Water Body' : 'Place';

            row.innerHTML = `
                <span class="loc-item-icon">${icon}</span>
                <div class="loc-item-text">
                    <div class="loc-item-title">${escapeHtml(item.name || item.display_name)}</div>
                    <div class="loc-item-subtitle">${escapeHtml(item.display_name)}</div>
                </div>
                <span class="loc-item-badge">${badgeText}</span>
            `;

            row.addEventListener('click', () => {
                if (searchInput) {
                    searchInput.value = item.display_name;
                    if (clearBtn) clearBtn.style.display = 'block';
                }
                closeAutocomplete();
                traceLocation(item.lat, item.lon, item.display_name, true, item.name);
            });

            dropdown.appendChild(row);
        });

        dropdown.style.display = 'block';
    }

    function updateActiveSuggestion(items) {
        items.forEach((it, idx) => {
            if (idx === activeSuggestionIndex) {
                it.classList.add('active');
                it.scrollIntoView({ block: 'nearest' });
            } else {
                it.classList.remove('active');
            }
        });
    }

    function closeAutocomplete() {
        if (dropdown) {
            dropdown.style.display = 'none';
            dropdown.innerHTML = '';
        }
        activeSuggestionIndex = -1;
    }

    function escapeHtml(str) {
        return (str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // -------------------------------------------------------------
    // 5. Search Button Click & Direct Geocoding
    // -------------------------------------------------------------
    function executeSearch(query) {
        closeAutocomplete();
        const address = (query || (searchInput ? searchInput.value : '')).trim();
        if (!address) {
            showFeedback("Please type a place, lake, or city name first.", "warning");
            if (searchInput) searchInput.focus();
            return;
        }

        if (searchBtn) {
            searchBtn.disabled = true;
            searchBtn.innerHTML = '<span>Tracing...</span>';
        }

        if (statusChip && statusText) {
            statusChip.className = 'loc-status-chip tracing';
            statusText.textContent = 'Tracing coordinates...';
        }

        fetch(`/api/geocode?q=${encodeURIComponent(address)}`)
            .then(res => res.json())
            .then(data => {
                if (searchBtn) {
                    searchBtn.disabled = false;
                    searchBtn.innerHTML = '<span>Find &amp; Trace</span> <span>📍</span>';
                }

                if (data && data.success && data.lat && data.lon) {
                    traceLocation(data.lat, data.lon, data.display_name, true, address);
                    if (searchInput) searchInput.value = data.display_name;
                    showFeedback(`✓ Traced: ${data.display_name}`, "success");
                } else {
                    const msg = data && data.message ? data.message : `Could not trace location for "${address}". Please try a nearby area or click directly on the map.`;
                    showFeedback(msg, "warning");
                    if (statusChip && statusText && (!latInput.value || !lonInput.value)) {
                        statusChip.className = 'loc-status-chip untraced';
                        statusText.textContent = 'Location Not Found';
                    }
                }
            })
            .catch(err => {
                if (searchBtn) {
                    searchBtn.disabled = false;
                    searchBtn.innerHTML = '<span>Find &amp; Trace</span> <span>📍</span>';
                }
                showFeedback("Connection issue tracing location. You can click directly on the map to pinpoint.", "warning");
            });
    }

    if (searchBtn) {
        searchBtn.addEventListener('click', () => {
            executeSearch(searchInput ? searchInput.value.trim() : '');
        });
    }

    // -------------------------------------------------------------
    // 6. Device GPS Location Detection
    // -------------------------------------------------------------
    if (gpsBtn) {
        gpsBtn.addEventListener('click', () => {
            if (!navigator.geolocation) {
                showFeedback("Your browser does not support GPS. You can search or click directly on the map.", "info");
                return;
            }

            gpsBtn.disabled = true;
            gpsBtn.innerHTML = '<span>Acquiring GPS...</span>';

            if (statusChip && statusText) {
                statusChip.className = 'loc-status-chip tracing';
                statusText.textContent = 'Acquiring GPS...';
            }

            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    gpsBtn.disabled = false;
                    gpsBtn.innerHTML = '<span>🛰️</span> <span>Use GPS</span>';
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    traceLocation(lat, lon, "Your Device Location (GPS)", true);
                    reverseGeocodeLocation(lat, lon);
                    showFeedback("✓ Live device GPS location acquired and traced!", "success");
                },
                (err) => {
                    gpsBtn.disabled = false;
                    gpsBtn.innerHTML = '<span>🛰️</span> <span>Use GPS</span>';

                    let errorMsg = "GPS access was not permitted. You can type any place name above or click directly on the map.";
                    if (err.code === err.TIMEOUT) {
                        errorMsg = "GPS detection timed out. Please type your location or click on the map.";
                    }
                    showFeedback(errorMsg, "info");

                    if (statusChip && statusText && (!latInput.value || !lonInput.value)) {
                        statusChip.className = 'loc-status-chip untraced';
                        statusText.textContent = 'GPS Unavailable';
                    }
                },
                {
                    enableHighAccuracy: true,
                    timeout: 8000,
                    maximumAge: 60000
                }
            );
        });
    }

    // -------------------------------------------------------------
    // 7. Popular Preset Helpers
    // -------------------------------------------------------------
    window.tracePopularPlace = function(name, lat, lon, type) {
        if (searchInput) {
            searchInput.value = name;
            if (clearBtn) clearBtn.style.display = 'block';
        }
        traceLocation(lat, lon, name, true, name);
        if (type && waterBodyTypeInput) {
            waterBodyTypeInput.value = type;
        }
        if (waterBodyNameInput && (!waterBodyNameInput.value || waterBodyNameInput.value === '')) {
            waterBodyNameInput.value = name.split(',')[0];
        }
    };

    // Re-center button on verified card
    if (recenterBtn) {
        recenterBtn.addEventListener('click', () => {
            const curLat = parseFloat(latInput.value);
            const curLon = parseFloat(lonInput.value);
            if (!isNaN(curLat) && !isNaN(curLon) && map) {
                map.flyTo([curLat, curLon], 15, { animate: true });
            }
        });
    }

    // Backward compatibility helper functions
    window.searchForAddress = function(query) {
        if (searchInput) searchInput.value = query;
        executeSearch(query);
    };

    window.applyPresetLocation = function(lat, lon, label) {
        traceLocation(lat, lon, label, true, label);
    };

    // -------------------------------------------------------------
    // 8. Collapsible Numeric Coordinates
    // -------------------------------------------------------------
    if (toggleExactCoordsBtn && exactCoordsDrawer) {
        toggleExactCoordsBtn.addEventListener('click', () => {
            const isClosed = exactCoordsDrawer.style.display === 'none';
            exactCoordsDrawer.style.display = isClosed ? 'block' : 'none';
            if (coordsArrow) coordsArrow.textContent = isClosed ? '▲' : '▼';
        });
    }

    if (confirmManualCoordsBtn) {
        confirmManualCoordsBtn.addEventListener('click', () => {
            const latVal = parseFloat(manualLatInput ? manualLatInput.value : '');
            const lonVal = parseFloat(manualLonInput ? manualLonInput.value : '');
            if (isNaN(latVal) || isNaN(lonVal)) {
                alert("Please enter valid numeric latitude and longitude coordinates.");
                return;
            }
            traceLocation(latVal, lonVal, `Manual Coordinates (${latVal.toFixed(4)}, ${lonVal.toFixed(4)})`, true);
            reverseGeocodeLocation(latVal, lonVal);
            showFeedback(`✓ Coordinates set to (${latVal.toFixed(5)}, ${lonVal.toFixed(5)})`, "success");
        });
    }

    // -------------------------------------------------------------
    // 9. Feedback Notification Helper
    // -------------------------------------------------------------
    function showFeedback(text, type) {
        if (!feedback) return;
        feedback.style.display = 'block';
        if (type === 'success') {
            feedback.style.background = '#f0fdf4';
            feedback.style.border = '1px solid #86efac';
            feedback.style.color = '#166534';
        } else if (type === 'warning' || type === 'error') {
            feedback.style.background = '#fffbeb';
            feedback.style.border = '1px solid #fde68a';
            feedback.style.color = '#92400e';
        } else {
            feedback.style.background = '#f0f9ff';
            feedback.style.border = '1px solid #bae6fd';
            feedback.style.color = '#0369a1';
        }
        feedback.innerHTML = text;
    }

    function hideFeedback() {
        if (feedback) feedback.style.display = 'none';
    }

    // -------------------------------------------------------------
    // 10. Form Validation on Submit
    // -------------------------------------------------------------
    if (reportForm) {
        reportForm.addEventListener('submit', (e) => {
            if (!latInput.value || !lonInput.value) {
                e.preventDefault();
                showFeedback("⚠️ Please select or trace the water body location on the map before submitting.", "warning");
                if (searchInput) {
                    searchInput.focus();
                    searchInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });
    }

    // -------------------------------------------------------------
    // 11. Initial State Restoration & Draft Auto-Save
    // -------------------------------------------------------------
    const DRAFT_KEY = 'hydria_report_draft';
    const draftNotice = document.getElementById('draft-notice');
    const clearDraftBtn = document.getElementById('btn-clear-draft');

    function saveDraft() {
        try {
            const deadFishEl = document.querySelector('input[name="dead_fish"]:checked');
            const draft = {
                water_body_name: waterBodyNameInput ? waterBodyNameInput.value : '',
                water_body_type: waterBodyTypeInput ? waterBodyTypeInput.value : '',
                latitude: latInput.value,
                longitude: lonInput.value,
                address: searchInput ? searchInput.value : '',
                water_colour: document.getElementById('water_colour') ? document.getElementById('water_colour').value : '',
                smell: document.getElementById('smell') ? document.getElementById('smell').value : '',
                algae: document.getElementById('algae') ? document.getElementById('algae').value : '',
                visible_waste: document.getElementById('visible_waste') ? document.getElementById('visible_waste').value : '',
                water_appearance: document.getElementById('water_appearance') ? document.getElementById('water_appearance').value : '',
                dead_fish: deadFishEl ? deadFishEl.value : 'No',
                additional_observation: document.getElementById('additional_observation') ? document.getElementById('additional_observation').value : '',
                saved_at: Date.now()
            };
            // Only save if at least one meaningful field has been filled
            if (draft.water_body_name || draft.latitude || draft.water_body_type || draft.water_colour || draft.smell || draft.address) {
                localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
            }
        } catch (e) {
            // localStorage might be unavailable or restricted
        }
    }

    // Auto-save on any change or typing in the form
    if (reportForm) {
        reportForm.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(saveDraft, 400);
        });
        reportForm.addEventListener('change', saveDraft);
    }

    // If server passed retained coordinates (e.g. from missing fields validation), use those
    if (latInput.value && lonInput.value) {
        traceLocation(latInput.value, lonInput.value, searchInput ? searchInput.value : 'Retained Location', false);
    } else {
        // Otherwise restore from localStorage draft if available
        try {
            const savedDraftJson = localStorage.getItem(DRAFT_KEY);
            if (savedDraftJson) {
                const draft = JSON.parse(savedDraftJson);
                let restoredAny = false;

                if (draft.water_body_name && waterBodyNameInput && !waterBodyNameInput.value) {
                    waterBodyNameInput.value = draft.water_body_name;
                    restoredAny = true;
                }
                if (draft.water_body_type && waterBodyTypeInput && !waterBodyTypeInput.value) {
                    waterBodyTypeInput.value = draft.water_body_type;
                    restoredAny = true;
                }
                if (draft.address && searchInput && !searchInput.value) {
                    searchInput.value = draft.address;
                }
                
                ['water_colour', 'smell', 'algae', 'visible_waste', 'water_appearance', 'additional_observation'].forEach(fieldId => {
                    const el = document.getElementById(fieldId);
                    if (el && draft[fieldId] && !el.value) {
                        el.value = draft[fieldId];
                        restoredAny = true;
                    }
                });

                if (draft.dead_fish) {
                    const radio = document.querySelector(`input[name="dead_fish"][value="${draft.dead_fish}"]`);
                    if (radio) radio.checked = true;
                }

                if (draft.latitude && draft.longitude) {
                    traceLocation(draft.latitude, draft.longitude, draft.address || draft.water_body_name || 'Restored Location', true, draft.water_body_name);
                    restoredAny = true;
                }

                if (restoredAny && draftNotice) {
                    draftNotice.style.display = 'flex';
                }
            }
        } catch (e) {
            console.warn('Draft restoration error:', e);
        }
    }

    // Discard draft button
    if (clearDraftBtn) {
        clearDraftBtn.addEventListener('click', () => {
            try {
                localStorage.removeItem(DRAFT_KEY);
            } catch (e) {}
            if (draftNotice) draftNotice.style.display = 'none';
            if (reportForm) reportForm.reset();
            latInput.value = '';
            lonInput.value = '';
            if (searchInput) searchInput.value = '';
            if (verifiedCard) verifiedCard.style.display = 'none';
            if (statusChip && statusText) {
                statusChip.className = 'loc-status-chip untraced';
                statusText.textContent = 'Location Not Traced';
            }
            if (marker && map) {
                map.removeLayer(marker);
                marker = null;
            }
        });
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

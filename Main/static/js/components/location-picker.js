/**
 * LocationPicker - Reusable location selection component
 * 
 * Features:
 * - Text search with dropdown autocomplete
 * - Map pin button for click-to-select
 * - OSM road snapping support
 * - Variants: start (green), destination (red), normal (blue/default)
 * 
 * Usage:
 *   const picker = new LocationPicker({
 *     containerId: 'my-container',
 *     variant: 'start', // 'start' | 'destination' | 'normal'
 *     placeholder: 'Search location...',
 *     osmSnapping: true,
 *     onSelect: (result) => console.log(result)
 *   });
 */

class LocationPicker {
    static instanceCounter = 0;
    static activeInstances = new Map();
    static activePinningInstance = null;
    
    /**
     * Create a LocationPicker instance
     * @param {Object} options Configuration options
     * @param {string} options.containerId - Container element ID where the picker will be rendered
     * @param {string} options.variant - Visual variant: 'start' | 'destination' | 'normal'
     * @param {string} options.placeholder - Input placeholder text
     * @param {boolean} options.osmSnapping - Enable OSM road snapping (default: true)
     * @param {number} options.snapRadius - OSM snap radius in meters (default: 25)
     * @param {Function} options.onSelect - Callback when location is selected
     * @param {Function} options.onClear - Callback when location is cleared
     * @param {Function} options.onPinModeStart - Callback when pin mode starts
     * @param {Function} options.onPinModeEnd - Callback when pin mode ends
     * @param {boolean} options.showCoordinates - Show coordinates badge (default: false)
     * @param {boolean} options.showSearchResults - Enable search functionality (default: true)
     * @param {string} options.searchEndpoint - Custom search API endpoint
     * @param {Object} options.map - Leaflet map instance (required for pinning)
     */
    constructor(options) {
        this.id = `location-picker-${++LocationPicker.instanceCounter}`;
        this.options = {
            containerId: null,
            variant: 'normal', // 'start' | 'destination' | 'normal'
            placeholder: 'Search location...',
            osmSnapping: true,
            snapRadius: 25,
            onSelect: null,
            onClear: null,
            onPinModeStart: null,
            onPinModeEnd: null,
            showCoordinates: false,
            showSearchResults: true,
            searchEndpoint: '/search_location',
            map: null,
            ...options
        };
        
        this.container = null;
        this.elements = {};
        this.searchTimeout = null;
        this.currentFocusIndex = -1;
        this.isPinning = false;
        this.selectedLocation = null;
        this.markers = {
            clicked: null,
            snapped: null,
            connector: null
        };
        
        // Map click handler reference
        this._mapClickHandler = null;
        
        // Validate required options
        if (!this.options.containerId) {
            throw new Error('LocationPicker: containerId is required');
        }
        
        // Initialize
        this._init();
        
        // Register instance
        LocationPicker.activeInstances.set(this.id, this);
    }
    
    /**
     * Get variant-specific configuration
     */
    _getVariantConfig() {
        const configs = {
            start: {
                pinBtnClass: 'search-combobox__pin-btn--success',
                iconColor: '#10B981', // emerald-500
                markerColor: 'green',
                markerIcon: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
                snapMarkerColor: '#10B981',
                connectorColor: '#10B981',
                tagClass: 'search-result__tag--start',
                label: 'Start'
            },
            destination: {
                pinBtnClass: 'search-combobox__pin-btn--danger',
                iconColor: '#EF4444', // red-500
                markerColor: 'red',
                markerIcon: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                snapMarkerColor: '#EF4444',
                connectorColor: '#EF4444',
                tagClass: 'search-result__tag--dest',
                label: 'Destination'
            },
            normal: {
                pinBtnClass: 'search-combobox__pin-btn--primary',
                iconColor: '#6366F1', // indigo-500
                markerColor: 'blue',
                markerIcon: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
                snapMarkerColor: '#6366F1',
                connectorColor: '#6366F1',
                tagClass: 'search-result__tag--normal',
                label: 'Location'
            }
        };
        return configs[this.options.variant] || configs.normal;
    }
    
    /**
     * Initialize the component
     */
    _init() {
        this.container = document.getElementById(this.options.containerId);
        if (!this.container) {
            console.error(`LocationPicker: Container #${this.options.containerId} not found`);
            return;
        }
        
        this._render();
        this._bindEvents();
        
        console.log(`✅ LocationPicker initialized: ${this.id} (${this.options.variant})`);
    }
    
    /**
     * Render the component HTML
     */
    _render() {
        const variantConfig = this._getVariantConfig();
        
        this.container.innerHTML = `
            <div class="search-combobox location-picker" id="${this.id}" data-variant="${this.options.variant}">
                <div class="search-combobox__wrapper">
                    <input type="text" 
                           id="${this.id}-input" 
                           class="search-combobox__input" 
                           placeholder="${this.options.placeholder}"
                           autocomplete="off">
                    <button type="button"
                            class="search-combobox__pin-btn ${variantConfig.pinBtnClass}" 
                            id="${this.id}-pin-btn" 
                            title="Pin on map">
                        <i data-lucide="map-pin"></i>
                    </button>
                </div>
                <div class="search-combobox__dropdown" id="${this.id}-dropdown"></div>
                ${this.options.showCoordinates ? `
                    <div class="location-picker__coords badge badge--primary badge--lg hidden mt-2 w-full justify-center" id="${this.id}-coords"></div>
                ` : ''}
            </div>
        `;
        
        // Cache element references
        this.elements = {
            wrapper: this.container.querySelector('.search-combobox'),
            input: document.getElementById(`${this.id}-input`),
            pinBtn: document.getElementById(`${this.id}-pin-btn`),
            dropdown: document.getElementById(`${this.id}-dropdown`),
            coords: document.getElementById(`${this.id}-coords`)
        };
        
        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons({ icons: { 'map-pin': lucide.icons['map-pin'] } });
        }
    }
    
    /**
     * Bind event listeners
     */
    _bindEvents() {
        const { input, pinBtn, dropdown } = this.elements;
        
        // Input search handler
        if (input && this.options.showSearchResults) {
            input.addEventListener('input', (e) => {
                clearTimeout(this.searchTimeout);
                const query = e.target.value.trim();
                this.currentFocusIndex = -1;
                
                if (query.length < 2) {
                    this._hideDropdown();
                    return;
                }
                
                this.searchTimeout = setTimeout(() => {
                    this._performSearch(query);
                }, 300);
            });
            
            // Keyboard navigation
            input.addEventListener('keydown', (e) => {
                this._handleKeyboardNavigation(e);
            });
            
            // Focus handler
            input.addEventListener('focus', () => {
                if (input.value.trim().length >= 2) {
                    this._showDropdown();
                }
            });
        }
        
        // Pin button handler
        if (pinBtn) {
            pinBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this._activatePinMode();
            });
        }
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest(`#${this.id}`)) {
                this._hideDropdown();
            }
        });
    }
    
    /**
     * Show the dropdown
     */
    _showDropdown() {
        if (this.elements.dropdown) {
            this.elements.dropdown.classList.add('open');
        }
    }
    
    /**
     * Hide the dropdown
     */
    _hideDropdown() {
        if (this.elements.dropdown) {
            this.elements.dropdown.classList.remove('open');
            this.currentFocusIndex = -1;
        }
    }
    
    /**
     * Handle keyboard navigation
     */
    _handleKeyboardNavigation(e) {
        const dropdown = this.elements.dropdown;
        if (!dropdown) return;
        
        const items = dropdown.querySelectorAll('.dropdown-item');
        if (items.length === 0) return;
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.currentFocusIndex = (this.currentFocusIndex + 1) % items.length;
                this._updateFocus(items);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.currentFocusIndex = (this.currentFocusIndex - 1 + items.length) % items.length;
                this._updateFocus(items);
                break;
            case 'Enter':
                e.preventDefault();
                if (this.currentFocusIndex >= 0 && this.currentFocusIndex < items.length) {
                    items[this.currentFocusIndex].click();
                }
                break;
            case 'Escape':
                this._hideDropdown();
                break;
        }
    }
    
    /**
     * Update visual focus on dropdown items
     */
    _updateFocus(items) {
        items.forEach((item, index) => {
            if (index === this.currentFocusIndex) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } else {
                item.classList.remove('selected');
            }
        });
    }
    
    /**
     * Perform location search
     */
    async _performSearch(query) {
        const dropdown = this.elements.dropdown;
        if (!dropdown) return;
        
        const variantConfig = this._getVariantConfig();
        
        // Show loading state
        dropdown.innerHTML = `
            <div class="search-loading">
                <div class="search-loading__spinner search-loading__spinner--${this.options.variant}"></div>
                <p class="search-loading__text">Searching...</p>
            </div>
        `;
        this._showDropdown();
        
        try {
            const response = await fetch(this.options.searchEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            
            const data = await response.json();
            
            if (!data.success) {
                dropdown.innerHTML = `
                    <div class="search-empty">
                        <div class="search-empty__icon">
                            <i data-lucide="alert-circle"></i>
                        </div>
                        <p class="search-empty__title">${data.error || 'Search failed'}</p>
                    </div>
                `;
                if (typeof lucide !== 'undefined') lucide.createIcons();
                return;
            }
            
            if (data.results.length === 0) {
                dropdown.innerHTML = `
                    <div class="search-empty">
                        <div class="search-empty__icon">
                            <i data-lucide="search-x"></i>
                        </div>
                        <p class="search-empty__title">No locations found</p>
                        <p class="search-empty__subtitle">Try a different search</p>
                    </div>
                `;
                if (typeof lucide !== 'undefined') lucide.createIcons();
                return;
            }
            
            // Render results
            const iconVariant = `search-result__icon--${this.options.variant}`;
            const resultHTML = data.results.map((result, index) => `
                <div class="search-result dropdown-item"
                     data-lat="${result.lat}" 
                     data-lng="${result.lng}" 
                     data-name="${result.name.replace(/"/g, '&quot;')}">
                    <div class="search-result__icon ${iconVariant}">
                        <i data-lucide="map-pin"></i>
                    </div>
                    <div class="search-result__content">
                        <h4 class="search-result__title">${result.name.split(',')[0]}</h4>
                        <p class="search-result__subtitle">${result.name}</p>
                        <div class="search-result__meta">
                            <span class="search-result__tag ${variantConfig.tagClass}">${result.type || 'Location'}</span>
                            <span class="search-result__coords">${result.lat.toFixed(4)}, ${result.lng.toFixed(4)}</span>
                        </div>
                    </div>
                </div>
            `).join('');
            
            dropdown.innerHTML = resultHTML;
            if (typeof lucide !== 'undefined') lucide.createIcons();
            
            // Bind click handlers
            this._bindSearchResultHandlers();
            
        } catch (error) {
            console.error('LocationPicker search error:', error);
            dropdown.innerHTML = `
                <div class="search-empty">
                    <div class="search-empty__icon">
                        <i data-lucide="wifi-off"></i>
                    </div>
                    <p class="search-empty__title">Network error</p>
                    <p class="search-empty__subtitle">${error.message}</p>
                </div>
            `;
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    }
    
    /**
     * Bind click handlers to search results
     */
    _bindSearchResultHandlers() {
        const dropdown = this.elements.dropdown;
        const items = dropdown.querySelectorAll('.dropdown-item');
        
        items.forEach(item => {
            item.addEventListener('click', async (e) => {
                e.stopPropagation();
                const lat = parseFloat(item.dataset.lat);
                const lng = parseFloat(item.dataset.lng);
                const name = item.dataset.name;
                
                // Update input
                this.elements.input.value = name.split(',')[0];
                this._hideDropdown();
                
                // Handle selection with snapping if enabled
                await this._handleLocationSelect(lat, lng, name);
                
                // Pan map if available
                if (this.options.map) {
                    this.options.map.setView([lat, lng], 17);
                }
            });
        });
    }
    
    /**
     * Activate map pin mode
     */
    _activatePinMode() {
        const mapInstance = this.options.map || window.map;
        if (!mapInstance) {
            console.warn('LocationPicker: No map instance available for pinning');
            if (typeof showUpdateToast === 'function') {
                showUpdateToast('Map not available for pinning', 'warning');
            }
            return;
        }
        
        // Deactivate any other picker's pin mode
        if (LocationPicker.activePinningInstance && LocationPicker.activePinningInstance !== this) {
            LocationPicker.activePinningInstance._deactivatePinMode();
        }
        
        this.isPinning = true;
        LocationPicker.activePinningInstance = this;
        
        // Set cursor
        mapInstance.getContainer().style.cursor = 'crosshair';
        
        // Remove previous handler if exists
        if (this._mapClickHandler) {
            mapInstance.off('click', this._mapClickHandler);
        }
        
        // Create click handler
        this._mapClickHandler = async (e) => {
            const lat = e.latlng.lat;
            const lng = e.latlng.lng;
            
            await this._handleLocationSelect(lat, lng, null);
            this._deactivatePinMode();
        };
        
        // Register click handler
        mapInstance.on('click', this._mapClickHandler);
        
        // Hide dropdown
        this._hideDropdown();
        
        // Callback
        if (typeof this.options.onPinModeStart === 'function') {
            this.options.onPinModeStart();
        }
        
        // Show toast
        const variantConfig = this._getVariantConfig();
        if (typeof showUpdateToast === 'function') {
            showUpdateToast(`Click on map to pin ${variantConfig.label.toLowerCase()} location`, 'info');
        }
        
        console.log(`📍 LocationPicker ${this.id}: Pin mode activated`);
    }
    
    /**
     * Deactivate map pin mode
     */
    _deactivatePinMode() {
        if (!this.isPinning) return;
        
        const mapInstance = this.options.map || window.map;
        if (mapInstance) {
            mapInstance.getContainer().style.cursor = '';
            if (this._mapClickHandler) {
                mapInstance.off('click', this._mapClickHandler);
                this._mapClickHandler = null;
            }
        }
        
        this.isPinning = false;
        if (LocationPicker.activePinningInstance === this) {
            LocationPicker.activePinningInstance = null;
        }
        
        if (typeof this.options.onPinModeEnd === 'function') {
            this.options.onPinModeEnd();
        }
        
        console.log(`📍 LocationPicker ${this.id}: Pin mode deactivated`);
    }
    
    /**
     * Handle location selection (from search or pin)
     */
    async _handleLocationSelect(lat, lng, name = null) {
        this.clearMarkers();
        
        let result = {
            name: name,
            actualPin: { lat, lng },
            snappedPin: null,
            snapData: null,
            variant: this.options.variant
        };
        
        // Attempt OSM snapping if enabled
        if (this.options.osmSnapping && typeof snapToOSMRoad === 'function') {
            try {
                const snapData = await snapToOSMRoad(lat, lng, this.options.variant, this.options.snapRadius);
                
                if (snapData) {
                    result.snappedPin = {
                        lat: snapData.snapped_point.lat,
                        lng: snapData.snapped_point.lng
                    };
                    result.snapData = snapData;
                    result.name = name || snapData.road_name || `Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
                    
                    // Create markers
                    this._createSnapMarkers(lat, lng, snapData);
                    
                    // Update input
                    this.elements.input.value = result.name.split(',')[0];
                    
                    // Show coordinates if enabled
                    if (this.options.showCoordinates && this.elements.coords) {
                        this.elements.coords.textContent = `📍 ${snapData.snapped_point.lat.toFixed(6)}, ${snapData.snapped_point.lng.toFixed(6)}`;
                        this.elements.coords.classList.remove('hidden');
                    }
                    
                    // Success toast
                    const variantConfig = this._getVariantConfig();
                    if (typeof showUpdateToast === 'function') {
                        showUpdateToast(`${variantConfig.label} pinned: ${result.name}`, 'success');
                    }
                } else {
                    // Snapping failed - use raw coordinates
                    result.name = name || `Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
                    this.elements.input.value = result.name;
                    
                    if (typeof showUpdateToast === 'function') {
                        showUpdateToast('Could not snap to road. Using clicked location.', 'warning');
                    }
                }
            } catch (error) {
                console.error('OSM snapping error:', error);
                result.name = name || `Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
                this.elements.input.value = result.name;
            }
        } else {
            // No snapping - just use the coordinates
            result.name = name || `Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
            this.elements.input.value = result.name.split(',')[0];
            
            if (!name) {
                // Try to get road name from API
                try {
                    const response = await fetch('/api/demo/get_location_name', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ lat, lng })
                    });
                    const data = await response.json();
                    if (data.name || data.road_name) {
                        result.name = data.name || data.road_name;
                        this.elements.input.value = result.name.split(',')[0];
                    }
                } catch (e) {
                    // Ignore error, use coordinates
                }
            }
        }
        
        // Store selected location
        this.selectedLocation = result;
        
        // Call onSelect callback
        if (typeof this.options.onSelect === 'function') {
            this.options.onSelect(result);
        }
        
        console.log(`✅ LocationPicker ${this.id}: Location selected`, result);
        
        return result;
    }
    
    /**
     * Create snap markers on the map
     */
    _createSnapMarkers(clickedLat, clickedLng, snapData) {
        const mapInstance = this.options.map || window.map;
        if (!mapInstance) return;
        
        const variantConfig = this._getVariantConfig();
        const snappedLat = snapData.snapped_point.lat;
        const snappedLng = snapData.snapped_point.lng;
        const distance = snapData.distance_m;
        
        // 1. Clicked marker (semi-transparent)
        const clickedIcon = L.icon({
            iconUrl: variantConfig.markerIcon,
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
            iconSize: [20, 33],
            iconAnchor: [10, 33],
            popupAnchor: [0, -28],
            shadowSize: [33, 33]
        });
        
        this.markers.clicked = L.marker([clickedLat, clickedLng], {
            icon: clickedIcon,
            title: `${variantConfig.label} (Clicked)`,
            opacity: 0.4,
            zIndexOffset: 1
        }).addTo(mapInstance);
        
        this.markers.clicked.bindPopup(
            `<div class="p-2 min-w-[220px]">` +
            `<div class="font-bold text-lg mb-2" style="color: ${variantConfig.iconColor}">${variantConfig.label} Location</div>` +
            `<div class="text-sm text-slate-600 mb-1">📍 Clicked Point</div>` +
            `<div class="text-xs text-slate-500 font-mono bg-slate-50 px-2 py-1 rounded">${clickedLat.toFixed(6)}, ${clickedLng.toFixed(6)}</div>` +
            `</div>`
        );
        
        // 2. Snapped marker (solid on road)
        const snappedIcon = L.divIcon({
            className: 'location-picker-snap-marker',
            html: `<div style="background: ${variantConfig.snapMarkerColor}; border: 3px solid white; border-radius: 50%; width: 18px; height: 18px; box-shadow: 0 3px 6px rgba(0,0,0,0.5);"></div>`,
            iconSize: [18, 18],
            iconAnchor: [9, 9]
        });
        
        this.markers.snapped = L.marker([snappedLat, snappedLng], {
            icon: snappedIcon,
            title: `${variantConfig.label} on Road`,
            zIndexOffset: 10
        }).addTo(mapInstance);
        
        const methodText = snapData.method === 'osm_geometry' 
            ? 'Snapped to OSM Road' 
            : 'Fallback to Nearest Node';
        
        this.markers.snapped.bindPopup(
            `<div class="p-3 min-w-[300px]">` +
            `<div class="font-bold text-xl mb-3" style="color: ${variantConfig.iconColor}">` +
            `📍 ${variantConfig.label}</div>` +
            `<div class="bg-slate-50 px-3 py-2 rounded-lg mb-2 border border-slate-200">` +
            `<div class="text-xs font-semibold uppercase tracking-wide" style="color: ${variantConfig.iconColor}">${methodText}</div>` +
            `</div>` +
            `<div class="space-y-2 text-sm">` +
            `<div class="flex items-start"><span class="font-semibold text-slate-700 w-20">🛣️ Road:</span><span class="text-slate-900 flex-1">${snapData.road_name}</span></div>` +
            `<div class="flex items-start"><span class="font-semibold text-slate-700 w-20">🏷️ Type:</span><span class="text-slate-600">${snapData.highway_type}</span></div>` +
            `${snapData.oneway ? '<div class="bg-yellow-50 border border-yellow-300 px-2 py-1 rounded text-yellow-800 font-semibold text-xs">⚠️ One-way road</div>' : ''}` +
            `<div class="flex items-start"><span class="font-semibold text-slate-700 w-20">📏 Snap:</span><span style="color: ${variantConfig.iconColor}" class="font-bold">${distance.toFixed(1)}m</span></div>` +
            `<div class="text-xs text-slate-400 font-mono bg-slate-50 px-2 py-1 rounded mt-2">${snappedLat.toFixed(6)}, ${snappedLng.toFixed(6)}</div>` +
            `</div></div>`
        );
        
        // 3. Connector line (if distance > 3m)
        if (distance > 3) {
            this.markers.connector = L.polyline([
                [clickedLat, clickedLng],
                [snappedLat, snappedLng]
            ], {
                color: variantConfig.connectorColor,
                weight: 2,
                dashArray: '8, 12',
                opacity: 0.7,
                zIndexOffset: 0
            }).addTo(mapInstance);
            
            this.markers.connector.bindTooltip(
                `🚶 ${distance.toFixed(0)}m`,
                {
                    permanent: true,
                    direction: 'center',
                    className: 'walking-distance-label',
                    opacity: 0.9
                }
            );
        }
    }
    
    /**
     * Clear all markers
     */
    clearMarkers() {
        const mapInstance = this.options.map || window.map;
        if (!mapInstance) return;
        
        Object.keys(this.markers).forEach(key => {
            if (this.markers[key]) {
                mapInstance.removeLayer(this.markers[key]);
                this.markers[key] = null;
            }
        });
    }
    
    /**
     * Clear the selected location and reset input
     */
    clear() {
        this.clearMarkers();
        this.selectedLocation = null;
        this.elements.input.value = '';
        
        if (this.elements.coords) {
            this.elements.coords.classList.add('hidden');
            this.elements.coords.textContent = '';
        }
        
        if (typeof this.options.onClear === 'function') {
            this.options.onClear();
        }
        
        console.log(`🗑️ LocationPicker ${this.id}: Cleared`);
    }
    
    /**
     * Get the currently selected location
     */
    getSelectedLocation() {
        return this.selectedLocation;
    }
    
    /**
     * Set a location programmatically
     */
    async setLocation(lat, lng, name = null) {
        return await this._handleLocationSelect(lat, lng, name);
    }
    
    /**
     * Set input value without triggering selection
     */
    setInputValue(value) {
        if (this.elements.input) {
            this.elements.input.value = value;
        }
    }
    
    /**
     * Disable the picker
     */
    disable() {
        if (this.elements.input) {
            this.elements.input.disabled = true;
        }
        if (this.elements.pinBtn) {
            this.elements.pinBtn.disabled = true;
        }
        this._deactivatePinMode();
    }
    
    /**
     * Enable the picker
     */
    enable() {
        if (this.elements.input) {
            this.elements.input.disabled = false;
        }
        if (this.elements.pinBtn) {
            this.elements.pinBtn.disabled = false;
        }
    }
    
    /**
     * Destroy the component
     */
    destroy() {
        this._deactivatePinMode();
        this.clearMarkers();
        
        if (this.container) {
            this.container.innerHTML = '';
        }
        
        LocationPicker.activeInstances.delete(this.id);
        console.log(`🗑️ LocationPicker ${this.id}: Destroyed`);
    }
    
    /**
     * Static method to get instance by ID
     */
    static getInstance(id) {
        return LocationPicker.activeInstances.get(id);
    }
    
    /**
     * Static method to cancel all active pin modes
     */
    static cancelAllPinModes() {
        if (LocationPicker.activePinningInstance) {
            LocationPicker.activePinningInstance._deactivatePinMode();
        }
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LocationPicker;
}

// Make globally available
window.LocationPicker = LocationPicker;

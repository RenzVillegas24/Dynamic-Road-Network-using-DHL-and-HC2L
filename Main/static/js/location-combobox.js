// location-combobox.js - Location search with dropdown autocomplete

let searchTimeout;
let currentFocusIndex = -1;

// Position dropdown below input field using fixed positioning
function positionDropdown(inputElement, dropdownElement) {
  if (!inputElement || !dropdownElement) return;
  
  const rect = inputElement.getBoundingClientRect();
  const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
  const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
  
  // Position dropdown below the input with 8px gap (mt-2) and 8px margin (mr-8 equivalent)
  dropdownElement.style.top = (rect.bottom + scrollTop + 8) + 'px';
  dropdownElement.style.left = (rect.left + scrollLeft) + 'px';
  dropdownElement.style.width = (rect.width - 16) + 'px'; // 8px margin on each side
  dropdownElement.style.marginRight = '8px';
}

function initializeLocationCombobox() {
  console.log('🔍 Initializing location combobox...');
  
  // Start location input
  const startInput = document.getElementById('start-location-input');
  if (startInput) {
    startInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      const query = e.target.value.trim();
      currentFocusIndex = -1; // Reset focus
      
      if (query.length < 2) {
        document.getElementById('start-location-dropdown').classList.add('hidden');
        return;
      }
      
      // Debounce search to avoid too many requests
      searchTimeout = setTimeout(() => {
        performLocationSearch(query, 'start');
      }, 300);
    });
    
    // Keyboard navigation
    startInput.addEventListener('keydown', (e) => {
      handleKeyboardNavigation(e, 'start');
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('#start-location-input') && 
          !e.target.closest('#start-location-dropdown')) {
        document.getElementById('start-location-dropdown').classList.add('hidden');
      }
    });
    
    console.log('✅ Start location input initialized');
  }
  
  // Destination location input
  const destInput = document.getElementById('dest-location-input');
  if (destInput) {
    destInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      const query = e.target.value.trim();
      currentFocusIndex = -1; // Reset focus
      
      if (query.length < 2) {
        document.getElementById('dest-location-dropdown').classList.add('hidden');
        return;
      }
      
      // Debounce search
      searchTimeout = setTimeout(() => {
        performLocationSearch(query, 'dest');
      }, 300);
    });
    
    // Keyboard navigation
    destInput.addEventListener('keydown', (e) => {
      handleKeyboardNavigation(e, 'dest');
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('#dest-location-input') && 
          !e.target.closest('#dest-location-dropdown')) {
        document.getElementById('dest-location-dropdown').classList.add('hidden');
      }
    });
    
    console.log('✅ Destination location input initialized');
  }
  
  // Pin button handlers (existing behavior)
  const startPinBtn = document.getElementById('start-location-pin-btn');
  if (startPinBtn) {
    startPinBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      console.log('Start pin button clicked');
      pinningMode = 'start';
      if (map && map.getContainer) {
        map.getContainer().style.cursor = 'crosshair';
      }
      showUpdateToast('Click on map to pin start location', 'info');
      // Close dropdown
      document.getElementById('start-location-dropdown').classList.add('hidden');
    });
    console.log('✅ Start pin button handler registered');
  }
  
  const destPinBtn = document.getElementById('dest-location-pin-btn');
  if (destPinBtn) {
    destPinBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      console.log('Dest pin button clicked');
      pinningMode = 'dest';
      if (map && map.getContainer) {
        map.getContainer().style.cursor = 'crosshair';
      }
      showUpdateToast('Click on map to pin destination', 'info');
      // Close dropdown
      document.getElementById('dest-location-dropdown').classList.add('hidden');
    });
    console.log('✅ Dest pin button handler registered');
  }
  
  console.log('✅ Location combobox fully initialized');
  
  // Reposition dropdowns on window resize or scroll
  window.addEventListener('resize', () => {
    const startDropdown = document.getElementById('start-location-dropdown');
    const destDropdown = document.getElementById('dest-location-dropdown');
    const startInput = document.getElementById('start-location-input');
    const destInput = document.getElementById('dest-location-input');
    
    if (startDropdown && !startDropdown.classList.contains('hidden')) {
      positionDropdown(startInput, startDropdown);
    }
    if (destDropdown && !destDropdown.classList.contains('hidden')) {
      positionDropdown(destInput, destDropdown);
    }
  });
  
  window.addEventListener('scroll', () => {
    const startDropdown = document.getElementById('start-location-dropdown');
    const destDropdown = document.getElementById('dest-location-dropdown');
    const startInput = document.getElementById('start-location-input');
    const destInput = document.getElementById('dest-location-input');
    
    if (startDropdown && !startDropdown.classList.contains('hidden')) {
      positionDropdown(startInput, startDropdown);
    }
    if (destDropdown && !destDropdown.classList.contains('hidden')) {
      positionDropdown(destInput, destDropdown);
    }
  });
}

// Handle keyboard navigation (arrow keys, Enter, Escape)
function handleKeyboardNavigation(e, type) {
  const dropdownId = type === 'start' ? 'start-location-dropdown' : 'dest-location-dropdown';
  const dropdown = document.getElementById(dropdownId);
  const items = dropdown.querySelectorAll('.dropdown-item');
  
  if (items.length === 0) return;
  
  // Arrow Down
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    currentFocusIndex = (currentFocusIndex + 1) % items.length;
    updateFocus(items);
  }
  // Arrow Up
  else if (e.key === 'ArrowUp') {
    e.preventDefault();
    currentFocusIndex = (currentFocusIndex - 1 + items.length) % items.length;
    updateFocus(items);
  }
  // Enter - select focused item
  else if (e.key === 'Enter') {
    e.preventDefault();
    if (currentFocusIndex >= 0 && currentFocusIndex < items.length) {
      items[currentFocusIndex].click();
    }
  }
  // Escape - close dropdown
  else if (e.key === 'Escape') {
    dropdown.classList.add('hidden');
    currentFocusIndex = -1;
  }
}

// Update visual focus on dropdown items
function updateFocus(items) {
  items.forEach((item, index) => {
    if (index === currentFocusIndex) {
      item.classList.add('selected');
      item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else {
      item.classList.remove('selected');
    }
  });
}

// Perform location search and show dropdown results
async function performLocationSearch(query, type) {
  const dropdownId = type === 'start' ? 'start-location-dropdown' : 'dest-location-dropdown';
  const inputId = type === 'start' ? 'start-location-input' : 'dest-location-input';
  const dropdown = document.getElementById(dropdownId);
  const input = document.getElementById(inputId);
  
  console.log(`🔍 Searching for "${query}" (${type})`);
  
  // Position dropdown below the input field
  positionDropdown(input, dropdown);
  
  // Show loading state with framework classes
  const iconVariant = type === 'start' ? 'search-result__icon--start' : 'search-result__icon--dest';
  dropdown.innerHTML = `
    <div class="search-loading">
      <div class="search-loading__spinner ${type === 'start' ? 'search-loading__spinner--start' : 'search-loading__spinner--dest'}"></div>
      <p class="search-loading__text">Searching...</p>
    </div>
  `;
  dropdown.classList.remove('hidden');
  
  try {
    console.log('📡 Sending search request');
    const response = await fetch('/search_location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    
    console.log(`📥 Response status: ${response.status}`);
    const data = await response.json();
    console.log('📊 Search response:', data);
    
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
    
    // Display results using framework search-result classes
    const resultHTML = data.results.map((result, index) => `
      <div class="search-result dropdown-item"
           data-lat="${result.lat}" 
           data-lng="${result.lng}" 
           data-type="${type}"
           data-name="${result.name.replace(/"/g, '&quot;')}">
        <div class="search-result__icon ${iconVariant}">
          <i data-lucide="map-pin"></i>
        </div>
        <div class="search-result__content">
          <h4 class="search-result__title">${result.name.split(',')[0]}</h4>
          <p class="search-result__subtitle">${result.name}</p>
          <div class="search-result__meta">
            <span class="search-result__tag search-result__tag--${type}">${result.type}</span>
            <span class="search-result__coords">${result.lat.toFixed(4)}, ${result.lng.toFixed(4)}</span>
          </div>
        </div>
      </div>
    `).join('');
    
    dropdown.innerHTML = resultHTML;
    if (typeof lucide !== 'undefined') lucide.createIcons();
    console.log(`✅ Displayed ${data.results.length} results`);
    
    // Add click handlers to results - use setTimeout to ensure DOM is updated
    setTimeout(() => {
      const items = dropdown.querySelectorAll('.dropdown-item');
      items.forEach(item => {
        item.addEventListener('click', (e) => {
          e.stopPropagation();
          const lat = parseFloat(item.dataset.lat);
          const lng = parseFloat(item.dataset.lng);
          const locType = item.dataset.type;
          const name = item.dataset.name;
          
          console.log(`📍 Location selected: ${name} (${lat}, ${lng})`);
          
          // Get the correct input element based on data-type
          const selectedType = item.dataset.type;
          const selectedInputId = selectedType === 'start' ? 'start-location-input' : 'dest-location-input';
          const targetInput = document.getElementById(selectedInputId);
          
          if (targetInput) {
            const displayName = name.split(',')[0]; // Show just the main name
            targetInput.value = displayName;
            console.log(`✅ Set ${selectedInputId} value to: ${displayName}`);
            
            // Dispatch input event to trigger any listeners
            targetInput.dispatchEvent(new Event('input', { bubbles: true }));
          } else {
            console.error(`❌ Input ${selectedInputId} not found`);
          }
          
          // Hide dropdown
          dropdown.classList.add('hidden');
          
          // Set location
          if (locType === 'start') {
            handleStartLocationPin(lat, lng, name);
          } else {
            handleDestLocationPin(lat, lng, name);
          }
          
          // Pan map to location
          if (map) {
            map.setView([lat, lng], 17);
          }
        });
      });
    }, 0);
    
    showUpdateToast(`Found ${data.count} location${data.count !== 1 ? 's' : ''}`, 'success');
    
  } catch (error) {
    console.error('❌ Search error:', error);
    dropdown.innerHTML = `
      <div class="p-4 text-center text-red-500">
        <svg class="w-10 h-10 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <p class="text-sm font-medium">Network error</p>
        <p class="text-xs text-slate-400 mt-1">${error.message}</p>
      </div>
    `;
    showUpdateToast(`Search failed: ${error.message}`, 'error');
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeLocationCombobox);
} else {
  initializeLocationCombobox();
}

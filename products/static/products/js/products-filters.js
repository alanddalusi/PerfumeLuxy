// Products Filters and Interactions
document.addEventListener('DOMContentLoaded', function() {
    console.log('Products filters initialized');

    // Toggle filters sidebar on mobile
    const toggleFiltersBtn = document.getElementById('toggleFiltersBtn');
    const filtersSidebar = document.getElementById('filtersSidebar');
    
    if (toggleFiltersBtn && filtersSidebar) {
        toggleFiltersBtn.addEventListener('click', function() {
            filtersSidebar.classList.toggle('show');
        });
    }

    // Get current URL parameters
    function getUrlParams() {
        const params = new URLSearchParams(window.location.search);
        return params;
    }

    // Update URL and reload with new filters
    function applyFilters() {
        const params = new URLSearchParams();
        
        // Get all checked checkboxes
        const checkboxes = document.querySelectorAll('.filter-option input[type="checkbox"]:checked');
        checkboxes.forEach(checkbox => {
            const name = checkbox.getAttribute('name');
            const value = checkbox.value;
            params.append(name, value);
        });

        // Get sorting
        const sortSelect = document.getElementById('sortSelect');
        if (sortSelect && sortSelect.value) {
            const [sortKey, direction] = sortSelect.value.split('_');
            params.set('sort', sortKey);
            params.set('direction', direction);
        }

        // Get price range if available
        const priceRange = document.getElementById('priceRange');
        if (priceRange && priceRange.value) {
            const [priceFrom, priceTo] = priceRange.value.split(';');
            if (priceFrom) params.set('price_from', priceFrom);
            if (priceTo) params.set('price_to', priceTo);
        }

        // Preserve search query if exists
        const urlParams = getUrlParams();
        const searchTerm = urlParams.get('q');
        if (searchTerm) {
            params.set('q', searchTerm);
        }

        // Redirect with new params
        const newUrl = `${window.location.pathname}?${params.toString()}`;
        window.location.href = newUrl;
    }

    // Apply filters on checkbox change
    const filterCheckboxes = document.querySelectorAll('.filter-option input[type="checkbox"]');
    filterCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            applyFilters();
        });
    });

    // Apply filters on sort change
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            applyFilters();
        });
    }

    // Clear all filters
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');
    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener('click', function() {
            // Uncheck all checkboxes
            filterCheckboxes.forEach(checkbox => {
                checkbox.checked = false;
            });
            
            // Reset sort
            if (sortSelect) {
                sortSelect.value = 'name_asc';
            }
            
            // Reset price range
            const priceRange = document.getElementById('priceRange');
            if (priceRange && priceRange.data && priceRange.data('ionRangeSlider')) {
                priceRange.data('ionRangeSlider').reset();
            }
            
            // Redirect to base products page
            window.location.href = window.location.pathname;
        });
    }

    // Set checked state based on URL params on page load
    function setFiltersFromUrl() {
        const params = getUrlParams();
        
        // Set checkboxes
        filterCheckboxes.forEach(checkbox => {
            const name = checkbox.getAttribute('name');
            const value = checkbox.value;
            
            // Check if this value is in the URL params
            const paramValues = params.getAll(name);
            if (paramValues.includes(value)) {
                checkbox.checked = true;
            }
        });

        // Set sort select
        if (sortSelect) {
            const sort = params.get('sort');
            const direction = params.get('direction');
            if (sort && direction) {
                sortSelect.value = `${sort}_${direction}`;
            }
        }
    }

    // Initialize filters from URL
    setFiltersFromUrl();

    // Active filters display
    function updateActiveFilters() {
        const activeFiltersContainer = document.getElementById('activeFilters');
        if (!activeFiltersContainer) return;

        activeFiltersContainer.innerHTML = '';
        
        const params = getUrlParams();
        const filterChips = [];

        // Create chips for each active filter
        params.forEach((value, key) => {
            if (key !== 'sort' && key !== 'direction' && key !== 'page') {
                const chip = document.createElement('span');
                chip.className = 'filter-chip';
                chip.innerHTML = `
                    ${getFilterLabel(key, value)}
                    <button class="filter-chip-remove" onclick="removeFilter('${key}', '${value}')">
                        <i class="fas fa-times"></i>
                    </button>
                `;
                activeFiltersContainer.appendChild(chip);
            }
        });
    }

    // Get human-readable filter label
    function getFilterLabel(key, value) {
        const labels = {
            'fragrance_family': value, // Use actual family name
            'intensity': {
                'light': 'Ligera',
                'moderate': 'Moderada',
                'strong': 'Fuerte',
                'very_strong': 'Muy Fuerte'
            },
            'duration': {
                'short': 'Corta (2-4h)',
                'moderate': 'Moderada (4-8h)',
                'long': 'Larga (8+h)'
            },
            'occasion': {
                'daily': 'Uso Diario',
                'night': 'Noche',
                'formal': 'Formal',
                'casual': 'Casual',
                'sport': 'Deporte'
            },
            'season': {
                'spring': 'Primavera',
                'summer': 'Verano',
                'autumn': 'Otoño',
                'winter': 'Invierno'
            },
            'in_stock': {
                'true': 'En Stock'
            },
            'has_discount': {
                'true': 'En Rebaja'
            },
            'gender': {
                'M': 'Para Él',
                'F': 'Para Ella',
                'U': 'Unisex'
            },
            'category': {
                'perfumes': 'Perfumes',
                'candles': 'Velas'
            },
            'brand': value, // Use actual brand name
            'concentration': {
                'parfum': 'Parfum',
                'edp': 'EDP',
                'edt': 'EDT',
                'edc': 'EDC',
                'splash': 'Splash'
            }
        };

        if (key === 'fragrance_family' || key === 'brand') {
            return value;
        }
        
        if (labels[key] && labels[key][value]) {
            return labels[key][value];
        }
        return value;
    }

    // Remove specific filter
    window.removeFilter = function(key, value) {
        const params = getUrlParams();
        
        // Remove all instances of this key-value pair
        const newParams = new URLSearchParams();
        params.forEach((v, k) => {
            if (!(k === key && v === value)) {
                newParams.append(k, v);
            }
        });

        const newUrl = `${window.location.pathname}?${newParams.toString()}`;
        window.location.href = newUrl;
    };

    // Update active filters on load
    updateActiveFilters();

    // Initialize price range slider if ion.rangeSlider is loaded
    const priceRange = document.getElementById('priceRange');
    if (priceRange && typeof $.fn.ionRangeSlider !== 'undefined') {
        const minPrice = parseInt(priceRange.dataset.min) || 0;
        const maxPrice = parseInt(priceRange.dataset.max) || 500;
        const params = getUrlParams();
        const fromPrice = parseInt(params.get('price_from')) || minPrice;
        const toPrice = parseInt(params.get('price_to')) || maxPrice;

        $(priceRange).ionRangeSlider({
            type: 'double',
            min: minPrice,
            max: maxPrice,
            from: fromPrice,
            to: toPrice,
            prefix: '€',
            onFinish: function(data) {
                const params = getUrlParams();
                params.set('price_from', data.from);
                params.set('price_to', data.to);
                const newUrl = `${window.location.pathname}?${params.toString()}`;
                window.location.href = newUrl;
            }
        });
    }

    // Product card hover effects
    const productCards = document.querySelectorAll('.product-card');
    productCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.zIndex = '10';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.zIndex = '1';
        });
    });

    // Wishlist toggle
    const wishlistBtns = document.querySelectorAll('.wishlist-toggle');
    wishlistBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const icon = this.querySelector('i');
            const productId = this.dataset.productId;
            
            // Toggle heart icon
            if (icon.classList.contains('far')) {
                icon.classList.remove('far');
                icon.classList.add('fas');
                this.style.color = '#dc3545';
            } else {
                icon.classList.remove('fas');
                icon.classList.add('far');
                this.style.color = '';
            }
            
            // TODO: Add AJAX call to backend to save wishlist state
            console.log('Wishlist toggled for product:', productId);
        });
    });

    // Quick view button
    const quickViewBtns = document.querySelectorAll('.quick-view-btn');
    quickViewBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const productId = this.dataset.productId;
            console.log('Quick view for product:', productId);
            // TODO: Implement quick view modal
        });
    });

    // Comparison checkbox
    const comparisonCheckboxes = document.querySelectorAll('.comparison-checkbox');
    comparisonCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function(e) {
            e.stopPropagation();
            
            const productId = this.dataset.productId;
            console.log('Comparison toggled for product:', productId);
            // TODO: Implement comparison logic
        });
    });

    console.log('Products filters and interactions ready ✨');
});

// Products Page - Advanced Filtering and Interactions
document.addEventListener('DOMContentLoaded', function() {
    
    // Prevent navigation to undefined URLs
    document.addEventListener('click', function(e) {
        const target = e.target.closest('a');
        if (target && target.href) {
            const url = target.href;
            if (url.includes('/undefined') || url.endsWith('/undefined')) {
                e.preventDefault();
                console.error('Prevented navigation to undefined URL:', url);
                showToast('Error: Enlace no válido', 'error');
                return false;
            }
        }
    }, true); // Use capture phase
    
    // Initialize comparison tracking
    let selectedProducts = [];
    const MAX_COMPARISON = 4;

    // Toggle Filters Sidebar (Mobile)
    const toggleFiltersBtn = document.getElementById('toggleFiltersBtn');
    const filtersSidebar = document.getElementById('filtersSidebar');
    
    if (toggleFiltersBtn) {
        toggleFiltersBtn.addEventListener('click', function() {
            filtersSidebar.classList.toggle('show');
        });
    }

    // Clear All Filters
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');
    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener('click', function() {
            // Uncheck all filter checkboxes
            document.querySelectorAll('.filter-option input[type="checkbox"]').forEach(cb => {
                if (cb.name !== 'in_stock') { // Keep in_stock checked by default
                    cb.checked = false;
                }
            });
            
            // Reset sort select
            const sortSelect = document.getElementById('sortSelect');
            if (sortSelect) sortSelect.selectedIndex = 0;
            
            // Clear active filters display
            updateActiveFilters();
            
            // Reload products
            applyFilters();
        });
    }

    // Monitor filter changes
    document.querySelectorAll('.filter-option input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateActiveFilters();
            applyFilters();
        });
    });

    // Sort change
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            applyFilters();
        });
    }

    // Update Active Filters Display
    function updateActiveFilters() {
        const activeFiltersContainer = document.getElementById('activeFilters');
        if (!activeFiltersContainer) return;

        activeFiltersContainer.innerHTML = '';
        
        document.querySelectorAll('.filter-option input[type="checkbox"]:checked').forEach(cb => {
            if (cb.name === 'in_stock') return; // Don't show "in stock" chip
            
            const chip = document.createElement('div');
            chip.className = 'filter-chip';
            chip.innerHTML = `
                <span>${cb.nextElementSibling.textContent}</span>
                <button class="filter-chip-remove" data-filter="${cb.name}" data-value="${cb.value}">
                    <i class="fas fa-times"></i>
                </button>
            `;
            activeFiltersContainer.appendChild(chip);
            
            // Add remove functionality
            chip.querySelector('.filter-chip-remove').addEventListener('click', function() {
                cb.checked = false;
                updateActiveFilters();
                applyFilters();
            });
        });
    }

    // Apply Filters (AJAX)
    function applyFilters() {
        const formData = new FormData();
        
        // Collect all checked filters
        document.querySelectorAll('.filter-option input[type="checkbox"]:checked').forEach(cb => {
            formData.append(cb.name, cb.value);
        });
        
        // Add sort
        const sortValue = document.getElementById('sortSelect')?.value;
        if (sortValue) {
            formData.append('sort', sortValue);
        }
        
        // Show loading
        const productsContainer = document.getElementById('product-detail-container');
        if (productsContainer) {
            productsContainer.style.opacity = '0.5';
        }
        
        // Build query string
        const params = new URLSearchParams(formData);
        const currentUrl = new URL(window.location.href);
        currentUrl.search = params.toString();
        
        // Update URL without reload (for better UX)
        window.history.pushState({}, '', currentUrl);
        
        // In production, you'd make an AJAX call here
        // For now, we'll just reload the page
        // Uncomment the next line to enable actual filtering:
        // window.location.href = currentUrl;
        
        // Simulate filter delay
        setTimeout(() => {
            if (productsContainer) {
                productsContainer.style.opacity = '1';
            }
        }, 300);
    }

    // Product Comparison
    document.querySelectorAll('.comparison-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const productId = this.dataset.productId;
            
            // Validate productId
            if (!productId || productId === 'undefined' || productId === 'null') {
                console.error('Invalid product ID for comparison:', productId);
                this.checked = false;
                showToast('Error: Producto no válido para comparar', 'error');
                return;
            }
            
            if (this.checked) {
                if (selectedProducts.length >= MAX_COMPARISON) {
                    this.checked = false;
                    showToast('You can only compare up to ' + MAX_COMPARISON + ' products', 'warning');
                    return;
                }
                selectedProducts.push(productId);
            } else {
                selectedProducts = selectedProducts.filter(id => id !== productId);
            }
            
            updateComparisonBar();
        });
    });

    function updateComparisonBar() {
        const comparisonBar = document.getElementById('comparisonBar');
        const comparisonCount = document.getElementById('comparisonCount');
        const compareNowBtn = document.getElementById('compareNowBtn');
        
        if (selectedProducts.length > 0) {
            comparisonBar.style.display = 'block';
            comparisonCount.textContent = selectedProducts.length;
            
            if (selectedProducts.length >= 2) {
                compareNowBtn.href = `/products/compare/?products=${selectedProducts.join(',')}`;
                compareNowBtn.classList.remove('disabled');
            } else {
                compareNowBtn.classList.add('disabled');
            }
        } else {
            comparisonBar.style.display = 'none';
        }
    }

    // Clear Comparison
    const clearComparisonBtn = document.getElementById('clearComparisonBtn');
    if (clearComparisonBtn) {
        clearComparisonBtn.addEventListener('click', function() {
            selectedProducts = [];
            document.querySelectorAll('.comparison-checkbox').forEach(cb => {
                cb.checked = false;
            });
            updateComparisonBar();
        });
    }

    // Wishlist Toggles (using ecommerce.js functionality)
    document.querySelectorAll('.wishlist-toggle').forEach(button => {
        // Check if product is already in wishlist
        const productId = button.dataset.productId;
        
        // Validate productId
        if (!productId || productId === 'undefined' || productId === 'null') {
            console.warn('Invalid product ID for wishlist button:', productId);
            button.disabled = true;
            button.style.opacity = '0.5';
            return;
        }
        
        // You'd fetch this from the server in production
        // For now, we'll use localStorage for demo
        const wishlist = JSON.parse(localStorage.getItem('wishlist') || '[]');
        if (wishlist.includes(productId)) {
            button.querySelector('i').classList.remove('far');
            button.querySelector('i').classList.add('fas');
        }
    });

    // Quick View Modal
    document.querySelectorAll('.quick-view-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation(); // Prevent event bubbling
            const productId = this.dataset.productId;
            
            // Validate productId before opening
            if (!productId || productId === 'undefined' || productId === 'null') {
                console.error('Invalid product ID:', productId);
                showToast('Error: Producto no válido', 'error');
                return;
            }
            
            openQuickView(productId);
        });
    });

    function openQuickView(productId) {
        // In production, fetch product details via AJAX
        // For now, show a placeholder toast
        showToast('Quick view coming soon!', 'info');
        
        // TODO: Implement modal with product details:
        // - Large image
        // - Title, brand, price
        // - Short description
        // - Add to cart button
        // - View full details link
    }

    // Lazy Load Images (enhance the one in ecommerce.js)
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    observer.unobserve(img);
                }
            }
        });
    }, {
        rootMargin: '50px'
    });

    document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
    });

    // Smooth scroll for pagination
    const infiniteMoreLink = document.querySelector('.infinite-more-link');
    if (infiniteMoreLink) {
        infiniteMoreLink.addEventListener('click', function(e) {
            const loading = document.getElementById('loading');
            if (loading) {
                loading.style.display = 'block';
            }
        });
    }

    // Initialize active filters on page load
    updateActiveFilters();

    // Handle product card hover animations
    document.querySelectorAll('.product-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.classList.add('hovered');
        });
        
        card.addEventListener('mouseleave', function() {
            this.classList.remove('hovered');
        });
    });
});

// Utility function to show toast notifications
function showToast(message, type = 'info') {
    // Use the toast system from ecommerce.js if available
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        // Fallback to console
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}

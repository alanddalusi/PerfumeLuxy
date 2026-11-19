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
    const MAX_COMPARISON = 3;

    // Toggle Filters Sidebar (Mobile)
    const toggleFiltersBtn = document.getElementById('toggleFiltersBtn');
    const filtersSidebar = document.getElementById('filtersSidebar');
    
    if (toggleFiltersBtn) {
        toggleFiltersBtn.addEventListener('click', function() {
            filtersSidebar.classList.toggle('show');
        });
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
                compareNowBtn.href = `/products/compare/?products=${new URLSearchParams(selectedProducts.map(id => ['products', id]))}`;
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

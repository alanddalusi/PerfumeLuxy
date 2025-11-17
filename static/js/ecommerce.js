// ============================================
// MODERN E-COMMERCE INTERACTIONS
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    
    // ==================== Wishlist Functionality ====================
    const wishlistButtons = document.querySelectorAll('.wishlist-toggle');
    
    wishlistButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation(); // Prevent event bubbling
            const productId = this.dataset.productId;
            
            // Validate productId
            if (!productId || productId === 'undefined' || productId === 'null') {
                console.error('Invalid product ID for wishlist:', productId);
                showToast('Error: Producto no válido', 'error');
                return;
            }
            
            const icon = this.querySelector('i');
            
            // Optimistic UI update
            icon.classList.toggle('fas');
            icon.classList.toggle('far');
            
            // Send AJAX request
            fetch(`/products/wishlist/toggle/${productId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message, 'success');
                    // Update wishlist counter if exists
                    updateWishlistCounter();
                } else {
                    // Revert UI change if failed
                    icon.classList.toggle('fas');
                    icon.classList.toggle('far');
                    showToast('Error al actualizar la lista de deseos', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                icon.classList.toggle('fas');
                icon.classList.toggle('far');
            });
        });
    });
    
    // ==================== Product Comparison ====================
    const comparisonCheckboxes = document.querySelectorAll('.comparison-checkbox');
    const compareButton = document.getElementById('compare-button');
    let selectedProducts = [];
    
    comparisonCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const productId = this.dataset.productId;
            
            if (this.checked) {
                if (selectedProducts.length >= 4) {
                    this.checked = false;
                    showToast('Máximo 4 productos para comparar', 'warning');
                    return;
                }
                selectedProducts.push(productId);
            } else {
                selectedProducts = selectedProducts.filter(id => id !== productId);
            }
            
            updateCompareButton();
        });
    });
    
    function updateCompareButton() {
        if (compareButton) {
            if (selectedProducts.length >= 2) {
                compareButton.disabled = false;
                compareButton.textContent = `Comparar (${selectedProducts.length})`;
            } else {
                compareButton.disabled = true;
                compareButton.textContent = 'Selecciona al menos 2 productos';
            }
        }
    }
    
    if (compareButton) {
        compareButton.addEventListener('click', function() {
            if (selectedProducts.length >= 2) {
                const params = selectedProducts.map(id => `products=${id}`).join('&');
                window.location.href = `/products/compare/?${params}`;
            }
        });
    }
    
    // ==================== Image Gallery ====================
    const thumbnails = document.querySelectorAll('.product-thumbnail');
    const mainImage = document.getElementById('main-product-image');
    
    thumbnails.forEach(thumb => {
        thumb.addEventListener('click', function() {
            const newSrc = this.dataset.fullImage || this.src;
            if (mainImage) {
                mainImage.style.opacity = '0';
                setTimeout(() => {
                    mainImage.src = newSrc;
                    mainImage.style.opacity = '1';
                }, 200);
            }
            
            // Update active thumbnail
            thumbnails.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
        });
    });
    
    // ==================== Filter Chips ====================
    const filterChips = document.querySelectorAll('.filter-chip-remove');
    
    filterChips.forEach(chip => {
        chip.addEventListener('click', function() {
            const chipElement = this.closest('.filter-chip');
            const filterType = chipElement.dataset.filterType;
            const filterValue = chipElement.dataset.filterValue;
            
            // Remove chip with animation
            chipElement.style.opacity = '0';
            chipElement.style.transform = 'scale(0.8)';
            
            setTimeout(() => {
                chipElement.remove();
                // Trigger filter update
                updateFilters(filterType, filterValue);
            }, 300);
        });
    });
    
    // ==================== Smooth Scroll to Reviews ====================
    const reviewLinks = document.querySelectorAll('a[href="#reviews"]');
    
    reviewLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const reviewSection = document.getElementById('reviews');
            if (reviewSection) {
                reviewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });
    
    // ==================== Star Rating Interaction ====================
    const starRatings = document.querySelectorAll('.star-rating-input');
    
    starRatings.forEach(container => {
        const stars = container.querySelectorAll('i');
        const input = container.querySelector('input[type="hidden"]');
        
        stars.forEach((star, index) => {
            star.addEventListener('mouseenter', function() {
                highlightStars(stars, index + 1);
            });
            
            star.addEventListener('click', function() {
                const rating = index + 1;
                if (input) input.value = rating;
                highlightStars(stars, rating);
                stars.forEach(s => s.style.opacity = '1');
            });
        });
        
        container.addEventListener('mouseleave', function() {
            const currentRating = input ? parseInt(input.value) || 0 : 0;
            highlightStars(stars, currentRating);
        });
    });
    
    function highlightStars(stars, count) {
        stars.forEach((star, index) => {
            if (index < count) {
                star.classList.remove('far');
                star.classList.add('fas');
            } else {
                star.classList.remove('fas');
                star.classList.add('far');
            }
        });
    }
    
    // ==================== Review Image Preview ====================
    const reviewImageInputs = document.querySelectorAll('.review-image-input');
    
    reviewImageInputs.forEach(input => {
        input.addEventListener('change', function() {
            const preview = document.getElementById('review-image-preview');
            if (preview && this.files) {
                preview.innerHTML = '';
                
                Array.from(this.files).slice(0, 5).forEach(file => {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.className = 'review-preview-image';
                        preview.appendChild(img);
                    };
                    reader.readAsDataURL(file);
                });
            }
        });
    });
    
    // ==================== Price Alert Toggle ====================
    const priceAlertButtons = document.querySelectorAll('.price-alert-toggle');
    
    priceAlertButtons.forEach(button => {
        button.addEventListener('click', function() {
            const modal = document.getElementById('price-alert-modal');
            const productId = this.dataset.productId;
            const currentPrice = this.dataset.currentPrice;
            
            if (modal) {
                const form = modal.querySelector('form');
                if (form) {
                    form.action = `/products/${productId}/alert/price/`;
                    const priceInput = form.querySelector('input[name="target_price"]');
                    if (priceInput && currentPrice) {
                        priceInput.placeholder = `Precio actual: €${currentPrice}`;
                    }
                }
            }
        });
    });
    
    // ==================== Stock Alert ====================
    const stockAlertButtons = document.querySelectorAll('.stock-alert-btn');
    
    stockAlertButtons.forEach(button => {
        button.addEventListener('click', function() {
            const productId = this.dataset.productId;
            const email = this.dataset.userEmail;
            
            if (!email) {
                showToast('Debes iniciar sesión para recibir alertas', 'warning');
                return;
            }
            
            fetch(`/products/${productId}/alert/stock/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
            })
            .then(response => response.json())
            .then(data => {
                showToast(data.message || 'Alerta creada', 'success');
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Error al crear la alerta', 'error');
            });
        });
    });
    
    // ==================== Lazy Loading Images ====================
    const lazyImages = document.querySelectorAll('img[data-src]');
    
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
                observer.unobserve(img);
            }
        });
    });
    
    lazyImages.forEach(img => imageObserver.observe(img));
    
    // ==================== Quantity Selector Enhancement ====================
    const quantityInputs = document.querySelectorAll('.quantity-input');
    
    quantityInputs.forEach(input => {
        const minusBtn = input.parentElement.querySelector('.quantity-minus');
        const plusBtn = input.parentElement.querySelector('.quantity-plus');
        
        if (minusBtn) {
            minusBtn.addEventListener('click', function() {
                let value = parseInt(input.value) || 1;
                if (value > 1) {
                    input.value = value - 1;
                    input.dispatchEvent(new Event('change'));
                }
            });
        }
        
        if (plusBtn) {
            plusBtn.addEventListener('click', function() {
                let value = parseInt(input.value) || 1;
                const max = parseInt(input.max) || 99;
                if (value < max) {
                    input.value = value + 1;
                    input.dispatchEvent(new Event('change'));
                }
            });
        }
    });
    
    // ==================== Toast Notifications ====================
    function showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container') || createToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${getToastIcon(type)}"></i>
                <span>${message}</span>
            </div>
            <button class="toast-close">&times;</button>
        `;
        
        toastContainer.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 10);
        
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => removeToast(toast));
        
        setTimeout(() => removeToast(toast), 5000);
    }
    
    function removeToast(toast) {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }
    
    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        `;
        document.body.appendChild(container);
        return container;
    }
    
    function getToastIcon(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        return icons[type] || icons.info;
    }
    
    // ==================== Utility Functions ====================
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    function updateWishlistCounter() {
        const counter = document.getElementById('wishlist-counter');
        if (counter) {
            fetch('/products/wishlist/count/')
                .then(response => response.json())
                .then(data => {
                    counter.textContent = data.count;
                    if (data.count > 0) {
                        counter.style.display = 'inline-block';
                    } else {
                        counter.style.display = 'none';
                    }
                });
        }
    }
    
    function updateFilters(filterType, filterValue) {
        const url = new URL(window.location);
        const params = url.searchParams;
        
        // Remove the filter
        const values = params.getAll(filterType);
        params.delete(filterType);
        values.filter(v => v !== filterValue).forEach(v => params.append(filterType, v));
        
        // Reload with new params
        window.location.search = params.toString();
    }
    
    // ==================== Scroll Animations ====================
    const animateOnScroll = () => {
        const elements = document.querySelectorAll('.animate-on-scroll');
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animated');
                }
            });
        }, { threshold: 0.1 });
        
        elements.forEach(el => observer.observe(el));
    };
    
    animateOnScroll();
    
    // ==================== Back to Top Button ====================
    const backToTopButton = document.getElementById('back-to-top');
    
    if (backToTopButton) {
        window.addEventListener('scroll', () => {
            if (window.pageYOffset > 300) {
                backToTopButton.classList.add('show');
            } else {
                backToTopButton.classList.remove('show');
            }
        });
        
        backToTopButton.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
});

// ==================== Add CSS for Toast Notifications ====================
const toastStyles = `
.toast-notification {
    background: white;
    border-radius: 0.5rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    padding: 1rem 1.5rem;
    min-width: 300px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    transform: translateX(400px);
    opacity: 0;
    transition: all 0.3s ease;
}

.toast-notification.show {
    transform: translateX(0);
    opacity: 1;
}

.toast-content {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.toast-success { border-left: 4px solid #28a745; }
.toast-error { border-left: 4px solid #dc3545; }
.toast-warning { border-left: 4px solid #ffc107; }
.toast-info { border-left: 4px solid #17a2b8; }

.toast-success i { color: #28a745; }
.toast-error i { color: #dc3545; }
.toast-warning i { color: #ffc107; }
.toast-info i { color: #17a2b8; }

.toast-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #999;
    cursor: pointer;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.toast-close:hover {
    color: #333;
}

.review-preview-image {
    width: 100px;
    height: 100px;
    object-fit: cover;
    border-radius: 0.5rem;
    margin: 0.5rem;
}

#back-to-top {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background: var(--gold);
    color: white;
    border: none;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    cursor: pointer;
    opacity: 0;
    transform: scale(0);
    transition: all 0.3s ease;
    z-index: 1000;
}

#back-to-top.show {
    opacity: 1;
    transform: scale(1);
}

#back-to-top:hover {
    background: var(--gold-dark);
    transform: scale(1.1);
}
`;

const styleSheet = document.createElement('style');
styleSheet.textContent = toastStyles;
document.head.appendChild(styleSheet);

// Product Detail Improved JavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    // ==================== Thumbnail Image Switching ====================
    const mainImage = document.getElementById('mainProductImage');
    const thumbnails = document.querySelectorAll('.thumbnail-img');
    
    thumbnails.forEach(thumb => {
        thumb.addEventListener('click', function() {
            // Remove active class from all thumbnails
            thumbnails.forEach(t => t.classList.remove('active'));
            
            // Add active class to clicked thumbnail
            this.classList.add('active');
            
            // Change main image
            const newImageSrc = this.getAttribute('data-image');
            mainImage.src = newImageSrc;
            
            // Update zoom modal image
            const zoomModalImage = document.querySelector('#imageZoomModal img');
            if (zoomModalImage) {
                zoomModalImage.src = newImageSrc;
            }
        });
    });

    // ==================== Size Selection with Price Update ====================
    const sizeRadios = document.querySelectorAll('.size-radio');
    const priceDisplay = document.querySelector('.product-price');
    
    sizeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.checked && priceDisplay) {
                const newPrice = this.getAttribute('data-price');
                priceDisplay.textContent = '€' + newPrice;
                
                // Animation effect
                priceDisplay.style.transform = 'scale(1.1)';
                setTimeout(() => {
                    priceDisplay.style.transform = 'scale(1)';
                }, 300);
            }
        });
    });

    // ==================== Quantity Controls ====================
    const decrementButtons = document.querySelectorAll('.decrement-qty');
    const incrementButtons = document.querySelectorAll('.increment-qty');
    
    decrementButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const itemId = this.getAttribute('data-item_id');
            const qtyInput = document.querySelector(`.id_qty_${itemId}`);
            
            if (qtyInput) {
                let currentValue = parseInt(qtyInput.value);
                const minValue = parseInt(qtyInput.getAttribute('min'));
                
                if (currentValue > minValue) {
                    qtyInput.value = currentValue - 1;
                    qtyInput.dispatchEvent(new Event('change'));
                }
            }
        });
    });
    
    incrementButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const itemId = this.getAttribute('data-item_id');
            const qtyInput = document.querySelector(`.id_qty_${itemId}`);
            
            if (qtyInput) {
                let currentValue = parseInt(qtyInput.value);
                const maxValue = parseInt(qtyInput.getAttribute('max'));
                
                if (currentValue < maxValue) {
                    qtyInput.value = currentValue + 1;
                    qtyInput.dispatchEvent(new Event('change'));
                }
            }
        });
    });

    // ==================== Wishlist Toggle ====================
    const wishlistBtn = document.querySelector('.wishlist-btn');
    
    if (wishlistBtn) {
        wishlistBtn.addEventListener('click', function() {
            const productId = this.getAttribute('data-product-id');
            const heartIcon = this.querySelector('.fa-heart');
            
            // Toggle visual state
            if (heartIcon.classList.contains('far')) {
                // Add to wishlist
                heartIcon.classList.remove('far');
                heartIcon.classList.add('fas');
                this.classList.add('active');
                
                // Show toast notification
                showToast('success', 'Añadido a tu lista de deseos');
                
                // TODO: Send AJAX request to backend
                // addToWishlist(productId);
                
            } else {
                // Remove from wishlist
                heartIcon.classList.remove('fas');
                heartIcon.classList.add('far');
                this.classList.remove('active');
                
                showToast('info', 'Eliminado de tu lista de deseos');
                
                // TODO: Send AJAX request to backend
                // removeFromWishlist(productId);
            }
        });
    }

    // ==================== Review Star Rating (Modal) ====================
    const ratingInputs = document.querySelectorAll('.rating-input input[type="radio"]');
    const ratingLabels = document.querySelectorAll('.rating-input label');
    
    ratingLabels.forEach((label, index) => {
        label.addEventListener('mouseenter', function() {
            // Highlight stars on hover
            for (let i = 0; i <= index; i++) {
                ratingLabels[ratingLabels.length - 1 - i].style.color = '#ffc107';
            }
        });
    });
    
    const ratingContainer = document.querySelector('.rating-input');
    if (ratingContainer) {
        ratingContainer.addEventListener('mouseleave', function() {
            // Reset to selected rating
            const checkedRating = document.querySelector('.rating-input input[type="radio"]:checked');
            
            ratingLabels.forEach(label => {
                label.style.color = '#ddd';
            });
            
            if (checkedRating) {
                const checkedIndex = Array.from(ratingInputs).indexOf(checkedRating);
                for (let i = 0; i <= checkedIndex; i++) {
                    ratingLabels[ratingLabels.length - 1 - i].style.color = '#ffc107';
                }
            }
        });
    }

    // ==================== Smooth Scroll to Reviews ====================
    const reviewLinks = document.querySelectorAll('a[href="#reviews-section"]');
    
    reviewLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Activate reviews tab
            const reviewsTab = document.getElementById('reviews-tab');
            if (reviewsTab) {
                reviewsTab.click();
            }
            
            // Scroll to reviews section with offset
            setTimeout(() => {
                const reviewsSection = document.getElementById('reviews');
                if (reviewsSection) {
                    const offset = 100;
                    const elementPosition = reviewsSection.getBoundingClientRect().top;
                    const offsetPosition = elementPosition + window.pageYOffset - offset;
                    
                    window.scrollTo({
                        top: offsetPosition,
                        behavior: 'smooth'
                    });
                }
            }, 100);
        });
    });

    // ==================== Product Tabs Tracking ====================
    const productTabs = document.querySelectorAll('#productTabs button');
    
    productTabs.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(e) {
            const tabName = e.target.id.replace('-tab', '');
            console.log('User viewed tab:', tabName);
            
            // TODO: Track with analytics
            // trackEvent('product_tab_view', { tab: tabName });
        });
    });

    // ==================== Image Zoom Modal Enhancement ====================
    const imageZoomModal = document.getElementById('imageZoomModal');
    
    if (imageZoomModal) {
        imageZoomModal.addEventListener('shown.bs.modal', function() {
            const modalImage = this.querySelector('img');
            
            // Enable pinch zoom on mobile
            if (modalImage && 'ontouchstart' in window) {
                enablePinchZoom(modalImage);
            }
        });
    }

    // ==================== Sample Checkbox Enhanced ====================
    const sampleCheckbox = document.getElementById('addSample');
    
    if (sampleCheckbox) {
        sampleCheckbox.addEventListener('change', function() {
            const priceDisplay = document.querySelector('.current-price');
            
            if (this.checked) {
                showToast('info', 'Muestra de 2ml añadida (+€3.99)');
            } else {
                showToast('info', 'Muestra eliminada');
            }
        });
    }

    // ==================== Add to Cart Enhanced ====================
    const addToCartForm = document.querySelector('.add-to-cart-form');
    
    if (addToCartForm) {
        addToCartForm.addEventListener('submit', function(e) {
            // Don't prevent default - let it submit normally
            
            const btn = this.querySelector('button[type="submit"]');
            const originalText = btn.innerHTML;
            
            // Visual feedback
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Añadiendo...';
            btn.disabled = true;
            
            // Re-enable after short delay (form will redirect)
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }, 2000);
        });
    }

    // ==================== Share Buttons ====================
    const shareButtons = document.querySelectorAll('.share-buttons a');
    
    shareButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const platform = this.querySelector('i').classList[1].replace('fa-', '');
            const productUrl = window.location.href;
            const productTitle = document.querySelector('.product-title').textContent;
            
            let shareUrl = '';
            
            switch(platform) {
                case 'facebook-f':
                    shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(productUrl)}`;
                    break;
                case 'twitter':
                    shareUrl = `https://twitter.com/intent/tweet?url=${encodeURIComponent(productUrl)}&text=${encodeURIComponent(productTitle)}`;
                    break;
                case 'pinterest':
                    const imageUrl = document.getElementById('mainProductImage').src;
                    shareUrl = `https://pinterest.com/pin/create/button/?url=${encodeURIComponent(productUrl)}&media=${encodeURIComponent(imageUrl)}&description=${encodeURIComponent(productTitle)}`;
                    break;
                case 'envelope':
                    shareUrl = `mailto:?subject=${encodeURIComponent(productTitle)}&body=${encodeURIComponent(productUrl)}`;
                    break;
            }
            
            if (shareUrl) {
                if (platform === 'envelope') {
                    window.location.href = shareUrl;
                } else {
                    window.open(shareUrl, '_blank', 'width=600,height=400');
                }
            }
        });
    });

    // ==================== Lazy Loading for Images ====================
    if ('IntersectionObserver' in window) {
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
        });
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }

    // ==================== Helper Functions ====================
    
    /**
     * Show toast notification
     */
    function showToast(type, message) {
        // Check if Bootstrap toast container exists
        let toastContainer = document.querySelector('.toast-container');
        
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }
        
        const toastId = 'toast-' + Date.now();
        const bgClass = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-info';
        
        const toastHTML = `
            <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHTML);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
        toast.show();
        
        // Remove toast element after it's hidden
        toastElement.addEventListener('hidden.bs.toast', function() {
            this.remove();
        });
    }
    
    /**
     * Enable pinch zoom for images
     */
    function enablePinchZoom(image) {
        let scale = 1;
        let lastDistance = 0;
        
        image.addEventListener('touchstart', function(e) {
            if (e.touches.length === 2) {
                lastDistance = getDistance(e.touches[0], e.touches[1]);
            }
        });
        
        image.addEventListener('touchmove', function(e) {
            if (e.touches.length === 2) {
                e.preventDefault();
                
                const currentDistance = getDistance(e.touches[0], e.touches[1]);
                const delta = currentDistance - lastDistance;
                
                scale += delta * 0.01;
                scale = Math.min(Math.max(1, scale), 3); // Limit scale between 1 and 3
                
                image.style.transform = `scale(${scale})`;
                lastDistance = currentDistance;
            }
        });
        
        image.addEventListener('touchend', function(e) {
            if (e.touches.length < 2) {
                // Reset zoom when fingers are lifted
                setTimeout(() => {
                    scale = 1;
                    image.style.transform = 'scale(1)';
                }, 300);
            }
        });
        
        function getDistance(touch1, touch2) {
            const dx = touch1.clientX - touch2.clientX;
            const dy = touch1.clientY - touch2.clientY;
            return Math.sqrt(dx * dx + dy * dy);
        }
    }
    
    /**
     * Format price with currency
     */
    function formatPrice(price) {
        return '€' + parseFloat(price).toFixed(2);
    }
    
    /**
     * Calculate price with sample
     */
    function calculateTotalPrice() {
        const sizeRadio = document.querySelector('.size-radio:checked');
        const sampleCheckbox = document.getElementById('addSample');
        
        let basePrice = 0;
        
        if (sizeRadio) {
            basePrice = parseFloat(sizeRadio.getAttribute('data-price'));
        }
        
        if (sampleCheckbox && sampleCheckbox.checked) {
            basePrice += 3.99;
        }
        
        return basePrice;
    }

    // ==================== Accessibility Enhancements ====================
    
    // Add keyboard navigation for thumbnails
    thumbnails.forEach((thumb, index) => {
        thumb.setAttribute('tabindex', '0');
        thumb.setAttribute('role', 'button');
        thumb.setAttribute('aria-label', `Ver imagen ${index + 1}`);
        
        thumb.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });
    
    // Add aria-live region for price changes
    const priceRegion = document.querySelector('.price-section');
    if (priceRegion) {
        priceRegion.setAttribute('aria-live', 'polite');
    }
    
    // Announce tab changes to screen readers
    productTabs.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function() {
            const announcement = `${this.textContent} tab selected`;
            announceToScreenReader(announcement);
        });
    });
    
    function announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('role', 'status');
        announcement.setAttribute('aria-live', 'polite');
        announcement.className = 'visually-hidden';
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        
        setTimeout(() => {
            announcement.remove();
        }, 1000);
    }

    // ==================== Performance Monitoring ====================
    
    // Log page load time
    window.addEventListener('load', function() {
        const loadTime = performance.now();
        console.log(`Product detail page loaded in ${loadTime.toFixed(2)}ms`);
        
        // TODO: Send to analytics
        // trackTiming('page_load', 'product_detail', loadTime);
    });

    console.log('Product detail page initialized successfully');
});

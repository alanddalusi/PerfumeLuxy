// Luxury Product Detail JavaScript
document.addEventListener('DOMContentLoaded', function() {
    
    // =====================================
    // Luxury Tabs Functionality
    // =====================================
    const tabButtons = document.querySelectorAll('.luxury-tab-btn');
    const tabPanels = document.querySelectorAll('.luxury-tab-panel');
    
    if (tabButtons.length > 0) {
        tabButtons.forEach(button => {
            button.addEventListener('click', function() {
                const targetTab = this.getAttribute('data-tab');
                
                // Remove active class from all buttons and panels
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabPanels.forEach(panel => panel.classList.remove('active'));
                
                // Add active class to clicked button
                this.classList.add('active');
                
                // Show corresponding panel
                const targetPanel = document.getElementById(`luxury-${targetTab}`);
                if (targetPanel) {
                    targetPanel.classList.add('active');
                }
            });
        });
    }
    
    // =====================================
    // Luxury Quantity Selector
    // =====================================
    const decrementBtns = document.querySelectorAll('.decrement-qty');
    const incrementBtns = document.querySelectorAll('.increment-qty');
    
    decrementBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const itemId = this.getAttribute('data-item_id');
            const input = document.querySelector(`.id_qty_${itemId}`);
            if (input) {
                let currentValue = parseInt(input.value);
                if (currentValue > 1) {
                    input.value = currentValue - 1;
                }
            }
        });
    });
    
    incrementBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const itemId = this.getAttribute('data-item_id');
            const input = document.querySelector(`.id_qty_${itemId}`);
            if (input) {
                let currentValue = parseInt(input.value);
                const maxValue = parseInt(input.getAttribute('max')) || 99;
                if (currentValue < maxValue) {
                    input.value = currentValue + 1;
                }
            }
        });
    });
    
    // =====================================
    // Luxury Image Gallery
    // =====================================
    const thumbnails = document.querySelectorAll('.luxury-thumbnail');
    const mainImage = document.querySelector('.luxury-main-image');
    
    if (thumbnails.length > 0 && mainImage) {
        thumbnails.forEach(thumb => {
            thumb.addEventListener('click', function() {
                // Remove active class from all thumbnails
                thumbnails.forEach(t => t.classList.remove('active'));
                
                // Add active class to clicked thumbnail
                this.classList.add('active');
                
                // Change main image
                const newImageSrc = this.getAttribute('data-image');
                if (newImageSrc) {
                    mainImage.src = newImageSrc;
                    mainImage.alt = this.alt;
                }
            });
        });
    }
    
    // =====================================
    // Luxury Zoom Functionality
    // =====================================
    const zoomBtn = document.querySelector('.luxury-zoom-btn');
    const mainImageContainer = document.querySelector('.luxury-main-image-container');
    
    if (zoomBtn && mainImageContainer) {
        zoomBtn.addEventListener('click', function() {
            mainImageContainer.classList.toggle('zoomed');
            
            // Update zoom button icon
            const icon = this.querySelector('i');
            if (mainImageContainer.classList.contains('zoomed')) {
                icon.classList.remove('fa-search-plus');
                icon.classList.add('fa-search-minus');
            } else {
                icon.classList.remove('fa-search-minus');
                icon.classList.add('fa-search-plus');
            }
        });
    }
    
    // =====================================
    // Luxury Size Selector
    // =====================================
    const sizeOptions = document.querySelectorAll('.luxury-size-option');
    
    if (sizeOptions.length > 0) {
        sizeOptions.forEach(option => {
            option.addEventListener('click', function() {
                // Remove active class from all options
                sizeOptions.forEach(opt => opt.classList.remove('active'));
                
                // Add active class to selected option
                this.classList.add('active');
                
                // Update hidden input value
                const hiddenInput = document.querySelector('input[name="product_size"]');
                if (hiddenInput) {
                    hiddenInput.value = this.textContent.trim();
                }
                
                // Update price if different sizes have different prices
                const priceAttr = this.getAttribute('data-price');
                if (priceAttr) {
                    const priceElement = document.querySelector('.luxury-current-price');
                    if (priceElement) {
                        priceElement.textContent = priceAttr;
                    }
                }
            });
        });
    }
    
    // =====================================
    // Luxury Wishlist Functionality
    // =====================================
    const wishlistBtns = document.querySelectorAll('.wishlist-btn');
    
    wishlistBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const productId = this.getAttribute('data-product-id');
            const icon = this.querySelector('i');
            
            // Toggle heart icon
            if (icon.classList.contains('far')) {
                icon.classList.remove('far');
                icon.classList.add('fas');
                this.style.color = '#dc3545';
                
                // Show success message
                showLuxuryToast('Añadido a la lista de deseos', 'success');
            } else {
                icon.classList.remove('fas');
                icon.classList.add('far');
                this.style.color = '';
                
                // Show info message
                showLuxuryToast('Eliminado de la lista de deseos', 'info');
            }
        });
    });
    
    // =====================================
    // Luxury Toast Notifications
    // =====================================
    function showLuxuryToast(message, type = 'success') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `luxury-toast luxury-toast-${type}`;
        toast.innerHTML = `
            <div class="luxury-toast-content">
                <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;
        
        // Add toast styles if not exist
        if (!document.getElementById('luxury-toast-styles')) {
            const styles = document.createElement('style');
            styles.id = 'luxury-toast-styles';
            styles.textContent = `
                .luxury-toast {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: white;
                    border-radius: 10px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                    padding: 1rem 1.5rem;
                    z-index: 9999;
                    transform: translateX(400px);
                    transition: transform 0.3s ease;
                    border-left: 4px solid var(--luxury-gold);
                }
                
                .luxury-toast.show {
                    transform: translateX(0);
                }
                
                .luxury-toast-content {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    font-weight: 600;
                    color: var(--luxury-dark);
                }
                
                .luxury-toast-success {
                    border-left-color: #28a745;
                }
                
                .luxury-toast-info {
                    border-left-color: #17a2b8;
                }
                
                .luxury-toast i {
                    font-size: 1.2rem;
                    color: var(--luxury-gold);
                }
                
                .luxury-toast-success i {
                    color: #28a745;
                }
                
                .luxury-toast-info i {
                    color: #17a2b8;
                }
            `;
            document.head.appendChild(styles);
        }
        
        // Add to DOM
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Auto remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 3000);
    }
    
    // =====================================
    // Luxury Smooth Scrolling for Anchors
    // =====================================
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    
    anchorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // =====================================
    // Luxury Loading Animation for Forms
    // =====================================
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                const originalText = submitBtn.textContent || submitBtn.value;
                
                // Show loading state
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Procesando...';
                submitBtn.disabled = true;
                
                // Reset after 5 seconds if no response (fallback)
                setTimeout(() => {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }, 5000);
            }
        });
    });
    
    // =====================================
    // Luxury Parallax Effect (Optional)
    // =====================================
    const parallaxElements = document.querySelectorAll('.luxury-parallax');
    
    if (parallaxElements.length > 0) {
        window.addEventListener('scroll', function() {
            const scrolled = window.pageYOffset;
            const rate = scrolled * -0.5;
            
            parallaxElements.forEach(element => {
                element.style.transform = `translateY(${rate}px)`;
            });
        });
    }
    
});
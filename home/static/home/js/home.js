// Home Page Interactions
document.addEventListener('DOMContentLoaded', function() {
    // Hero Scroll Indicator
    const scrollIndicator = document.querySelector('.hero-scroll-indicator');
    if (scrollIndicator) {
        scrollIndicator.addEventListener('click', function() {
            const categoriesSection = document.querySelector('.categories-section');
            if (categoriesSection) {
                categoriesSection.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }

    // Hide scroll indicator on scroll
    let lastScrollTop = 0;
    window.addEventListener('scroll', function() {
        const st = window.pageYOffset || document.documentElement.scrollTop;
        if (st > 100 && scrollIndicator) {
            scrollIndicator.style.opacity = '0';
        } else if (scrollIndicator) {
            scrollIndicator.style.opacity = '1';
        }
        lastScrollTop = st <= 0 ? 0 : st;
    });

    // Animate elements on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -100px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe category cards
    document.querySelectorAll('.category-card').forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = `all 0.6s ease ${index * 0.1}s`;
        observer.observe(card);
    });

    // Observe feature boxes
    document.querySelectorAll('.feature-box').forEach((box, index) => {
        box.style.opacity = '0';
        box.style.transform = 'translateY(30px)';
        box.style.transition = `all 0.6s ease ${index * 0.1}s`;
        observer.observe(box);
    });

    // Observe newsletter section
    const newsletterCard = document.querySelector('.newsletter-card');
    if (newsletterCard) {
        newsletterCard.style.opacity = '0';
        newsletterCard.style.transform = 'translateY(30px)';
        newsletterCard.style.transition = 'all 0.8s ease';
        observer.observe(newsletterCard);
    }

    // Animate stats counter
    const animateCounter = (element, target, duration = 2000) => {
        let start = 0;
        const increment = target / (duration / 16);
        const timer = setInterval(() => {
            start += increment;
            if (start >= target) {
                element.textContent = formatNumber(target);
                clearInterval(timer);
            } else {
                element.textContent = formatNumber(Math.floor(start));
            }
        }, 16);
    };

    const formatNumber = (num) => {
        if (num >= 1000) {
            return (num / 1000).toFixed(0) + 'K+';
        }
        return num + '+';
    };

    const statsObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const statNumber = entry.target.querySelector('.stat-number');
                if (statNumber && !statNumber.dataset.animated) {
                    const target = parseInt(statNumber.textContent.replace(/[^0-9]/g, ''));
                    statNumber.dataset.animated = 'true';
                    animateCounter(statNumber, target);
                }
                statsObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    document.querySelectorAll('.stat-item').forEach(stat => {
        statsObserver.observe(stat);
    });

    // Newsletter form enhancement
    const newsletterForm = document.querySelector('#newsletterSignUp form');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Subscribing...';
                submitBtn.disabled = true;
            }
        });
    }

    // Add parallax effect to hero
    const hero = document.querySelector('.hero-modern');
    if (hero) {
        window.addEventListener('scroll', function() {
            const scrolled = window.pageYOffset;
            const parallax = scrolled * 0.5;
            hero.style.backgroundPositionY = parallax + 'px';
        });
    }

    // Category card hover sound effect (optional)
    document.querySelectorAll('.category-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.querySelector('.category-overlay').style.opacity = '1';
        });
        
        card.addEventListener('mouseleave', function() {
            this.querySelector('.category-overlay').style.opacity = '0';
        });
    });

    // Toast notification for newsletter modal
    const newsletterModal = document.getElementById('newsletterSignUp');
    if (newsletterModal) {
        newsletterModal.addEventListener('shown.bs.modal', function() {
            const input = this.querySelector('input[type="email"]');
            if (input) {
                setTimeout(() => input.focus(), 300);
            }
        });
    }

    // Add ripple effect to buttons
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;

            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');

            this.appendChild(ripple);

            setTimeout(() => ripple.remove(), 600);
        });
    });

    // Brands carousel auto-scroll animation
    const brandsCarousel = document.querySelector('.brands-carousel');
    if (brandsCarousel) {
        let scrollAmount = 0;
        const brandItems = brandsCarousel.querySelectorAll('.brand-item');
        
        brandItems.forEach((item, index) => {
            item.style.animation = `fadeInScale 0.6s ease ${index * 0.1}s backwards`;
        });
    }

    // Testimonials auto-rotate
    const testimonialCards = document.querySelectorAll('.testimonial-card');
    let currentTestimonial = 0;

    const highlightTestimonial = () => {
        testimonialCards.forEach((card, index) => {
            if (index === currentTestimonial) {
                card.style.transform = 'translateY(-10px) scale(1.02)';
                card.style.boxShadow = '0 20px 40px rgba(212, 175, 55, 0.3)';
            } else {
                card.style.transform = '';
                card.style.boxShadow = '';
            }
        });
        currentTestimonial = (currentTestimonial + 1) % testimonialCards.length;
    };

    if (testimonialCards.length > 0) {
        setInterval(highlightTestimonial, 3000);
    }

    // Instagram items hover effect
    document.querySelectorAll('.instagram-item').forEach(item => {
        item.addEventListener('mouseenter', function() {
            this.style.zIndex = '10';
        });
        
        item.addEventListener('mouseleave', function() {
            this.style.zIndex = '1';
        });
    });

    // Featured products wishlist buttons
    document.querySelectorAll('.featured-wishlist-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const icon = this.querySelector('i');
            const productId = this.dataset.productId;
            
            // Toggle heart icon
            if (icon.classList.contains('far')) {
                icon.classList.remove('far');
                icon.classList.add('fas');
                this.style.color = '#dc3545';
                
                // Show toast if function exists
                if (typeof showToast === 'function') {
                    showToast('Added to wishlist!', 'success');
                }
            } else {
                icon.classList.remove('fas');
                icon.classList.add('far');
                this.style.color = '';
                
                if (typeof showToast === 'function') {
                    showToast('Removed from wishlist', 'info');
                }
            }
            
            // Store in localStorage for demo
            const wishlist = JSON.parse(localStorage.getItem('wishlist') || '[]');
            const index = wishlist.indexOf(productId);
            if (index > -1) {
                wishlist.splice(index, 1);
            } else {
                wishlist.push(productId);
            }
            localStorage.setItem('wishlist', JSON.stringify(wishlist));
        });
    });

    // Check localStorage for wishlist on load
    const wishlist = JSON.parse(localStorage.getItem('wishlist') || '[]');
    document.querySelectorAll('.featured-wishlist-btn').forEach(button => {
        const productId = button.dataset.productId;
        if (wishlist.includes(productId)) {
            const icon = button.querySelector('i');
            icon.classList.remove('far');
            icon.classList.add('fas');
            button.style.color = '#dc3545';
        }
    });

    // Smooth reveal for sections
    const revealSections = document.querySelectorAll('.brands-section, .testimonials-section, .instagram-section');
    const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                sectionObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    revealSections.forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(50px)';
        section.style.transition = 'all 1s ease';
        sectionObserver.observe(section);
    });

    // Add CSS for ripple effect and animations
    const style = document.createElement('style');
    style.textContent = `
        .btn {
            position: relative;
            overflow: hidden;
        }
        .ripple {
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.6);
            transform: scale(0);
            animation: ripple-animation 0.6s ease-out;
            pointer-events: none;
        }
        @keyframes ripple-animation {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
        @keyframes fadeInScale {
            from {
                opacity: 0;
                transform: scale(0.8);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }
    `;
    document.head.appendChild(style);

    console.log('Home page interactions initialized ✨');
});

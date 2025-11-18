/**
 * CHECKOUT LUXURY JAVASCRIPT
 * Premium checkout functionality with step navigation and form validation
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize checkout functionality
    initializeLuxuryCheckout();
});

function initializeLuxuryCheckout() {
    // Step navigation
    setupStepNavigation();
    
    // Form validation
    setupFormValidation();
    
    // Stripe integration
    setupStripeElements();
    
    // Progress indicator
    updateProgressIndicator();
    
    // Trust badges animation
    animateTrustBadges();
}

/**
 * Step Navigation System
 */
function setupStepNavigation() {
    const steps = document.querySelectorAll('.luxury-step');
    const sections = document.querySelectorAll('.luxury-form-section');
    let currentStep = 1;

    // Continue to shipping button
    document.getElementById('continue-to-shipping')?.addEventListener('click', function() {
        if (validatePersonalDetails()) {
            goToStep(2);
        }
    });

    // Continue to payment button
    document.getElementById('continue-to-payment')?.addEventListener('click', function() {
        if (validateShippingDetails()) {
            goToStep(3);
        }
    });

    // Back buttons
    document.getElementById('back-to-personal')?.addEventListener('click', function() {
        goToStep(1);
    });

    document.getElementById('back-to-shipping')?.addEventListener('click', function() {
        goToStep(2);
    });

    function goToStep(stepNumber) {
        // Hide all sections
        sections.forEach(section => {
            section.style.display = 'none';
            section.classList.remove('active');
        });

        // Show target section
        const targetSection = document.getElementById(`step-${stepNumber}`);
        if (targetSection) {
            targetSection.style.display = 'block';
            targetSection.classList.add('active');
        }

        // Update step indicators
        updateStepIndicators(stepNumber);
        
        // Update progress line
        updateProgressLine(stepNumber);
        
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
        
        currentStep = stepNumber;
    }

    function updateStepIndicators(activeStep) {
        steps.forEach((step, index) => {
            const stepNumber = index + 1;
            const circle = step.querySelector('.luxury-step-circle');
            const numberSpan = circle.querySelector('span');
            const checkIcon = circle.querySelector('i');

            step.classList.remove('active', 'completed');
            circle.classList.remove('active', 'completed');

            if (stepNumber < activeStep) {
                // Completed step
                step.classList.add('completed');
                circle.classList.add('completed');
                if (numberSpan) numberSpan.style.display = 'none';
                if (checkIcon) checkIcon.style.display = 'block';
            } else if (stepNumber === activeStep) {
                // Active step
                step.classList.add('active');
                circle.classList.add('active');
                if (numberSpan) numberSpan.style.display = 'block';
                if (checkIcon) checkIcon.style.display = 'none';
            } else {
                // Future step
                if (numberSpan) numberSpan.style.display = 'block';
                if (checkIcon) checkIcon.style.display = 'none';
            }
        });
    }

    function updateProgressLine(activeStep) {
        const progressLine = document.getElementById('progress-line');
        if (progressLine) {
            const width = ((activeStep - 1) / (steps.length - 1)) * 100;
            progressLine.style.width = `${width}%`;
        }
    }
}

/**
 * Form Validation System
 */
function setupFormValidation() {
    // Real-time validation for inputs
    const inputs = document.querySelectorAll('.luxury-form-input');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            validateInput(this);
        });

        input.addEventListener('input', function() {
            clearError(this);
        });
    });
}

function validateInput(input) {
    const value = input.value.trim();
    const fieldName = input.name;
    let isValid = true;
    let errorMessage = '';

    // Clear previous error
    clearError(input);

    // Required field validation
    if (input.hasAttribute('required') && !value) {
        isValid = false;
        errorMessage = 'Este campo es obligatorio';
    }

    // Specific field validations
    switch (fieldName) {
        case 'full_name':
            if (value && value.length < 2) {
                isValid = false;
                errorMessage = 'El nombre debe tener al menos 2 caracteres';
            }
            break;
        
        case 'email':
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (value && !emailRegex.test(value)) {
                isValid = false;
                errorMessage = 'Introduce un email válido';
            }
            break;
        
        case 'phone_number':
            const phoneRegex = /^[\+]?[\d\s\-\(\)]{9,}$/;
            if (value && !phoneRegex.test(value)) {
                isValid = false;
                errorMessage = 'Introduce un número de teléfono válido';
            }
            break;
        
        case 'postcode':
            const postcodeRegex = /^\d{5}$/;
            if (value && !postcodeRegex.test(value)) {
                isValid = false;
                errorMessage = 'El código postal debe tener 5 dígitos';
            }
            break;
    }

    if (!isValid) {
        showError(input, errorMessage);
    } else {
        input.classList.add('is-valid');
    }

    return isValid;
}

function showError(input, message) {
    input.classList.add('error');
    input.classList.remove('is-valid');
    
    const errorDiv = input.parentNode.querySelector('.luxury-form-error');
    if (errorDiv) {
        const errorSpan = errorDiv.querySelector('span');
        if (errorSpan) {
            errorSpan.textContent = message;
        }
        errorDiv.style.display = 'flex';
    }
}

function clearError(input) {
    input.classList.remove('error');
    
    const errorDiv = input.parentNode.querySelector('.luxury-form-error');
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

function validatePersonalDetails() {
    const nameInput = document.querySelector('input[name="full_name"]');
    const emailInput = document.querySelector('input[name="email"]');
    const phoneInput = document.querySelector('input[name="phone_number"]');

    const isNameValid = validateInput(nameInput);
    const isEmailValid = validateInput(emailInput);
    const isPhoneValid = validateInput(phoneInput);

    return isNameValid && isEmailValid && isPhoneValid;
}

function validateShippingDetails() {
    const addressInput = document.querySelector('input[name="street_address1"]');
    const cityInput = document.querySelector('input[name="town_or_city"]');
    const postcodeInput = document.querySelector('input[name="postcode"]');

    const isAddressValid = validateInput(addressInput);
    const isCityValid = validateInput(cityInput);
    const isPostcodeValid = validateInput(postcodeInput);

    return isAddressValid && isCityValid && isPostcodeValid;
}

/**
 * Stripe Elements Integration
 */
function setupStripeElements() {
    // Get Stripe public key
    const stripePublicKey = document.getElementById('id_stripe_public_key');
    if (!stripePublicKey) return;

    const stripe = Stripe(JSON.parse(stripePublicKey.textContent));
    const elements = stripe.elements();

    // Create card element with luxury styling
    const style = {
        base: {
            color: '#2c2c2c',
            fontFamily: '"Inter", sans-serif',
            fontSmoothing: 'antialiased',
            fontSize: '16px',
            '::placeholder': {
                color: '#6c757d'
            }
        },
        invalid: {
            fontFamily: '"Inter", sans-serif',
            color: '#dc3545',
            iconColor: '#dc3545'
        }
    };

    const card = elements.create('card', { style: style });
    card.mount('#card-element');

    // Handle real-time validation errors from the card Element
    card.on('change', function(event) {
        const errorDiv = document.getElementById('card-errors');
        if (event.error) {
            errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i><span>${event.error.message}</span>`;
            errorDiv.style.display = 'flex';
        } else {
            errorDiv.style.display = 'none';
        }
    });

    // Handle form submission
    const form = document.getElementById('luxury-payment-form');
    form.addEventListener('submit', function(event) {
        event.preventDefault();
        
        // Show loading
        showLoading();
        
        // Disable submit button
        const submitButton = document.getElementById('complete-order');
        submitButton.disabled = true;

        // Get client secret
        const clientSecretInput = document.querySelector('input[name="client_secret"]');
        const clientSecret = clientSecretInput.value;

        // Confirm payment with Stripe
        stripe.confirmCardPayment(clientSecret, {
            payment_method: {
                card: card,
                billing_details: {
                    name: document.querySelector('input[name="full_name"]').value,
                    email: document.querySelector('input[name="email"]').value,
                    phone: document.querySelector('input[name="phone_number"]').value,
                    address: {
                        line1: document.querySelector('input[name="street_address1"]').value,
                        line2: document.querySelector('input[name="street_address2"]').value,
                        city: document.querySelector('input[name="town_or_city"]').value,
                        postal_code: document.querySelector('input[name="postcode"]').value,
                        country: document.querySelector('select[name="country"]').value,
                    }
                }
            }
        }).then(function(result) {
            if (result.error) {
                // Show error to customer
                const errorDiv = document.getElementById('card-errors');
                errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i><span>${result.error.message}</span>`;
                errorDiv.style.display = 'flex';
                
                // Hide loading and re-enable button
                hideLoading();
                submitButton.disabled = false;
            } else {
                // Payment succeeded, submit form
                if (result.paymentIntent.status === 'succeeded') {
                    form.submit();
                }
            }
        });
    });
}

/**
 * Progress Indicator Updates
 */
function updateProgressIndicator() {
    // This function can be called to update progress based on form completion
    // Already handled in step navigation
}

/**
 * Trust Badges Animation
 */
function animateTrustBadges() {
    const trustBadges = document.querySelectorAll('.luxury-trust-badge');
    
    // Intersection Observer for animation on scroll
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.style.animation = 'fadeInUp 0.6s ease forwards';
                }, index * 100);
            }
        });
    });

    trustBadges.forEach(badge => {
        badge.style.opacity = '0';
        badge.style.transform = 'translateY(20px)';
        observer.observe(badge);
    });
}

/**
 * Loading Overlay Functions
 */
function showLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'flex';
    }
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

/**
 * Utility Functions
 */
function smoothScrollTo(element) {
    element.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
    });
}

// Add CSS animations keyframes if not already defined
if (!document.querySelector('#luxury-animations')) {
    const style = document.createElement('style');
    style.id = 'luxury-animations';
    style.textContent = `
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes pulse {
            0%, 100% {
                transform: scale(1);
            }
            50% {
                transform: scale(1.05);
            }
        }
        
        .luxury-form-input.is-valid {
            border-color: #28a745;
            box-shadow: 0 0 0 3px rgba(40, 167, 69, 0.1);
        }
    `;
    document.head.appendChild(style);
}
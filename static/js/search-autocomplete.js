// ============================================
// INTELLIGENT SEARCH WITH AUTOCOMPLETE
// ============================================

class SearchAutocomplete {
    constructor(inputSelector, resultsSelector, options = {}) {
        this.input = document.querySelector(inputSelector);
        this.resultsContainer = document.querySelector(resultsSelector);
        
        if (!this.input || !this.resultsContainer) {
            console.warn('Search autocomplete: Input or results container not found');
            return;
        }
        
        this.options = {
            minChars: 2,
            debounceMs: 300,
            maxResults: 8,
            searchUrl: '/api/search/',
            highlightMatch: true,
            showCategories: true,
            ...options
        };
        
        this.debounceTimer = null;
        this.selectedIndex = -1;
        this.currentResults = [];
        this.isOpen = false;
        
        this.init();
    }
    
    init() {
        // Input events
        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('keydown', (e) => this.handleKeyboard(e));
        this.input.addEventListener('focus', () => this.handleFocus());
        
        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.resultsContainer.contains(e.target)) {
                this.close();
            }
        });
        
        // Prevent form submission on Enter when selecting result
        const form = this.input.closest('form');
        if (form) {
            form.addEventListener('submit', (e) => {
                if (this.isOpen && this.selectedIndex >= 0) {
                    e.preventDefault();
                    this.selectResult(this.selectedIndex);
                }
            });
        }
    }
    
    handleInput(e) {
        const query = e.target.value.trim();
        
        clearTimeout(this.debounceTimer);
        
        if (query.length < this.options.minChars) {
            this.close();
            return;
        }
        
        this.debounceTimer = setTimeout(() => {
            this.search(query);
        }, this.options.debounceMs);
    }
    
    handleKeyboard(e) {
        if (!this.isOpen) return;
        
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, this.currentResults.length - 1);
                this.updateSelection();
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
                this.updateSelection();
                break;
                
            case 'Enter':
                if (this.selectedIndex >= 0) {
                    e.preventDefault();
                    this.selectResult(this.selectedIndex);
                }
                break;
                
            case 'Escape':
                this.close();
                break;
        }
    }
    
    handleFocus() {
        if (this.input.value.length >= this.options.minChars && this.currentResults.length > 0) {
            this.open();
        }
    }
    
    async search(query) {
        try {
            // Show loading state
            this.showLoading();
            
            // In production, make API call
            // For now, simulate with mock data
            const results = await this.mockSearch(query);
            
            this.currentResults = results;
            this.selectedIndex = -1;
            this.render(results, query);
            this.open();
            
        } catch (error) {
            console.error('Search error:', error);
            this.showError();
        }
    }
    
    // Mock search - replace with real API call
    async mockSearch(query) {
        return new Promise((resolve) => {
            setTimeout(() => {
                const q = query.toLowerCase();
                
                // Simulate categorized results
                const allResults = [];
                
                // Products
                if (q.includes('d') || q.includes('ch') || q.includes('sa')) {
                    allResults.push({
                        type: 'product',
                        id: 1,
                        name: 'Dior Sauvage',
                        brand: 'Dior',
                        price: 89.99,
                        image: '/media/products/dior-sauvage.jpg',
                        url: '/products/1/'
                    });
                    allResults.push({
                        type: 'product',
                        id: 2,
                        name: 'Chanel Bleu de Chanel',
                        brand: 'Chanel',
                        price: 110.00,
                        image: '/media/products/bleu-chanel.jpg',
                        url: '/products/2/'
                    });
                }
                
                // Brands
                if (q.includes('d') || q.includes('ch')) {
                    allResults.push({
                        type: 'brand',
                        id: 1,
                        name: 'Dior',
                        productCount: 45,
                        url: '/products/?brand=1'
                    });
                    allResults.push({
                        type: 'brand',
                        id: 2,
                        name: 'Chanel',
                        productCount: 38,
                        url: '/products/?brand=2'
                    });
                }
                
                // Notes
                if (q.includes('van') || q.includes('ci') || q.includes('ber')) {
                    allResults.push({
                        type: 'note',
                        id: 1,
                        name: 'Vainilla',
                        productCount: 127,
                        url: '/products/?note=1'
                    });
                    allResults.push({
                        type: 'note',
                        id: 2,
                        name: 'Bergamota',
                        productCount: 89,
                        url: '/products/?note=2'
                    });
                }
                
                // Fragrance families
                if (q.includes('ori') || q.includes('flo') || q.includes('ci')) {
                    allResults.push({
                        type: 'family',
                        id: 1,
                        name: 'Oriental',
                        productCount: 156,
                        url: '/products/?family=1'
                    });
                    allResults.push({
                        type: 'family',
                        id: 2,
                        name: 'Cítrico',
                        productCount: 92,
                        url: '/products/?family=2'
                    });
                }
                
                resolve(allResults.slice(0, this.options.maxResults));
            }, 200);
        });
    }
    
    render(results, query) {
        if (results.length === 0) {
            this.resultsContainer.innerHTML = `
                <div class="search-no-results">
                    <i class="fas fa-search"></i>
                    <p>No se encontraron resultados para "<strong>${this.escapeHtml(query)}</strong>"</p>
                    <small>Intenta con otra búsqueda</small>
                </div>
            `;
            return;
        }
        
        // Group by type
        const grouped = this.groupByType(results);
        
        let html = '';
        
        // Render each group
        if (grouped.products?.length) {
            html += this.renderGroup('Productos', grouped.products, query);
        }
        if (grouped.brands?.length) {
            html += this.renderGroup('Marcas', grouped.brands, query);
        }
        if (grouped.notes?.length) {
            html += this.renderGroup('Notas', grouped.notes, query);
        }
        if (grouped.families?.length) {
            html += this.renderGroup('Familias', grouped.families, query);
        }
        
        this.resultsContainer.innerHTML = html;
        
        // Add click handlers
        this.attachClickHandlers();
    }
    
    groupByType(results) {
        return results.reduce((acc, item) => {
            const type = item.type + 's';
            if (!acc[type]) acc[type] = [];
            acc[type].push(item);
            return acc;
        }, {});
    }
    
    renderGroup(title, items, query) {
        let html = `<div class="search-group">`;
        
        if (this.options.showCategories) {
            html += `<div class="search-group-title">${title}</div>`;
        }
        
        items.forEach((item, index) => {
            const globalIndex = this.currentResults.indexOf(item);
            html += this.renderItem(item, query, globalIndex);
        });
        
        html += `</div>`;
        return html;
    }
    
    renderItem(item, query, index) {
        const isSelected = index === this.selectedIndex;
        const selectedClass = isSelected ? 'selected' : '';
        
        switch(item.type) {
            case 'product':
                return `
                    <a href="${item.url}" class="search-result-item ${selectedClass}" data-index="${index}">
                        <div class="search-result-image">
                            <img src="${item.image}" alt="${item.name}" onerror="this.src='/static/img/noimage.png'">
                        </div>
                        <div class="search-result-content">
                            <div class="search-result-brand">${this.highlight(item.brand, query)}</div>
                            <div class="search-result-name">${this.highlight(item.name, query)}</div>
                            <div class="search-result-price">€${item.price.toFixed(2)}</div>
                        </div>
                        <i class="fas fa-arrow-right search-result-arrow"></i>
                    </a>
                `;
                
            case 'brand':
                return `
                    <a href="${item.url}" class="search-result-item ${selectedClass}" data-index="${index}">
                        <div class="search-result-icon">
                            <i class="fas fa-tag"></i>
                        </div>
                        <div class="search-result-content">
                            <div class="search-result-name">${this.highlight(item.name, query)}</div>
                            <div class="search-result-meta">${item.productCount} productos</div>
                        </div>
                        <i class="fas fa-arrow-right search-result-arrow"></i>
                    </a>
                `;
                
            case 'note':
                return `
                    <a href="${item.url}" class="search-result-item ${selectedClass}" data-index="${index}">
                        <div class="search-result-icon">
                            <i class="fas fa-leaf"></i>
                        </div>
                        <div class="search-result-content">
                            <div class="search-result-name">${this.highlight(item.name, query)}</div>
                            <div class="search-result-meta">${item.productCount} perfumes con esta nota</div>
                        </div>
                        <i class="fas fa-arrow-right search-result-arrow"></i>
                    </a>
                `;
                
            case 'family':
                return `
                    <a href="${item.url}" class="search-result-item ${selectedClass}" data-index="${index}">
                        <div class="search-result-icon">
                            <i class="fas fa-sitemap"></i>
                        </div>
                        <div class="search-result-content">
                            <div class="search-result-name">${this.highlight(item.name, query)}</div>
                            <div class="search-result-meta">${item.productCount} perfumes</div>
                        </div>
                        <i class="fas fa-arrow-right search-result-arrow"></i>
                    </a>
                `;
                
            default:
                return '';
        }
    }
    
    highlight(text, query) {
        if (!this.options.highlightMatch) return this.escapeHtml(text);
        
        const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
        return this.escapeHtml(text).replace(regex, '<mark>$1</mark>');
    }
    
    attachClickHandlers() {
        const items = this.resultsContainer.querySelectorAll('.search-result-item');
        items.forEach(item => {
            item.addEventListener('click', (e) => {
                const index = parseInt(item.dataset.index);
                this.selectResult(index);
            });
        });
    }
    
    updateSelection() {
        const items = this.resultsContainer.querySelectorAll('.search-result-item');
        items.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } else {
                item.classList.remove('selected');
            }
        });
    }
    
    selectResult(index) {
        const result = this.currentResults[index];
        if (result) {
            window.location.href = result.url;
        }
    }
    
    showLoading() {
        this.resultsContainer.innerHTML = `
            <div class="search-loading">
                <div class="spinner-border spinner-border-sm text-gold" role="status">
                    <span class="visually-hidden">Buscando...</span>
                </div>
                <span>Buscando...</span>
            </div>
        `;
        this.open();
    }
    
    showError() {
        this.resultsContainer.innerHTML = `
            <div class="search-error">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Error al buscar. Intenta de nuevo.</p>
            </div>
        `;
    }
    
    open() {
        this.resultsContainer.classList.add('show');
        this.isOpen = true;
    }
    
    close() {
        this.resultsContainer.classList.remove('show');
        this.isOpen = false;
        this.selectedIndex = -1;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    escapeRegex(text) {
        return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize desktop search
    const desktopSearch = new SearchAutocomplete(
        '#search-desktop',
        '#search-results-desktop',
        {
            minChars: 2,
            debounceMs: 300,
            maxResults: 8,
            highlightMatch: true,
            showCategories: true
        }
    );
    
    // Initialize mobile search
    const mobileSearch = new SearchAutocomplete(
        '#search-mobile',
        '#search-results-mobile',
        {
            minChars: 2,
            debounceMs: 300,
            maxResults: 6,
            highlightMatch: true,
            showCategories: true
        }
    );
});

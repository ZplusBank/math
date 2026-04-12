/**
 * Content Renderer Module
 * Processes question text through: Markdown → Code Highlighting → Math Typesetting
 * 
 * Supports:
 *   - LaTeX math/physics: \(...\) (inline), \[...\] (display)
 *   - Chemistry (mhchem): \ce{...}
 *   - Markdown: bold, italic, lists, tables, etc.
 *   - Fenced code blocks: ```java ... ``` with Prism.js highlighting
 *   - Legacy HTML: <span class="keyword">, <br>, &nbsp; pass through unchanged
 */
const ContentRenderer = {

    _placeholder: '%%MATH_BLOCK_',
    _counter: 0,
    _cacheMaxSize: 300,

    // LRU cache using Map insertion order
    _renderCache: new Map(),

    // Pre-compiled regex patterns (avoid re-compilation per call)
    _patterns: {
        displayMath: /\\\[[\s\S]*?\\\]/g,
        inlineMath: /\\\([\s\S]*?\\\)/g,
        chemistry: /\\ce\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/g,
        tripleAsterisk: /^\*{3,}\s*$/gm,
        loneAsterisk: /^\*\s*$/gm,
        table: /(<table\b[^>]*>[\s\S]*?<\/table>)/g,
        htmlEntities: /[&<>"']/g,
    },

    // Entity map for escaping
    _entityMap: { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' },

    // Active MathJax typeset abort controller
    _typesetController: null,

    /**
     * Initialize Marked.js with Prism.js integration.
     * Safe to call multiple times — no-ops if already initialized or libs missing.
     */
    _initialized: false,

    init() {
        if (this._initialized) return;
        if (typeof marked === 'undefined') {
            // Will be called again after lazy load
            return;
        }

        const renderer = new marked.Renderer();
        const self = this;

        // Override code block renderer to use Prism.js with line numbers, language badge, and copy button
        renderer.code = function ({ text, lang }) {
            const sourceLang = String(lang || '').trim().toLowerCase();
            const prismLanguage = sourceLang && Prism.languages[sourceLang] ? sourceLang : 'plaintext';
            const displayLang = (sourceLang || prismLanguage).charAt(0).toUpperCase() + (sourceLang || prismLanguage).slice(1);
            let highlighted;
            try {
                highlighted = Prism.languages[prismLanguage]
                    ? Prism.highlight(text, Prism.languages[prismLanguage], prismLanguage)
                    : self._escapeHtml(text);
            } catch (e) {
                highlighted = self._escapeHtml(text);
            }
            return `<div class="code-block-wrapper" data-source-lang="${self._escapeHtml(sourceLang)}">
                <div class="code-block-header">
                    <span class="code-block-dots"><span></span><span></span><span></span></span>
                    <span class="code-block-lang">${displayLang}</span>
                    <button class="code-copy-btn" onclick="ContentRenderer.copyCode(this)" title="Copy code">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                        <span class="copy-label">Copy</span>
                    </button>
                </div>
                <pre class="code-block language-${prismLanguage} line-numbers"><code class="language-${prismLanguage}">${highlighted}</code></pre>
            </div>`;
        };

        // Override em (italic) — skip if content is empty or whitespace-only
        renderer.em = function ({ text }) {
            if (!text || !text.trim()) return `*${text || ''}*`;
            return `<em>${text}</em>`;
        };

        // Override strong (bold) — skip if content is empty or whitespace-only
        renderer.strong = function ({ text }) {
            if (!text || !text.trim()) return `**${text || ''}**`;
            return `<strong>${text}</strong>`;
        };

        marked.setOptions({
            renderer: renderer,
            gfm: true,
            breaks: true
        });

        this._initialized = true;
    },

    /**
     * Copy code content to clipboard
     */
    copyCode(button) {
        const wrapper = button.closest('.code-block-wrapper');
        const codeEl = wrapper.querySelector('code');
        const text = codeEl.textContent;
        navigator.clipboard.writeText(text).then(() => {
            const label = button.querySelector('.copy-label');
            label.textContent = 'Copied!';
            button.classList.add('copied');
            setTimeout(() => {
                label.textContent = 'Copy';
                button.classList.remove('copied');
            }, 2000);
        });
    },

    /**
     * Render text content: protect math → Markdown → restore math
     * Returns HTML string (MathJax typesetting must be triggered separately)
     */
    render(text) {
        if (!text && text !== 0) return '';
        text = String(text);

        // LRU cache lookup — move to end on hit for proper LRU eviction
        if (this._renderCache.has(text)) {
            const cached = this._renderCache.get(text);
            this._renderCache.delete(text);
            this._renderCache.set(text, cached);
            return cached;
        }

        // If Marked is not available, just return the text as-is
        if (typeof marked === 'undefined') return text;

        // Step 1: Protect math/chemistry delimiters from Markdown processing (single pass)
        const { text: safeText, blocks } = this._protectMath(text);

        // Step 1.5: Escape lone asterisks that Marked would misinterpret
        let processedText = safeText
            .replace(this._patterns.tripleAsterisk, (m) => m.replace(/\*/g, '\\*'))
            .replace(this._patterns.loneAsterisk, '\\*');

        // Step 2: Run through Marked.js (Markdown → HTML)
        let html = marked.parse(processedText);

        // Step 2.5: Wrap tables in scrolling container
        html = html.replace(this._patterns.table, '<div class="table-overflow">$1</div>');

        // Step 3: Restore math blocks
        html = this._restoreMath(html, blocks);

        // LRU cache insert — evict oldest if at capacity
        if (this._renderCache.size >= this._cacheMaxSize) {
            const firstKey = this._renderCache.keys().next().value;
            this._renderCache.delete(firstKey);
        }
        this._renderCache.set(text, html);

        return html;
    },

    /**
     * Trigger MathJax typesetting on a DOM element.
     * Lazy-loads MathJax on first call. Cancels any pending typeset for same element.
     */
    async typeset(element) {
        // Check if element contains any math content before loading MathJax
        const html = element.innerHTML;
        const hasMath = html.indexOf('\\(') !== -1 || html.indexOf('\\[') !== -1 || html.indexOf('\\ce{') !== -1;
        if (!hasMath) return;

        // Lazy-load MathJax if not available
        if (typeof MathJax === 'undefined' || !MathJax.typesetPromise) {
            if (typeof LibLoader !== 'undefined') {
                try {
                    await LibLoader.loadMathJax();
                } catch (e) {
                    console.warn('Failed to load MathJax:', e);
                    return;
                }
            } else {
                return;
            }
        }

        // Cancel previous pending typeset
        if (this._typesetController) {
            this._typesetController.abort();
        }
        this._typesetController = new AbortController();
        const signal = this._typesetController.signal;

        try {
            // MathJax.typesetClear prevents re-processing already-typeset nodes
            MathJax.typesetClear([element]);
            await MathJax.typesetPromise([element]);
        } catch (e) {
            if (!signal.aborted) {
                console.warn('MathJax typeset error:', e);
            }
        }
    },

    /**
     * Render text and typeset in one step — sets innerHTML then typesets
     */
    async renderAndTypeset(element, text) {
        element.innerHTML = this.render(text);
        await this.typeset(element);
        this.attachImageListeners(element);
    },

    /**
     * Attach click listeners to images for lightbox using event delegation
     */
    attachImageListeners(element) {
        const images = element.querySelectorAll('img:not(.lightbox-image):not(.content-image)');
        if (images.length === 0) return;

        for (let i = 0; i < images.length; i++) {
            const img = images[i];
            img.classList.add('content-image');
            img.loading = 'lazy';
            img.decoding = 'async';
            img.addEventListener('click', this._onImageClick, { passive: true });
        }
    },

    /** Bound image click handler (avoids closure per image) */
    _onImageClick(e) {
        ContentRenderer._openLightbox(e.currentTarget.src, e.currentTarget.alt);
    },

    /**
     * Open lightbox with zoom, drag, keyboard & touch support.
     * All event listeners are properly cleaned up on close.
     */
    _openLightbox(src, alt) {
        // Cleanup reference for all bound listeners
        const listeners = [];
        const addListener = (target, event, handler, opts) => {
            target.addEventListener(event, handler, opts);
            listeners.push({ target, event, handler, opts });
        };

        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'lightbox-overlay';

        // Create content wrapper
        const content = document.createElement('div');
        content.className = 'lightbox-content';

        // Create image
        const img = document.createElement('img');
        img.src = src;
        img.alt = alt || 'Preview';
        img.className = 'lightbox-image';

        // Zoom/pan state
        let scale = 1, translateX = 0, translateY = 0;
        let isDragging = false, startX = 0, startY = 0;

        const updateTransform = () => {
            img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
        };

        const clampScale = (s) => Math.max(0.5, Math.min(5, s));

        const resetView = () => {
            scale = 1; translateX = 0; translateY = 0;
            updateTransform();
        };

        // Cleanup function
        const closeLightbox = () => {
            listeners.forEach(({ target, event, handler, opts }) => {
                target.removeEventListener(event, handler, opts);
            });
            listeners.length = 0;
            if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            document.body.style.overflow = '';
        };

        // Wheel zoom (passive: false to allow preventDefault)
        addListener(overlay, 'wheel', (e) => {
            e.preventDefault();
            scale = clampScale(scale + (e.deltaY < 0 ? 0.15 : -0.15));
            updateTransform();
        }, { passive: false });

        // Mouse drag
        addListener(img, 'mousedown', (e) => {
            isDragging = true;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
            img.style.cursor = 'grabbing';
            e.preventDefault();
        });

        addListener(window, 'mousemove', (e) => {
            if (!isDragging) return;
            translateX = e.clientX - startX;
            translateY = e.clientY - startY;
            updateTransform();
        });

        addListener(window, 'mouseup', () => {
            isDragging = false;
            img.style.cursor = 'grab';
        });

        // Touch support (pinch zoom + drag)
        let lastTouchDist = 0;
        addListener(img, 'touchstart', (e) => {
            if (e.touches.length === 1) {
                isDragging = true;
                startX = e.touches[0].clientX - translateX;
                startY = e.touches[0].clientY - translateY;
            } else if (e.touches.length === 2) {
                isDragging = false;
                lastTouchDist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
            }
        }, { passive: true });

        addListener(img, 'touchmove', (e) => {
            if (e.touches.length === 1 && isDragging) {
                translateX = e.touches[0].clientX - startX;
                translateY = e.touches[0].clientY - startY;
                updateTransform();
            } else if (e.touches.length === 2) {
                const dist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
                if (lastTouchDist > 0) {
                    scale = clampScale(scale * (dist / lastTouchDist));
                    updateTransform();
                }
                lastTouchDist = dist;
            }
        }, { passive: true });

        addListener(img, 'touchend', () => { isDragging = false; lastTouchDist = 0; }, { passive: true });

        // Keyboard: Escape to close, +/- to zoom, 0 to reset
        addListener(document, 'keydown', (e) => {
            if (e.key === 'Escape') closeLightbox();
            else if (e.key === '+' || e.key === '=') { scale = clampScale(scale + 0.5); updateTransform(); }
            else if (e.key === '-') { scale = clampScale(scale - 0.5); updateTransform(); }
            else if (e.key === '0') resetView();
        });

        // Close button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'lightbox-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.onclick = closeLightbox;

        // Controls (Zoom In/Out/Reset)
        const controls = document.createElement('div');
        controls.className = 'lightbox-controls';

        const makeBtn = (label, onClick) => {
            const btn = document.createElement('button');
            btn.className = 'lightbox-btn';
            btn.innerHTML = label;
            btn.onclick = (e) => { e.stopPropagation(); onClick(); };
            return btn;
        };

        controls.appendChild(makeBtn('-', () => { scale = clampScale(scale - 0.5); updateTransform(); }));
        controls.appendChild(makeBtn('&#x21bb;', resetView));
        controls.appendChild(makeBtn('+', () => { scale = clampScale(scale + 0.5); updateTransform(); }));

        // Assemble DOM
        content.appendChild(img);
        overlay.appendChild(content);
        overlay.appendChild(closeBtn);
        overlay.appendChild(controls);
        document.body.appendChild(overlay);
        document.body.style.overflow = 'hidden';

        // Animate in
        requestAnimationFrame(() => overlay.classList.add('active'));

        // Close on overlay click (not content)
        addListener(overlay, 'click', (e) => {
            if (e.target === overlay || e.target === content) closeLightbox();
        });
    },

    /**
     * Replace math delimiters with placeholders so Marked doesn't mangle them.
     * Single-pass replacement using pre-compiled patterns.
     */
    _protectMath(text) {
        const blocks = [];
        const self = this;

        const protect = (match) => {
            const id = self._placeholder + (self._counter++) + '%%';
            blocks.push({ id, content: match });
            return id;
        };

        // Protect display math \[...\], chemistry \ce{...}, inline math \(...\)
        text = text.replace(this._patterns.displayMath, protect);
        text = text.replace(this._patterns.chemistry, protect);
        text = text.replace(this._patterns.inlineMath, protect);

        return { text, blocks };
    },

    /**
     * Restore math blocks from placeholders
     */
    _restoreMath(html, blocks) {
        for (let i = 0; i < blocks.length; i++) {
            const block = blocks[i];
            let content = block.content;
            if (content.startsWith('\\(')) {
                content = `<span class="math-scroll-wrapper">${content}</span>`;
            }
            html = html.replace(block.id, content);
        }
        return html;
    },

    /**
     * HTML escape using entity map (faster than chained .replace)
     */
    _escapeHtml(text) {
        if (!text && text !== 0) return '';
        const map = this._entityMap;
        return String(text).replace(this._patterns.htmlEntities, (ch) => map[ch]);
    }
};

// Try to initialize immediately if libs are already loaded (e.g. cached),
// otherwise init() will be called by exam-engine before first render.
if (typeof marked !== 'undefined') {
    ContentRenderer.init();
}

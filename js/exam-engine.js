// Data loading and app initialization
const app = {
    subjects: [],
    allChapters: [],
    selectedChapters: [],
    currentQuestionIndex: 0,
    questions: [],
    userAnswers: {},
    checkedAnswers: {},
    questionStatuses: {},
    currentView: 'subjects',
    currentSubject: null,
    modalCallback: null,
    _answeredCount: 0,       // Incremental answered-question counter
    _saveTimer: null,        // Debounced save timer
    _resultIO: null,         // IntersectionObserver for lazy results
    _resultImageIO: null,    // IntersectionObserver for lazy result images
    _subjectIconObserver: null, // IntersectionObserver for subject icons

    // === Toast Notification System ===
    showToast(message, type = 'info', duration = 3000) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const icons = { success: '✓', error: '✗', info: 'ℹ' };
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-exit');
            toast.addEventListener('animationend', () => toast.remove());
        }, duration);
    },

    // === Scroll to Top ===
    initScrollToTop() {
        const btn = document.getElementById('scrollTopBtn');
        if (!btn) return;

        let ticking = false;
        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(() => {
                    btn.classList.toggle('visible', window.scrollY > 300);
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });

        btn.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    },

    // Show custom modal (replaces alert/confirm)
    showModal(title, message, isConfirm = false, callback = null) {
        const modal = document.getElementById('appModal');
        const titleEl = document.getElementById('modalTitle');
        const messageEl = document.getElementById('modalMessage');
        const confirmBtn = document.getElementById('modalConfirmBtn');
        const cancelBtn = document.getElementById('modalCancelBtn');

        titleEl.textContent = title;
        messageEl.textContent = message;
        modal.style.display = 'flex';

        if (isConfirm) {
            cancelBtn.style.display = 'inline-block';
            confirmBtn.textContent = 'Confirm';
            confirmBtn.className = 'btn-confirm';
            this.modalCallback = callback;
        } else {
            cancelBtn.style.display = 'none';
            confirmBtn.textContent = 'OK';
            confirmBtn.className = 'btn-confirm';
            this.modalCallback = callback;
        }

        // Focus on confirm button
        setTimeout(() => confirmBtn.focus(), 100);
    },

    closeModal() {
        const modal = document.getElementById('appModal');
        modal.style.display = 'none';
        this.modalCallback = null;
    },

    handleModalConfirm() {
        if (this.modalCallback) {
            this.modalCallback();
        }
        this.closeModal();
    },

    // Loading overlay
    showLoading(message = 'Loading...') {
        const overlay = document.getElementById('loadingOverlay');
        const text = overlay.querySelector('.loading-text');
        text.textContent = message;
        overlay.style.display = 'flex';
    },

    hideLoading() {
        const overlay = document.getElementById('loadingOverlay');
        overlay.style.display = 'none';
    },

    // Keyboard help
    showKeyboardHelp() {
        document.getElementById('keyboardHelp').style.display = 'flex';
    },

    closeKeyboardHelp() {
        document.getElementById('keyboardHelp').style.display = 'none';
    },

    // Local storage helpers (debounced to avoid thrashing on rapid answer changes)
    saveProgress() {
        if (this._saveTimer) return; // Already scheduled
        this._saveTimer = setTimeout(() => {
            this._saveTimer = null;
            if (this.currentView === 'exam' && this.questions.length > 0) {
                const progress = {
                    subjectId: this.currentSubject?.id,
                    selectedChapters: this.selectedChapters,
                    currentQuestionIndex: this.currentQuestionIndex,
                    userAnswers: this.userAnswers,
                    checkedAnswers: this.checkedAnswers,
                    questionStatuses: this.questionStatuses,
                    timestamp: Date.now()
                };
                localStorage.setItem('examProgress', JSON.stringify(progress));
            }
        }, 2000);
    },

    /** Flush any pending save immediately (e.g. before exit) */
    _flushSave() {
        if (this._saveTimer) {
            clearTimeout(this._saveTimer);
            this._saveTimer = null;
            if (this.currentView === 'exam' && this.questions.length > 0) {
                const progress = {
                    subjectId: this.currentSubject?.id,
                    selectedChapters: this.selectedChapters,
                    currentQuestionIndex: this.currentQuestionIndex,
                    userAnswers: this.userAnswers,
                    checkedAnswers: this.checkedAnswers,
                    questionStatuses: this.questionStatuses,
                    timestamp: Date.now()
                };
                localStorage.setItem('examProgress', JSON.stringify(progress));
            }
        }
    },

    loadProgress() {
        const saved = localStorage.getItem('examProgress');
        if (saved) {
            try {
                const progress = JSON.parse(saved);
                // Check if progress is recent (within 24 hours)
                if (Date.now() - progress.timestamp < 24 * 60 * 60 * 1000) {
                    return progress;
                }
            } catch (e) {
                console.error('Failed to parse saved progress:', e);
            }
        }
        return null;
    },

    clearProgress() {
        localStorage.removeItem('examProgress');
    },

    // Confetti animation (optimized: fewer particles, batched DOM)
    triggerConfetti() {
        const colors = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#a78bfa', '#22d3ee'];
        const shapes = ['circle', 'rect'];
        const fragment = document.createDocumentFragment();
        const confettiElements = [];
        for (let i = 0; i < 40; i++) {
            const confetti = document.createElement('div');
            confetti.className = 'confetti';
            const shape = shapes[Math.floor(Math.random() * shapes.length)];
            const size = 6 + Math.random() * 8;
            confetti.style.cssText = `left:${Math.random() * 100}vw;top:-10px;background:${colors[Math.floor(Math.random() * colors.length)]};animation-delay:${Math.random() * 0.8}s;animation-duration:${2.5 + Math.random() * 2}s;width:${size}px;height:${shape === 'rect' ? size * 0.6 : size}px;border-radius:${shape === 'circle' ? '50%' : '2px'};transform:rotate(${Math.random() * 360}deg)`;
            fragment.appendChild(confetti);
            confettiElements.push(confetti);
        }
        document.body.appendChild(fragment);
        setTimeout(() => {
            confettiElements.forEach(el => el.remove());
        }, 5000);
    },

    async init() {
        this.initTheme();
        this.initKeyboardShortcuts();
        this.initModalHandlers();
        this.initScrollToTop();
        await this.loadData();

        // Check for saved progress
        const progress = this.loadProgress();
        if (progress) {
            this.showModal(
                'Resume Exam?',
                'You have an unfinished exam. Would you like to continue where you left off?',
                true,
                () => this.resumeExam(progress)
            );
        }

        this.showSubjectsView();
        this.initSearch();
    },

    initModalHandlers() {
        // Set up modal button handlers
        const confirmBtn = document.getElementById('modalConfirmBtn');
        const cancelBtn = document.getElementById('modalCancelBtn');

        confirmBtn.onclick = () => this.handleModalConfirm();
        cancelBtn.onclick = () => this.closeModal();

        // Close modal on overlay click
        document.getElementById('appModal').addEventListener('click', (e) => {
            if (e.target.id === 'appModal') {
                this.closeModal();
            }
        });

        // Keyboard help button
        const helpBtn = document.getElementById('keyboardHelpBtn');
        if (helpBtn) {
            helpBtn.onclick = () => this.showKeyboardHelp();
        }

        // Close keyboard help on overlay click
        document.getElementById('keyboardHelp').addEventListener('click', (e) => {
            if (e.target.id === 'keyboardHelp') {
                this.closeKeyboardHelp();
            }
        });
    },

    initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            // Escape - Close modals
            if (e.key === 'Escape') {
                this.closeModal();
                this.closeKeyboardHelp();
                return;
            }

            // ? - Show keyboard help
            if (e.key === '?' && this.currentView === 'exam') {
                this.showKeyboardHelp();
                return;
            }

            // Exam view shortcuts
            if (this.currentView === 'exam') {
                // Arrow keys for navigation
                if (e.key === 'ArrowLeft' && !document.getElementById('prevBtn').disabled) {
                    e.preventDefault();
                    this.previousQuestion();
                } else if (e.key === 'ArrowRight' && !document.getElementById('nextBtn').disabled) {
                    e.preventDefault();
                    this.nextQuestion();
                }
                // Enter - Check answer or next
                else if (e.key === 'Enter') {
                    e.preventDefault();
                    const checkBtn = document.getElementById('checkBtn');
                    const nextBtn = document.getElementById('nextBtn');
                    const submitBtn = document.getElementById('submitBtn');

                    if (checkBtn.style.display !== 'none' && !this.checkedAnswers[this.currentQuestionIndex]) {
                        this.checkAnswer();
                    } else if (submitBtn.style.display !== 'none') {
                        this.showReviewModal();
                    } else if (!nextBtn.disabled) {
                        this.nextQuestion();
                    }
                }
                // A, B, C, D - Select answer
                else if (['a', 'b', 'c', 'd', 'e', 'f'].includes(e.key.toLowerCase())) {
                    e.preventDefault();
                    const value = e.key.toUpperCase();
                    const input = document.getElementById(`choice-${value}`);
                    if (input) {
                        input.click();
                    }
                }
            }
        });

        // Auto-save progress periodically during exam
        setInterval(() => {
            if (this.currentView === 'exam') {
                this.saveProgress();
            }
        }, 30000); // Every 30 seconds
    },

    async resumeExam(progress) {
        try {
            this.showLoading('Resuming exam...');

            // Find and select the subject
            const subject = this.subjects.find(s => s.id === progress.subjectId);
            if (!subject) {
                throw new Error('Subject not found');
            }

            this.currentSubject = subject;

            // Load chapters if needed
            if (!subject.loaded) {
                await this.loadChaptersForSubject(subject);
            }

            // Restore state
            const rawSelected = Array.isArray(progress.selectedChapters) ? progress.selectedChapters : [];
            // Normalize legacy saved chapter IDs to section-scoped keys.
            this.selectedChapters = rawSelected.map(ch => {
                const chapterId = String(ch);
                return chapterId.includes('::') ? chapterId : this._makeChapterKey(subject.id, chapterId);
            });
            await this.startExam();
            this.currentQuestionIndex = progress.currentQuestionIndex;
            this.userAnswers = progress.userAnswers;
            this.checkedAnswers = progress.checkedAnswers;
            this.questionStatuses = progress.questionStatuses || {};

            // Recalculate incremental answered count from restored state
            this._answeredCount = 0;
            for (const idx in this.userAnswers) {
                if (!this._isSkipped(this.userAnswers[idx])) this._answeredCount++;
            }

            // Backfill statuses from older saves that only stored checked flags
            for (const idx in this.checkedAnswers) {
                if (!this.questionStatuses[idx]) {
                    const question = this.questions[idx];
                    if (question) {
                        this.questionStatuses[idx] = this._getQuestionStatus(question, this.userAnswers[idx]);
                    }
                }
            }

            this.renderCurrentQuestion();
            this.updateQuestionNumberStyles();

            this.hideLoading();
        } catch (error) {
            console.error('Failed to resume exam:', error);
            this.hideLoading();
            this.showModal('Error', 'Failed to resume exam. Starting fresh.');
            this.clearProgress();
        }
    },

    initSearch() {
        const subjectInput = document.getElementById('subjectSearch');
        const chapterInput = document.getElementById('chapterSearch');
        const subjectClear = document.getElementById('subjectSearchClear');
        const chapterClear = document.getElementById('chapterSearchClear');

        // Debounce helper for search performance
        const debounce = (fn, delay) => {
            let timer;
            return (...args) => {
                clearTimeout(timer);
                timer = setTimeout(() => fn(...args), delay);
            };
        };

        if (subjectInput) {
            const debouncedSubjectFilter = debounce((value) => this.filterSubjects(value), 80);
            subjectInput.addEventListener('input', (e) => {
                debouncedSubjectFilter(e.target.value);
                if (subjectClear) {
                    subjectClear.style.display = e.target.value ? 'flex' : 'none';
                }
            });
        }
        if (chapterInput) {
            const debouncedChapterFilter = debounce((value) => this.filterChapters(value), 80);
            chapterInput.addEventListener('input', (e) => {
                debouncedChapterFilter(e.target.value);
                if (chapterClear) {
                    chapterClear.style.display = e.target.value ? 'flex' : 'none';
                }
            });
        }
    },

    clearSearch(type) {
        if (type === 'subject') {
            const input = document.getElementById('subjectSearch');
            const clearBtn = document.getElementById('subjectSearchClear');
            if (input) {
                input.value = '';
                input.focus();
                this.filterSubjects('');
            }
            if (clearBtn) clearBtn.style.display = 'none';
        } else if (type === 'chapter') {
            const input = document.getElementById('chapterSearch');
            const clearBtn = document.getElementById('chapterSearchClear');
            if (input) {
                input.value = '';
                input.focus();
                this.filterChapters('');
            }
            if (clearBtn) clearBtn.style.display = 'none';
        }
    },

    filterSubjects(query) {
        const cards = document.querySelectorAll('#subjectsGrid .subject-card');
        const q = query.toLowerCase().trim();
        let visibleCount = 0;

        cards.forEach(card => {
            const name = (card.getAttribute('data-name') || '').toLowerCase();
            const desc = (card.getAttribute('data-desc') || '').toLowerCase();
            const match = !q || name.includes(q) || desc.includes(q);
            card.style.display = match ? '' : 'none';
            if (match) visibleCount++;
        });

        const noResults = document.getElementById('subjectNoResults');
        if (noResults) noResults.style.display = visibleCount === 0 ? 'block' : 'none';
    },

    filterChapters(query) {
        const cards = document.querySelectorAll('#chaptersGrid .chapter-card');
        const q = query.toLowerCase().trim();
        let visibleCount = 0;

        cards.forEach(card => {
            const name = (card.getAttribute('data-name') || '').toLowerCase();
            const match = !q || name.includes(q);
            card.style.display = match ? '' : 'none';
            if (match) visibleCount++;
        });

        const noResults = document.getElementById('chapterNoResults');
        if (noResults) noResults.style.display = visibleCount === 0 ? 'block' : 'none';
    },

    initTheme() {
        const toggle = document.getElementById('themeToggle');
        if (!toggle) return;

        // Check local storage or system preference
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            document.documentElement.setAttribute('data-theme', savedTheme);
        }

        toggle.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';

            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    },

    async loadData() {
        try {
            if (typeof EXAM_CONFIG === 'undefined') {
                console.error('EXAM_CONFIG not found in exam-config.js');
                this.showModal('Error', 'Exam configuration not found. Please contact support.');
                this.subjects = [];
                return;
            }

            // Map basic subject info from config without loading chapter files yet
            this.subjects = EXAM_CONFIG.map(subjectConfig => {
                const iconMeta = this.resolveSubjectIcon(subjectConfig);
                return {
                    id: subjectConfig.id,
                    name: subjectConfig.name,
                    description: subjectConfig.description,
                    iconEmoji: iconMeta.emoji,
                    iconPath: iconMeta.path,
                    chaptersConfig: subjectConfig.chapters || [], // Save config for later loading
                    chapters: [], // Loaded data goes here
                    loaded: false // Track if chapters are loaded
                };
            });

            // subjects loaded
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showModal('Error', 'Error initializing exam data. Please refresh the page.');
        }
    },

    // Single-pass HTML escape (faster than 5 chained .replace calls)
    _escapeMap: { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' },
    _escapeRe: /[&<>"']/g,
    escapeHtml(text) {
        if (!text && text !== 0) return '';
        const map = this._escapeMap;
        return String(text).replace(this._escapeRe, ch => map[ch]);
    },

    async copyTextToClipboard(text) {
        const value = String(text || '').trim();
        if (!value) return false;

        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(value);
                return true;
            }
        } catch (_) {
            // Fallback below
        }

        try {
            const ta = document.createElement('textarea');
            ta.value = value;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            const ok = document.execCommand('copy');
            ta.remove();
            return !!ok;
        } catch (_) {
            return false;
        }
    },

    _isWebRelatedQuestion(question) {
        if (!question) return false;

        if (this.currentSubject?.id === 'web') {
            return true;
        }

        const choicesText = (question.choices || [])
            .map(c => c?.text || c?.label || '')
            .join(' ');
        const haystack = `${question.text || ''} ${question.explanation || ''} ${choicesText}`;

        const hasHtmlLikeTags = /<\s*\/?\s*[a-z][^>]*>/i.test(haystack);
        const hasWebTerms = /\b(html|css|javascript|js|php|stylesheet|href|src|dom)\b/i.test(haystack);

        return hasHtmlLikeTags && hasWebTerms;
    },

    _renderQuestionContent(rawText, question) {
        const text = rawText == null ? '' : String(rawText);

        if (this._isWebRelatedQuestion(question)) {
            // Prepare HTML code for markdown rendering: escape raw HTML,
            // auto-wrap snippets in inline code, and auto-fence code blocks.
            return ContentRenderer.render(this._prepareWebContent(text));
        }

        return ContentRenderer.render(text);
    },

    /**
     * Prepare web/HTML question content for markdown rendering.
     * - Auto-wraps single-line HTML snippets in inline code backticks
     * - Auto-fences unfenced code blocks (e.g. "html\n<code>" → ```html)
     * - Escapes HTML tags/entities outside markdown code regions
     */
    _prepareWebContent(text) {
        if (!text) return text;

        // Normalize line endings
        text = text.replace(/\r\n/g, '\n');

        // Quick path: single-line text with HTML tags and no backticks
        // → wrap entire text in inline code (typical for choice texts)
        if (!text.includes('\n') && !text.includes('`') && /<[a-zA-Z/!][^>]*>/.test(text)) {
            return '`' + text.trim() + '`';
        }

        // Multi-line / mixed content path

        // Step 1: Auto-fence unfenced code blocks.
        // Detects patterns like "\nhtml\n<code..." or "\ncss\n.selector{..."
        // and wraps them in proper markdown fenced code blocks.
        text = text.replace(
            /\n(html|css|javascript|js|php|xml)\n([\s\S]+?)(?=\n\n[A-Za-z]|$)/gi,
            (_, lang, code) => '\n\n```' + lang + '\n' + code.trimEnd() + '\n```'
        );

        // Step 2: Protect existing markdown code regions from escaping
        const codeRegions = [];
        let codeCounter = 0;
        const CODE_PH = '%%WEBCODE_';
        const protectCode = (match) => {
            const id = CODE_PH + (codeCounter++) + '%%';
            codeRegions.push({ id, content: match });
            return id;
        };

        // Protect fenced code blocks (```...```), then inline code (`...`)
        text = text.replace(/```[\s\S]*?```/g, protectCode);
        text = text.replace(/`[^`\n]+`/g, protectCode);

        // Step 3: Escape HTML in non-code regions so tags are visible, not rendered
        text = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Step 4: Restore protected code regions
        for (let i = 0; i < codeRegions.length; i++) {
            text = text.replace(codeRegions[i].id, codeRegions[i].content);
        }

        return text;
    },

    getIconForSubject(id) {
        const icons = {
            'java1': '☕',
            'java2': '☕',
            'algorithm': '🧮',
            'data_structure': '🌲',
            'java_advanced': '🚀'
        };
        return icons[id] || '📚';
    },

    resolveSubjectIcon(subjectConfig) {
        const explicit = String(subjectConfig?.icon || '').trim().replace(/\\/g, '/');
        const fallbackEmoji = this.getIconForSubject(subjectConfig?.id);

        if (explicit) {
            const looksLikePath = /^(https?:\/\/|\.\/|\.\.\/|\/)/i.test(explicit)
                || explicit.includes('/')
                || /\.(png|jpg|jpeg|webp|gif|bmp|ico|svg)$/i.test(explicit);

            if (looksLikePath) {
                return { emoji: fallbackEmoji, path: explicit };
            }

            // Non-path icon values are treated as custom emoji/text icons.
            return { emoji: explicit, path: '' };
        }

        const basePath = String(subjectConfig?.path || '').trim().replace(/\\/g, '/').replace(/\/+$/, '');
        if (!basePath) return { emoji: fallbackEmoji, path: '' };
        return { emoji: fallbackEmoji, path: `${basePath}/icon.png` };
    },

    renderSubjectIcon(subject) {
        const fallback = this.escapeHtml(subject.iconEmoji || '📚');
        if (!subject.iconPath) return fallback;

        const src = this.escapeHtml(subject.iconPath);
        const sid = this.escapeHtml(subject.id || '');
        const alt = this.escapeHtml(`${subject.name || 'Subject'} icon`);
        return `<img class="subject-icon-image" data-src="${src}" alt="${alt}" loading="lazy" decoding="async" data-sid="${sid}">`;
    },

    _loadSubjectIconImage(img, prioritize = false) {
        if (!img || img.dataset.loaded === '1') return;
        const src = img.getAttribute('data-src');
        if (!src) return;
        if (prioritize) {
            img.loading = 'eager';
            img.fetchPriority = 'high';
        }
        img.dataset.loaded = '1';
        img.src = src;
    },

    _initSubjectIconLazyLoad(grid) {
        if (!grid) return;

        const iconImages = grid.querySelectorAll('.subject-icon-image[data-src]');
        if (!iconImages.length) return;

        if (!('IntersectionObserver' in window)) {
            iconImages.forEach((img) => this._loadSubjectIconImage(img));
            return;
        }

        const isPhoneViewport = window.matchMedia('(max-width: 768px)').matches;
        const eagerCount = isPhoneViewport ? 8 : 3;

        iconImages.forEach((img, index) => {
            if (index < eagerCount) {
                this._loadSubjectIconImage(img, true);
            }
        });

        if (this._subjectIconObserver) {
            this._subjectIconObserver.disconnect();
        }

        this._subjectIconObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting || entry.intersectionRatio > 0) {
                    this._loadSubjectIconImage(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, {
            root: null,
            rootMargin: isPhoneViewport ? '420px 0px' : '220px 0px',
            threshold: 0.01,
        });

        iconImages.forEach((img, index) => {
            if (index >= eagerCount && img.dataset.loaded !== '1') {
                this._subjectIconObserver.observe(img);
            }
        });
    },

    showSubjectsView() {
        this.currentView = 'subjects';
        this.resetExam();
        this.hideAllViews();
        const view = document.getElementById('subjectsView');
        view.style.display = 'block';
        view.classList.add('view-enter');
        setTimeout(() => view.classList.remove('view-enter'), 400);
        this.renderSubjects();
        // Clear search
        const searchInput = document.getElementById('subjectSearch');
        if (searchInput) { searchInput.value = ''; }
        const noResults = document.getElementById('subjectNoResults');
        if (noResults) noResults.style.display = 'none';
    },

    renderSubjects() {
        const grid = document.getElementById('subjectsGrid');
        const totalQs = (subject) => {
            return subject.chaptersConfig.reduce((sum, ch) => sum + (ch.q || 0), 0);
        };

        // Prefetch chapters on hover for faster navigation
        grid.addEventListener('pointerenter', (e) => {
            const card = e.target.closest('.subject-card');
            if (!card) return;
            const sid = card.getAttribute('data-sid');
            const subject = this.subjects.find(s => s.id === sid);
            if (subject && !subject.loaded && !subject._prefetching) {
                subject._prefetching = true;
                this.loadChaptersForSubject(subject).catch(() => { }).finally(() => {
                    subject._prefetching = false;
                });
            }
        }, { passive: true, capture: true });
        grid.innerHTML = this.subjects.map((subject, i) => `
            <div class="subject-card" onclick="app.selectSubject('${subject.id}')"
                 data-name="${this.escapeHtml(subject.name)}" data-desc="${this.escapeHtml(subject.description)}"
                 data-sid="${subject.id}"
                 style="--i: ${i}">
                <span class="subject-icon">${this.renderSubjectIcon(subject)}</span>
                <h2>${this.escapeHtml(subject.name)}</h2>
                <p>${this.escapeHtml(subject.description)}</p>
                <span class="chapter-count">
                    <span class="count-item"><strong>${subject.chaptersConfig.length}</strong> Chapters</span>
                    <span class="count-sep">•</span>
                    <span class="count-item"><strong>${totalQs(subject)}</strong> Questions</span>
                </span>
            </div>
        `).join('');

        // Fallback to emoji when icon image is missing/broken.
        grid.querySelectorAll('.subject-icon-image').forEach((img) => {
            img.addEventListener('error', () => {
                const host = img.closest('.subject-icon');
                if (!host) return;
                const sid = img.getAttribute('data-sid') || '';
                const subject = this.subjects.find(s => s.id === sid);
                host.textContent = (subject && subject.iconEmoji) || this.getIconForSubject(sid);
            }, { once: true });
        });

        this._initSubjectIconLazyLoad(grid);
    },

    async selectSubject(subjectId) {
        const subject = this.subjects.find(s => s.id === subjectId);
        this.currentSubject = subject;

        if (!subject) return;

        // If not loaded, fetch chapters now
        if (!subject.loaded) {
            this.showLoading('Loading chapters...');
            try {
                await this.loadChaptersForSubject(subject);
                this.hideLoading();
            } catch (error) {
                console.error('Failed to load chapters:', error);
                this.hideLoading();
                this.showModal('Error', 'Failed to load chapters for this subject. Please try again.');
                return;
            }
        }

        // UX: Check if subject has chapters after loading
        if (subject.chapters.length === 0) {
            this.showModal('Coming Soon', 'This subject has no chapters yet. Please check back later!');
            this.showToast('No chapters available yet for this subject', 'info', 3000);
            return;
        }

        this.showChaptersView(subject);
    },

    // Active fetch controller — allows cancelling in-flight chapter loads
    _chapterLoadController: null,

    async loadChaptersForSubject(subject) {
        if (!subject.chaptersConfig || subject.chaptersConfig.length === 0) {
            subject.loaded = true;
            return;
        }

        // Cancel any previous in-flight load
        if (this._chapterLoadController) {
            this._chapterLoadController.abort();
        }
        this._chapterLoadController = new AbortController();
        const signal = this._chapterLoadController.signal;

        // Concurrency-limited parallel fetch (max 4 at once to avoid saturating network)
        const MAX_CONCURRENT = 4;
        const configs = subject.chaptersConfig.filter(ch => ch.file);
        const chapters = [];

        for (let i = 0; i < configs.length; i += MAX_CONCURRENT) {
            if (signal.aborted) break;
            const batch = configs.slice(i, i + MAX_CONCURRENT);
            const batchResults = await Promise.allSettled(
                batch.map(chInfo => this._fetchChapter(chInfo, signal, subject.id))
            );
            for (const result of batchResults) {
                if (result.status === 'fulfilled' && result.value) {
                    chapters.push(result.value);
                }
            }
        }

        subject.chapters = chapters;
        subject.loaded = true;
        this._chapterLoadController = null;
    },

    /** Fetch and parse a single chapter file */
    async _fetchChapter(chInfo, signal, subjectId = '') {
        try {
            const response = await fetch(`./${chInfo.file}`, { signal });
            if (!response.ok) return null;

            const data = await response.json();
            const chapterData = Array.isArray(data) ? data[0] : data;

            if (!chapterData?.title || !Array.isArray(chapterData.questions)) return null;

            return {
                id: chInfo.id,
                subjectId,
                scopedId: this._makeChapterKey(subjectId, chInfo.id),
                title: chInfo.name || chapterData.title,
                questions: chapterData.questions,
                totalQuestions: chapterData.questions.length
            };
        } catch (e) {
            if (e.name !== 'AbortError') {
                console.warn(`Failed to load ${chInfo.file}:`, e);
            }
            return null;
        }
    },

    _makeChapterKey(subjectId, chapterId) {
        return `${String(subjectId)}::${String(chapterId)}`;
    },

    showChaptersView(subject) {
        this.currentView = 'chapters';
        this.hideAllViews();
        const view = document.getElementById('chaptersView');
        view.style.display = 'block';
        view.classList.add('view-enter');
        setTimeout(() => view.classList.remove('view-enter'), 400);

        // Reset selection and button state
        this.selectedChapters = [];
        const startBtn = document.getElementById('startExamBtn');
        if (startBtn) {
            startBtn.disabled = true;
            startBtn.style.display = 'none'; // Initially hidden
        }

        this.renderChapters(subject.chapters);
        // Clear search
        const searchInput = document.getElementById('chapterSearch');
        if (searchInput) { searchInput.value = ''; }
        const noResults = document.getElementById('chapterNoResults');
        if (noResults) noResults.style.display = 'none';
    },

    _formatChapterIdBadge(chapterId) {
        const raw = String(chapterId || '').trim();
        if (!raw) return 'Chapter';

        // Only normalize to "Ch N" when ID explicitly uses Chapter/Ch prefix.
        const hasChapterPrefix = /^(chapter|ch)\b/i.test(raw);
        if (hasChapterPrefix) {
            const numberLike = raw.match(/^(?:chapter|ch)\s*[-_:]*\s*([0-9]+[a-z]?)/i);
            if (numberLike && numberLike[1]) {
                return `Ch ${numberLike[1].toUpperCase()}`;
            }
        }

        // Keep custom IDs as-is (compact only for badge safety).
        return raw.length > 10 ? `${raw.slice(0, 10)}...` : raw;
    },

    renderChapters(chapters) {
        const grid = document.getElementById('chaptersGrid');
        grid.innerHTML = chapters.map((chapter, idx) => `
            <div class="chapter-card" data-name="${this.escapeHtml(chapter.title)}" style="--i: ${idx}">
                <input type="checkbox" id="ch-${idx}" value="${chapter.scopedId || this._makeChapterKey(this.currentSubject?.id || '', chapter.id)}" 
                       onchange="app.updateSelectedChapters()">
                <label for="ch-${idx}" class="chapter-content">
                    <span class="chapter-head">
                        <span class="chapter-id-badge" title="${this.escapeHtml(String(chapter.id || ''))}">${this.escapeHtml(this._formatChapterIdBadge(chapter.id))}</span>
                        <span class="chapter-title">${this.escapeHtml(chapter.title)}</span>
                    </span>
                    <span class="chapter-meta">
                        <span class="chapter-dot"></span>
                        ${chapter.totalQuestions} questions
                    </span>
                </label>
            </div>
        `).join('');

        // Make whole chapter cards clickable with fallback hit detection.
        grid.onclick = (e) => {
            const card = e.target.closest('.chapter-card')
                || document.elementFromPoint(e.clientX, e.clientY)?.closest('.chapter-card');
            if (!card) return;

            const cb = card.querySelector('input[type="checkbox"]');
            if (!cb) return;

            // Let native checkbox/label behavior run, but keep UI state synced.
            if (e.target === cb || e.target.closest('label')) {
                queueMicrotask(() => this.updateSelectedChapters());
                return;
            }

            cb.checked = !cb.checked;
            this.updateSelectedChapters();
        };

        this.updateSelectedChapters();
    },

    updateSelectedChapters() {
        const checkboxes = document.querySelectorAll('#chaptersGrid input[type="checkbox"]:checked');
        this.selectedChapters = Array.from(checkboxes).map(cb => cb.value);

        // Update visual selection state on chapter cards
        document.querySelectorAll('#chaptersGrid .chapter-card').forEach(card => {
            const cb = card.querySelector('input[type="checkbox"]');
            card.classList.toggle('selected-chapter', cb && cb.checked);
        });

        const startBtn = document.getElementById('startExamBtn');
        if (startBtn) {
            const hasSelection = this.selectedChapters.length > 0;
            startBtn.disabled = !hasSelection;
            startBtn.style.display = hasSelection ? 'block' : 'none';
        }
    },

    selectAllChapters() {
        const checkboxes = document.querySelectorAll('#chaptersGrid input[type="checkbox"]');
        checkboxes.forEach(cb => {
            if (cb.closest('.chapter-card').style.display !== 'none') {
                cb.checked = true;
            }
        });
        this.updateSelectedChapters();
    },

    selectNoneChapters() {
        const checkboxes = document.querySelectorAll('#chaptersGrid input[type="checkbox"]');
        checkboxes.forEach(cb => cb.checked = false);
        this.updateSelectedChapters();
    },

    // Track whether content libs are loaded
    _contentLibsReady: false,

    async _enhanceDiagrams(element) {
        if (!element || typeof DiagramHandler === 'undefined') return;

        try {
            await DiagramHandler.enhanceContainer(element, {
                subjectId: this.currentSubject?.id || ''
            });
        } catch (e) {
            console.warn('Diagram enhancement failed:', e);
        }
    },

    _cleanupResultImageIO() {
        if (this._resultImageIO) {
            this._resultImageIO.disconnect();
            this._resultImageIO = null;
        }
    },

    _loadDeferredImage(img) {
        if (!img || img.dataset.loaded === '1') return;
        const src = img.getAttribute('data-src');
        if (!src) return;
        img.dataset.loaded = '1';
        img.src = src;
    },

    _initLazyResultImages(container) {
        if (!container) return;

        const images = container.querySelectorAll('img[data-src]');
        if (!images.length) return;

        if (!('IntersectionObserver' in window)) {
            images.forEach((img) => this._loadDeferredImage(img));
            return;
        }

        if (this._resultImageIO) {
            this._resultImageIO.disconnect();
        }

        this._resultImageIO = new IntersectionObserver((entries, observer) => {
            for (const entry of entries) {
                if (!entry.isIntersecting && entry.intersectionRatio <= 0) continue;
                this._loadDeferredImage(entry.target);
                observer.unobserve(entry.target);
            }
        }, {
            root: null,
            rootMargin: '250px 0px',
            threshold: 0.01,
        });

        images.forEach((img) => this._resultImageIO.observe(img));
    },

    async _finalizeResultCard(card) {
        if (!card) return;
        ContentRenderer.typeset(card);
        await this._enhanceDiagrams(card);
        ContentRenderer.attachImageListeners(card);
        this._initLazyResultImages(card);
    },

    /**
     * Load content-rendering libraries on demand (Marked, Prism).
     * Called once before first question render.
     */
    async _ensureContentLibs() {
        if (this._contentLibsReady) return;
        if (typeof LibLoader !== 'undefined') {
            await LibLoader.loadContentLibs();
        }
        // Re-initialize ContentRenderer now that libs are loaded
        if (typeof ContentRenderer !== 'undefined') {
            ContentRenderer.init();
        }
        this._contentLibsReady = true;
    },

    async startExam() {
        // Collect questions from selected chapters
        this.questions = [];
        const selectedChapterIds = new Set(this.selectedChapters);

        this.allChapters = []; // Re-populate for safety or just search in subjects

        // Flatten all chapters from all subjects for easy lookup
        this.subjects.forEach(s => {
            this.allChapters.push(...s.chapters);
        });

        this.allChapters.forEach(chapter => {
            const chapterKey = chapter.scopedId || this._makeChapterKey(chapter.subjectId || this.currentSubject?.id || '', chapter.id);
            if (selectedChapterIds.has(chapterKey)) {
                this.questions.push(...chapter.questions);
            }
        });

        if (this.questions.length === 0) {
            this.showModal('No Questions', 'Please select at least one chapter.');
            return;
        }

        this.currentQuestionIndex = 0;
        this.userAnswers = {};
        this.checkedAnswers = {};
        this.questionStatuses = {};
        this._answeredCount = 0;
        this.clearProgress(); // Clear any old progress when starting new exam

        // Lazy-load content rendering libs before showing exam
        this.showLoading('Preparing exam...');
        try {
            await this._ensureContentLibs();
        } catch (e) {
            console.warn('Some content libs failed to load:', e);
        }
        this.hideLoading();

        this.showExamView();
    },

    showExamView() {
        this.currentView = 'exam';
        this.hideAllViews();
        document.body.classList.add('exam-active');
        // Pause WebGL background animation during exam to save GPU cycles
        if (typeof window._floatingLinesPause === 'function') window._floatingLinesPause();
        document.querySelector('header').style.display = 'none'; // Hide header
        const view = document.getElementById('examView');
        view.style.display = 'block';
        view.classList.add('view-enter');
        setTimeout(() => view.classList.remove('view-enter'), 400);

        // Update title
        const subjectName = this.currentSubject ? this.currentSubject.name : 'Exam';
        document.getElementById('examTitle').textContent = `${subjectName} — ${this.questions.length} questions`;
        document.getElementById('totalQuestions').textContent = this.questions.length;

        this.renderQuestionNumbers();
        this.renderCurrentQuestion();
        this.updateQuestionNumberStyles();

        // Toast notification
        this.showToast(`Exam started with ${this.questions.length} questions. Good luck!`, 'info', 3500);
    },

    // Cached question number buttons for O(1) class updates
    _questionBtns: [],

    renderQuestionNumbers() {
        const container = document.getElementById('questionNumbers');
        const fragment = document.createDocumentFragment();
        const count = this.questions.length;
        this._questionBtns = new Array(count);

        // Use event delegation instead of per-button onclick
        container.textContent = '';
        container.onclick = (e) => {
            const btn = e.target.closest('.question-number');
            if (!btn) return;
            const idx = parseInt(btn.dataset.idx, 10);
            if (!isNaN(idx)) this.goToQuestion(idx);
        };

        for (let idx = 0; idx < count; idx++) {
            const btn = document.createElement('button');
            btn.className = 'question-number' + (idx === 0 ? ' active' : '');
            btn.textContent = idx + 1;
            btn.dataset.idx = idx;
            fragment.appendChild(btn);
            this._questionBtns[idx] = btn;
        }
        container.appendChild(fragment);
        this.updateQuestionNumberStyles();
    },

    renderCurrentQuestion() {
        const idx = this.currentQuestionIndex;
        const question = this.questions[idx];
        const container = document.getElementById('questionContainer');
        const isCheckbox = question.inputType === 'checkbox';
        const inputType = isCheckbox ? 'checkbox' : 'radio';
        const currentAnswer = this.userAnswers[idx] || (isCheckbox ? [] : '');
        const isLastQuestion = idx === this.questions.length - 1;

        document.getElementById('currentQuestion').textContent = idx + 1;

        // Build DOM with DocumentFragment for single reflow
        const fragment = document.createDocumentFragment();

        // Question text
        const textDiv = document.createElement('div');
        textDiv.className = 'question-text';
        textDiv.innerHTML = this._renderQuestionContent(question.text, question);
        fragment.appendChild(textDiv);

        // Question image (lazy loaded with decode hints)
        if (question.image) {
            const imgWrapper = document.createElement('div');
            imgWrapper.className = 'question-image';
            const img = document.createElement('img');
            img.src = question.image;
            img.alt = 'Question illustration';
            img.loading = 'lazy';
            img.decoding = 'async';
            imgWrapper.appendChild(img);
            fragment.appendChild(imgWrapper);
        }

        // Choices container with event delegation
        const choicesDiv = document.createElement('div');
        choicesDiv.className = 'choices';
        choicesDiv.addEventListener('change', (e) => {
            const input = e.target;
            if (input.name === 'answer') {
                this.selectAnswer(input.value, isCheckbox);
            }
        });

        // Improve click/tap reliability by treating the whole answer card as selectable.
        choicesDiv.addEventListener('click', (e) => {
            const choiceCard = e.target.closest('.choice');
            if (!choiceCard) return;

            const input = choiceCard.querySelector('input[name="answer"]');
            if (!input || e.target === input) return;

            if (isCheckbox) {
                input.checked = !input.checked;
            } else {
                input.checked = true;
            }

            input.dispatchEvent(new Event('change', { bubbles: true }));
        });

        const normalizeText = (value) => String(value || '').replace(/\s+/g, ' ').trim();

        // Right-click on an answer card copies question + answer for quick sharing/review.
        choicesDiv.addEventListener('contextmenu', async (e) => {
            const choiceCard = e.target.closest('.choice')
                || document.elementFromPoint(e.clientX, e.clientY)?.closest('.choice');
            if (!choiceCard) return;

            const questionText = normalizeText(container.querySelector('.question-text')?.textContent || '');
            const label = choiceCard.querySelector('label');
            const answerText = normalizeText(label?.textContent || '');
            if (!answerText) return;

            e.preventDefault();
            const payload = questionText
                ? `Question: ${questionText}\nAnswer: ${answerText}`
                : `Answer: ${answerText}`;
            const copied = await this.copyTextToClipboard(payload);
            this.showToast(copied ? 'Question + answer copied' : 'Copy failed', copied ? 'success' : 'error', 1200);
        });

        // Right-click question text to copy question only.
        const questionTextDiv = fragment.querySelector?.('.question-text') || null;
        if (questionTextDiv) {
            questionTextDiv.addEventListener('contextmenu', async (e) => {
                const questionText = normalizeText(questionTextDiv.textContent || '');
                if (!questionText) return;
                e.preventDefault();
                const copied = await this.copyTextToClipboard(`Question: ${questionText}`);
                this.showToast(copied ? 'Question copied' : 'Copy failed', copied ? 'success' : 'error', 1200);
            });
        }

        for (let i = 0; i < question.choices.length; i++) {
            const choice = question.choices[i];
            const isSelected = isCheckbox
                ? (Array.isArray(currentAnswer) && currentAnswer.includes(choice.value))
                : currentAnswer === choice.value;

            const choiceDiv = document.createElement('div');
            choiceDiv.className = 'choice' + (isSelected ? ' selected' : '');

            const input = document.createElement('input');
            input.type = inputType;
            input.id = `choice-${choice.value}`;
            input.name = 'answer';
            input.value = choice.value;
            if (isSelected) input.checked = true;

            const label = document.createElement('label');
            label.htmlFor = `choice-${choice.value}`;
            label.innerHTML = this._renderQuestionContent(choice.text, question);

            choiceDiv.appendChild(input);
            choiceDiv.appendChild(label);
            choicesDiv.appendChild(choiceDiv);
        }
        fragment.appendChild(choicesDiv);

        // Single DOM write
        container.textContent = '';
        container.appendChild(fragment);

        // Typeset MathJax + render diagrams + attach image listeners
        ContentRenderer.typeset(container);
        this._enhanceDiagrams(container);
        ContentRenderer.attachImageListeners(container);

        // Update button states (batch reads then writes to avoid layout thrashing)
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const checkBtn = document.getElementById('checkBtn');
        const submitBtn = document.getElementById('submitBtn');
        const feedbackEl = document.getElementById('feedback');

        prevBtn.disabled = idx === 0;
        nextBtn.disabled = false;
        checkBtn.style.display = 'block';
        submitBtn.style.display = isLastQuestion ? 'block' : 'none';

        // Clear feedback
        feedbackEl.className = 'feedback';
        feedbackEl.textContent = '';

        // Restore check state if already checked
        if (this.checkedAnswers[idx]) {
            this.showFeedback(idx);
        }
    },

    selectAnswer(value, isCheckbox) {
        const idx = this.currentQuestionIndex;
        const wasPreviouslyAnswered = !this._isSkipped(this.userAnswers[idx]);
        const wasChecked = !!this.checkedAnswers[idx];

        if (isCheckbox) {
            const current = this.userAnswers[idx] || [];
            const pos = current.indexOf(value);
            if (pos !== -1) {
                current.splice(pos, 1);
                this.userAnswers[idx] = current;
            } else {
                current.push(value);
                this.userAnswers[idx] = current;
            }
        } else {
            this.userAnswers[idx] = value;
        }

        if (wasChecked) {
            delete this.checkedAnswers[idx];
            delete this.questionStatuses[idx];
            const feedbackEl = document.getElementById('feedback');
            if (feedbackEl) {
                feedbackEl.className = 'feedback';
                feedbackEl.textContent = '';
            }
        }

        // Update incremental answered count
        const isNowAnswered = !this._isSkipped(this.userAnswers[idx]);
        if (!wasPreviouslyAnswered && isNowAnswered) this._answeredCount++;
        else if (wasPreviouslyAnswered && !isNowAnswered) this._answeredCount--;

        // Update visual selected state on all choices
        const choices = document.querySelectorAll('.choice');
        choices.forEach(choice => {
            const input = choice.querySelector('input');
            choice.classList.toggle('selected', input && input.checked);
        });

        this.updateQuestionNumberStyles();

        // Auto-save on answer change (debounced)
        this.saveProgress();
    },

    checkAnswer() {
        const idx = this.currentQuestionIndex;
        const question = this.questions[idx];
        const userAnswer = this.userAnswers[idx];
        const status = this._getQuestionStatus(question, userAnswer);

        this.checkedAnswers[idx] = true;
        this.questionStatuses[idx] = status;
        this.updateQuestionNumberStyles();
        this.showFeedback(idx, status);

        // Toast feedback 
        this.showToast(
            status === 'correct'
                ? 'Correct! Well done!'
                : (status === 'wrong' ? 'Incorrect. Check the explanation below.' : 'Skipped. Review the answer below.'),
            status === 'correct' ? 'success' : (status === 'wrong' ? 'error' : 'info'),
            2500
        );
    },

    /** Determine the status for a checked question */
    _getQuestionStatus(question, userAnswer) {
        if (this._isSkipped(userAnswer)) return 'skipped';
        return this._isAnswerCorrect(question, userAnswer) ? 'correct' : 'wrong';
    },

    /** Check if an answer is correct (reusable helper) */
    _isAnswerCorrect(question, userAnswer) {
        if (question.inputType === 'checkbox') {
            const correct = question.correctAnswer.split('');
            const user = Array.isArray(userAnswer) ? userAnswer : [];
            return correct.length === user.length && correct.every(a => user.includes(a));
        }
        return userAnswer === question.correctAnswer;
    },

    /** Resolve answer key (A/B/C...) to the actual choice text */
    _getChoiceTextByValue(question, value) {
        const choices = Array.isArray(question?.choices) ? question.choices : [];
        const choice = choices.find(c => c.value === value);
        if (!choice) return value;

        // For web questions, return raw text to preserve visible HTML tags
        if (this._isWebRelatedQuestion(question)) {
            return choice.text || value;
        }

        // Convert rendered rich text to plain text for compact feedback line
        const temp = document.createElement('div');
        temp.innerHTML = ContentRenderer.render(choice.text || '');
        const plain = (temp.textContent || temp.innerText || '').trim();
        return plain || value;
    },

    showFeedback(index, status = null) {
        const question = this.questions[index];
        const userAnswer = this.userAnswers[index];
        const feedbackEl = document.getElementById('feedback');
        const answerStatus = status || this._getQuestionStatus(question, userAnswer);

        feedbackEl.className = `feedback ${answerStatus}`;

        const message = answerStatus === 'correct' ? '✓ Correct!' : (answerStatus === 'wrong' ? '✗ Incorrect' : '○ Skipped');
        const correctAnswerText = question.inputType === 'checkbox'
            ? question.correctAnswer.split('').map(a => this._getChoiceTextByValue(question, a)).join(', ')
            : this._getChoiceTextByValue(question, question.correctAnswer);
        const correctText = question.inputType === 'checkbox'
            ? `Correct answers: ${correctAnswerText}`
            : `Correct answer: ${correctAnswerText}`;

        const explanationRaw = question.explanation || 'Coming soon...';

        // Build feedback DOM
        const frag = document.createDocumentFragment();

        const strong = document.createElement('strong');
        strong.textContent = message;
        frag.appendChild(strong);

        const correctDiv = document.createElement('div');
        correctDiv.className = 'correct-answer';
        correctDiv.textContent = correctText;
        frag.appendChild(correctDiv);

        const explanationDiv = document.createElement('div');
        explanationDiv.className = 'explanation';
        explanationDiv.style.cssText = 'margin-top:10px;padding-top:10px;border-top:1px solid rgba(0,0,0,0.1)';
        explanationDiv.innerHTML = `<strong>Explanation:</strong><br>${this._renderQuestionContent(explanationRaw, question)}`;
        frag.appendChild(explanationDiv);

        feedbackEl.textContent = '';
        feedbackEl.appendChild(frag);

        ContentRenderer.typeset(feedbackEl);
        this._enhanceDiagrams(feedbackEl);
        ContentRenderer.attachImageListeners(feedbackEl);
    },

    goToQuestion(index) {
        this.currentQuestionIndex = index;
        this.renderCurrentQuestion();
        this.updateQuestionNumberStyles();
        this.scrollToActiveQuestion();
        // Scroll question container into view smoothly
        const container = document.getElementById('questionContainer');
        if (container) {
            container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    },

    scrollToActiveQuestion() {
        const activeBtn = document.querySelector('.question-number.active');
        if (activeBtn) {
            activeBtn.scrollIntoView({
                behavior: 'auto',
                block: 'nearest',
                inline: 'center'
            });
        }
    },

    nextQuestion() {
        if (this.currentQuestionIndex < this.questions.length - 1) {
            this.currentQuestionIndex++;
            this.renderCurrentQuestion();
            this.updateQuestionNumberStyles();
        }
    },

    previousQuestion() {
        if (this.currentQuestionIndex > 0) {
            this.currentQuestionIndex--;
            this.renderCurrentQuestion();
            this.updateQuestionNumberStyles();
        }
    },

    updateQuestionNumberStyles() {
        const btns = this._questionBtns;
        const currentIdx = this.currentQuestionIndex;
        const answers = this.userAnswers;
        const statuses = this.questionStatuses;
        for (let idx = 0; idx < btns.length; idx++) {
            const btn = btns[idx];
            if (!btn) continue;
            btn.classList.toggle('active', idx === currentIdx);
            const status = statuses[idx];
            btn.classList.toggle('answered', !!answers[idx] && !status);
            btn.classList.toggle('correct', status === 'correct');
            btn.classList.toggle('wrong', status === 'wrong');
            btn.classList.toggle('skipped', status === 'skipped');
        }
        this.updateProgressIndicator();
    },

    updateProgressIndicator() {
        const totalQuestions = this.questions.length;
        const answeredCount = this._answeredCount;
        const percentage = totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0;

        const progressBar = document.getElementById('examProgressBar');
        const answeredCountEl = document.getElementById('answeredCount');
        const totalAnswerableEl = document.getElementById('totalAnswerable');

        if (progressBar) progressBar.style.width = `${percentage}%`;
        if (answeredCountEl) answeredCountEl.textContent = answeredCount;
        if (totalAnswerableEl) totalAnswerableEl.textContent = totalQuestions;
    },

    showReviewModal() {
        const totalQuestions = this.questions.length;
        let answeredCount = this._answeredCount;
        const unansweredCount = totalQuestions - answeredCount;

        // Build review question grid with array push (faster than map+join for large arrays)
        const gridParts = [];
        for (let idx = 0; idx < totalQuestions; idx++) {
            const isAnswered = !this._isSkipped(this.userAnswers[idx]);
            gridParts.push(`<button class="review-q-btn ${isAnswered ? 'answered' : 'unanswered'}" 
                                    onclick="app.closeReviewModal(); app.goToQuestion(${idx});">
                                ${idx + 1}
                            </button>`);
        }

        // Create review modal content
        const modalHtml = `
            <div class="modal-overlay" id="reviewModal" style="display: flex;">
                <div class="modal review-modal">
                    <div class="modal-header">
                        <h3>📋 Review Your Exam</h3>
                    </div>
                    <div class="modal-body">
                        <div class="review-stats">
                            <div class="review-stat">
                                <div class="review-stat-number">${totalQuestions}</div>
                                <div class="review-stat-label">Total</div>
                            </div>
                            <div class="review-stat">
                                <div class="review-stat-number" style="color: var(--success);">${answeredCount}</div>
                                <div class="review-stat-label">Answered</div>
                            </div>
                            <div class="review-stat">
                                <div class="review-stat-number" style="color: var(--warning);">${unansweredCount}</div>
                                <div class="review-stat-label">Unanswered</div>
                            </div>
                        </div>
                        ${unansweredCount > 0 ? `<p style="color: var(--warning); text-align: center; margin-bottom: 16px;">⚠️ You have ${unansweredCount} unanswered question${unansweredCount > 1 ? 's' : ''}.</p>` : ''}
                        <div class="review-questions-grid">
                            ${gridParts.join('')}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-cancel" onclick="app.closeReviewModal()">Continue Exam</button>
                        <button class="btn-confirm" onclick="app.confirmSubmit()" style="background: var(--success);">✓ Submit Exam</button>
                    </div>
                </div>
            </div>
        `;

        // Add to body
        const existingModal = document.getElementById('reviewModal');
        if (existingModal) {
            existingModal.remove();
        }
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },

    closeReviewModal() {
        const modal = document.getElementById('reviewModal');
        if (modal) {
            modal.remove();
        }
    },

    confirmSubmit() {
        this.closeReviewModal();
        this.submitExam();
    },

    submitExam() {
        this.clearProgress(); // Clear saved progress on submit
        this.showResultsView();
    },

    showResultsView() {
        this.currentView = 'results';
        this.hideAllViews();
        const view = document.getElementById('resultsView');
        view.style.display = 'block';
        view.classList.add('view-enter');
        setTimeout(() => view.classList.remove('view-enter'), 400);
        this.calculateAndDisplayResults();
        // Scroll to top of results
        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    /** Check if answer was skipped */
    _isSkipped(answer) {
        return answer === undefined || answer === '' ||
            (Array.isArray(answer) && answer.length === 0);
    },

    getLetterGrade(percentage) {
        if (percentage >= 97) return 'Z+';
        if (percentage >= 93) return 'Z';
        if (percentage >= 90) return 'Z-';
        if (percentage >= 87) return 'B+';
        if (percentage >= 83) return 'B';
        if (percentage >= 80) return 'B-';
        if (percentage >= 77) return 'C+';
        if (percentage >= 73) return 'C';
        if (percentage >= 70) return 'C-';
        return 'F';
    },



    _getScoreTone(percentage) {
        if (percentage >= 85) return 'success';
        if (percentage >= 70) return 'primary';
        if (percentage >= 60) return 'warning';
        return 'danger';
    },

    calculateAndDisplayResults() {
        const totalCount = this.questions.length;
        let correctCount = 0, wrongCount = 0, skippedCount = 0;
        const questionResults = new Array(totalCount);

        // Single pass classification
        for (let idx = 0; idx < totalCount; idx++) {
            const question = this.questions[idx];
            const userAnswer = this.userAnswers[idx];
            const wasSkipped = this._isSkipped(userAnswer);
            const isCorrect = wasSkipped ? false : this._isAnswerCorrect(question, userAnswer);

            if (wasSkipped) skippedCount++;
            else if (isCorrect) correctCount++;
            else wrongCount++;

            questionResults[idx] = { question, idx, userAnswer, isCorrect, wasSkipped };
        }

        const percentage = totalCount > 0 ? Math.round((correctCount / totalCount) * 100) : 0;
        const displayGrade = this.getLetterGrade(percentage);
        const scoreTone = this._getScoreTone(percentage);

        const resultsView = document.getElementById('resultsView');
        if (resultsView) {
            resultsView.dataset.scoreTone = scoreTone;
        }

        const scoreGradeEl = document.getElementById('scoreGrade');
        const scorePercentEl = document.getElementById('scorePercentage');
        if (scoreGradeEl) scoreGradeEl.textContent = displayGrade;
        if (scorePercentEl) scorePercentEl.textContent = `${percentage}%`;

        document.getElementById('scoreDisplay').textContent = `${correctCount} / ${totalCount}`;
        document.getElementById('scoreText').textContent = '';

        // Animate score ring
        this.animateScoreRing(percentage, scoreTone);

        if (percentage >= 90) this.triggerConfetti();

        // Result message lookup (avoids if-else chain)
        const messages = [
            [90, '🌟 Outstanding! You have mastered this material!'],
            [80, '😊 Great job! You have a good understanding.'],
            [70, '👍 Good effort! Keep practicing to improve.'],
            [60, '📚 You\'re making progress. Study more and try again.'],
            [0, '💪 Keep practicing! Review the material and try again.']
        ];
        const resultMessage = messages.find(([threshold]) => percentage >= threshold)[1];

        // Build results DOM using DocumentFragment
        const resultDetails = document.getElementById('resultDetails');
        const mainFrag = document.createDocumentFragment();

        // Stats section
        const statsDiv = document.createElement('div');
        statsDiv.className = 'results-stats';
        const statDefs = [
            { cls: 'stat-correct', icon: '✓', count: correctCount, label: 'Correct', filter: 'correct' },
            { cls: 'stat-wrong', icon: '✗', count: wrongCount, label: 'Wrong', filter: 'wrong' },
            { cls: 'stat-skipped', icon: '○', count: skippedCount, label: 'Skipped', filter: 'skipped' },
        ];
        for (const stat of statDefs) {
            const card = document.createElement('div');
            card.className = `results-stat-card ${stat.cls}`;
            card.title = `Show only ${stat.label.toLowerCase()} answers`;
            card.onclick = () => this.filterResults(stat.filter);
            card.innerHTML = `<div class="stat-icon">${stat.icon}</div><div class="stat-number">${stat.count}</div><div class="stat-label">${stat.label}</div>`;
            statsDiv.appendChild(card);
        }
        mainFrag.appendChild(statsDiv);

        // Show All button
        const showAllWrap = document.createElement('div');
        showAllWrap.style.cssText = 'text-align:center;margin-bottom:20px';
        const showAllBtn = document.createElement('button');
        showAllBtn.className = 'nav-btn';
        showAllBtn.style.cssText = 'display:inline-block;width:auto;padding:8px 16px;font-size:0.9rem;opacity:0.8';
        showAllBtn.textContent = 'Show All Questions';
        showAllBtn.onclick = () => this.filterResults('all');
        showAllWrap.appendChild(showAllBtn);
        mainFrag.appendChild(showAllWrap);

        // Question cards list — LAZY RENDERED via IntersectionObserver
        const listDiv = document.createElement('div');
        listDiv.className = 'results-questions-list';

        // Create lightweight placeholder sentinel divs for each card
        const INITIAL_RENDER_COUNT = 8; // Render first N cards immediately
        const sentinels = [];

        for (let i = 0; i < questionResults.length; i++) {
            if (i < INITIAL_RENDER_COUNT) {
                // Render first batch immediately for instant LCP
                const card = this._buildResultCard(questionResults[i]);
                listDiv.appendChild(card);
            } else {
                // Create a lightweight sentinel placeholder
                const sentinel = document.createElement('div');
                sentinel.className = 'results-card-sentinel';
                sentinel.style.minHeight = '200px'; // Approximate card height for scroll stability
                sentinel.dataset.idx = i;
                listDiv.appendChild(sentinel);
                sentinels.push(sentinel);
            }
        }
        mainFrag.appendChild(listDiv);

        // Single DOM write
        resultDetails.textContent = '';
        resultDetails.appendChild(mainFrag);

        // Hydrate only the initially-rendered cards
        const initialCards = listDiv.querySelectorAll('.results-question-card');
        if (initialCards.length > 0) {
            initialCards.forEach((card) => this._finalizeResultCard(card));
        }

        // Set up IntersectionObserver for lazy card rendering
        this._cleanupResultIO();
        if (sentinels.length > 0) {
            this._resultIO = new IntersectionObserver((entries) => {
                for (const entry of entries) {
                    if (!entry.isIntersecting) continue;
                    const sentinel = entry.target;
                    const idx = parseInt(sentinel.dataset.idx, 10);
                    if (isNaN(idx)) continue;

                    // Replace sentinel with fully rendered card
                    const card = this._buildResultCard(questionResults[idx]);
                    sentinel.replaceWith(card);
                    this._resultIO.unobserve(sentinel);

                    // Hydrate just this card
                    this._finalizeResultCard(card);
                }
            }, { rootMargin: '300px 0px' }); // Start rendering 300px before visible

            for (const sentinel of sentinels) {
                this._resultIO.observe(sentinel);
            }
        }
    },

    /** Build a single result question card DOM element */
    _buildResultCard(result) {
        const { question, idx, userAnswer, isCorrect, wasSkipped } = result;
        const statusClass = wasSkipped ? 'skipped' : (isCorrect ? 'correct' : 'wrong');
        const statusText = wasSkipped ? 'Skipped' : (isCorrect ? 'Correct' : 'Wrong');
        const statusIcon = wasSkipped ? '○' : (isCorrect ? '✓' : '✗');

        const card = document.createElement('div');
        card.className = `results-question-card ${statusClass}`;

        // Header
        const header = document.createElement('div');
        header.className = 'results-q-header';
        header.innerHTML = `<span class="results-q-number">Question ${idx + 1}</span><span class="results-q-badge ${statusClass}">${statusIcon} ${statusText}</span>`;
        card.appendChild(header);

        // Image
        if (question.image) {
            const imgWrap = document.createElement('div');
            imgWrap.className = 'question-image';
            const img = document.createElement('img');
            img.dataset.src = question.image;
            img.src = 'data:image/gif;base64,R0lGODlhAQABAAAAACw=';
            img.alt = 'Question illustration';
            img.loading = 'lazy';
            img.decoding = 'async';
            imgWrap.appendChild(img);
            card.appendChild(imgWrap);
        }

        // Question text
        const qText = document.createElement('div');
        qText.className = 'results-q-text question-text';
        qText.innerHTML = this._renderQuestionContent(question.text, question);
        card.appendChild(qText);

        // Choices
        const correctAnswers = question.inputType === 'checkbox'
            ? question.correctAnswer.split('') : [question.correctAnswer];
        const userAnswers = wasSkipped ? []
            : (Array.isArray(userAnswer) ? userAnswer : [userAnswer]);

        const choicesList = document.createElement('div');
        choicesList.className = 'results-choices-list';

        for (const choice of question.choices) {
            const isThisCorrect = correctAnswers.includes(choice.value);
            const isUserPick = userAnswers.includes(choice.value);

            let choiceClass = '', choiceIcon = '';
            if (isThisCorrect) { choiceClass = 'correct'; choiceIcon = '✓'; }
            else if (isUserPick) { choiceClass = 'user-wrong'; choiceIcon = '✗'; }

            const choiceDiv = document.createElement('div');
            choiceDiv.className = `results-choice ${choiceClass}`;
            choiceDiv.innerHTML = `<div class="results-choice-letter">${choice.value}</div><div class="results-choice-text">${this._renderQuestionContent(choice.text, question)}</div>${choiceIcon ? `<div class="results-choice-icon">${choiceIcon}</div>` : ''}`;
            choicesList.appendChild(choiceDiv);
        }
        card.appendChild(choicesList);

        // Explanation
        if (question.explanation) {
            const expDiv = document.createElement('div');
            expDiv.className = 'results-explanation';
            expDiv.innerHTML = `<strong>💡 Explanation:</strong><div class="results-explanation-text">${this._renderQuestionContent(question.explanation, question)}</div>`;
            card.appendChild(expDiv);
        }

        return card;
    },

    goBackToSubjects() {
        this.showSubjectsView();
    },

    restart() {
        this.selectedChapters = [];
        this.showSubjectsView();
    },

    hideAllViews() {
        document.body.classList.remove('exam-active');
        // Resume WebGL background when leaving exam
        if (typeof window._floatingLinesResume === 'function') window._floatingLinesResume();
        document.querySelector('header').style.display = 'block'; // Show header by default
        document.getElementById('subjectsView').style.display = 'none';
        document.getElementById('chaptersView').style.display = 'none';
        document.getElementById('examView').style.display = 'none';
        document.getElementById('resultsView').style.display = 'none';
    },

    resetExam() {
        this.currentQuestionIndex = 0;
        this.questions = [];
        this.userAnswers = {};
        this.checkedAnswers = {};
        this.questionStatuses = {};
        this._answeredCount = 0;
        this._cleanupResultIO();
        this._cleanupResultImageIO();
    },

    /** Cleanup IntersectionObserver for results lazy rendering */
    _cleanupResultIO() {
        if (this._resultIO) {
            this._resultIO.disconnect();
            this._resultIO = null;
        }
    },

    handleHomeClick() {
        if (this.currentView === 'exam' || this.currentView === 'results') {
            this.showModal(
                'Exit to Home?',
                'Are you sure you want to go to the Home screen? Your current exam progress will be lost.',
                true,
                () => this.restart()
            );
        } else {
            this.showSubjectsView();
        }
    },

    filterResults(status) {
        // status: 'correct', 'wrong', 'skipped', 'all'
        const cards = document.querySelectorAll('.results-question-card');
        const statCards = document.querySelectorAll('.results-stat-card');

        // Batch reads first, then writes (avoid layout thrashing)
        const isAll = status === 'all';

        // Write phase — stat card opacity/transform
        for (let i = 0; i < statCards.length; i++) {
            const c = statCards[i];
            if (isAll) {
                c.style.opacity = '1';
                c.style.transform = '';
            } else if (c.classList.contains(`stat-${status}`)) {
                c.style.opacity = '1';
                c.style.transform = 'scale(1.05)';
            } else {
                c.style.opacity = '0.5';
                c.style.transform = 'scale(0.95)';
            }
        }

        // Write phase — card visibility
        for (let i = 0; i < cards.length; i++) {
            cards[i].style.display = (isAll || cards[i].classList.contains(status)) ? 'block' : 'none';
        }
    },

    confirmExit() {
        this._flushSave(); // Ensure progress is saved before exit dialog
        this.showModal(
            'Exit Exam?',
            'Are you sure you want to exit? Your current progress will be lost.',
            true,
            () => this.exitExam()
        );
    },

    closeConfirmModal() {
        // Legacy function for compatibility
        this.closeModal();
    },

    exitExam() {
        this.clearProgress();
        this.restart();
    },

    // === Score Ring Animation ===
    animateScoreRing(percentage, scoreTone = 'primary') {
        const ring = document.getElementById('scoreRingProgress');
        const percentText = document.getElementById('scorePercentage');
        const startStop = document.getElementById('scoreGradientStart');
        const endStop = document.getElementById('scoreGradientEnd');
        if (!ring || !percentText) return;

        const toneStops = {
            success: ['#10b981', '#22d3ee'],
            primary: ['#6366f1', '#8b5cf6'],
            warning: ['#f59e0b', '#f97316'],
            danger: ['#ff4d5e', '#ff7a59'],
        };
        const [startColor, endColor] = toneStops[scoreTone] || toneStops.primary;
        if (startStop) startStop.setAttribute('style', `stop-color: ${startColor}`);
        if (endStop) endStop.setAttribute('style', `stop-color: ${endColor}`);

        const circumference = 2 * Math.PI * 65; // r=65
        const offset = circumference - (percentage / 100) * circumference;

        // Start from full offset (empty)
        ring.style.strokeDasharray = circumference;
        ring.style.strokeDashoffset = circumference;

        // Animate after a tiny delay for the transition to work
        requestAnimationFrame(() => {
            setTimeout(() => {
                ring.style.strokeDashoffset = offset;
            }, 100);
        });

        // Animate percentage counter
        let current = 0;
        const step = Math.max(1, Math.ceil(percentage / 60));
        const timer = setInterval(() => {
            current = Math.min(current + step, percentage);
            percentText.textContent = `${current}%`;
            if (current >= percentage) clearInterval(timer);
        }, 20);
    }
};

// Initialize app when page loads
window.addEventListener('DOMContentLoaded', async () => {
    await app.init();

    const params = new URLSearchParams(window.location.search);
    const requestedSubject = (params.get('subject') || '').trim();
    if (!requestedSubject) return;

    const normalizedSubject = requestedSubject.toLowerCase();
    const matchedSubject = app.subjects.find((subject) =>
        String(subject?.id || '').trim().toLowerCase() === normalizedSubject
    );

    if (matchedSubject) {
        await app.selectSubject(matchedSubject.id);
    }
});

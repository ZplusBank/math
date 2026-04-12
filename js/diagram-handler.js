/**
 * Diagram Handler
 *
 * Pluggable diagram rendering pipeline that can:
 * - map subjects to preferred diagram engines
 * - auto-detect diagram code blocks from fenced language hints
 * - lazy-load rendering libraries only when needed
 * - allow future engine registration without touching exam flow
 */
const DiagramHandler = {
    _initialized: false,
    _engines: {},
    _languageAliases: {},
    _subjectEngineMap: {
        network: ['mermaid', 'graphviz'],
        data_structure: ['mermaid', 'nomnoml'],
        uml: ['nomnoml', 'mermaid'],
        dbms: ['mermaid'],
        database: ['mermaid'],
        algorithm: ['mermaid']
    },

    init() {
        if (this._initialized) return;

        this.registerEngine('mermaid', {
            load: async () => {
                if (typeof LibLoader !== 'undefined') {
                    await LibLoader.loadDiagramEngine('mermaid');
                }
                if (typeof mermaid !== 'undefined' && !mermaid.__zplusInited) {
                    mermaid.initialize({ startOnLoad: false, securityLevel: 'loose' });
                    mermaid.__zplusInited = true;
                }
            },
            render: async (code, mountEl) => {
                if (typeof mermaid === 'undefined') {
                    throw new Error('Mermaid is not available');
                }
                const diagramId = `diagram_mermaid_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
                const rendered = await mermaid.render(diagramId, code);
                mountEl.innerHTML = rendered.svg || '';
            }
        });

        this.registerEngine('graphviz', {
            load: async () => {
                if (typeof LibLoader !== 'undefined') {
                    await LibLoader.loadDiagramEngine('graphviz');
                }
            },
            render: async (code, mountEl) => {
                if (typeof Viz === 'undefined') {
                    throw new Error('Viz.js is not available');
                }
                const viz = new Viz();
                const svg = await viz.renderString(code);
                mountEl.innerHTML = svg;
            }
        });

        this.registerEngine('nomnoml', {
            load: async () => {
                if (typeof LibLoader !== 'undefined') {
                    await LibLoader.loadDiagramEngine('nomnoml');
                }
            },
            render: async (code, mountEl) => {
                if (typeof nomnoml === 'undefined' || !nomnoml.renderSvg) {
                    throw new Error('Nomnoml is not available');
                }
                mountEl.innerHTML = nomnoml.renderSvg(code);
            }
        });

        // Canonical aliases.
        this.registerLanguageAlias(['mermaid', 'flowchart', 'sequence', 'mindmap', 'erd', 'database', 'network', 'datastructure'], 'mermaid');
        this.registerLanguageAlias(['dot', 'graphviz', 'digraph'], 'graphviz');
        this.registerLanguageAlias(['uml', 'classdiagram', 'nomnoml'], 'nomnoml');

        this._initialized = true;
    },

    registerEngine(engineName, handlers) {
        const name = String(engineName || '').toLowerCase();
        if (!name || !handlers || typeof handlers.render !== 'function') return;
        this._engines[name] = {
            load: handlers.load || (async () => { }),
            render: handlers.render
        };
    },

    registerLanguageAlias(languageIds, engineName) {
        const engine = String(engineName || '').toLowerCase();
        if (!engine) return;

        const list = Array.isArray(languageIds) ? languageIds : [languageIds];
        for (let i = 0; i < list.length; i++) {
            const key = String(list[i] || '').toLowerCase();
            if (key) this._languageAliases[key] = engine;
        }
    },

    registerSubjectEngines(subjectId, engineNames) {
        const sid = String(subjectId || '').toLowerCase();
        if (!sid) return;
        const list = (Array.isArray(engineNames) ? engineNames : [engineNames])
            .map(x => String(x || '').toLowerCase())
            .filter(Boolean);
        if (list.length) {
            this._subjectEngineMap[sid] = list;
        }
    },

    _resolveSubjectEngines(subjectId) {
        const sid = String(subjectId || '').toLowerCase();
        return this._subjectEngineMap[sid] || [];
    },

    _resolveEngineFromLang(lang, subjectId) {
        const key = String(lang || '').toLowerCase();
        if (this._languageAliases[key]) return this._languageAliases[key];

        // Subject-level fallback for generic tags.
        if (key === 'diagram' || key === 'chart') {
            const preferred = this._resolveSubjectEngines(subjectId);
            if (preferred.length) return preferred[0];
        }

        return '';
    },

    _resolveEngineFromCode(code, subjectId) {
        const text = String(code || '');
        if (!text) return '';

        if (/^\s*(graph\s+\w+|digraph\s+\w+)/i.test(text)) return 'graphviz';
        if (/^\s*#?title\s*:/i.test(text) || /\[[^\]]+\]\s*[-:o+<>*]+\s*\[[^\]]+\]/.test(text)) return 'nomnoml';
        if (/\b(flowchart|sequenceDiagram|classDiagram|erDiagram|stateDiagram|mindmap)\b/i.test(text)) return 'mermaid';

        // Do not force generic code blocks into a diagram engine.
        // Only explicit language hints or known diagram syntax should render as diagrams.
        return '';
    },

    _getLanguageHint(wrapper, codeEl) {
        const dataLang = wrapper ? String(wrapper.getAttribute('data-source-lang') || '').toLowerCase().trim() : '';
        if (dataLang) return dataLang;

        const cls = codeEl ? String(codeEl.className || '') : '';
        const m = cls.match(/language-([a-z0-9_\-]+)/i);
        if (m && m[1]) return String(m[1]).toLowerCase();

        return '';
    },

    _extractCandidates(container) {
        const wrappers = container.querySelectorAll('.code-block-wrapper');
        const candidates = [];

        for (let i = 0; i < wrappers.length; i++) {
            const wrapper = wrappers[i];
            if (wrapper.dataset.diagramEnhanced === '1') continue;

            const codeEl = wrapper.querySelector('pre code');
            if (!codeEl) continue;

            const code = String(codeEl.textContent || '').trim();
            if (!code) continue;

            candidates.push({ wrapper, codeEl, code });
        }

        return candidates;
    },

    async _renderCandidate(candidate, engineName) {
        const engine = this._engines[engineName];
        if (!engine) return false;

        const wrapper = candidate.wrapper;
        const pre = wrapper.querySelector('pre');
        if (!pre) return false;

        const mount = document.createElement('div');
        mount.className = `diagram-surface diagram-${engineName}`;
        mount.innerHTML = '<div class="diagram-loading">Rendering diagram...</div>';

        pre.replaceWith(mount);

        try {
            await engine.load();
            await engine.render(candidate.code, mount);
            wrapper.dataset.diagramEnhanced = '1';
            wrapper.classList.add('diagram-enhanced');
            return true;
        } catch (e) {
            // Restore original code block if rendering fails.
            mount.replaceWith(pre);
            console.warn(`Diagram render failed for ${engineName}:`, e);
            return false;
        }
    },

    async enhanceContainer(container, options = {}) {
        if (!container) return;
        this.init();

        const subjectId = String(options.subjectId || '');
        const candidates = this._extractCandidates(container);
        if (!candidates.length) return;

        for (let i = 0; i < candidates.length; i++) {
            const item = candidates[i];
            const langHint = this._getLanguageHint(item.wrapper, item.codeEl);
            const fromLang = this._resolveEngineFromLang(langHint, subjectId);
            const fromCode = this._resolveEngineFromCode(item.code, subjectId);
            const engineName = fromLang || fromCode;

            if (!engineName) continue;
            await this._renderCandidate(item, engineName);
        }
    }
};

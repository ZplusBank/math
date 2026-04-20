/**
 * Lazy Library Loader
 * Loads 3rd-party scripts on-demand to eliminate TBT on initial page load.
 * Each library is loaded at most once; subsequent calls return immediately.
 */
const LibLoader = {
    _loaded: {},
    _loading: {},
    _preconnectDone: false,

    _ensurePreconnect() {
        if (this._preconnectDone || typeof document === 'undefined') return;
        this._preconnectDone = true;

        const link = document.createElement('link');
        link.rel = 'preconnect';
        link.href = 'https://cdn.jsdelivr.net';
        link.crossOrigin = 'anonymous';
        document.head.appendChild(link);
    },

    /**
     * Load a single script by URL. Returns a Promise.
     * Deduplicates: if already loaded or loading, reuses the promise.
     */
    loadScript(url) {
        if (this._loaded[url]) return Promise.resolve();
        if (this._loading[url]) return this._loading[url];

        this._ensurePreconnect();

        this._loading[url] = new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = url;
            s.async = true;
            s.onload = () => {
                this._loaded[url] = true;
                delete this._loading[url];
                resolve();
            };
            s.onerror = () => {
                delete this._loading[url];
                reject(new Error('Failed to load: ' + url));
            };
            document.head.appendChild(s);
        });
        return this._loading[url];
    },

    /**
     * Load multiple scripts sequentially (order matters for dependencies).
     */
    async loadScriptsSequential(urls) {
        for (const url of urls) {
            await this.loadScript(url);
        }
    },

    /**
     * Load Marked.js + Prism.js (needed for rendering question content)
     * Only loads core language packs initially; others loaded on-demand.
     */
    async loadMarkdownAndPrism() {
        if (this._loaded._markdownPrism) return;
        if (this._loading._markdownPrism) return this._loading._markdownPrism;

        const promise = (async () => {
            // Load Marked and Prism core in parallel, then common language packs.
            await Promise.all([
                this.loadScript('https://cdn.jsdelivr.net/npm/marked/marked.min.js'),
                this.loadScript('https://cdn.jsdelivr.net/npm/prismjs@1/prism.min.js')
            ]);

            await Promise.all([
                this.loadScript('https://cdn.jsdelivr.net/npm/prismjs@1/components/prism-java.min.js'),
                this.loadScript('https://cdn.jsdelivr.net/npm/prismjs@1/components/prism-c.min.js'),
                this.loadScript('https://cdn.jsdelivr.net/npm/prismjs@1/components/prism-cpp.min.js'),
                this.loadScript('https://cdn.jsdelivr.net/npm/prismjs@1/plugins/line-numbers/prism-line-numbers.min.js'),
            ]);

            this._loaded._markdownPrism = true;
        })();

        this._loading._markdownPrism = promise.finally(() => {
            delete this._loading._markdownPrism;
        });

        return this._loading._markdownPrism;
    },

    /**
     * Load additional Prism language pack on-demand (e.g. 'python', 'csharp', 'sql')
     */
    async loadPrismLanguage(lang) {
        const url = `https://cdn.jsdelivr.net/npm/prismjs@1/components/prism-${lang}.min.js`;
        if (this._loaded[url]) return;
        try {
            await this.loadScript(url);
        } catch (e) {
            console.warn(`Prism language "${lang}" not available:`, e);
        }
    },

    /**
     * Load MathJax (only when math content is detected)
     */
    async loadMathJax() {
        if (this._loaded._mathjax) return;
        if (this._loading._mathjax) return this._loading._mathjax;
        if (typeof MathJax !== 'undefined' && MathJax.typesetPromise) {
            this._loaded._mathjax = true;
            return;
        }
        const promise = (async () => {
            await this.loadScript('https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js');

            if (typeof MathJax !== 'undefined' && MathJax.startup && MathJax.startup.promise) {
                await MathJax.startup.promise;
            } else {
                await new Promise((resolve, reject) => {
                    let elapsed = 0;
                    const check = () => {
                        if (typeof MathJax !== 'undefined' && MathJax.typesetPromise) {
                            resolve();
                        } else if (elapsed > 10000) {
                            reject(new Error('MathJax init timeout'));
                        } else {
                            elapsed += 50;
                            setTimeout(check, 50);
                        }
                    };
                    check();
                });
            }

            this._loaded._mathjax = true;
        })();

        this._loading._mathjax = promise.finally(() => {
            delete this._loading._mathjax;
        });

        return this._loading._mathjax;
    },

    /**
     * Load Mermaid.js (flowcharts, UML-like, ER, mindmap, etc.)
     */
    async loadMermaid() {
        if (this._loaded._mermaid) return;
        if (typeof mermaid !== 'undefined') {
            this._loaded._mermaid = true;
            return;
        }
        await this.loadScript('https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js');
        this._loaded._mermaid = true;
    },

    /**
     * Load Viz.js (Graphviz DOT renderer)
     */
    async loadGraphviz() {
        if (this._loaded._graphviz) return;
        if (typeof Viz !== 'undefined') {
            this._loaded._graphviz = true;
            return;
        }
        await this.loadScriptsSequential([
            'https://cdn.jsdelivr.net/npm/viz.js@2.1.2/viz.js',
            'https://cdn.jsdelivr.net/npm/viz.js@2.1.2/full.render.js'
        ]);
        this._loaded._graphviz = true;
    },

    /**
     * Load Nomnoml (simple UML class/structure diagrams)
     */
    async loadNomnoml() {
        if (this._loaded._nomnoml) return;
        if (typeof nomnoml !== 'undefined') {
            this._loaded._nomnoml = true;
            return;
        }
        await this.loadScript('https://cdn.jsdelivr.net/npm/nomnoml@1/dist/nomnoml.js');
        this._loaded._nomnoml = true;
    },

    /**
     * Generic diagram engine loader by engine id.
     */
    async loadDiagramEngine(engineName) {
        const key = String(engineName || '').toLowerCase();
        if (!key) return;

        if (key === 'mermaid') {
            await this.loadMermaid();
            return;
        }
        if (key === 'graphviz' || key === 'dot') {
            await this.loadGraphviz();
            return;
        }
        if (key === 'nomnoml' || key === 'uml') {
            await this.loadNomnoml();
            return;
        }
    },

    /**
     * Load all content-rendering libs (call before first question render)
     */
    async loadContentLibs() {
        if (this._loaded._contentLibs) return;
        if (this._loading._contentLibs) return this._loading._contentLibs;

        const promise = (async () => {
            await this.loadMarkdownAndPrism();
            // MathJax loaded lazily on first typeset call, not here
            this._loaded._contentLibs = true;
        })();

        this._loading._contentLibs = promise.finally(() => {
            delete this._loading._contentLibs;
        });

        return this._loading._contentLibs;
    }
};

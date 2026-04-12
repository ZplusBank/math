// Floating Lines Background — Vanilla JS (adapted from ReactBits)
// Uses Three.js + GLSL shaders for animated wave lines

(function () {
  const container = document.getElementById('floatingLinesBg');
  if (!container) return;

  // --- GLSL Shaders ---
  const vertexShader = `
precision mediump float;
void main() {
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

  const fragmentShader = `
precision mediump float;

uniform float iTime;
uniform vec3  iResolution;
uniform float animationSpeed;

uniform bool enableTop;
uniform bool enableMiddle;
uniform bool enableBottom;

uniform int topLineCount;
uniform int middleLineCount;
uniform int bottomLineCount;

uniform float topLineDistance;
uniform float middleLineDistance;
uniform float bottomLineDistance;

uniform vec3 topWavePosition;
uniform vec3 middleWavePosition;
uniform vec3 bottomWavePosition;

uniform vec2 iMouse;
uniform bool interactive;
uniform float bendRadius;
uniform float bendStrength;
uniform float bendInfluence;

uniform bool parallax;
uniform float parallaxStrength;
uniform vec2 parallaxOffset;

uniform vec3 lineGradient[8];
uniform int lineGradientCount;

const vec3 BLACK = vec3(0.0);
const vec3 PINK  = vec3(0.9137, 0.2784, 0.9608);
const vec3 BLUE  = vec3(0.1843, 0.2941, 0.6353);

mat2 rotate(float r) {
  float c = cos(r), s = sin(r);
  return mat2(c, s, -s, c);
}

vec3 background_color(vec2 uv) {
  float y = sin(uv.x - 0.2) * 0.3 - 0.1;
  float m = uv.y - y;
  vec3 col = mix(BLUE, BLACK, smoothstep(0.0, 1.0, abs(m)));
  col += mix(PINK, BLACK, smoothstep(0.0, 1.0, abs(m - 0.8)));
  return col * 0.5;
}

vec3 getLineColor(float t) {
  if (lineGradientCount <= 1) {
    return lineGradient[0] * 0.5;
  }
  float scaled = clamp(t, 0.0, 0.9999) * float(lineGradientCount - 1);
  int idx = int(floor(scaled));
  int idx2 = min(idx + 1, lineGradientCount - 1);
  return mix(lineGradient[idx], lineGradient[idx2], fract(scaled)) * 0.5;
}

// Precomputed time passed in to avoid recomputing per wave call
float wave(vec2 uv, float offset, float time, vec2 screenUv, vec2 mouseUv, bool shouldBend) {
  float x_movement = time * 0.1;
  float amp = sin(offset + time * 0.2) * 0.3;
  float y = sin(uv.x + offset + x_movement) * amp;

  // Skip expensive exp() when bend influence is negligible
  if (shouldBend && bendInfluence > 0.001) {
    vec2 d = screenUv - mouseUv;
    float influence = exp(-dot(d, d) * bendRadius);
    y += (mouseUv.y - screenUv.y) * influence * bendStrength * bendInfluence;
  }

  float m = uv.y - y;
  return 0.0175 / (abs(m) + 0.01) + 0.01;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
  vec2 baseUv = (2.0 * fragCoord - iResolution.xy) / iResolution.y;
  baseUv.y *= -1.0;

  if (parallax) { baseUv += parallaxOffset; }

  // Precompute shared values once per pixel
  float time = iTime * animationSpeed;
  float logLen = log(length(baseUv) + 1.0);
  bool doBend = interactive && bendInfluence > 0.001;

  vec3 col = vec3(0.0);
  vec3 b = lineGradientCount > 0 ? vec3(0.0) : background_color(baseUv);

  vec2 mouseUv = vec2(0.0);
  if (doBend) {
    mouseUv = (2.0 * iMouse - iResolution.xy) / iResolution.y;
    mouseUv.y *= -1.0;
  }

  if (enableBottom) {
    mat2 rot = rotate(bottomWavePosition.z * logLen);
    vec2 ruv = baseUv * rot;
    for (int i = 0; i < bottomLineCount; ++i) {
      float fi = float(i);
      vec3 lineCol = lineGradientCount > 0 ? getLineColor(fi / max(float(bottomLineCount - 1), 1.0)) : b;
      col += lineCol * wave(
        ruv + vec2(bottomLineDistance * fi + bottomWavePosition.x, bottomWavePosition.y),
        1.5 + 0.2 * fi, time, baseUv, mouseUv, doBend
      ) * 0.2;
    }
  }

  if (enableMiddle) {
    mat2 rot = rotate(middleWavePosition.z * logLen);
    vec2 ruv = baseUv * rot;
    for (int i = 0; i < middleLineCount; ++i) {
      float fi = float(i);
      vec3 lineCol = lineGradientCount > 0 ? getLineColor(fi / max(float(middleLineCount - 1), 1.0)) : b;
      col += lineCol * wave(
        ruv + vec2(middleLineDistance * fi + middleWavePosition.x, middleWavePosition.y),
        2.0 + 0.15 * fi, time, baseUv, mouseUv, doBend
      );
    }
  }

  if (enableTop) {
    mat2 rot = rotate(topWavePosition.z * logLen);
    vec2 ruv = baseUv * rot;
    ruv.x *= -1.0;
    for (int i = 0; i < topLineCount; ++i) {
      float fi = float(i);
      vec3 lineCol = lineGradientCount > 0 ? getLineColor(fi / max(float(topLineCount - 1), 1.0)) : b;
      col += lineCol * wave(
        ruv + vec2(topLineDistance * fi + topWavePosition.x, topWavePosition.y),
        1.0 + 0.2 * fi, time, baseUv, mouseUv, doBend
      ) * 0.1;
    }
  }

  fragColor = vec4(col, 1.0);
}

void main() {
  mainImage(gl_FragColor, gl_FragCoord.xy);
}
`;

  // --- Config ---
  const isMobile = window.innerWidth < 768;
  const config = {
    linesGradient: ['#3730a3', '#4338ca', '#5b21b6', '#6d28d9'],
    enabledWaves: ['top', 'middle', 'bottom'],
    lineCount: isMobile ? [2, 2, 2] : [4, 4, 4],
    lineDistance: [5, 5, 5],
    topWavePosition: { x: 10.0, y: 0.5, rotate: -0.4 },
    middleWavePosition: { x: 5.0, y: 0.0, rotate: 0.2 },
    bottomWavePosition: { x: 2.0, y: -0.7, rotate: -1.0 },
    animationSpeed: 1,
    interactive: !isMobile,
    bendRadius: 5.0,
    bendStrength: -0.5,
    mouseDamping: 0.04,
    parallax: !isMobile,
    parallaxStrength: 0.2
  };

  // --- Helpers ---
  function hexToVec3(hex) {
    let v = hex.replace('#', '');
    if (v.length === 3) v = v[0] + v[0] + v[1] + v[1] + v[2] + v[2];
    return new THREE.Vector3(
      parseInt(v.slice(0, 2), 16) / 255,
      parseInt(v.slice(2, 4), 16) / 255,
      parseInt(v.slice(4, 6), 16) / 255
    );
  }

  function getIdx(arr, wave, def) {
    if (typeof arr === 'number') return arr;
    const i = config.enabledWaves.indexOf(wave);
    return i >= 0 && i < arr.length ? arr[i] : def;
  }

  // --- Three.js Setup ---
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  camera.position.z = 1;

  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1));
  renderer.domElement.style.width = '100%';
  renderer.domElement.style.height = '100%';
  container.appendChild(renderer.domElement);

  // --- Uniforms ---
  const MAX_GRADIENT = 8;
  const gradientArr = Array.from({ length: MAX_GRADIENT }, () => new THREE.Vector3(1, 1, 1));
  let gradientCount = 0;

  if (config.linesGradient && config.linesGradient.length > 0) {
    const stops = config.linesGradient.slice(0, MAX_GRADIENT);
    gradientCount = stops.length;
    stops.forEach((hex, i) => {
      const c = hexToVec3(hex);
      gradientArr[i].set(c.x, c.y, c.z);
    });
  }

  const topLC = config.enabledWaves.includes('top') ? getIdx(config.lineCount, 'top', 6) : 0;
  const midLC = config.enabledWaves.includes('middle') ? getIdx(config.lineCount, 'middle', 6) : 0;
  const botLC = config.enabledWaves.includes('bottom') ? getIdx(config.lineCount, 'bottom', 6) : 0;

  const topLD = (config.enabledWaves.includes('top') ? getIdx(config.lineDistance, 'top', 5) : 0.1) * 0.01;
  const midLD = (config.enabledWaves.includes('middle') ? getIdx(config.lineDistance, 'middle', 5) : 0.1) * 0.01;
  const botLD = (config.enabledWaves.includes('bottom') ? getIdx(config.lineDistance, 'bottom', 5) : 0.1) * 0.01;

  const uniforms = {
    iTime: { value: 0 },
    iResolution: { value: new THREE.Vector3(1, 1, 1) },
    animationSpeed: { value: config.animationSpeed },

    enableTop: { value: config.enabledWaves.includes('top') },
    enableMiddle: { value: config.enabledWaves.includes('middle') },
    enableBottom: { value: config.enabledWaves.includes('bottom') },

    topLineCount: { value: topLC },
    middleLineCount: { value: midLC },
    bottomLineCount: { value: botLC },

    topLineDistance: { value: topLD },
    middleLineDistance: { value: midLD },
    bottomLineDistance: { value: botLD },

    topWavePosition: {
      value: new THREE.Vector3(config.topWavePosition.x, config.topWavePosition.y, config.topWavePosition.rotate)
    },
    middleWavePosition: {
      value: new THREE.Vector3(config.middleWavePosition.x, config.middleWavePosition.y, config.middleWavePosition.rotate)
    },
    bottomWavePosition: {
      value: new THREE.Vector3(config.bottomWavePosition.x, config.bottomWavePosition.y, config.bottomWavePosition.rotate)
    },

    iMouse: { value: new THREE.Vector2(-1000, -1000) },
    interactive: { value: config.interactive },
    bendRadius: { value: config.bendRadius },
    bendStrength: { value: config.bendStrength },
    bendInfluence: { value: 0 },

    parallax: { value: config.parallax },
    parallaxStrength: { value: config.parallaxStrength },
    parallaxOffset: { value: new THREE.Vector2(0, 0) },

    lineGradient: { value: gradientArr },
    lineGradientCount: { value: gradientCount }
  };

  const material = new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader });
  const geometry = new THREE.PlaneGeometry(2, 2);
  const mesh = new THREE.Mesh(geometry, material);
  scene.add(mesh);

  // --- Cached state for performance ---
  let isMobileCached = window.innerWidth < 768;
  let cachedRect = null;
  const cachedDpr = renderer.getPixelRatio();

  // --- Resize Handler ---
  function setSize() {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    uniforms.iResolution.value.set(renderer.domElement.width, renderer.domElement.height, 1);
    cachedRect = renderer.domElement.getBoundingClientRect();

    // Update mobile state on resize
    const newIsMobile = window.innerWidth < 768;
    isMobileCached = newIsMobile;
    if (uniforms.interactive.value !== !newIsMobile) {
      // Update uniforms for mobile/desktop switch
      uniforms.interactive.value = !newIsMobile;
      uniforms.parallax.value = !newIsMobile;

      // Update line counts
      const newCounts = newIsMobile ? [2, 2, 2] : [4, 4, 4];
      uniforms.topLineCount.value = config.enabledWaves.includes('top') ? getIdx(newCounts, 'top', 6) : 0;
      uniforms.middleLineCount.value = config.enabledWaves.includes('middle') ? getIdx(newCounts, 'middle', 6) : 0;
      uniforms.bottomLineCount.value = config.enabledWaves.includes('bottom') ? getIdx(newCounts, 'bottom', 6) : 0;
    }
  }
  setSize();

  // (Resize observer moved to bottom to handle loop restart)

  // --- Mouse interactivity (throttled) ---
  const targetMouse = new THREE.Vector2(-1000, -1000);
  const currentMouse = new THREE.Vector2(-1000, -1000);
  let targetInfluence = 0;
  let currentInfluence = 0;
  const targetParallax = new THREE.Vector2(0, 0);
  const currentParallax = new THREE.Vector2(0, 0);
  const damping = config.mouseDamping;
  let pointerDirty = false;

  document.addEventListener('pointermove', (e) => {
    if (!cachedRect || pointerDirty) return;
    pointerDirty = true;
    const x = e.clientX - cachedRect.left;
    const y = e.clientY - cachedRect.top;
    targetMouse.set(x * cachedDpr, (cachedRect.height - y) * cachedDpr);
    targetInfluence = 1.0;

    if (config.parallax) {
      const cx = cachedRect.width * 0.5;
      const cy = cachedRect.height * 0.5;
      targetParallax.set(
        ((x - cx) / cachedRect.width) * config.parallaxStrength,
        -((y - cy) / cachedRect.height) * config.parallaxStrength
      );
    }
  }, { passive: true });

  document.addEventListener('pointerleave', () => {
    targetInfluence = 0.0;
  });

  // --- Visibility API: pause when tab hidden ---
  let tabHidden = document.hidden;
  let appPaused = false; // External pause (e.g. during exam)
  document.addEventListener('visibilitychange', () => {
    tabHidden = document.hidden;
    if (!tabHidden && !appPaused && !isMobileCached && !animationId) {
      clock.start();
      animationId = requestAnimationFrame(renderLoop);
    }
  });

  // Expose pause/resume for exam mode (saves GPU cycles)
  window._floatingLinesPause = function () {
    appPaused = true;
    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }
  };
  window._floatingLinesResume = function () {
    appPaused = false;
    if (!tabHidden && !isMobileCached && !animationId) {
      clock.start();
      animationId = requestAnimationFrame(renderLoop);
    }
  };

  // --- Render Loop (throttled to ~30fps) ---
  const clock = new THREE.Clock();
  let animationId = null;
  let lastRenderTime = 0;
  const FRAME_INTERVAL = 1000 / 30;

  function renderLoop(timestamp) {
    // Mobile optimization: Render only once, then stop loop
    if (isMobileCached) {
      renderer.render(scene, camera);
      animationId = null;
      return;
    }

    // Pause when tab is not visible or app explicitly paused
    if (tabHidden || appPaused) {
      animationId = null;
      return;
    }

    // Throttle to ~30fps
    if (timestamp - lastRenderTime < FRAME_INTERVAL) {
      animationId = requestAnimationFrame(renderLoop);
      return;
    }
    lastRenderTime = timestamp;

    uniforms.iTime.value = clock.getElapsedTime();

    // Smooth mouse interpolation
    currentMouse.lerp(targetMouse, damping);
    uniforms.iMouse.value.copy(currentMouse);
    currentInfluence += (targetInfluence - currentInfluence) * damping;
    uniforms.bendInfluence.value = currentInfluence;

    currentParallax.lerp(targetParallax, damping);
    uniforms.parallaxOffset.value.copy(currentParallax);

    // Allow next pointer event
    pointerDirty = false;

    renderer.render(scene, camera);
    animationId = requestAnimationFrame(renderLoop);
  }

  // Initial render
  renderLoop();

  // --- Resize handler with loop management ---
  let resizeTimer = 0;
  function handleResize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      setSize();

      if (!isMobileCached && !animationId && !tabHidden) {
        clock.start();
        renderLoop();
      } else if (isMobileCached && animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
        renderer.render(scene, camera);
      } else if (isMobileCached) {
        renderer.render(scene, camera);
      }
    }, 100);
  }

  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(handleResize).observe(container);
  } else {
    window.addEventListener('resize', handleResize);
  }
})();

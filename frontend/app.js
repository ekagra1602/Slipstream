/* ================================================================
   DomBot Knowledge Graph - Obsidian Route Atlas
   3D force-directed graph + live route motion + cinematic camera
   ================================================================ */

(function () {
  "use strict";

  const VISUAL_CONFIG = {
    background: "#0A0A0C",
    bloom: {
      strength: 1.35,
      radius: 0.45,
      threshold: 0.28,
    },
    confidence: {
      low: { r: 100, g: 105, b: 115 },
      mid: { r: 140, g: 138, b: 130 },
      high: { r: 180, g: 165, b: 130 },
    },
    links: {
      hubBaseAlpha: 0.1,
      hubAlphaScale: 0.25,
      crossBaseAlpha: 0.13,
      crossAlphaScale: 0.3,
      hubBaseWidth: 0.35,
      hubWidthScale: 1.35,
      crossBaseWidth: 0.45,
      crossWidthScale: 1.55,
    },
    particles: {
      color: "#BFCBDA",
      width: 1.55,
      baseSpeed: 0.0019,
      speedScale: 0.0023,
      minStrength: 0.35,
      hardCapMin: 70,
      hardCapMax: 240,
      batchCount: 4,
      epochMs: 650,
    },
    hover: {
      delayMs: 400,
      nonFocusLinkAlpha: 0.02,
      nonFocusLinkWidthFactor: 0.3,
      focusLinkAlphaBoost: 0.48,
      focusLinkWidthBoost: 2.3,
      dimNodeOpacityFactor: 0.13,
      neighborNodeOpacityFactor: 1.08,
      focusNodeOpacityFactor: 1.46,
      dimNodeScaleFactor: 0.93,
      neighborNodeScaleFactor: 1.08,
      focusNodeScaleFactor: 1.28,
      dimLabelOpacity: 0.12,
    },
    replay: {
      durationMs: 2800,
      nodeEaseMs: 520,
      linkEaseMs: 420,
      minScale: 0.001,
      ringCount: 14,
      ringJitterMs: 90,
      edgeLagMs: 120,
    },
    flyIn: {
      spawnYOffset: 760,
      durationMs: 1850,
      edgeRevealDistance: 8,
      edgeFadeMs: 320,
      glowHoldMs: 3000,
      queueMax: 20,
      highlightColor: 0xf5e9b8,
      replayLockBufferMs: 220,
    },
    ambient: {
      pointsCount: 4000,
      linksCount: 1000,
      clusterSpread: 165,
      fallbackRadius: 240,
      pointSize: 1.1,
      pointOpacity: 0.14,
      linkOpacity: 0.055,
      pointColor: 0x9fb2c7,
      linkColor: 0x8f9daf,
      motionY: 0.000016,
      motionX: 0.000007,
    },
    bursts: {
      lifeMs: 900,
      baseOpacity: 0.52,
      scale: 10,
      color: 0xc6d4e5,
    },
    camera: {
      defaultDistance: 520,
      minDistance: 120,
      maxDistance: 2800,
      introDurationMs: 3600,
      introNearDistance: 4,
      introFarDistance: 430,
      launchHoldMs: 2600,
      frameRadiusScale: 2.75,
      framePadding: 135,
      frameSampleMs: 180,
      frameLerpFactor: 0.33,
      cinematicFrameScale: 0.86,
      focusDistanceTask: 205,
      focusDistanceDomain: 260,
      zoomStep: 26,
      wheelDeltaClampPx: 240,
      wheelZoomSensitivity: 0.00145,
      pinchZoomSensitivity: 0.00105,
      wheelTargetFollowFactor: 0.2,
      wheelTweenMs: 0,
      targetFollowFactor: 0.72,
      cinematicOrbitSpeed: 0.00012,
      cinematicSwitchMs: 6200,
      cinematicHeight: 75,
      cinematicBob: 34,
    },
    labels: {
      updateThrottleMs: 110,
      nearDistance: 235,
      activityThreshold: 0.72,
      domainOpacity: 0.95,
      taskOpacity: 0.68,
    },
    motion: {
      nodePulseSpeed: 0.0016,
      nodePulseMinScale: 1.0,
      nodePulseMaxScale: 1.08,
    },
    performance: {
      degradeMs: 22,
      recoverMs: 17,
      floorFactor: 0.45,
      stepDown: 0.03,
      stepUp: 0.02,
    },
    layout: {
      containmentRadius: 980,
      containmentPull: 0.09,
      velocityDamping: 0.86,
    },
    realtime: {
      convexSuppressFallbackMs: 1800,
      seenTraceCap: 2000,
    },
  };

  const dom = {
    graph: document.getElementById("graph"),
    landingOverlay: document.getElementById("landing-overlay"),
    landingCta: document.getElementById("landing-cta"),
    landingStatus: document.getElementById("landing-status"),
    detailPanel: document.getElementById("detail-panel"),
    detailTitle: document.getElementById("detail-title"),
    detailDomain: document.getElementById("detail-domain"),
    detailConfidenceBar: document.getElementById("detail-confidence-bar"),
    detailConfidenceText: document.getElementById("detail-confidence-text"),
    detailRuns: document.getElementById("detail-runs"),
    detailActions: document.getElementById("detail-actions"),
    detailTraces: document.getElementById("detail-traces"),
    detailClose: document.getElementById("detail-close"),
    statDomains: document.getElementById("stat-domains"),
    statTasks: document.getElementById("stat-tasks"),
    statRuns: document.getElementById("stat-runs"),
    statConfidence: document.getElementById("stat-confidence"),
    statRealNodes: document.getElementById("stat-real-nodes"),
    statAmbientVisuals: document.getElementById("stat-ambient-visuals"),
    btnSimulate: document.getElementById("btn-simulate"),
    btnReplayGrowth: document.getElementById("btn-replay-growth"),
    btnCinematic: document.getElementById("btn-cinematic"),
    chkAuto: document.getElementById("chk-auto"),
    timelineSlider: document.getElementById("timeline-slider"),
    timelinePlay: document.getElementById("timeline-play"),
    timelineDate: document.getElementById("timeline-date"),
  };

  // ---- Utility helpers ----
  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function lerpRound(a, b, t) {
    return Math.round(lerp(a, b, t));
  }

  function easeOutCubic(t) {
    const clamped = clamp(t, 0, 1);
    return 1 - Math.pow(1 - clamped, 3);
  }

  function easeInOutCubic(t) {
    const clamped = clamp(t, 0, 1);
    if (clamped < 0.5) return 4 * clamped * clamped * clamped;
    return 1 - Math.pow(-2 * clamped + 2, 3) / 2;
  }

  function hashString(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i += 1) {
      h ^= str.charCodeAt(i);
      h += (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24);
    }
    return h >>> 0;
  }

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function rand() {
      a += 0x6d2b79f5;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function confidenceRgb(confidence) {
    const conf = clamp(confidence || 0, 0, 1);
    const low = VISUAL_CONFIG.confidence.low;
    const mid = VISUAL_CONFIG.confidence.mid;
    const high = VISUAL_CONFIG.confidence.high;

    if (conf <= 0.5) {
      const t = conf / 0.5;
      return {
        r: lerpRound(low.r, mid.r, t),
        g: lerpRound(low.g, mid.g, t),
        b: lerpRound(low.b, mid.b, t),
      };
    }

    const t = (conf - 0.5) / 0.5;
    return {
      r: lerpRound(mid.r, high.r, t),
      g: lerpRound(mid.g, high.g, t),
      b: lerpRound(mid.b, high.b, t),
    };
  }

  function confidenceColor(confidence) {
    const c = confidenceRgb(confidence);
    return `rgb(${c.r},${c.g},${c.b})`;
  }

  function confidenceHex(confidence) {
    const c = confidenceRgb(confidence);
    return (c.r << 16) | (c.g << 8) | c.b;
  }

  function activityFromRuns(runCount, maxRunCount) {
    const maxRuns = Math.max(1, maxRunCount || 1);
    return clamp(Math.log1p(runCount || 0) / Math.log1p(maxRuns), 0, 1);
  }

  function animateValue(el, end, duration, isPercent) {
    const start = 0;
    const startTime = performance.now();

    function tick(now) {
      const elapsed = now - startTime;
      const progress = clamp(elapsed / duration, 0, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(start + (end - start) * eased);
      el.textContent = isPercent ? `${current}%` : current.toLocaleString();
      if (progress < 1) requestAnimationFrame(tick);
    }

    requestAnimationFrame(tick);
  }

  function animateValueBetween(el, start, end, duration, isPercent) {
    if (!el) return;
    if (start === end) {
      el.textContent = isPercent ? `${end}%` : end.toLocaleString();
      return;
    }

    const startTime = performance.now();
    function tick(now) {
      const elapsed = now - startTime;
      const progress = clamp(elapsed / duration, 0, 1);
      const eased = easeOutCubic(progress);
      const current = Math.round(start + (end - start) * eased);
      el.textContent = isPercent ? `${current}%` : current.toLocaleString();
      if (progress < 1) requestAnimationFrame(tick);
    }

    requestAnimationFrame(tick);
  }

  function safeNodeId(ref) {
    return typeof ref === "object" && ref !== null ? ref.id : ref;
  }

  function normalizeLinkPair(sourceId, targetId) {
    const a = String(sourceId);
    const b = String(targetId);
    return a < b ? `${a}::${b}` : `${b}::${a}`;
  }

  const RUNTIME_PARAMS = new window.URLSearchParams(window.location.search);
  const DEMO_QUERY_VALUE = RUNTIME_PARAMS.get("demoMock");
  const IS_LOCAL_HOST =
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "localhost";
  const RUNTIME_FLAGS = {
    demoMock:
      DEMO_QUERY_VALUE === "1" ||
      (DEMO_QUERY_VALUE === null && !IS_LOCAL_HOST),
  };
  const INTRO_GATE_CONFIG = {
    fadeOutMs: 620,
  };

  const MOCK_DEMO_CONFIG = {
    domainCount: 12,
    tasksPerDomain: 68,
    lookbackMs: 1000 * 60 * 60 * 24 * 12,
    maxHistoryEvents: 12000,
    autoSimMinMs: 1200,
    autoSimMaxMs: 2400,
  };

  const MOCK_DOMAIN_POOL = [
    "amazon.com",
    "walmart.com",
    "target.com",
    "bestbuy.com",
    "ebay.com",
    "etsy.com",
    "costco.com",
    "homedepot.com",
    "wayfair.com",
    "nike.com",
    "apple.com",
    "google.com",
    "github.com",
    "linkedin.com",
  ];

  // ---- Global state ----
  let graphData = { nodes: [], links: [] };
  let graph;

  let historyEvents = [];
  let timelineRange = { min: 0, max: Date.now() };
  let isPlaying = false;
  let playInterval = null;
  let currentTimeValue = 1000;
  let firstLoad = true;
  let refreshPending = false;

  let maxRunCount = 1;
  let maxDomainRuns = 1;
  let nodeById = new Map();
  let linkById = new Map();
  let adjacencyByNode = new Map();
  let incidentLinksByNode = new Map();

  const sceneLayers = {
    ambientPoints: null,
    ambientLinks: null,
    eventBurstLayer: null,
    ambientTimer: null,
  };

  const performanceState = {
    frameAvgMs: 16.7,
    particleFactor: 1,
    ambientOpacityFactor: 1,
    runningMs: 0,
  };

  const replayState = {
    active: false,
    startMs: 0,
    nowMs: 0,
    durationMs: VISUAL_CONFIG.replay.durationMs,
    nodeRevealMsById: new Map(),
    linkRevealMsById: new Map(),
    queuedRefresh: false,
  };

  const hoverState = {
    activeNodeId: null,
    activeNodeIds: new Set(),
    activeLinkIds: new Set(),
    pendingNodeId: null,
    pendingTimerId: null,
  };

  const particleBudgetState = {
    activeLinkIds: new Set(),
    epochIndex: 0,
    nextEpochTs: 0,
    dirty: true,
  };

  const flyInState = {
    queue: [],
    queuedNodeIds: new Set(),
    active: null,
    queuedRefresh: false,
    highlightColor: new THREE.Color(VISUAL_CONFIG.flyIn.highlightColor),
  };

  const realtimeState = {
    lastConvexSignalMs: 0,
    seenTraceIds: new Set(),
    seenTraceOrder: [],
    pendingTraceEvents: [],
  };

  const mockState = {
    enabled: RUNTIME_FLAGS.demoMock,
    initialized: false,
    graphStore: null,
    historyStore: [],
    domainList: [],
    tasksByDomain: new Map(),
    linkKeys: new Set(),
    taskSeq: 0,
    traceSeq: 0,
    rand: null,
    autoTimerId: null,
    autoEnabled: false,
  };

  const introGateState = {
    phase: "landing",
    started: false,
    prewarmPromise: null,
    error: null,
  };

  const cameraState = {
    cinematicEnabled: true,
    userInteracted: false,
    focusedNodeId: null,
    hoveredNodeId: null,
    cinematicTargetId: null,
    nextFocusSwitchTs: 0,
    orbitAngle: 0,
    target: new THREE.Vector3(0, 0, 0),
    pointerNDC: new THREE.Vector2(0, 0),
    renderStarted: false,
    lastFrameTs: performance.now(),
    introPlayed: false,
    introActive: false,
    introStartMs: 0,
    introFrom: new THREE.Vector3(0, 0, VISUAL_CONFIG.camera.introNearDistance),
    introTo: new THREE.Vector3(0, 90, VISUAL_CONFIG.camera.introFarDistance),
    introTarget: new THREE.Vector3(0, 0, 0),
    introDirection: new THREE.Vector3(0.9, 0.32, 1).normalize(),
    frameCenter: new THREE.Vector3(0, 0, 0),
    framedRadius: VISUAL_CONFIG.camera.defaultDistance * 0.45,
    framedDistance: VISUAL_CONFIG.camera.defaultDistance,
    lastFrameSampleMs: 0,
    launchFrameUntilMs: 0,
  };

  const labelState = {
    pending: false,
    lastUpdate: 0,
  };

  function randomIntInclusive(randFn, min, max) {
    const rand = typeof randFn === "function" ? randFn : Math.random;
    return Math.floor(rand() * (max - min + 1)) + min;
  }

  function pickRandom(items, randFn) {
    if (!items || !items.length) return null;
    const rand = typeof randFn === "function" ? randFn : Math.random;
    return items[Math.floor(rand() * items.length)] || null;
  }

  function cloneNodeForPayload(node) {
    const copy = { ...node };
    if (Array.isArray(node.optimal_actions)) {
      copy.optimal_actions = node.optimal_actions.slice();
    }
    if (Array.isArray(node.step_traces)) {
      copy.step_traces = node.step_traces.map((trace) => ({ ...trace }));
    }
    return copy;
  }

  function cloneGraphPayload(payload) {
    if (!payload) return { nodes: [], links: [] };
    return {
      nodes: (payload.nodes || []).map((node) => cloneNodeForPayload(node)),
      links: (payload.links || []).map((link) => ({ ...link })),
    };
  }

  function cloneHistoryPayload(events) {
    return { events: (events || []).map((event) => ({ ...event })) };
  }

  function createMockTaskRecord({
    domain,
    domainIndex,
    sequence,
    rand,
    incoming,
  }) {
    const intents = [
      "checkout",
      "price compare",
      "inventory check",
      "order track",
      "search products",
      "filter catalog",
      "collect reviews",
      "wishlist update",
    ];
    const verbs = ["type", "click", "select", "toggle", "submit", "focus"];
    const targets = [
      "search_input",
      "result_card",
      "filter_chip",
      "sort_dropdown",
      "primary_cta",
      "checkout_button",
      "details_panel",
    ];
    const slug = domain.replace(/[^a-z0-9]/g, "_");
    const taskId = incoming
      ? `task:${slug}:live:${sequence}`
      : `task:${slug}:seed:${sequence}`;
    const intent = intents[(sequence + domainIndex * 2) % intents.length];
    const runCount = incoming
      ? randomIntInclusive(rand, 3, 20)
      : randomIntInclusive(rand, 6, 110);
    const confidence = clamp(
      0.36 + rand() * 0.58 + (incoming ? 0.05 : 0),
      0.12,
      0.99,
    );

    const optimalActions = [];
    for (let i = 0; i < 3; i += 1) {
      const verb = verbs[(sequence + domainIndex + i) % verbs.length];
      const target = targets[(sequence + i * 2) % targets.length];
      optimalActions.push(`${verb}:${target}`);
    }

    const stepTraces = optimalActions.map((actionSignature, idx) => ({
      action_signature: actionSignature,
      success_rate: clamp(
        confidence * (0.74 + idx * 0.06 + rand() * 0.12),
        0.05,
        0.99,
      ),
    }));

    return {
      id: taskId,
      type: "task",
      task: `${intent} on ${domain}`,
      domain,
      confidence: Number(confidence.toFixed(3)),
      run_count: runCount,
      optimal_actions: optimalActions,
      step_traces: stepTraces,
    };
  }

  function buildMockHistoryEvents(taskNodes, rand) {
    const nowMs = Date.now();
    const startMs = nowMs - MOCK_DEMO_CONFIG.lookbackMs;
    const events = [];

    taskNodes.forEach((node, idx) => {
      const createdTs = startMs + Math.floor(rand() * (nowMs - startMs));
      events.push({
        timestamp: new Date(createdTs).toISOString(),
        type: "created",
        node_id: node.id,
        task: node.task,
        domain: node.domain,
        confidence: node.confidence,
        run_count: node.run_count,
      });

      if (idx % 3 === 0) {
        const updateTs =
          createdTs + randomIntInclusive(rand, 120000, 1000 * 60 * 60 * 36);
        if (updateTs < nowMs) {
          events.push({
            timestamp: new Date(updateTs).toISOString(),
            type: "updated",
            node_id: node.id,
            task: node.task,
            domain: node.domain,
            confidence: clamp(node.confidence + (rand() - 0.5) * 0.12, 0.08, 1),
            run_count: Math.max(
              1,
              node.run_count + randomIntInclusive(rand, 1, 12),
            ),
          });
        }
      }
    });

    events.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    return events;
  }

  function initializeMockDataset() {
    if (!mockState.enabled || mockState.initialized) return;

    const seed = hashString("slipstream-demo-mock-v1");
    const rand = mulberry32(seed);
    const domainList = MOCK_DOMAIN_POOL.slice(
      0,
      clamp(MOCK_DEMO_CONFIG.domainCount, 1, MOCK_DOMAIN_POOL.length),
    );
    const nodes = [];
    const links = [];
    const tasksByDomain = new Map();
    const linkKeys = new Set();
    const domainRollups = new Map();
    let taskSeq = 0;

    function addLink(source, target, type, strength) {
      if (!source || !target || source === target) return;
      const key = `${type}:${normalizeLinkPair(source, target)}`;
      if (linkKeys.has(key)) return;
      linkKeys.add(key);
      const link = { source, target, type };
      if (type === "cross") {
        link.strength = Math.max(1, Math.round(strength || 1));
      }
      links.push(link);
    }

    domainList.forEach((domain) => {
      tasksByDomain.set(domain, []);
      domainRollups.set(domain, {
        count: 0,
        totalRuns: 0,
        totalConfidence: 0,
      });
    });

    domainList.forEach((domain, domainIndex) => {
      const domainId = `domain:${domain}`;
      for (let i = 0; i < MOCK_DEMO_CONFIG.tasksPerDomain; i += 1) {
        taskSeq += 1;
        const taskNode = createMockTaskRecord({
          domain,
          domainIndex,
          sequence: taskSeq,
          rand,
          incoming: false,
        });
        nodes.push(taskNode);
        tasksByDomain.get(domain).push(taskNode.id);
        addLink(domainId, taskNode.id, "hub", 1);

        const rollup = domainRollups.get(domain);
        rollup.count += 1;
        rollup.totalRuns += taskNode.run_count || 0;
        rollup.totalConfidence += taskNode.confidence || 0;
      }
    });

    domainList.forEach((domain) => {
      const rollup = domainRollups.get(domain);
      const avgConfidence =
        rollup.count > 0 ? rollup.totalConfidence / rollup.count : 0;
      nodes.push({
        id: `domain:${domain}`,
        type: "domain",
        domain,
        task_count: rollup.count,
        total_runs: rollup.totalRuns,
        avg_confidence: Number(avgConfidence.toFixed(3)),
      });
    });

    domainList.forEach((domain, domainIndex) => {
      const taskIds = tasksByDomain.get(domain) || [];
      const len = taskIds.length;
      if (len < 2) return;

      for (let i = 0; i < len; i += 1) {
        if (i % 2 === 0) {
          addLink(
            taskIds[i],
            taskIds[(i + 5) % len],
            "cross",
            1 + ((i + domainIndex) % 3),
          );
        }
        if (i % 9 === 0) {
          addLink(
            taskIds[i],
            taskIds[(i + 17) % len],
            "cross",
            2 + ((i + domainIndex) % 2),
          );
        }
      }
    });

    domainList.forEach((domain, domainIndex) => {
      const nextDomain = domainList[(domainIndex + 1) % domainList.length];
      const aList = tasksByDomain.get(domain) || [];
      const bList = tasksByDomain.get(nextDomain) || [];
      const cap = Math.min(20, aList.length, bList.length);

      for (let i = 0; i < cap; i += 2) {
        const aTask = aList[(i * 3 + domainIndex) % aList.length];
        const bTask = bList[(i * 5 + domainIndex) % bList.length];
        addLink(aTask, bTask, "cross", 1 + ((i + domainIndex) % 3));
      }

      addLink(`domain:${domain}`, `domain:${nextDomain}`, "cross", 1);
    });

    const taskNodes = nodes.filter((node) => node.type === "task");
    const historyStore = buildMockHistoryEvents(taskNodes, rand);

    mockState.graphStore = { nodes, links };
    mockState.historyStore = historyStore;
    mockState.domainList = domainList.slice();
    mockState.tasksByDomain = tasksByDomain;
    mockState.linkKeys = linkKeys;
    mockState.taskSeq = taskSeq;
    mockState.traceSeq = taskSeq;
    mockState.rand = mulberry32(seed ^ 0x9e3779b9);
    mockState.initialized = true;
    console.info(
      "[Slipstream] Frontend demo mock enabled:",
      `${nodes.length} nodes, ${links.length} links`,
    );
  }

  function addMockStoreLink(source, target, type, strength) {
    if (!mockState.graphStore) return;
    if (!source || !target || source === target) return;
    const key = `${type}:${normalizeLinkPair(source, target)}`;
    if (mockState.linkKeys.has(key)) return;

    mockState.linkKeys.add(key);
    const link = { source, target, type };
    if (type === "cross") {
      link.strength = Math.max(1, Math.round(strength || 1));
    }
    mockState.graphStore.links.push(link);
  }

  function createMockTraceArrivalEvent() {
    if (!mockState.enabled) return null;
    initializeMockDataset();
    if (!mockState.graphStore) return null;

    const rand = mockState.rand || Math.random;
    const domain = pickRandom(mockState.domainList, rand);
    if (!domain) return null;
    const domainIndex = mockState.domainList.indexOf(domain);
    const domainId = `domain:${domain}`;
    const existingSameDomain = (
      mockState.tasksByDomain.get(domain) || []
    ).slice();

    const sequence = mockState.taskSeq + 1;
    mockState.taskSeq = sequence;

    const taskNode = createMockTaskRecord({
      domain,
      domainIndex: Math.max(0, domainIndex),
      sequence,
      rand,
      incoming: true,
    });

    mockState.graphStore.nodes.push(taskNode);
    if (!mockState.tasksByDomain.has(domain)) {
      mockState.tasksByDomain.set(domain, []);
    }
    mockState.tasksByDomain.get(domain).push(taskNode.id);

    let domainNode = mockState.graphStore.nodes.find(
      (node) => node.id === domainId && node.type === "domain",
    );
    if (!domainNode) {
      domainNode = {
        id: domainId,
        type: "domain",
        domain,
        task_count: 0,
        total_runs: 0,
        avg_confidence: 0,
      };
      mockState.graphStore.nodes.push(domainNode);
      if (!mockState.domainList.includes(domain)) {
        mockState.domainList.push(domain);
      }
    }

    const prevCount = domainNode.task_count || 0;
    const prevAvg = domainNode.avg_confidence || 0;
    const prevConfTotal = prevCount * prevAvg;
    domainNode.task_count = prevCount + 1;
    domainNode.total_runs =
      (domainNode.total_runs || 0) + (taskNode.run_count || 0);
    domainNode.avg_confidence = Number(
      (
        (prevConfTotal + (taskNode.confidence || 0)) /
        domainNode.task_count
      ).toFixed(3),
    );

    addMockStoreLink(domainId, taskNode.id, "hub", 1);

    const localLinkCount = Math.min(3, existingSameDomain.length);
    for (let i = 0; i < localLinkCount; i += 1) {
      const peer = pickRandom(existingSameDomain, rand);
      if (!peer) continue;
      addMockStoreLink(taskNode.id, peer, "cross", 1 + i);
    }

    const otherDomains = mockState.domainList.filter(
      (candidate) =>
        candidate !== domain &&
        (mockState.tasksByDomain.get(candidate) || []).length > 0,
    );
    if (otherDomains.length > 0) {
      const targetDomain = pickRandom(otherDomains, rand);
      const domainTasks = mockState.tasksByDomain.get(targetDomain) || [];
      const targetTask = pickRandom(domainTasks, rand);
      if (targetTask) {
        addMockStoreLink(
          taskNode.id,
          targetTask,
          "cross",
          randomIntInclusive(rand, 1, 3),
        );
        addMockStoreLink(domainId, `domain:${targetDomain}`, "cross", 1);
      }
    }

    const nowMs = Date.now();
    mockState.historyStore.push({
      timestamp: new Date(nowMs).toISOString(),
      type: "created",
      node_id: taskNode.id,
      task: taskNode.task,
      domain: taskNode.domain,
      confidence: taskNode.confidence,
      run_count: taskNode.run_count,
    });
    if (mockState.historyStore.length > MOCK_DEMO_CONFIG.maxHistoryEvents) {
      mockState.historyStore.splice(
        0,
        mockState.historyStore.length - MOCK_DEMO_CONFIG.maxHistoryEvents,
      );
    }

    mockState.traceSeq += 1;
    return {
      type: "trace_arrived",
      trace_id: `mock-trace-${mockState.traceSeq}`,
      task: taskNode.task,
      domain: taskNode.domain,
      success: true,
      partial: false,
      step_count: taskNode.step_traces.length,
      timestamp_ms: nowMs,
      signal_source: "demo_mock",
    };
  }

  function clearMockAutoTimer() {
    if (!mockState.autoTimerId) return;
    clearTimeout(mockState.autoTimerId);
    mockState.autoTimerId = null;
  }

  function scheduleMockAutoSim() {
    if (!mockState.autoEnabled) return;

    const rand = mockState.rand || Math.random;
    const delayMs = randomIntInclusive(
      rand,
      MOCK_DEMO_CONFIG.autoSimMinMs,
      MOCK_DEMO_CONFIG.autoSimMaxMs,
    );

    mockState.autoTimerId = setTimeout(async () => {
      mockState.autoTimerId = null;
      if (!mockState.autoEnabled) return;

      const event = createMockTraceArrivalEvent();
      if (event) await handleTraceArrivedEvent(event);
      scheduleMockAutoSim();
    }, delayMs);
  }

  function setMockAutoSimulate(enabled) {
    mockState.autoEnabled = !!enabled;
    clearMockAutoTimer();
    if (mockState.autoEnabled) {
      scheduleMockAutoSim();
    }
  }

  async function fetchGraphPayload() {
    if (mockState.enabled) {
      initializeMockDataset();
      return cloneGraphPayload(mockState.graphStore);
    }

    try {
      const res = await fetch("/api/graph");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn("Live /api/graph unavailable, falling back to demoMock:", err);
      mockState.enabled = true;
      initializeMockDataset();
      return cloneGraphPayload(mockState.graphStore);
    }
  }

  async function fetchHistoryPayload() {
    if (mockState.enabled) {
      initializeMockDataset();
      return cloneHistoryPayload(mockState.historyStore);
    }

    try {
      const res = await fetch("/api/graph/history");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn("Live /api/graph/history unavailable, falling back to demoMock:", err);
      mockState.enabled = true;
      initializeMockDataset();
      return cloneHistoryPayload(mockState.historyStore);
    }
  }

  function getRuntimeDataSource() {
    return mockState.enabled ? "demoMock" : "live";
  }

  function buildDemoSnapshot() {
    if (!mockState.enabled) return null;
    initializeMockDataset();
    if (!mockState.graphStore) return null;

    const taskRows = mockState.graphStore.nodes
      .filter((node) => node.type === "task")
      .map((node) => ({
        task: String(node.task || ""),
        domain: String(node.domain || ""),
        confidence: clamp(Number(node.confidence || 0), 0, 1),
        run_count: Math.max(0, Number(node.run_count || 0)),
        optimal_actions: Array.isArray(node.optimal_actions)
          ? node.optimal_actions.slice(0, 8)
          : [],
      }));

    const domainMap = new Map();
    taskRows.forEach((task) => {
      if (!task.domain) return;
      if (!domainMap.has(task.domain)) {
        domainMap.set(task.domain, {
          domain: task.domain,
          task_count: 0,
          total_runs: 0,
          confidence_sum: 0,
        });
      }
      const rollup = domainMap.get(task.domain);
      rollup.task_count += 1;
      rollup.total_runs += task.run_count;
      rollup.confidence_sum += task.confidence;
    });

    const domains = Array.from(domainMap.values())
      .map((rollup) => ({
        domain: rollup.domain,
        task_count: rollup.task_count,
        total_runs: rollup.total_runs,
        avg_confidence:
          rollup.task_count > 0 ? rollup.confidence_sum / rollup.task_count : 0,
      }))
      .sort((a, b) => b.total_runs - a.total_runs);

    const totalRuns = taskRows.reduce((sum, task) => sum + task.run_count, 0);
    const avgConfidence =
      taskRows.length > 0
        ? taskRows.reduce((sum, task) => sum + task.confidence, 0) /
          taskRows.length
        : 0;

    return {
      tasks: taskRows,
      domains,
      totals: {
        task_count: taskRows.length,
        domain_count: domains.length,
        total_runs: totalRuns,
        avg_confidence: avgConfidence,
      },
      generatedAt: new Date().toISOString(),
    };
  }

  window.__slipstreamGetDataSource = getRuntimeDataSource;
  window.__slipstreamGetAnDemoSnapshot = buildDemoSnapshot;

  let wsConnected = false;

  function setLandingStatus(message, isError) {
    if (!dom.landingStatus) return;
    dom.landingStatus.textContent = message || "";
    dom.landingStatus.style.color = isError ? "#cc7d7d" : "";
  }

  function setSceneUiEnabled(enabled) {
    const interactiveControls = [
      dom.btnSimulate,
      dom.btnReplayGrowth,
      dom.btnCinematic,
      dom.chkAuto,
      dom.timelineSlider,
      dom.timelinePlay,
    ];
    interactiveControls.forEach((el) => {
      if (!el) return;
      el.disabled = !enabled;
    });

    if (dom.graph) {
      dom.graph.style.pointerEvents = enabled ? "auto" : "none";
    }
  }

  function fadeOutLandingOverlay() {
    if (!dom.landingOverlay) {
      introGateState.phase = "running";
      document.body.classList.remove("scene-ready");
      document.body.classList.add("scene-running");
      return;
    }

    dom.landingOverlay.classList.add("landing-fade-out");
    window.setTimeout(() => {
      if (dom.landingOverlay && dom.landingOverlay.parentNode) {
        dom.landingOverlay.parentNode.removeChild(dom.landingOverlay);
      }
      introGateState.phase = "running";
      document.body.classList.remove("scene-ready");
      document.body.classList.add("scene-running");
    }, INTRO_GATE_CONFIG.fadeOutMs);
  }

  function primeScenePaused() {
    if (introGateState.prewarmPromise) return introGateState.prewarmPromise;

    introGateState.phase = "prewarming";
    introGateState.error = null;
    setLandingStatus("Staging network...");

    introGateState.prewarmPromise = loadGraph()
      .then(() => {
        if (!mockState.enabled && !wsConnected) {
          connectWS();
          wsConnected = true;
        }
        introGateState.phase = "ready";
        setLandingStatus("Network staged. Initialize when ready.");
      })
      .catch((err) => {
        introGateState.prewarmPromise = null;
        introGateState.phase = "failed";
        introGateState.error =
          err && err.message ? String(err.message) : "Graph prewarm failed";
        setLandingStatus("Network staging failed. Retry initialization.", true);
        throw err;
      });

    return introGateState.prewarmPromise;
  }

  async function startIntroFromLanding() {
    if (
      introGateState.phase === "fading" ||
      introGateState.phase === "running"
    ) {
      return;
    }

    // Reset state for retries
    introGateState.started = true;
    introGateState.phase = "landing";
    introGateState.prewarmPromise = null;
    introGateState.error = null;

    if (dom.landingCta) {
      dom.landingCta.disabled = true;
      dom.landingCta.textContent = "Initializing...";
    }
    setLandingStatus("Initializing cinematic sequence...");

    try {
      await primeScenePaused();
    } catch (err) {
      introGateState.started = false;
      if (dom.landingCta) {
        dom.landingCta.disabled = false;
        dom.landingCta.textContent = "Retry Initialize";
      }
      console.error("Landing initialization failed:", err);
      return;
    }

    introGateState.phase = "fading";
    document.body.classList.remove("scene-paused");
    document.body.classList.add("scene-ready");
    setSceneUiEnabled(true);

    setCinematicEnabled(true);
    startCameraIntro();
    requestAnimationFrame(() => {
      startReplayGrowth();
    });

    fadeOutLandingOverlay();
  }

  // ---- Derived metrics and graph-state enrichment ----
  function computeDerivedMetrics() {
    nodeById = new Map();
    linkById = new Map();
    adjacencyByNode = new Map();
    incidentLinksByNode = new Map();

    const tasks = graphData.nodes.filter((n) => n.type === "task");
    const domains = graphData.nodes.filter((n) => n.type === "domain");

    maxRunCount = Math.max(1, ...tasks.map((n) => n.run_count || 0));
    maxDomainRuns = Math.max(1, ...domains.map((n) => n.total_runs || 0));

    graphData.nodes.forEach((node) => {
      const runCount =
        node.type === "domain" ? node.total_runs : node.run_count;
      const conf =
        node.type === "domain"
          ? node.avg_confidence || 0
          : node.confidence || 0;
      const activity =
        node.type === "domain"
          ? activityFromRuns(runCount || 0, maxDomainRuns)
          : activityFromRuns(runCount || 0, maxRunCount);

      node.__activityNormalized = activity;
      node.__confidenceSignal = clamp(conf, 0, 1);
      node.__routeReliability = clamp(
        0.7 * node.__confidenceSignal + 0.3 * activity,
        0,
        1,
      );
      node.__pulsePhase = (hashString(String(node.id)) % 1000) / 160;
      if (node.__timelineVisible === undefined) node.__timelineVisible = true;
      if (node.__replayVisible === undefined) node.__replayVisible = true;
      node.__visible =
        node.__timelineVisible !== false && node.__replayVisible !== false;
      adjacencyByNode.set(node.id, new Set());
      incidentLinksByNode.set(node.id, new Set());
      nodeById.set(node.id, node);
    });

    const duplicateLinkCounter = new Map();
    const batchCount = Math.max(1, VISUAL_CONFIG.particles.batchCount);

    graphData.links.forEach((link) => {
      const sourceId = safeNodeId(link.source);
      const targetId = safeNodeId(link.target);
      const sourceNode = nodeById.get(sourceId);
      const targetNode = nodeById.get(targetId);
      const pairKey = normalizeLinkPair(sourceId, targetId);
      const typeKey = link.type || "edge";
      const dupKey = `${typeKey}:${pairKey}`;
      const serial = duplicateLinkCounter.get(dupKey) || 0;
      duplicateLinkCounter.set(dupKey, serial + 1);
      link.__id = `${dupKey}:${serial}`;
      if (link.__timelineVisible === undefined) link.__timelineVisible = true;
      if (link.__replayVisible === undefined) link.__replayVisible = true;
      if (link.__flyInVisible === undefined) link.__flyInVisible = true;
      if (link.__flyInFadeStartMs === undefined) link.__flyInFadeStartMs = null;

      const sourceReliability = sourceNode
        ? sourceNode.__routeReliability
        : 0.5;
      const targetReliability = targetNode
        ? targetNode.__routeReliability
        : 0.5;
      const sourceActivity = sourceNode ? sourceNode.__activityNormalized : 0.4;
      const targetActivity = targetNode ? targetNode.__activityNormalized : 0.4;

      const confidenceSignal = clamp(
        (sourceReliability + targetReliability) / 2,
        0,
        1,
      );
      const activitySignal = clamp((sourceActivity + targetActivity) / 2, 0, 1);
      let routeStrength = clamp(
        0.7 * confidenceSignal + 0.3 * activitySignal,
        0,
        1,
      );

      if (link.type === "cross") {
        const strengthNorm = clamp((link.strength || 1) / 5, 0, 1);
        routeStrength = clamp(routeStrength * 0.75 + strengthNorm * 0.25, 0, 1);
      }

      link.__routeStrength = routeStrength;
      link.__particleWeight = clamp(
        routeStrength * 0.55 + activitySignal * 0.45,
        0,
        1,
      );
      link.__particleBucket = hashString(link.__id) % batchCount;

      if (sourceNode && targetNode) {
        adjacencyByNode.get(sourceId).add(targetId);
        adjacencyByNode.get(targetId).add(sourceId);
        incidentLinksByNode.get(sourceId).add(link.__id);
        incidentLinksByNode.get(targetId).add(link.__id);
      }

      link.__visible =
        link.__timelineVisible !== false &&
        link.__replayVisible !== false &&
        link.__flyInVisible !== false &&
        sourceNode?.__visible !== false &&
        targetNode?.__visible !== false;

      linkById.set(link.__id, link);
    });

    particleBudgetState.dirty = true;
  }

  function refreshLinkAccessors() {
    if (!graph) return;
    if (typeof graph.linkColor !== "function") return;
    if (typeof graph.linkWidth !== "function") return;
    if (typeof graph.linkDirectionalParticles !== "function") return;
    if (typeof graph.linkDirectionalParticleSpeed !== "function") return;

    graph
      .linkColor(linkColor)
      .linkWidth(linkWidth)
      .linkDirectionalParticles(linkParticles)
      .linkDirectionalParticleSpeed(linkParticleSpeed);
  }

  function clearPendingHoverIntent() {
    if (hoverState.pendingTimerId) {
      clearTimeout(hoverState.pendingTimerId);
      hoverState.pendingTimerId = null;
    }
    hoverState.pendingNodeId = null;
  }

  function setHoverFocus(node) {
    if (!node || node.__visible === false) {
      if (!hoverState.activeNodeId) return;
      hoverState.activeNodeId = null;
      hoverState.activeNodeIds = new Set();
      hoverState.activeLinkIds = new Set();
      cameraState.hoveredNodeId = null;
      refreshLinkAccessors();
      scheduleLabelUpdate();
      return;
    }

    const nodeId = node.id;
    if (hoverState.activeNodeId === nodeId) return;
    const activeNodeIds = new Set([nodeId]);
    const neighbors = adjacencyByNode.get(nodeId) || new Set();
    neighbors.forEach((id) => activeNodeIds.add(id));

    hoverState.activeNodeId = nodeId;
    hoverState.activeNodeIds = activeNodeIds;
    hoverState.activeLinkIds = new Set(incidentLinksByNode.get(nodeId) || []);
    cameraState.hoveredNodeId = nodeId;
    refreshLinkAccessors();
    scheduleLabelUpdate();
  }

  function handleHoverIntent(node) {
    if (!node || node.__visible === false) {
      clearPendingHoverIntent();
      setHoverFocus(null);
      return;
    }

    const nodeId = node.id;
    if (hoverState.activeNodeId === nodeId) {
      clearPendingHoverIntent();
      return;
    }

    if (hoverState.pendingNodeId === nodeId) return;

    clearPendingHoverIntent();
    hoverState.pendingNodeId = nodeId;

    hoverState.pendingTimerId = setTimeout(() => {
      const pendingId = hoverState.pendingNodeId;
      hoverState.pendingTimerId = null;
      hoverState.pendingNodeId = null;

      if (!pendingId) return;
      const pendingNode = nodeById.get(pendingId);
      if (!pendingNode || pendingNode.__visible === false) return;
      setHoverFocus(pendingNode);
    }, VISUAL_CONFIG.hover.delayMs);
  }

  function replayRevealProgress(nowMs, revealMs, easeWindowMs) {
    if (!replayState.active) return 1;
    if (!Number.isFinite(revealMs)) return 1;
    const elapsed = nowMs - replayState.startMs;
    const raw = (elapsed - revealMs) / Math.max(1, easeWindowMs);
    return clamp(raw, 0, 1);
  }

  function replayNodeProgress(node, nowMs) {
    if (!replayState.active) return 1;
    const revealMs = replayState.nodeRevealMsById.get(node.id);
    return easeOutCubic(
      replayRevealProgress(nowMs, revealMs, VISUAL_CONFIG.replay.nodeEaseMs),
    );
  }

  function replayLinkProgress(link, nowMs) {
    if (!replayState.active) return 1;
    const revealMs = replayState.linkRevealMsById.get(link.__id);
    return easeOutCubic(
      replayRevealProgress(nowMs, revealMs, VISUAL_CONFIG.replay.linkEaseMs),
    );
  }

  function isNodeVisibleByComposite(node) {
    return node.__timelineVisible !== false && node.__replayVisible !== false;
  }

  function isLinkVisibleByComposite(link) {
    if (link.__timelineVisible === false || link.__replayVisible === false)
      return false;
    if (link.__flyInVisible === false) return false;

    const source = nodeById.get(safeNodeId(link.source));
    const target = nodeById.get(safeNodeId(link.target));
    return source?.__visible !== false && target?.__visible !== false;
  }

  function applyCompositeVisibility() {
    graphData.nodes.forEach((node) => {
      node.__visible = isNodeVisibleByComposite(node);
      if (node.__threeObj) {
        node.__threeObj.visible = node.__visible !== false;
      }
    });

    graphData.links.forEach((link) => {
      link.__visible = isLinkVisibleByComposite(link);
    });

    if (
      graph &&
      typeof graph.nodeVisibility === "function" &&
      typeof graph.linkVisibility === "function"
    ) {
      graph
        .nodeVisibility((node) => node.__visible !== false)
        .linkVisibility((link) => link.__visible !== false);
    }

    if (hoverState.activeNodeId) {
      const hovered = nodeById.get(hoverState.activeNodeId);
      if (!hovered || hovered.__visible === false) {
        clearPendingHoverIntent();
        setHoverFocus(null);
      }
    }

    particleBudgetState.dirty = true;
    updateParticleBudget(true);
    refreshLinkAccessors();
    scheduleLabelUpdate();
  }

  function setReplayControlsLocked(locked) {
    if (dom.timelineSlider) dom.timelineSlider.disabled = locked;
    if (dom.timelinePlay) dom.timelinePlay.disabled = locked;
    if (dom.btnSimulate && !locked) {
      dom.btnSimulate.textContent = "Simulate Agent Run";
    }
    if (dom.btnSimulate) dom.btnSimulate.disabled = locked;
    if (dom.btnReplayGrowth) {
      dom.btnReplayGrowth.disabled = locked;
      dom.btnReplayGrowth.classList.toggle("is-replaying", locked);
      dom.btnReplayGrowth.textContent = locked
        ? "Replaying..."
        : "Replay Growth";
    }

    if (!locked) {
      syncReplayButtonAvailability();
    }
  }

  function syncReplayButtonAvailability() {
    if (!dom.btnReplayGrowth || replayState.active) return;
    dom.btnReplayGrowth.disabled = !!flyInState.active;
  }

  function pickReplayHubNode() {
    let bestNode = null;
    let bestDegree = -1;

    graphData.nodes.forEach((node) => {
      const degree = adjacencyByNode.get(node.id)?.size || 0;
      const preferDomain = node.type === "domain" ? 0.2 : 0;
      const score = degree + preferDomain;
      if (score > bestDegree) {
        bestDegree = score;
        bestNode = node;
      }
    });

    return bestNode || graphData.nodes[0] || null;
  }

  function buildReplaySchedule() {
    const hub = pickReplayHubNode();
    if (!hub)
      return { nodeRevealMsById: new Map(), linkRevealMsById: new Map() };

    // Demo replay is intentionally synthetic (not history timestamps):
    // reveal nodes in deterministic radial rings from the most connected hub.
    const distances = new Map();
    const queue = [hub.id];
    distances.set(hub.id, 0);

    while (queue.length) {
      const currentId = queue.shift();
      const currentDist = distances.get(currentId) || 0;
      const neighbors = adjacencyByNode.get(currentId) || new Set();

      neighbors.forEach((nextId) => {
        if (distances.has(nextId)) return;
        distances.set(nextId, currentDist + 1);
        queue.push(nextId);
      });
    }

    const maxKnownDist = Math.max(
      1,
      ...Array.from(distances.values(), (v) => v || 1),
    );
    const maxNodeRevealMs = Math.max(
      280,
      replayState.durationMs -
        VISUAL_CONFIG.replay.nodeEaseMs -
        VISUAL_CONFIG.replay.edgeLagMs -
        40,
    );
    const maxLinkRevealMs = Math.max(
      320,
      replayState.durationMs - VISUAL_CONFIG.replay.linkEaseMs,
    );
    const ringCount = Math.max(1, VISUAL_CONFIG.replay.ringCount);
    const nodeRevealMsById = new Map();
    graphData.nodes.forEach((node) => {
      const rawDist = distances.has(node.id)
        ? distances.get(node.id)
        : maxKnownDist + 1 + (hashString(`island:${node.id}`) % 3);
      const ringProgress = rawDist / (maxKnownDist + 2);
      const ringIndex = Math.min(
        ringCount - 1,
        Math.floor(ringProgress * ringCount),
      );
      const baseMs = (ringIndex / Math.max(1, ringCount - 1)) * maxNodeRevealMs;
      const jitter =
        hashString(`replay:${node.id}`) % VISUAL_CONFIG.replay.ringJitterMs;
      const revealMs = clamp(baseMs + jitter, 0, maxNodeRevealMs);
      nodeRevealMsById.set(node.id, revealMs);
    });

    const linkRevealMsById = new Map();
    graphData.links.forEach((link) => {
      const sourceId = safeNodeId(link.source);
      const targetId = safeNodeId(link.target);
      const sourceMs = nodeRevealMsById.get(sourceId) || 0;
      const targetMs = nodeRevealMsById.get(targetId) || 0;
      const revealMs = clamp(
        Math.max(sourceMs, targetMs) + VISUAL_CONFIG.replay.edgeLagMs,
        0,
        maxLinkRevealMs,
      );
      linkRevealMsById.set(link.__id, revealMs);
    });

    return { nodeRevealMsById, linkRevealMsById };
  }

  function finishReplayGrowth() {
    replayState.active = false;
    replayState.nodeRevealMsById = new Map();
    replayState.linkRevealMsById = new Map();
    replayState.nowMs = performance.now();

    graphData.nodes.forEach((node) => {
      node.__replayVisible = true;
    });
    graphData.links.forEach((link) => {
      link.__replayVisible = true;
    });

    setReplayControlsLocked(false);
    applyCompositeVisibility();

    if (replayState.queuedRefresh) {
      replayState.queuedRefresh = false;
      refreshGraph();
    }
  }

  function startReplayGrowth() {
    if (
      !graph ||
      replayState.active ||
      flyInState.active ||
      !graphData.nodes.length
    )
      return;

    if (isPlaying) togglePlay();

    currentTimeValue = 1000;
    dom.timelineSlider.value = 1000;
    updateTimelineLabel(1000);
    applyTimeFilter(1000);
    clearPendingHoverIntent();
    setHoverFocus(null);

    const { nodeRevealMsById, linkRevealMsById } = buildReplaySchedule();
    if (!nodeRevealMsById.size) return;

    replayState.active = true;
    replayState.startMs = performance.now();
    replayState.nowMs = replayState.startMs;
    replayState.nodeRevealMsById = nodeRevealMsById;
    replayState.linkRevealMsById = linkRevealMsById;
    replayState.queuedRefresh = false;
    setReplayControlsLocked(true);

    graphData.nodes.forEach((node) => {
      node.__replayVisible = true;
    });
    graphData.links.forEach((link) => {
      link.__replayVisible = true;
    });
    applyCompositeVisibility();
    refreshLinkAccessors();
    scheduleLabelUpdate();
  }

  function flyInLinkProgress(link, nowMs) {
    if (!link) return 1;
    if (link.__flyInVisible === false) return 0;
    if (!Number.isFinite(link.__flyInFadeStartMs)) return 1;
    const progress = clamp(
      (nowMs - link.__flyInFadeStartMs) / VISUAL_CONFIG.flyIn.edgeFadeMs,
      0,
      1,
    );
    return easeOutCubic(progress);
  }

  function resolveFlyInTarget(node) {
    if (
      Number.isFinite(node.x) &&
      Number.isFinite(node.y) &&
      Number.isFinite(node.z)
    ) {
      return new THREE.Vector3(node.x, node.y, node.z);
    }

    const domainNode = graphData.nodes.find(
      (candidate) =>
        candidate.type === "domain" && candidate.domain === node.domain,
    );
    if (
      domainNode &&
      Number.isFinite(domainNode.x) &&
      Number.isFinite(domainNode.y) &&
      Number.isFinite(domainNode.z)
    ) {
      return new THREE.Vector3(
        domainNode.x + (Math.random() - 0.5) * 26,
        domainNode.y + (Math.random() - 0.5) * 22,
        domainNode.z + (Math.random() - 0.5) * 26,
      );
    }

    const { center } = estimateGraphCenterAndRadius();
    return center.clone();
  }

  function enqueueIncomingNode(nodeId) {
    if (!nodeId) return;
    if (flyInState.active?.nodeId === nodeId) return;
    if (flyInState.queuedNodeIds.has(nodeId)) return;

    if (flyInState.queue.length >= VISUAL_CONFIG.flyIn.queueMax) {
      const dropped = flyInState.queue.shift();
      if (dropped) flyInState.queuedNodeIds.delete(dropped.nodeId);
    }

    flyInState.queue.push({ nodeId });
    flyInState.queuedNodeIds.add(nodeId);
    syncReplayButtonAvailability();
  }

  function beginNextFlyIn(nowMs) {
    if (flyInState.active || replayState.active) return;

    while (flyInState.queue.length) {
      const next = flyInState.queue.shift();
      if (!next) return;
      flyInState.queuedNodeIds.delete(next.nodeId);

      const node = nodeById.get(next.nodeId);
      if (!node || node.__visible === false) continue;

      const target = resolveFlyInTarget(node);
      const source = target.clone();
      source.y += VISUAL_CONFIG.flyIn.spawnYOffset;

      node.x = source.x;
      node.y = source.y;
      node.z = source.z;
      node.fx = source.x;
      node.fy = source.y;
      node.fz = source.z;
      node.__incomingGlowUntilMs =
        nowMs + VISUAL_CONFIG.flyIn.durationMs + VISUAL_CONFIG.flyIn.glowHoldMs;

      const linkIds = new Set(incidentLinksByNode.get(node.id) || []);
      linkIds.forEach((linkId) => {
        const link = linkById.get(linkId);
        if (!link) return;
        link.__flyInVisible = false;
        link.__flyInFadeStartMs = null;
      });

      flyInState.active = {
        nodeId: node.id,
        source,
        target,
        linkIds,
        startMs: nowMs,
        durationMs: VISUAL_CONFIG.flyIn.durationMs,
        edgeRevealStarted: false,
      };
      applyCompositeVisibility();
      syncReplayButtonAvailability();
      return;
    }

    syncReplayButtonAvailability();
  }

  function updateFlyInAnimation(nowMs) {
    if (!graph) return;
    if (!flyInState.active) {
      beginNextFlyIn(nowMs);
      return;
    }

    const active = flyInState.active;
    const node = nodeById.get(active.nodeId);
    if (!node) {
      flyInState.active = null;
      syncReplayButtonAvailability();
      return;
    }

    const progress = clamp((nowMs - active.startMs) / active.durationMs, 0, 1);
    const eased = easeInOutCubic(progress);
    const x = lerp(active.source.x, active.target.x, eased);
    const y = lerp(active.source.y, active.target.y, eased);
    const z = lerp(active.source.z, active.target.z, eased);

    node.x = x;
    node.y = y;
    node.z = z;
    node.fx = x;
    node.fy = y;
    node.fz = z;

    const dx = active.target.x - x;
    const dy = active.target.y - y;
    const dz = active.target.z - z;
    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

    if (
      !active.edgeRevealStarted &&
      (dist <= VISUAL_CONFIG.flyIn.edgeRevealDistance || progress >= 0.88)
    ) {
      active.edgeRevealStarted = true;
      active.linkIds.forEach((linkId) => {
        const link = linkById.get(linkId);
        if (!link) return;
        link.__flyInVisible = true;
        link.__flyInFadeStartMs = nowMs;
      });
      applyCompositeVisibility();
    }

    if (progress < 1) return;

    node.fx = null;
    node.fy = null;
    node.fz = null;
    node.__incomingGlowUntilMs = nowMs + VISUAL_CONFIG.flyIn.glowHoldMs;

    active.linkIds.forEach((linkId) => {
      const link = linkById.get(linkId);
      if (!link) return;
      if (link.__flyInVisible === false) {
        link.__flyInVisible = true;
      }
      if (!Number.isFinite(link.__flyInFadeStartMs)) {
        link.__flyInFadeStartMs = nowMs;
      }
    });

    flyInState.active = null;
    refreshLinkAccessors();
    applyCompositeVisibility();
    syncReplayButtonAvailability();
    beginNextFlyIn(nowMs + VISUAL_CONFIG.flyIn.replayLockBufferMs);

    if (flyInState.queuedRefresh) {
      flyInState.queuedRefresh = false;
      refreshGraphWithDiff().then((result) => {
        flushPendingTraceEvents(result);
      });
    }
  }

  function updateParticleBudget(force) {
    const nowMs = performance.now();
    if (
      !force &&
      !particleBudgetState.dirty &&
      nowMs < particleBudgetState.nextEpochTs
    )
      return;

    particleBudgetState.dirty = false;
    particleBudgetState.nextEpochTs = nowMs + VISUAL_CONFIG.particles.epochMs;
    particleBudgetState.epochIndex =
      (particleBudgetState.epochIndex + 1) %
      Math.max(1, VISUAL_CONFIG.particles.batchCount);

    // Optimization: apply a hard global cap + rotating link buckets to keep traffic feel
    // while preventing per-link particle overdraw from collapsing frame rate.
    const normalizedBudget = clamp(
      (performanceState.particleFactor -
        VISUAL_CONFIG.performance.floorFactor) /
        (1 - VISUAL_CONFIG.performance.floorFactor),
      0,
      1,
    );
    const cap = Math.max(
      1,
      Math.round(
        lerp(
          VISUAL_CONFIG.particles.hardCapMin,
          VISUAL_CONFIG.particles.hardCapMax,
          normalizedBudget,
        ),
      ),
    );

    const candidates = graphData.links
      .filter(
        (link) =>
          link.__visible !== false &&
          (link.__routeStrength || 0) >= VISUAL_CONFIG.particles.minStrength &&
          link.__particleBucket === particleBudgetState.epochIndex,
      )
      .sort((a, b) => (b.__particleWeight || 0) - (a.__particleWeight || 0));

    particleBudgetState.activeLinkIds = new Set(
      candidates.slice(0, cap).map((link) => link.__id),
    );
  }

  // ---- Node rendering ----
  function buildLabelSprite(node, size) {
    const rawLabel = node.type === "domain" ? node.domain : node.task;
    if (!rawLabel) return null;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    const fontSize = node.type === "domain" ? 44 : 24;

    canvas.width = 768;
    canvas.height = 96;

    ctx.font = `700 ${fontSize}px 'Orbitron', sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = node.type === "domain" ? "#FFFFFF" : "#A0A0A0";
    ctx.fillText(rawLabel.toUpperCase(), canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;

    const material = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      opacity:
        node.type === "domain"
          ? VISUAL_CONFIG.labels.domainOpacity
          : VISUAL_CONFIG.labels.taskOpacity,
      depthTest: false,
      depthWrite: false,
    });

    const sprite = new THREE.Sprite(material);
    const scale = node.type === "domain" ? 30 : 16;
    sprite.scale.set(scale, scale * (canvas.height / canvas.width), 1);
    sprite.position.y = size + (node.type === "domain" ? 7 : 3.5);
    sprite.visible = node.type === "domain";
    sprite.userData = {
      isLabel: true,
      nodeId: node.id,
      isDomain: node.type === "domain",
    };

    return sprite;
  }

  function buildNodeObject(node) {
    const group = new THREE.Group();

    const activity = node.__activityNormalized || 0;
    const confidence =
      node.type === "domain" ? node.avg_confidence || 0 : node.confidence || 0;
    const colorHex = confidenceHex(confidence);

    const size =
      node.type === "domain" ? 6.2 + activity * 1.8 : 1.85 + activity * 2.4;

    const geometry =
      node.type === "domain"
        ? new THREE.SphereGeometry(size, 16, 12)
        : new THREE.SphereGeometry(size, 10, 8);

    let coreMaterial = null;

    if (node.type === "domain") {
      const wireGeo = new THREE.EdgesGeometry(geometry);
      const wireMat = new THREE.LineBasicMaterial({
        color: 0xc1c1c1,
        transparent: true,
        opacity: 0.72,
      });
      const wire = new THREE.LineSegments(wireGeo, wireMat);
      group.add(wire);

      coreMaterial = new THREE.MeshBasicMaterial({
        color: 0xf0f0f0,
        transparent: true,
        opacity: 0.12,
      });
      const fill = new THREE.Mesh(geometry, coreMaterial);
      group.add(fill);
    } else {
      coreMaterial = new THREE.MeshBasicMaterial({
        color: colorHex,
        transparent: true,
        opacity: 0.78 + activity * 0.14,
      });
      const mesh = new THREE.Mesh(geometry, coreMaterial);
      group.add(mesh);
    }

    const innerGlowMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.1 + activity * 0.04,
      side: THREE.BackSide,
    });
    const innerGlow = new THREE.Mesh(
      new THREE.SphereGeometry(size * 1.16, 12, 8),
      innerGlowMaterial,
    );
    group.add(innerGlow);

    const outerGlowMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.045 + activity * 0.02,
      side: THREE.BackSide,
    });
    const outerGlow = new THREE.Mesh(
      new THREE.SphereGeometry(size * 1.62, 12, 8),
      outerGlowMaterial,
    );
    group.add(outerGlow);

    const labelSprite = buildLabelSprite(node, size);
    if (labelSprite) {
      group.add(labelSprite);
    }

    group.userData = {
      nodeId: node.id,
      nodeType: node.type,
      pulsePhase: node.__pulsePhase || 0,
      baseCoreOpacity: coreMaterial ? coreMaterial.opacity : 0.8,
      baseCoreColor:
        coreMaterial && coreMaterial.color ? coreMaterial.color.clone() : null,
      baseInnerOpacity: innerGlowMaterial.opacity,
      baseOuterOpacity: outerGlowMaterial.opacity,
      coreMaterial,
      innerGlowMaterial,
      outerGlowMaterial,
      labelSprite,
    };

    node.__threeObj = group;
    return group;
  }

  function linkColor(link) {
    if (!link) return "rgba(140, 145, 152, 0.1)";
    const replayProgress = replayLinkProgress(link, replayState.nowMs);
    const flyProgress = flyInLinkProgress(link, replayState.nowMs);
    if (replayProgress <= 0.001 || flyProgress <= 0.001)
      return "rgba(140, 145, 152, 0)";
    const strength = clamp(link.__routeStrength || 0.45, 0, 1);
    const hoverActive = !!hoverState.activeNodeId;
    const inFocus = !hoverActive || hoverState.activeLinkIds.has(link.__id);

    if (link.type === "cross") {
      let alpha =
        VISUAL_CONFIG.links.crossBaseAlpha +
        strength * VISUAL_CONFIG.links.crossAlphaScale;
      if (hoverActive && !inFocus) {
        alpha = VISUAL_CONFIG.hover.nonFocusLinkAlpha;
      } else if (hoverActive && inFocus) {
        alpha = clamp(alpha + VISUAL_CONFIG.hover.focusLinkAlphaBoost, 0, 0.95);
      }
      alpha *= replayProgress * flyProgress;
      return `rgba(176, 184, 194, ${alpha.toFixed(2)})`;
    }

    let alpha =
      VISUAL_CONFIG.links.hubBaseAlpha +
      strength * VISUAL_CONFIG.links.hubAlphaScale;
    if (hoverActive && !inFocus) {
      alpha = VISUAL_CONFIG.hover.nonFocusLinkAlpha;
    } else if (hoverActive && inFocus) {
      alpha = clamp(alpha + VISUAL_CONFIG.hover.focusLinkAlphaBoost, 0, 0.95);
    }
    alpha *= replayProgress * flyProgress;
    return `rgba(140, 145, 152, ${alpha.toFixed(2)})`;
  }

  function linkWidth(link) {
    if (!link) return VISUAL_CONFIG.links.hubBaseWidth;
    const replayProgress = replayLinkProgress(link, replayState.nowMs);
    const flyProgress = flyInLinkProgress(link, replayState.nowMs);
    if (replayProgress <= 0.001 || flyProgress <= 0.001) return 0;
    const strength = clamp(link.__routeStrength || 0.45, 0, 1);
    const hoverActive = !!hoverState.activeNodeId;
    const inFocus = !hoverActive || hoverState.activeLinkIds.has(link.__id);
    let width =
      link.type === "cross"
        ? VISUAL_CONFIG.links.crossBaseWidth +
          strength * VISUAL_CONFIG.links.crossWidthScale
        : VISUAL_CONFIG.links.hubBaseWidth +
          strength * VISUAL_CONFIG.links.hubWidthScale;

    if (hoverActive && !inFocus) {
      width *= VISUAL_CONFIG.hover.nonFocusLinkWidthFactor;
    } else if (hoverActive && inFocus) {
      width *= VISUAL_CONFIG.hover.focusLinkWidthBoost;
    }

    return width * replayProgress * flyProgress;
  }

  function linkParticles(link) {
    if (!link) return 0;
    if (link.__visible === false) return 0;
    if (flyInLinkProgress(link, replayState.nowMs) < 0.82) return 0;
    if (
      replayState.active &&
      replayLinkProgress(link, replayState.nowMs) < 0.78
    )
      return 0;
    // Optimization: render at most one particle per selected link.
    // Global caps are handled in updateParticleBudget() to keep frame time stable.
    if (!particleBudgetState.activeLinkIds.has(link.__id)) return 0;
    if (hoverState.activeNodeId && !hoverState.activeLinkIds.has(link.__id))
      return 0;
    return 1;
  }

  function linkParticleSpeed(link) {
    if (!link) return VISUAL_CONFIG.particles.baseSpeed;
    const strength = clamp(link.__routeStrength || 0.45, 0, 1);
    return (
      VISUAL_CONFIG.particles.baseSpeed +
      strength * VISUAL_CONFIG.particles.speedScale
    );
  }

  // ---- Scene layers: ambient and bursts ----
  function disposeLayerObject(obj) {
    if (!obj) return;
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) {
      if (Array.isArray(obj.material)) {
        obj.material.forEach((m) => m.dispose());
      } else {
        obj.material.dispose();
      }
    }
  }

  function clearAmbientLayer() {
    const scene = graph ? graph.scene() : null;
    if (!scene) return;

    if (sceneLayers.ambientPoints) {
      scene.remove(sceneLayers.ambientPoints);
      disposeLayerObject(sceneLayers.ambientPoints);
      sceneLayers.ambientPoints = null;
    }

    if (sceneLayers.ambientLinks) {
      scene.remove(sceneLayers.ambientLinks);
      disposeLayerObject(sceneLayers.ambientLinks);
      sceneLayers.ambientLinks = null;
    }
  }

  function getDomainAnchors() {
    const domains = graphData.nodes.filter((n) => n.type === "domain");
    const fallbackRadius = VISUAL_CONFIG.ambient.fallbackRadius;

    return domains.map((domain, idx) => {
      const x = Number.isFinite(domain.x)
        ? domain.x
        : Math.cos((idx / Math.max(1, domains.length)) * Math.PI * 2) *
          fallbackRadius;
      const y = Number.isFinite(domain.y) ? domain.y : ((idx % 5) - 2) * 35;
      const z = Number.isFinite(domain.z)
        ? domain.z
        : Math.sin((idx / Math.max(1, domains.length)) * Math.PI * 2) *
          fallbackRadius;

      return {
        id: domain.id,
        activity: domain.__activityNormalized || 0.4,
        x,
        y,
        z,
      };
    });
  }

  function rebuildAmbientLayer() {
    if (!graph) return;

    const scene = graph.scene();
    if (!scene) return;

    clearAmbientLayer();

    const anchors = getDomainAnchors();
    if (!anchors.length) return;

    const pointCount = VISUAL_CONFIG.ambient.pointsCount;
    const linkCount = VISUAL_CONFIG.ambient.linksCount;

    const pointPositions = new Float32Array(pointCount * 3);
    const anchorPerPoint = new Uint16Array(pointCount);

    for (let i = 0; i < pointCount; i += 1) {
      const anchor = anchors[i % anchors.length];
      const random = mulberry32(hashString(`${anchor.id}:p:${i}`));
      const spread =
        VISUAL_CONFIG.ambient.clusterSpread * (0.68 + random() * 0.86);

      const theta = random() * Math.PI * 2;
      const phi = Math.acos(random() * 2 - 1);
      const radius = spread * Math.pow(random(), 0.55);

      const x = anchor.x + radius * Math.sin(phi) * Math.cos(theta);
      const y = anchor.y + radius * Math.cos(phi) * 0.65;
      const z = anchor.z + radius * Math.sin(phi) * Math.sin(theta);

      pointPositions[i * 3 + 0] = x;
      pointPositions[i * 3 + 1] = y;
      pointPositions[i * 3 + 2] = z;
      anchorPerPoint[i] = i % anchors.length;
    }

    const linkPositions = new Float32Array(linkCount * 6);

    for (let i = 0; i < linkCount; i += 1) {
      const random = mulberry32(hashString(`l:${i}:${anchors.length}`));
      const a = Math.floor(random() * pointCount);

      let b = Math.floor(random() * pointCount);
      if (random() < 0.82) {
        // Keep most ambient links local to a cluster.
        for (let attempt = 0; attempt < 8; attempt += 1) {
          const candidate = Math.floor(random() * pointCount);
          if (anchorPerPoint[candidate] === anchorPerPoint[a]) {
            b = candidate;
            break;
          }
        }
      }

      const a3 = a * 3;
      const b3 = b * 3;
      const i6 = i * 6;

      linkPositions[i6 + 0] = pointPositions[a3 + 0];
      linkPositions[i6 + 1] = pointPositions[a3 + 1];
      linkPositions[i6 + 2] = pointPositions[a3 + 2];
      linkPositions[i6 + 3] = pointPositions[b3 + 0];
      linkPositions[i6 + 4] = pointPositions[b3 + 1];
      linkPositions[i6 + 5] = pointPositions[b3 + 2];
    }

    const pointGeometry = new THREE.BufferGeometry();
    pointGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(pointPositions, 3),
    );

    const pointMaterial = new THREE.PointsMaterial({
      color: VISUAL_CONFIG.ambient.pointColor,
      size: VISUAL_CONFIG.ambient.pointSize,
      sizeAttenuation: true,
      transparent: true,
      opacity:
        VISUAL_CONFIG.ambient.pointOpacity *
        performanceState.ambientOpacityFactor,
      depthWrite: false,
    });

    const points = new THREE.Points(pointGeometry, pointMaterial);
    scene.add(points);
    sceneLayers.ambientPoints = points;

    const linkGeometry = new THREE.BufferGeometry();
    linkGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(linkPositions, 3),
    );

    const lineMaterial = new THREE.LineBasicMaterial({
      color: VISUAL_CONFIG.ambient.linkColor,
      transparent: true,
      opacity:
        VISUAL_CONFIG.ambient.linkOpacity *
        performanceState.ambientOpacityFactor,
      depthWrite: false,
    });

    const lines = new THREE.LineSegments(linkGeometry, lineMaterial);
    scene.add(lines);
    sceneLayers.ambientLinks = lines;
  }

  function scheduleAmbientRebuild(delayMs) {
    if (sceneLayers.ambientTimer) {
      clearTimeout(sceneLayers.ambientTimer);
    }

    sceneLayers.ambientTimer = setTimeout(() => {
      rebuildAmbientLayer();
    }, delayMs);
  }

  function ensureEventBurstLayer() {
    if (!graph) return;
    if (sceneLayers.eventBurstLayer) return;

    sceneLayers.eventBurstLayer = new THREE.Group();
    graph.scene().add(sceneLayers.eventBurstLayer);
  }

  function spawnBurstAtNode(node) {
    if (!graph || !sceneLayers.eventBurstLayer || !node) return;
    if (
      !Number.isFinite(node.x) ||
      !Number.isFinite(node.y) ||
      !Number.isFinite(node.z)
    )
      return;

    const geometry = new THREE.SphereGeometry(1.8, 11, 8);
    const material = new THREE.MeshBasicMaterial({
      color: VISUAL_CONFIG.bursts.color,
      transparent: true,
      opacity: VISUAL_CONFIG.bursts.baseOpacity,
      wireframe: true,
      depthWrite: false,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(node.x, node.y, node.z);
    mesh.userData = {
      age: 0,
      life: VISUAL_CONFIG.bursts.lifeMs,
      baseOpacity: VISUAL_CONFIG.bursts.baseOpacity,
    };

    sceneLayers.eventBurstLayer.add(mesh);
  }

  function findNodeFromEvent(event) {
    if (!event) return null;

    if (event.node_id && nodeById.has(event.node_id)) {
      return nodeById.get(event.node_id);
    }

    if (event.task && event.domain) {
      return (
        graphData.nodes.find(
          (n) =>
            n.type === "task" &&
            n.task === event.task &&
            n.domain === event.domain,
        ) || null
      );
    }

    if (event.domain) {
      return (
        graphData.nodes.find(
          (n) => n.type === "domain" && n.domain === event.domain,
        ) || null
      );
    }

    return null;
  }

  // ---- Camera behavior ----
  function getCameraPositionVector() {
    const pos = graph.cameraPosition();
    return new THREE.Vector3(pos.x, pos.y, pos.z);
  }

  function estimateGraphCenterAndRadius() {
    const positioned = graphData.nodes.filter(
      (node) =>
        node.__visible !== false &&
        Number.isFinite(node.x) &&
        Number.isFinite(node.y) &&
        Number.isFinite(node.z),
    );

    if (!positioned.length) {
      return {
        center: new THREE.Vector3(0, 0, 0),
        radius: VISUAL_CONFIG.camera.defaultDistance * 0.45,
      };
    }

    const center = new THREE.Vector3(0, 0, 0);
    positioned.forEach((node) => {
      center.x += node.x;
      center.y += node.y;
      center.z += node.z;
    });
    center.multiplyScalar(1 / positioned.length);

    let maxDistSq = 0;
    positioned.forEach((node) => {
      const dx = node.x - center.x;
      const dy = node.y - center.y;
      const dz = node.z - center.z;
      const distSq = dx * dx + dy * dy + dz * dz;
      if (distSq > maxDistSq) maxDistSq = distSq;
    });

    const radius = Math.max(80, Math.sqrt(maxDistSq));
    return { center, radius };
  }

  function computeFramedDistance(radius) {
    const paddedRadius =
      Math.max(60, radius) + VISUAL_CONFIG.camera.framePadding;
    const desiredDistance = Math.max(
      VISUAL_CONFIG.camera.introFarDistance,
      paddedRadius * VISUAL_CONFIG.camera.frameRadiusScale,
    );

    return clamp(
      desiredDistance,
      VISUAL_CONFIG.camera.minDistance * 0.95,
      VISUAL_CONFIG.camera.maxDistance * 0.98,
    );
  }

  function sampleNetworkFraming(nowMs, force) {
    const throttleMs = Math.max(16, VISUAL_CONFIG.camera.frameSampleMs);
    if (
      !force &&
      nowMs - cameraState.lastFrameSampleMs < throttleMs &&
      cameraState.framedDistance > 0
    ) {
      return {
        center: cameraState.frameCenter.clone(),
        radius: cameraState.framedRadius,
        distance: cameraState.framedDistance,
      };
    }

    const { center, radius } = estimateGraphCenterAndRadius();
    const desiredDistance = computeFramedDistance(radius);
    const lerpFactor = force
      ? 1
      : clamp(VISUAL_CONFIG.camera.frameLerpFactor, 0.05, 1);

    cameraState.frameCenter.lerp(center, lerpFactor);
    cameraState.framedRadius = lerp(
      cameraState.framedRadius,
      radius,
      lerpFactor,
    );
    cameraState.framedDistance = lerp(
      cameraState.framedDistance,
      desiredDistance,
      lerpFactor,
    );
    cameraState.lastFrameSampleMs = nowMs;

    return {
      center: cameraState.frameCenter.clone(),
      radius: cameraState.framedRadius,
      distance: cameraState.framedDistance,
    };
  }

  function startCameraIntro() {
    if (!graph) return;

    const nowMs = performance.now();
    const frame = sampleNetworkFraming(nowMs, true);
    const baseDir = cameraState.introDirection.clone().normalize();
    const nearDistance = Math.max(0.1, VISUAL_CONFIG.camera.introNearDistance);
    const farDistance = frame.distance;

    cameraState.introTarget.copy(frame.center);
    cameraState.target.copy(frame.center);
    cameraState.introFrom.copy(
      frame.center.clone().add(baseDir.clone().multiplyScalar(nearDistance)),
    );
    cameraState.introTo.copy(
      frame.center
        .clone()
        .add(baseDir.clone().multiplyScalar(farDistance))
        .add(new THREE.Vector3(0, frame.radius * 0.12, 0)),
    );
    cameraState.introStartMs = nowMs;
    cameraState.introActive = true;
    cameraState.introPlayed = false;
    cameraState.launchFrameUntilMs = 0;
    cameraState.nextFocusSwitchTs = 0;

    graph.cameraPosition(
      {
        x: cameraState.introFrom.x,
        y: cameraState.introFrom.y,
        z: cameraState.introFrom.z,
      },
      {
        x: cameraState.introTarget.x,
        y: cameraState.introTarget.y,
        z: cameraState.introTarget.z,
      },
      0,
    );
  }

  function updateCameraIntro(nowMs) {
    if (!graph || !cameraState.introActive) return false;

    const frame = sampleNetworkFraming(nowMs, false);
    cameraState.introTarget.lerp(frame.center, 0.2);
    const desiredIntroTo = cameraState.introTarget
      .clone()
      .add(cameraState.introDirection.clone().multiplyScalar(frame.distance))
      .add(new THREE.Vector3(0, frame.radius * 0.12, 0));
    cameraState.introTo.lerp(desiredIntroTo, 0.24);

    const elapsed = nowMs - cameraState.introStartMs;
    const t = clamp(elapsed / VISUAL_CONFIG.camera.introDurationMs, 0, 1);
    const eased = easeInOutCubic(t);
    const x = lerp(cameraState.introFrom.x, cameraState.introTo.x, eased);
    const y = lerp(cameraState.introFrom.y, cameraState.introTo.y, eased);
    const z = lerp(cameraState.introFrom.z, cameraState.introTo.z, eased);

    graph.cameraPosition(
      { x, y, z },
      {
        x: cameraState.introTarget.x,
        y: cameraState.introTarget.y,
        z: cameraState.introTarget.z,
      },
      0,
    );

    if (t >= 1) {
      cameraState.introActive = false;
      cameraState.introPlayed = true;
      cameraState.target.copy(cameraState.introTarget);
      cameraState.launchFrameUntilMs =
        nowMs + VISUAL_CONFIG.camera.launchHoldMs;
      cameraState.nextFocusSwitchTs = nowMs + 1200;
      return false;
    }

    return true;
  }

  function updateCinematicButton() {
    if (!dom.btnCinematic) return;

    if (cameraState.cinematicEnabled) {
      dom.btnCinematic.textContent = "Cinematic: On";
      dom.btnCinematic.classList.add("toggle-on");
      dom.btnCinematic.classList.remove("toggle-off");
    } else {
      dom.btnCinematic.textContent = "Cinematic: Off";
      dom.btnCinematic.classList.add("toggle-off");
      dom.btnCinematic.classList.remove("toggle-on");
    }
  }

  function disableCinematic() {
    if (!cameraState.cinematicEnabled) return;
    cameraState.cinematicEnabled = false;
    cameraState.userInteracted = true;
    cameraState.introActive = false;
    cameraState.introPlayed = true;
    updateCinematicButton();
  }

  function setCinematicEnabled(enabled) {
    cameraState.cinematicEnabled = !!enabled;
    cameraState.userInteracted = !enabled;

    if (enabled) {
      cameraState.nextFocusSwitchTs = 0;
      cameraState.focusedNodeId = null;
      if (!cameraState.introPlayed) {
        startCameraIntro();
      } else {
        cameraState.launchFrameUntilMs =
          performance.now() + VISUAL_CONFIG.camera.launchHoldMs * 0.65;
      }
    } else {
      cameraState.introActive = false;
      cameraState.launchFrameUntilMs = 0;
    }

    updateCinematicButton();
  }

  function focusNode(node, fromUser) {
    if (!graph || !node) return;
    if (
      !Number.isFinite(node.x) ||
      !Number.isFinite(node.y) ||
      !Number.isFinite(node.z)
    )
      return;

    if (fromUser) {
      disableCinematic();
    }

    cameraState.focusedNodeId = node.id;
    cameraState.target.set(node.x, node.y, node.z);

    const current = getCameraPositionVector();
    const target = new THREE.Vector3(node.x, node.y, node.z);

    const direction = current.clone().sub(target);
    if (direction.lengthSq() < 0.001) {
      direction.set(1, 0.35, 1);
    }
    direction.normalize();

    const distance =
      node.type === "domain"
        ? VISUAL_CONFIG.camera.focusDistanceDomain
        : VISUAL_CONFIG.camera.focusDistanceTask;

    const nextPos = target.clone().add(direction.multiplyScalar(distance));

    graph.cameraPosition(
      { x: nextPos.x, y: nextPos.y, z: nextPos.z },
      { x: target.x, y: target.y, z: target.z },
      900,
    );

    scheduleLabelUpdate();
  }

  function updatePointerNDC(evt) {
    const rect = dom.graph.getBoundingClientRect();
    const x = ((evt.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -(((evt.clientY - rect.top) / rect.height) * 2 - 1);
    cameraState.pointerNDC.set(clamp(x, -1, 1), clamp(y, -1, 1));
  }

  function normalizeWheelDelta(evt) {
    let delta = Number(evt.deltaY || 0);
    if (!Number.isFinite(delta)) return 0;

    // Normalize line/page wheel modes to px-like deltas for consistent zoom feel.
    if (evt.deltaMode === 1) {
      delta *= 16;
    } else if (evt.deltaMode === 2) {
      delta *= window.innerHeight || 800;
    }

    return clamp(
      delta,
      -VISUAL_CONFIG.camera.wheelDeltaClampPx,
      VISUAL_CONFIG.camera.wheelDeltaClampPx,
    );
  }

  function handleCursorDolly(evt) {
    if (!graph) return;

    evt.preventDefault();
    evt.stopPropagation();
    disableCinematic();

    if (Number.isFinite(evt.clientX) && Number.isFinite(evt.clientY)) {
      updatePointerNDC(evt);
    }

    const normalizedDelta = normalizeWheelDelta(evt);
    if (Math.abs(normalizedDelta) < 0.001) return;
    const isPinchGesture = evt.ctrlKey === true;
    const zoomSensitivity = isPinchGesture
      ? VISUAL_CONFIG.camera.pinchZoomSensitivity
      : VISUAL_CONFIG.camera.wheelZoomSensitivity;
    const zoomFactor = Math.exp(normalizedDelta * zoomSensitivity);

    const currentPos = getCameraPositionVector();
    const currentTarget = cameraState.target.clone();
    let viewDirection = currentPos.clone().sub(currentTarget);
    if (viewDirection.lengthSq() < 0.00001) {
      viewDirection.set(1, 0.35, 1);
    }

    const currentDistance = clamp(
      viewDirection.length(),
      VISUAL_CONFIG.camera.minDistance,
      VISUAL_CONFIG.camera.maxDistance,
    );
    viewDirection.normalize();
    const nextDistance = clamp(
      currentDistance * zoomFactor,
      VISUAL_CONFIG.camera.minDistance,
      VISUAL_CONFIG.camera.maxDistance,
    );

    let nextTarget = currentTarget.clone();
    if (!isPinchGesture && VISUAL_CONFIG.camera.wheelTargetFollowFactor > 0) {
      const camera = graph.camera();
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(cameraState.pointerNDC, camera);

      const pointerDirection = raycaster.ray.direction.clone().normalize();
      const distanceDelta = nextDistance - currentDistance;
      nextTarget.add(
        pointerDirection.multiplyScalar(
          distanceDelta * VISUAL_CONFIG.camera.wheelTargetFollowFactor,
        ),
      );
    }

    const nextPos = nextTarget
      .clone()
      .add(viewDirection.multiplyScalar(nextDistance));

    cameraState.target.copy(nextTarget);

    graph.cameraPosition(
      { x: nextPos.x, y: nextPos.y, z: nextPos.z },
      { x: nextTarget.x, y: nextTarget.y, z: nextTarget.z },
      VISUAL_CONFIG.camera.wheelTweenMs,
    );

    scheduleLabelUpdate();
  }

  function pickNextCinematicTarget() {
    const domains = graphData.nodes
      .filter(
        (n) =>
          n.type === "domain" &&
          Number.isFinite(n.x) &&
          Number.isFinite(n.y) &&
          Number.isFinite(n.z),
      )
      .sort(
        (a, b) => (b.__activityNormalized || 0) - (a.__activityNormalized || 0),
      );

    if (!domains.length) return null;

    if (!cameraState.cinematicTargetId) {
      return domains[0];
    }

    const idx = domains.findIndex(
      (n) => n.id === cameraState.cinematicTargetId,
    );
    if (idx < 0) return domains[0];

    return domains[(idx + 1) % domains.length];
  }

  function updateCinematicCamera(dtMs, nowMs) {
    if (!graph || !cameraState.cinematicEnabled) return;

    const frame = sampleNetworkFraming(nowMs, false);
    if (nowMs < cameraState.launchFrameUntilMs) {
      // Keep launch sequence wide so the full constellation is visible before target hopping.
      cameraState.target.lerp(frame.center, 0.16);
      cameraState.orbitAngle +=
        dtMs * VISUAL_CONFIG.camera.cinematicOrbitSpeed * 0.58;

      const radiusBase = Math.max(
        VISUAL_CONFIG.camera.defaultDistance,
        frame.distance * 0.92,
      );
      const radius = radiusBase * (0.96 + 0.06 * Math.sin(nowMs * 0.00015));
      const height =
        cameraState.target.y +
        Math.max(VISUAL_CONFIG.camera.cinematicHeight, frame.radius * 0.18) +
        Math.sin(nowMs * 0.0002) * (VISUAL_CONFIG.camera.cinematicBob * 0.55);

      graph.cameraPosition(
        {
          x: cameraState.target.x + Math.cos(cameraState.orbitAngle) * radius,
          y: height,
          z: cameraState.target.z + Math.sin(cameraState.orbitAngle) * radius,
        },
        {
          x: cameraState.target.x,
          y: cameraState.target.y,
          z: cameraState.target.z,
        },
        0,
      );
      return;
    }

    const nextSwitchDue = nowMs >= cameraState.nextFocusSwitchTs;
    if (nextSwitchDue) {
      const targetNode = pickNextCinematicTarget();
      if (targetNode) {
        cameraState.cinematicTargetId = targetNode.id;
      }
      cameraState.nextFocusSwitchTs =
        nowMs + VISUAL_CONFIG.camera.cinematicSwitchMs;
    }

    const targetNode = cameraState.cinematicTargetId
      ? nodeById.get(cameraState.cinematicTargetId)
      : null;

    if (!targetNode || !Number.isFinite(targetNode.x)) return;

    const desiredTarget = new THREE.Vector3(
      targetNode.x,
      targetNode.y,
      targetNode.z,
    );
    cameraState.target.lerp(desiredTarget, 0.035);
    cameraState.target.lerp(frame.center, 0.04);

    cameraState.orbitAngle += dtMs * VISUAL_CONFIG.camera.cinematicOrbitSpeed;

    const radiusBase = Math.max(
      VISUAL_CONFIG.camera.defaultDistance,
      frame.distance * VISUAL_CONFIG.camera.cinematicFrameScale,
    );
    const radius = radiusBase * (0.88 + 0.17 * Math.sin(nowMs * 0.00017));
    const height =
      cameraState.target.y +
      Math.max(VISUAL_CONFIG.camera.cinematicHeight, frame.radius * 0.16) +
      Math.sin(nowMs * 0.00023) * VISUAL_CONFIG.camera.cinematicBob;

    const nextPos = {
      x: cameraState.target.x + Math.cos(cameraState.orbitAngle) * radius,
      y: height,
      z: cameraState.target.z + Math.sin(cameraState.orbitAngle) * radius,
    };

    graph.cameraPosition(
      nextPos,
      {
        x: cameraState.target.x,
        y: cameraState.target.y,
        z: cameraState.target.z,
      },
      0,
    );
  }

  function setupInputListeners() {
    dom.graph.addEventListener("pointermove", (evt) => {
      updatePointerNDC(evt);
    });

    dom.graph.addEventListener("wheel", handleCursorDolly, {
      passive: false,
      capture: true,
    });

    const stopCinematic = () => {
      disableCinematic();
    };

    dom.graph.addEventListener("mousedown", stopCinematic);
    dom.graph.addEventListener("touchstart", stopCinematic, { passive: true });
    window.addEventListener("keydown", stopCinematic);

    if (dom.btnCinematic) {
      dom.btnCinematic.addEventListener("click", () => {
        setCinematicEnabled(!cameraState.cinematicEnabled);
      });
      updateCinematicButton();
    }
  }

  // ---- Label density ----
  function shouldShowTaskLabel(node, cameraPos) {
    const isFocused = node.id === cameraState.focusedNodeId;
    const isHovered = node.id === cameraState.hoveredNodeId;
    if (isFocused || isHovered) return true;

    const activity = node.__activityNormalized || 0;
    if (activity >= VISUAL_CONFIG.labels.activityThreshold) return true;

    if (
      !Number.isFinite(node.x) ||
      !Number.isFinite(node.y) ||
      !Number.isFinite(node.z)
    )
      return false;

    const dx = cameraPos.x - node.x;
    const dy = cameraPos.y - node.y;
    const dz = cameraPos.z - node.z;
    const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);

    return distance <= VISUAL_CONFIG.labels.nearDistance;
  }

  function updateLabelVisibility() {
    if (!graph) return;

    const now = performance.now();
    if (now - labelState.lastUpdate < VISUAL_CONFIG.labels.updateThrottleMs)
      return;
    labelState.lastUpdate = now;

    const cameraPos = getCameraPositionVector();

    graphData.nodes.forEach((node) => {
      if (!node.__threeObj || !node.__threeObj.userData) return;

      const label = node.__threeObj.userData.labelSprite;
      if (!label) return;

      const visibleByTime = node.__visible !== false;
      if (!visibleByTime) {
        label.visible = false;
        return;
      }

      if (
        replayState.active &&
        replayNodeProgress(node, replayState.nowMs) < 0.82
      ) {
        label.visible = false;
        return;
      }

      if (flyInState.active?.nodeId === node.id) {
        label.visible = true;
        return;
      }

      if (node.type === "domain") {
        if (hoverState.activeNodeId) {
          label.visible = hoverState.activeNodeIds.has(node.id);
        } else {
          label.visible = true;
        }
        return;
      }

      if (hoverState.activeNodeId) {
        label.visible = hoverState.activeNodeIds.has(node.id);
        return;
      }

      label.visible = shouldShowTaskLabel(node, cameraPos);
    });
  }

  function scheduleLabelUpdate() {
    if (labelState.pending) return;
    labelState.pending = true;

    requestAnimationFrame(() => {
      labelState.pending = false;
      updateLabelVisibility();
    });
  }

  // ---- Runtime animation loops ----
  function updatePerformanceBudget(dtMs) {
    const prevParticleFactor = performanceState.particleFactor;
    performanceState.frameAvgMs =
      performanceState.frameAvgMs * 0.92 + dtMs * 0.08;

    if (performanceState.frameAvgMs > VISUAL_CONFIG.performance.degradeMs) {
      performanceState.particleFactor = clamp(
        performanceState.particleFactor - VISUAL_CONFIG.performance.stepDown,
        VISUAL_CONFIG.performance.floorFactor,
        1,
      );
      performanceState.ambientOpacityFactor = clamp(
        performanceState.ambientOpacityFactor -
          VISUAL_CONFIG.performance.stepDown,
        VISUAL_CONFIG.performance.floorFactor,
        1,
      );
    } else if (
      performanceState.frameAvgMs < VISUAL_CONFIG.performance.recoverMs
    ) {
      performanceState.particleFactor = clamp(
        performanceState.particleFactor + VISUAL_CONFIG.performance.stepUp,
        VISUAL_CONFIG.performance.floorFactor,
        1,
      );
      performanceState.ambientOpacityFactor = clamp(
        performanceState.ambientOpacityFactor +
          VISUAL_CONFIG.performance.stepUp,
        VISUAL_CONFIG.performance.floorFactor,
        1,
      );
    }

    if (sceneLayers.ambientPoints && sceneLayers.ambientPoints.material) {
      sceneLayers.ambientPoints.material.opacity =
        VISUAL_CONFIG.ambient.pointOpacity *
        performanceState.ambientOpacityFactor;
    }

    if (sceneLayers.ambientLinks && sceneLayers.ambientLinks.material) {
      sceneLayers.ambientLinks.material.opacity =
        VISUAL_CONFIG.ambient.linkOpacity *
        performanceState.ambientOpacityFactor;
    }

    // Only recompute particle budgets when performance tier meaningfully changes.
    if (
      Math.abs(prevParticleFactor - performanceState.particleFactor) > 0.009
    ) {
      particleBudgetState.dirty = true;
    }
  }

  function updateAmbientMotion(dtMs) {
    if (sceneLayers.ambientPoints) {
      sceneLayers.ambientPoints.rotation.y +=
        dtMs * VISUAL_CONFIG.ambient.motionY;
      sceneLayers.ambientPoints.rotation.x +=
        dtMs * VISUAL_CONFIG.ambient.motionX;
    }

    if (sceneLayers.ambientLinks) {
      sceneLayers.ambientLinks.rotation.y +=
        dtMs * (VISUAL_CONFIG.ambient.motionY * 0.9);
      sceneLayers.ambientLinks.rotation.x +=
        dtMs * (VISUAL_CONFIG.ambient.motionX * 0.9);
    }
  }

  function updateNodeBreathing(nowMs) {
    graphData.nodes.forEach((node) => {
      if (!node.__threeObj || node.__visible === false) return;

      const data = node.__threeObj.userData;
      if (!data) return;
      const replayProgress = replayNodeProgress(node, nowMs);
      const replayScale = lerp(
        VISUAL_CONFIG.replay.minScale,
        1,
        replayProgress,
      );
      const replayOpacity = clamp(replayProgress * 1.08, 0, 1);

      const activity = node.__activityNormalized || 0;
      const pulse =
        0.5 +
        0.5 *
          Math.sin(
            nowMs * VISUAL_CONFIG.motion.nodePulseSpeed + data.pulsePhase,
          );
      const hoverActive = !!hoverState.activeNodeId;
      const isHoverFocus = hoverState.activeNodeId === node.id;
      const isHoverNeighbor =
        hoverActive && !isHoverFocus && hoverState.activeNodeIds.has(node.id);
      const isDimmed = hoverActive && !hoverState.activeNodeIds.has(node.id);

      const maxScale = VISUAL_CONFIG.motion.nodePulseMaxScale;
      const minScale = VISUAL_CONFIG.motion.nodePulseMinScale;
      let scale =
        minScale + (maxScale - minScale) * pulse * (0.35 + activity * 0.65);
      if (isHoverFocus) {
        scale *= VISUAL_CONFIG.hover.focusNodeScaleFactor;
      } else if (isHoverNeighbor) {
        scale *= VISUAL_CONFIG.hover.neighborNodeScaleFactor;
      } else if (isDimmed) {
        scale *= VISUAL_CONFIG.hover.dimNodeScaleFactor;
      }

      const isActiveFlyIn = flyInState.active?.nodeId === node.id;
      let incomingGlow = 0;
      if (isActiveFlyIn) {
        incomingGlow = 1;
      } else if (Number.isFinite(node.__incomingGlowUntilMs)) {
        const remainingMs = node.__incomingGlowUntilMs - nowMs;
        if (remainingMs > 0) {
          incomingGlow = clamp(
            remainingMs / VISUAL_CONFIG.flyIn.glowHoldMs,
            0,
            1,
          );
        } else {
          node.__incomingGlowUntilMs = null;
        }
      }

      scale *= replayScale;
      if (incomingGlow > 0) {
        scale *= 1 + incomingGlow * 0.14;
      }
      node.__threeObj.scale.set(scale, scale, scale);

      let opacityFactor = 1;
      if (isHoverFocus) {
        opacityFactor = VISUAL_CONFIG.hover.focusNodeOpacityFactor;
      } else if (isHoverNeighbor) {
        opacityFactor = VISUAL_CONFIG.hover.neighborNodeOpacityFactor;
      } else if (isDimmed) {
        opacityFactor = VISUAL_CONFIG.hover.dimNodeOpacityFactor;
      }
      opacityFactor *= 1 + incomingGlow * 0.22;

      if (data.coreMaterial) {
        data.coreMaterial.opacity = clamp(
          data.baseCoreOpacity *
            (0.9 + pulse * 0.14) *
            opacityFactor *
            replayOpacity,
          0.0,
          1,
        );

        if (data.baseCoreColor) {
          data.coreMaterial.color
            .copy(data.baseCoreColor)
            .lerp(flyInState.highlightColor, incomingGlow);
        }
      }
      if (data.innerGlowMaterial) {
        data.innerGlowMaterial.opacity = clamp(
          data.baseInnerOpacity *
            (0.86 + pulse * 0.22) *
            opacityFactor *
            replayOpacity,
          0.0,
          1,
        );
      }
      if (data.outerGlowMaterial) {
        data.outerGlowMaterial.opacity = clamp(
          data.baseOuterOpacity *
            (0.88 + pulse * 0.18 + incomingGlow * 0.35) *
            opacityFactor *
            replayOpacity,
          0.0,
          1,
        );
      }

      if (data.labelSprite?.material) {
        if (replayProgress < 0.82) {
          data.labelSprite.material.opacity = 0;
        } else if (isDimmed) {
          data.labelSprite.material.opacity =
            VISUAL_CONFIG.hover.dimLabelOpacity;
        } else if (isHoverFocus) {
          data.labelSprite.material.opacity = 0.98;
        } else if (isHoverNeighbor) {
          data.labelSprite.material.opacity = 0.84;
        } else if (incomingGlow > 0.05) {
          data.labelSprite.material.opacity = 0.95;
        } else if (node.type === "domain") {
          data.labelSprite.material.opacity =
            VISUAL_CONFIG.labels.domainOpacity;
        } else {
          data.labelSprite.material.opacity = VISUAL_CONFIG.labels.taskOpacity;
        }
      }
    });
  }

  function updateEventBursts(dtMs) {
    if (!sceneLayers.eventBurstLayer) return;

    const children = sceneLayers.eventBurstLayer.children;
    for (let i = children.length - 1; i >= 0; i -= 1) {
      const burst = children[i];
      burst.userData.age += dtMs;

      const t = clamp(burst.userData.age / burst.userData.life, 0, 1);
      if (t >= 1) {
        sceneLayers.eventBurstLayer.remove(burst);
        if (burst.geometry) burst.geometry.dispose();
        if (burst.material) burst.material.dispose();
        continue;
      }

      const scale = 1 + t * VISUAL_CONFIG.bursts.scale;
      burst.scale.set(scale, scale, scale);

      if (burst.material) {
        burst.material.opacity =
          burst.userData.baseOpacity * Math.pow(1 - t, 1.35);
      }
    }
  }

  function applyContainment() {
    const radius = VISUAL_CONFIG.layout.containmentRadius;
    const pull = VISUAL_CONFIG.layout.containmentPull;
    const damping = VISUAL_CONFIG.layout.velocityDamping;

    graphData.nodes.forEach((node) => {
      if (node.fx != null || node.fy != null || node.fz != null) return;
      if (
        !Number.isFinite(node.x) ||
        !Number.isFinite(node.y) ||
        !Number.isFinite(node.z)
      ) {
        return;
      }

      const dist = Math.sqrt(
        node.x * node.x + node.y * node.y + node.z * node.z,
      );
      if (dist <= radius) return;

      const overshoot = dist - radius;
      const factor = (overshoot / dist) * pull;

      node.x -= node.x * factor;
      node.y -= node.y * factor;
      node.z -= node.z * factor;

      if (Number.isFinite(node.vx)) node.vx *= damping;
      if (Number.isFinite(node.vy)) node.vy *= damping;
      if (Number.isFinite(node.vz)) node.vz *= damping;
    });
  }

  function updateReplayAnimation(nowMs) {
    // Keep replay driven by the same frame loop as camera + node motion.
    // A single RAF path avoids timer contention and reduces stutter on dense graphs.
    replayState.nowMs = nowMs;
    if (!replayState.active) return;

    const elapsed = nowMs - replayState.startMs;
    const endMs =
      replayState.durationMs +
      Math.max(
        VISUAL_CONFIG.replay.nodeEaseMs,
        VISUAL_CONFIG.replay.linkEaseMs,
      ) +
      40;

    if (elapsed >= endMs) {
      finishReplayGrowth();
      return;
    }
  }

  function frameLoop(nowMs) {
    const dtMs = Math.min(80, nowMs - cameraState.lastFrameTs);
    cameraState.lastFrameTs = nowMs;
    performanceState.runningMs += dtMs;

    updateReplayAnimation(nowMs);
    updateFlyInAnimation(nowMs);
    updatePerformanceBudget(dtMs);
    updateParticleBudget(false);
    updateAmbientMotion(dtMs);
    updateNodeBreathing(nowMs);
    updateEventBursts(dtMs);
    applyContainment();

    const introRunning =
      introGateState.started &&
      cameraState.cinematicEnabled &&
      !cameraState.userInteracted &&
      updateCameraIntro(nowMs);
    if (introRunning) {
      scheduleLabelUpdate();
    }

    if (
      introGateState.started &&
      cameraState.cinematicEnabled &&
      !cameraState.userInteracted &&
      !introRunning
    ) {
      updateCinematicCamera(dtMs, nowMs);
      scheduleLabelUpdate();
    }

    requestAnimationFrame(frameLoop);
  }

  function startFrameLoop() {
    if (cameraState.renderStarted) return;
    cameraState.renderStarted = true;
    cameraState.lastFrameTs = performance.now();
    replayState.nowMs = cameraState.lastFrameTs;
    requestAnimationFrame(frameLoop);
  }

  // ---- Fetch and initialization ----
  async function loadGraph() {
    graphData = await fetchGraphPayload();
    computeDerivedMetrics();

    try {
      initGraph();
    } catch (err) {
      console.error("Graph init error (non-fatal, continuing):", err);
    }
    try { updateStats(); } catch (e) { console.warn("Stats update skipped:", e); }
    try { await loadHistory(); } catch (e) { console.warn("History load skipped:", e); }
  }

  async function loadHistory() {
    const data = await fetchHistoryPayload();
    historyEvents = data.events || [];

    if (historyEvents.length > 0) {
      const timestamps = historyEvents.map((e) =>
        new Date(e.timestamp).getTime(),
      );
      timelineRange.min = Math.min(...timestamps);
      timelineRange.max = Math.max(...timestamps, Date.now());
    }

    updateTimelineLabel(1000);
    applyTimeFilter(currentTimeValue);
  }

  function setupBloom() {
    try {
      const renderer = graph.renderer();
      const scene = graph.scene();
      const camera = graph.camera();

      const composer = new THREE.EffectComposer(renderer);
      const renderPass = new THREE.RenderPass(scene, camera);
      composer.addPass(renderPass);

      const bloomPass = new THREE.UnrealBloomPass(
        new THREE.Vector2(window.innerWidth, window.innerHeight),
        VISUAL_CONFIG.bloom.strength,
        VISUAL_CONFIG.bloom.radius,
        VISUAL_CONFIG.bloom.threshold,
      );
      composer.addPass(bloomPass);

      graph.postProcessingComposer(composer);
    } catch (err) {
      // Keep graph functional if post-processing scripts fail to load.
      console.warn("Bloom pipeline disabled:", err);
    }
  }

  function initGraph() {
    graph = ForceGraph3D()(dom.graph);
    if (!graph) {
      throw new Error("ForceGraph3D initialization returned no instance");
    }

    graph
      .graphData(graphData)
      .backgroundColor(VISUAL_CONFIG.background)
      .showNavInfo(false)
      .nodeRelSize(1)
      .nodeVal((node) => {
        if (node.type === "domain") return 40;
        return Math.max(3, 3 + (node.__activityNormalized || 0) * 10);
      })
      .nodeColor((node) => {
        if (node.type === "domain") return "rgb(160,160,160)";
        return confidenceColor(node.confidence || 0);
      })
      .nodeOpacity(0.92)
      .nodeThreeObject(buildNodeObject)
      .linkColor(linkColor)
      .linkWidth(linkWidth)
      .linkDirectionalParticles(linkParticles)
      .linkDirectionalParticleWidth(VISUAL_CONFIG.particles.width)
      .linkDirectionalParticleSpeed(linkParticleSpeed)
      .linkDirectionalParticleColor(() => VISUAL_CONFIG.particles.color)
      .onNodeClick((node) => {
        handleNodeClick(node);
        focusNode(node, true);
      })
      .onNodeHover((node) => {
        handleHoverIntent(node);
      });

    const chargeForce =
      typeof graph.d3Force === "function" ? graph.d3Force("charge") : null;
    if (chargeForce && typeof chargeForce.strength === "function") {
      chargeForce.strength((node) => {
        if (node.type === "domain") return -900;
        return -220;
      });
    }

    const linkForce =
      typeof graph.d3Force === "function" ? graph.d3Force("link") : null;
    if (linkForce && linkForce.distance) {
      linkForce.distance((link) => {
        if (link.type === "cross") return 130;
        return 72;
      });
    }

    const centerForce =
      typeof graph.d3Force === "function" ? graph.d3Force("center") : null;
    if (centerForce && centerForce.x && centerForce.y && centerForce.z) {
      centerForce.x(0).y(0).z(0);
    }

    try { setupBloom(); } catch (e) { console.warn("Bloom disabled:", e.message); }
    try { ensureEventBurstLayer(); } catch (e) { console.warn("Event burst layer skipped:", e.message); }
    try { setupInputListeners(); } catch (e) { console.warn("Input listeners skipped:", e.message); }

    try { scheduleAmbientRebuild(1200); } catch (e) { console.warn("Ambient rebuild skipped:", e.message); }
    try { scheduleLabelUpdate(); } catch (e) { console.warn("Label update skipped:", e.message); }
    startFrameLoop();

    // Run composite visibility after the graph has entered its first render frame.
    requestAnimationFrame(() => {
      try {
        applyCompositeVisibility();
      } catch (err) {
        console.error("Initial visibility bootstrap failed:", err);
      }
    });
  }

  // ---- Detail panel ----
  function updateDetailPanel(
    node,
    confidence,
    runCount,
    actionsHtml,
    tracesRows,
  ) {
    dom.detailTitle.textContent =
      node.type === "domain" ? node.domain : node.task;
    dom.detailDomain.textContent =
      node.type === "domain" ? "DOMAIN" : node.domain;

    dom.detailConfidenceBar.style.width = `${(confidence * 100).toFixed(2)}%`;
    dom.detailConfidenceBar.style.background = `linear-gradient(90deg, rgb(100, 105, 115) 0%, ${confidenceColor(confidence)} 100%)`;

    dom.detailConfidenceText.textContent = `${(confidence * 100).toFixed(1)}%`;
    dom.detailRuns.textContent = runCount || 0;

    dom.detailActions.innerHTML = actionsHtml;
    dom.detailTraces.innerHTML = tracesRows;

    dom.detailPanel.classList.add("open");
  }

  function handleNodeClick(node) {
    if (!node) return;

    if (node.type === "domain") {
      const conf = node.avg_confidence || 0;
      const actionsHtml = `<li>${node.task_count || 0} tasks mapped</li>`;
      updateDetailPanel(node, conf, node.total_runs || 0, actionsHtml, "");
      return;
    }

    const conf = node.confidence || 0;

    const actionsHtml = (node.optimal_actions || [])
      .map((a) => `<li>${a}</li>`)
      .join("");

    const tracesRows = (node.step_traces || [])
      .slice(0, 10)
      .map((t) => {
        const rate = t.success_rate || 0;
        return `
          <div class="trace-row">
            <span class="trace-sig" title="${t.action_signature}">${t.action_signature}</span>
            <div class="trace-bar-outer">
              <div class="trace-bar-inner" style="width:${(rate * 100).toFixed(1)}%"></div>
            </div>
            <span class="trace-rate" style="color:${confidenceColor(rate)}">${(rate * 100).toFixed(0)}%</span>
          </div>
        `;
      })
      .join("");

    updateDetailPanel(node, conf, node.run_count || 0, actionsHtml, tracesRows);
  }

  // ---- Stats ----
  function updateStats() {
    const domains = graphData.nodes.filter((n) => n.type === "domain");
    const tasks = graphData.nodes.filter((n) => n.type === "task");
    const totalRuns = tasks.reduce((sum, n) => sum + (n.run_count || 0), 0);
    const avgConfidence = tasks.length
      ? tasks.reduce((sum, n) => sum + (n.confidence || 0), 0) / tasks.length
      : 0;
    const realNodes = graphData.nodes.length;
    const ambientVisuals =
      VISUAL_CONFIG.ambient.pointsCount + VISUAL_CONFIG.ambient.linksCount;

    if (firstLoad) {
      animateValue(dom.statDomains, domains.length, 1200, false);
      animateValue(dom.statTasks, tasks.length, 1200, false);
      animateValue(dom.statRuns, totalRuns, 1800, false);
      animateValue(
        dom.statConfidence,
        Math.round(avgConfidence * 100),
        1200,
        true,
      );
      animateValue(dom.statRealNodes, realNodes, 1300, false);
      animateValue(dom.statAmbientVisuals, ambientVisuals, 1300, false);
      firstLoad = false;
      return;
    }

    dom.statDomains.textContent = domains.length;
    dom.statTasks.textContent = tasks.length;
    dom.statRuns.textContent = totalRuns.toLocaleString();
    dom.statConfidence.textContent = `${(avgConfidence * 100).toFixed(0)}%`;
    dom.statRealNodes.textContent = realNodes.toLocaleString();
    dom.statAmbientVisuals.textContent = ambientVisuals.toLocaleString();
  }

  // ---- WebSocket ----
  function connectWS() {
    if (mockState.enabled) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws`);

    ws.onmessage = (evt) => {
      const event = JSON.parse(evt.data);
      handleWSEvent(event);
    };

    ws.onclose = () => {
      setTimeout(connectWS, 2000);
    };

    ws.onerror = () => ws.close();
  }

  function handleWSEvent(event) {
    if (!event) return;

    if (event.type === "trace_arrived") {
      handleTraceArrivedEvent(event);
      return;
    }

    if (
      event.type === "node_added" ||
      event.type === "node_updated" ||
      event.type === "step_recorded"
    ) {
      const sinceConvexMs =
        performance.now() - realtimeState.lastConvexSignalMs;
      if (
        sinceConvexMs < VISUAL_CONFIG.realtime.convexSuppressFallbackMs &&
        event.type !== "step_recorded"
      ) {
        return;
      }

      refreshGraphWithDiff().then((result) => {
        const node = findNodeFromEvent(event);
        spawnBurstAtNode(node);
        const newTaskNode = result.addedTaskNodes[0] || null;
        if (newTaskNode) enqueueIncomingNode(newTaskNode.id);
      });
    }
  }

  function rememberTraceSignal(traceId) {
    if (!traceId) return true;
    if (realtimeState.seenTraceIds.has(traceId)) return false;

    realtimeState.seenTraceIds.add(traceId);
    realtimeState.seenTraceOrder.push(traceId);

    while (
      realtimeState.seenTraceOrder.length > VISUAL_CONFIG.realtime.seenTraceCap
    ) {
      const oldId = realtimeState.seenTraceOrder.shift();
      if (oldId) realtimeState.seenTraceIds.delete(oldId);
    }

    return true;
  }

  function animateNodeCounters(beforeCounts, afterCounts) {
    if (afterCounts.realNodes > beforeCounts.realNodes) {
      animateValueBetween(
        dom.statRealNodes,
        beforeCounts.realNodes,
        afterCounts.realNodes,
        420,
        false,
      );
    }

    if (afterCounts.tasks > beforeCounts.tasks) {
      animateValueBetween(
        dom.statTasks,
        beforeCounts.tasks,
        afterCounts.tasks,
        420,
        false,
      );
    }
  }

  function pickNewTaskNodeFromTrace(event, addedTaskNodes) {
    if (!addedTaskNodes.length) return null;

    if (event.task && event.domain) {
      const exact = addedTaskNodes.find(
        (node) => node.task === event.task && node.domain === event.domain,
      );
      if (exact) return exact;
    }

    if (event.domain) {
      const byDomain = addedTaskNodes.find(
        (node) => node.domain === event.domain,
      );
      if (byDomain) return byDomain;
    }

    return addedTaskNodes[0];
  }

  function flushPendingTraceEvents(result) {
    if (!realtimeState.pendingTraceEvents.length) return;

    const pendingEvents = realtimeState.pendingTraceEvents.splice(0);
    animateNodeCounters(result.beforeCounts, result.afterCounts);

    const remainingAddedTaskNodes = result.addedTaskNodes.slice();
    pendingEvents.forEach((pendingEvent) => {
      const node = findNodeFromEvent(pendingEvent);
      spawnBurstAtNode(node);

      const newTaskNode = pickNewTaskNodeFromTrace(
        pendingEvent,
        remainingAddedTaskNodes,
      );
      if (!newTaskNode) return;

      enqueueIncomingNode(newTaskNode.id);
      const idx = remainingAddedTaskNodes.findIndex(
        (candidate) => candidate.id === newTaskNode.id,
      );
      if (idx >= 0) remainingAddedTaskNodes.splice(idx, 1);
    });
  }

  async function handleTraceArrivedEvent(event) {
    if (!rememberTraceSignal(event.trace_id || event.traceId || "")) return;
    realtimeState.lastConvexSignalMs = performance.now();

    if (flyInState.active) {
      flyInState.queuedRefresh = true;
      realtimeState.pendingTraceEvents.push(event);
      return;
    }

    const result = await refreshGraphWithDiff();
    animateNodeCounters(result.beforeCounts, result.afterCounts);

    const node = findNodeFromEvent(event);
    spawnBurstAtNode(node);

    const newTaskNode = pickNewTaskNodeFromTrace(event, result.addedTaskNodes);
    if (newTaskNode) {
      enqueueIncomingNode(newTaskNode.id);
    }
  }

  // ---- Graph refresh ----
  function refreshGraphWithDiff() {
    if (replayState.active) {
      replayState.queuedRefresh = true;
      return Promise.resolve({
        addedNodes: [],
        addedTaskNodes: [],
        beforeCounts: {
          realNodes: graphData.nodes.length,
          tasks: graphData.nodes.filter((node) => node.type === "task").length,
        },
        afterCounts: {
          realNodes: graphData.nodes.length,
          tasks: graphData.nodes.filter((node) => node.type === "task").length,
        },
      });
    }

    if (flyInState.active) {
      flyInState.queuedRefresh = true;
      return Promise.resolve({
        addedNodes: [],
        addedTaskNodes: [],
        beforeCounts: {
          realNodes: graphData.nodes.length,
          tasks: graphData.nodes.filter((node) => node.type === "task").length,
        },
        afterCounts: {
          realNodes: graphData.nodes.length,
          tasks: graphData.nodes.filter((node) => node.type === "task").length,
        },
      });
    }

    if (refreshPending) {
      return Promise.resolve({
        addedNodes: [],
        addedTaskNodes: [],
        beforeCounts: {
          realNodes: graphData.nodes.length,
          tasks: graphData.nodes.filter((node) => node.type === "task").length,
        },
        afterCounts: {
          realNodes: graphData.nodes.length,
          tasks: graphData.nodes.filter((node) => node.type === "task").length,
        },
      });
    }
    refreshPending = true;

    return new Promise((resolve) => {
      setTimeout(async () => {
        try {
          const previousNodes = graphData.nodes.slice();
          const previousNodeIds = new Set(previousNodes.map((node) => node.id));
          const previousTaskCount = previousNodes.filter(
            (node) => node.type === "task",
          ).length;

          const newData = await fetchGraphPayload();

          const posMap = {};
          graphData.nodes.forEach((node) => {
            if (
              Number.isFinite(node.x) &&
              Number.isFinite(node.y) &&
              Number.isFinite(node.z)
            ) {
              posMap[node.id] = {
                x: node.x,
                y: node.y,
                z: node.z,
                vx: node.vx,
                vy: node.vy,
                vz: node.vz,
              };
            }
          });

          newData.nodes.forEach((node) => {
            if (posMap[node.id]) {
              Object.assign(node, posMap[node.id]);
              return;
            }

            const domainNode = graphData.nodes.find(
              (d) => d.type === "domain" && d.domain === node.domain,
            );

            if (domainNode && Number.isFinite(domainNode.x)) {
              node.x = domainNode.x + (Math.random() - 0.5) * 20;
              node.y = domainNode.y + (Math.random() - 0.5) * 20;
              node.z = domainNode.z + (Math.random() - 0.5) * 20;
            }
          });

          graphData = newData;
          computeDerivedMetrics();

          graph.graphData(graphData);
          updateStats();
          applyTimeFilter(currentTimeValue);

          scheduleAmbientRebuild(450);
          scheduleLabelUpdate();

          const addedNodes = graphData.nodes.filter(
            (node) => !previousNodeIds.has(node.id),
          );
          const addedTaskNodes = addedNodes.filter(
            (node) => node.type === "task",
          );
          const currentTaskCount = graphData.nodes.filter(
            (node) => node.type === "task",
          ).length;

          resolve({
            addedNodes,
            addedTaskNodes,
            beforeCounts: {
              realNodes: previousNodes.length,
              tasks: previousTaskCount,
            },
            afterCounts: {
              realNodes: graphData.nodes.length,
              tasks: currentTaskCount,
            },
          });
        } catch (err) {
          console.error("Graph refresh failed:", err);
          resolve({
            addedNodes: [],
            addedTaskNodes: [],
            beforeCounts: {
              realNodes: graphData.nodes.length,
              tasks: graphData.nodes.filter((node) => node.type === "task")
                .length,
            },
            afterCounts: {
              realNodes: graphData.nodes.length,
              tasks: graphData.nodes.filter((node) => node.type === "task")
                .length,
            },
          });
        } finally {
          refreshPending = false;
        }
      }, 260);
    });
  }

  function refreshGraph() {
    return refreshGraphWithDiff().then(() => {});
  }

  // ---- Controls ----
  dom.btnSimulate.addEventListener("click", async () => {
    dom.btnSimulate.disabled = true;
    dom.btnSimulate.textContent = "RUNNING...";

    try {
      if (mockState.enabled) {
        const event = createMockTraceArrivalEvent();
        if (event) await handleTraceArrivedEvent(event);
      } else {
        await fetch("/api/simulate", { method: "POST" });
        await refreshGraph();
      }
    } catch (err) {
      console.error("Simulate failed:", err);
    }

    dom.btnSimulate.disabled = false;
    dom.btnSimulate.textContent = "Simulate Agent Run";
  });

  if (dom.btnReplayGrowth) {
    dom.btnReplayGrowth.addEventListener("click", startReplayGrowth);
  }

  dom.chkAuto.addEventListener("change", async (evt) => {
    if (mockState.enabled) {
      setMockAutoSimulate(evt.target.checked);
      return;
    }

    const action = evt.target.checked ? "start" : "stop";
    await fetch(`/api/auto-simulate/${action}`, { method: "POST" });
  });

  dom.detailClose.addEventListener("click", () => {
    dom.detailPanel.classList.remove("open");
  });

  if (dom.landingCta) {
    dom.landingCta.addEventListener("click", () => {
      startIntroFromLanding();
    });
  }

  setReplayControlsLocked(false);

  // ---- Timeline ----
  dom.timelineSlider.addEventListener("input", () => {
    if (replayState.active) return;
    currentTimeValue = parseInt(dom.timelineSlider.value, 10);
    applyTimeFilter(currentTimeValue);
    updateTimelineLabel(currentTimeValue);

    if (isPlaying) togglePlay();
  });

  dom.timelinePlay.addEventListener("click", togglePlay);

  function togglePlay() {
    if (replayState.active) return;
    isPlaying = !isPlaying;
    dom.timelinePlay.innerHTML = isPlaying ? "&#9646;&#9646;" : "&#9654;";

    if (isPlaying) {
      if (currentTimeValue >= 990) {
        currentTimeValue = 0;
        dom.timelineSlider.value = 0;
      }

      playInterval = setInterval(() => {
        currentTimeValue = Math.min(1000, currentTimeValue + 3);
        dom.timelineSlider.value = currentTimeValue;

        applyTimeFilter(currentTimeValue);
        updateTimelineLabel(currentTimeValue);

        if (currentTimeValue >= 1000) {
          togglePlay();
        }
      }, 50);

      return;
    }

    clearInterval(playInterval);
    playInterval = null;
  }

  function updateTimelineLabel(value) {
    const t = value / 1000;
    const ts = timelineRange.min + t * (timelineRange.max - timelineRange.min);
    const date = new Date(ts);
    dom.timelineDate.textContent =
      value >= 1000 ? "LIVE" : date.toLocaleString();
  }

  function applyTimeFilter(value) {
    if (!graph) return;

    if (!historyEvents.length || value >= 1000) {
      graphData.nodes.forEach((node) => {
        node.__timelineVisible = true;
        if (node.type === "task") {
          node.__displayConfidence = node.confidence;
        }
      });
      graphData.links.forEach((link) => {
        link.__timelineVisible = true;
      });
      applyCompositeVisibility();
      return;
    }

    const t = value / 1000;
    const cutoffTs =
      timelineRange.min + t * (timelineRange.max - timelineRange.min);

    const visibleTaskIds = new Set();
    const taskConfidence = {};

    historyEvents.forEach((event) => {
      const ts = new Date(event.timestamp).getTime();
      if (ts > cutoffTs) return;

      visibleTaskIds.add(event.node_id);
      taskConfidence[event.node_id] = event.confidence;
    });

    graphData.nodes.forEach((node) => {
      if (node.type === "domain") {
        const hasVisibleTasks = graphData.nodes.some(
          (task) =>
            task.type === "task" &&
            task.domain === node.domain &&
            visibleTaskIds.has(task.id),
        );
        node.__timelineVisible = hasVisibleTasks;
      } else {
        node.__timelineVisible = visibleTaskIds.has(node.id);
        if (taskConfidence[node.id] !== undefined) {
          node.__displayConfidence = taskConfidence[node.id];
        } else {
          node.__displayConfidence = node.confidence;
        }
      }
    });

    graphData.links.forEach((link) => {
      link.__timelineVisible = true;
    });

    applyCompositeVisibility();
  }

  // ---- Boot ----
  setSceneUiEnabled(false);
  primeScenePaused().catch((err) => {
    console.error("Scene prewarm failed:", err);
  });

  if (!dom.landingCta) {
    startIntroFromLanding();
  }

  window.addEventListener("beforeunload", () => {
    if (mockState.enabled) setMockAutoSimulate(false);
  });
})();

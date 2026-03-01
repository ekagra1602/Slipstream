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
      hubBaseAlpha: 0.10,
      hubAlphaScale: 0.25,
      crossBaseAlpha: 0.13,
      crossAlphaScale: 0.30,
      hubBaseWidth: 0.35,
      hubWidthScale: 1.35,
      crossBaseWidth: 0.45,
      crossWidthScale: 1.55,
    },
    particles: {
      color: "#BFCBDA",
      width: 1.8,
      hubBaseCount: 1,
      hubCountScale: 4,
      crossBaseCount: 1,
      crossCountScale: 5,
      baseSpeed: 0.0023,
      speedScale: 0.0032,
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
      defaultDistance: 380,
      minDistance: 140,
      maxDistance: 920,
      focusDistanceTask: 205,
      focusDistanceDomain: 260,
      zoomStep: 26,
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
  };

  const dom = {
    graph: document.getElementById("graph"),
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

  function safeNodeId(ref) {
    return typeof ref === "object" && ref !== null ? ref.id : ref;
  }

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
  };

  const labelState = {
    pending: false,
    lastUpdate: 0,
  };

  // ---- Derived metrics and graph-state enrichment ----
  function computeDerivedMetrics() {
    nodeById = new Map();

    const tasks = graphData.nodes.filter((n) => n.type === "task");
    const domains = graphData.nodes.filter((n) => n.type === "domain");

    maxRunCount = Math.max(1, ...tasks.map((n) => n.run_count || 0));
    maxDomainRuns = Math.max(1, ...domains.map((n) => n.total_runs || 0));

    graphData.nodes.forEach((node) => {
      const runCount = node.type === "domain" ? node.total_runs : node.run_count;
      const conf = node.type === "domain" ? (node.avg_confidence || 0) : (node.confidence || 0);
      const activity = node.type === "domain"
        ? activityFromRuns(runCount || 0, maxDomainRuns)
        : activityFromRuns(runCount || 0, maxRunCount);

      node.__activityNormalized = activity;
      node.__confidenceSignal = clamp(conf, 0, 1);
      node.__routeReliability = clamp(0.7 * node.__confidenceSignal + 0.3 * activity, 0, 1);
      node.__pulsePhase = (hashString(String(node.id)) % 1000) / 160;
      nodeById.set(node.id, node);
    });

    graphData.links.forEach((link) => {
      const sourceNode = nodeById.get(safeNodeId(link.source));
      const targetNode = nodeById.get(safeNodeId(link.target));

      const sourceReliability = sourceNode ? sourceNode.__routeReliability : 0.5;
      const targetReliability = targetNode ? targetNode.__routeReliability : 0.5;
      const sourceActivity = sourceNode ? sourceNode.__activityNormalized : 0.4;
      const targetActivity = targetNode ? targetNode.__activityNormalized : 0.4;

      const confidenceSignal = clamp((sourceReliability + targetReliability) / 2, 0, 1);
      const activitySignal = clamp((sourceActivity + targetActivity) / 2, 0, 1);
      let routeStrength = clamp(0.7 * confidenceSignal + 0.3 * activitySignal, 0, 1);

      if (link.type === "cross") {
        const strengthNorm = clamp((link.strength || 1) / 5, 0, 1);
        routeStrength = clamp(routeStrength * 0.75 + strengthNorm * 0.25, 0, 1);
      }

      link.__routeStrength = routeStrength;
    });
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
      opacity: node.type === "domain" ? VISUAL_CONFIG.labels.domainOpacity : VISUAL_CONFIG.labels.taskOpacity,
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
    const confidence = node.type === "domain" ? (node.avg_confidence || 0) : (node.confidence || 0);
    const colorHex = confidenceHex(confidence);

    const size = node.type === "domain"
      ? 6.2 + activity * 1.8
      : 1.85 + activity * 2.4;

    const geometry = node.type === "domain"
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
      opacity: 0.10 + activity * 0.04,
      side: THREE.BackSide,
    });
    const innerGlow = new THREE.Mesh(
      new THREE.SphereGeometry(size * 1.16, 12, 8),
      innerGlowMaterial
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
      outerGlowMaterial
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
    const strength = clamp(link.__routeStrength || 0.45, 0, 1);

    if (link.type === "cross") {
      const alpha = VISUAL_CONFIG.links.crossBaseAlpha + (strength * VISUAL_CONFIG.links.crossAlphaScale);
      return `rgba(176, 184, 194, ${alpha.toFixed(2)})`;
    }

    const alpha = VISUAL_CONFIG.links.hubBaseAlpha + (strength * VISUAL_CONFIG.links.hubAlphaScale);
    return `rgba(140, 145, 152, ${alpha.toFixed(2)})`;
  }

  function linkWidth(link) {
    const strength = clamp(link.__routeStrength || 0.45, 0, 1);
    if (link.type === "cross") {
      return VISUAL_CONFIG.links.crossBaseWidth + (strength * VISUAL_CONFIG.links.crossWidthScale);
    }
    return VISUAL_CONFIG.links.hubBaseWidth + (strength * VISUAL_CONFIG.links.hubWidthScale);
  }

  function linkParticles(link) {
    const strength = clamp(link.__routeStrength || 0.45, 0, 1);
    const base = link.type === "cross"
      ? VISUAL_CONFIG.particles.crossBaseCount
      : VISUAL_CONFIG.particles.hubBaseCount;
    const scale = link.type === "cross"
      ? VISUAL_CONFIG.particles.crossCountScale
      : VISUAL_CONFIG.particles.hubCountScale;
    const count = Math.round(base + (strength * scale));
    return Math.max(1, Math.round(count * performanceState.particleFactor));
  }

  function linkParticleSpeed(link) {
    const strength = clamp(link.__routeStrength || 0.45, 0, 1);
    return VISUAL_CONFIG.particles.baseSpeed + (strength * VISUAL_CONFIG.particles.speedScale);
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
        : Math.cos((idx / Math.max(1, domains.length)) * Math.PI * 2) * fallbackRadius;
      const y = Number.isFinite(domain.y) ? domain.y : ((idx % 5) - 2) * 35;
      const z = Number.isFinite(domain.z)
        ? domain.z
        : Math.sin((idx / Math.max(1, domains.length)) * Math.PI * 2) * fallbackRadius;

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
      const spread = VISUAL_CONFIG.ambient.clusterSpread * (0.68 + random() * 0.86);

      const theta = random() * Math.PI * 2;
      const phi = Math.acos((random() * 2) - 1);
      const radius = spread * Math.pow(random(), 0.55);

      const x = anchor.x + (radius * Math.sin(phi) * Math.cos(theta));
      const y = anchor.y + (radius * Math.cos(phi)) * 0.65;
      const z = anchor.z + (radius * Math.sin(phi) * Math.sin(theta));

      pointPositions[(i * 3) + 0] = x;
      pointPositions[(i * 3) + 1] = y;
      pointPositions[(i * 3) + 2] = z;
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
    pointGeometry.setAttribute("position", new THREE.BufferAttribute(pointPositions, 3));

    const pointMaterial = new THREE.PointsMaterial({
      color: VISUAL_CONFIG.ambient.pointColor,
      size: VISUAL_CONFIG.ambient.pointSize,
      sizeAttenuation: true,
      transparent: true,
      opacity: VISUAL_CONFIG.ambient.pointOpacity * performanceState.ambientOpacityFactor,
      depthWrite: false,
    });

    const points = new THREE.Points(pointGeometry, pointMaterial);
    scene.add(points);
    sceneLayers.ambientPoints = points;

    const linkGeometry = new THREE.BufferGeometry();
    linkGeometry.setAttribute("position", new THREE.BufferAttribute(linkPositions, 3));

    const lineMaterial = new THREE.LineBasicMaterial({
      color: VISUAL_CONFIG.ambient.linkColor,
      transparent: true,
      opacity: VISUAL_CONFIG.ambient.linkOpacity * performanceState.ambientOpacityFactor,
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
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || !Number.isFinite(node.z)) return;

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
      return graphData.nodes.find(
        (n) => n.type === "task" && n.task === event.task && n.domain === event.domain
      ) || null;
    }

    if (event.domain) {
      return graphData.nodes.find(
        (n) => n.type === "domain" && n.domain === event.domain
      ) || null;
    }

    return null;
  }

  // ---- Camera behavior ----
  function getCameraPositionVector() {
    const pos = graph.cameraPosition();
    return new THREE.Vector3(pos.x, pos.y, pos.z);
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
    updateCinematicButton();
  }

  function setCinematicEnabled(enabled) {
    cameraState.cinematicEnabled = !!enabled;
    cameraState.userInteracted = !enabled;

    if (enabled) {
      cameraState.nextFocusSwitchTs = 0;
      cameraState.focusedNodeId = null;
    }

    updateCinematicButton();
  }

  function focusNode(node, fromUser) {
    if (!graph || !node) return;
    if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || !Number.isFinite(node.z)) return;

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

    const distance = node.type === "domain"
      ? VISUAL_CONFIG.camera.focusDistanceDomain
      : VISUAL_CONFIG.camera.focusDistanceTask;

    const nextPos = target.clone().add(direction.multiplyScalar(distance));

    graph.cameraPosition(
      { x: nextPos.x, y: nextPos.y, z: nextPos.z },
      { x: target.x, y: target.y, z: target.z },
      900
    );

    scheduleLabelUpdate();
  }

  function updatePointerNDC(evt) {
    const rect = dom.graph.getBoundingClientRect();
    const x = ((evt.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -(((evt.clientY - rect.top) / rect.height) * 2 - 1);
    cameraState.pointerNDC.set(clamp(x, -1, 1), clamp(y, -1, 1));
  }

  function handleCursorDolly(evt) {
    if (!graph) return;

    evt.preventDefault();
    disableCinematic();

    if (Number.isFinite(evt.clientX) && Number.isFinite(evt.clientY)) {
      updatePointerNDC(evt);
    }

    const camera = graph.camera();
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(cameraState.pointerNDC, camera);

    const direction = raycaster.ray.direction.clone().normalize();
    const amount = evt.deltaY < 0
      ? VISUAL_CONFIG.camera.zoomStep
      : -VISUAL_CONFIG.camera.zoomStep;

    const currentPos = getCameraPositionVector();
    let nextPos = currentPos.clone().add(direction.clone().multiplyScalar(amount));
    const nextTarget = cameraState.target.clone().add(direction.clone().multiplyScalar(amount * VISUAL_CONFIG.camera.targetFollowFactor));

    let distance = nextPos.distanceTo(nextTarget);
    if (distance < VISUAL_CONFIG.camera.minDistance || distance > VISUAL_CONFIG.camera.maxDistance) {
      const dir = nextPos.clone().sub(nextTarget).normalize();
      distance = clamp(distance, VISUAL_CONFIG.camera.minDistance, VISUAL_CONFIG.camera.maxDistance);
      nextPos = nextTarget.clone().add(dir.multiplyScalar(distance));
    }

    cameraState.target.copy(nextTarget);

    graph.cameraPosition(
      { x: nextPos.x, y: nextPos.y, z: nextPos.z },
      { x: nextTarget.x, y: nextTarget.y, z: nextTarget.z },
      120
    );

    scheduleLabelUpdate();
  }

  function pickNextCinematicTarget() {
    const domains = graphData.nodes
      .filter((n) => n.type === "domain" && Number.isFinite(n.x) && Number.isFinite(n.y) && Number.isFinite(n.z))
      .sort((a, b) => (b.__activityNormalized || 0) - (a.__activityNormalized || 0));

    if (!domains.length) return null;

    if (!cameraState.cinematicTargetId) {
      return domains[0];
    }

    const idx = domains.findIndex((n) => n.id === cameraState.cinematicTargetId);
    if (idx < 0) return domains[0];

    return domains[(idx + 1) % domains.length];
  }

  function updateCinematicCamera(dtMs, nowMs) {
    if (!graph || !cameraState.cinematicEnabled) return;

    const nextSwitchDue = nowMs >= cameraState.nextFocusSwitchTs;
    if (nextSwitchDue) {
      const targetNode = pickNextCinematicTarget();
      if (targetNode) {
        cameraState.cinematicTargetId = targetNode.id;
      }
      cameraState.nextFocusSwitchTs = nowMs + VISUAL_CONFIG.camera.cinematicSwitchMs;
    }

    const targetNode = cameraState.cinematicTargetId
      ? nodeById.get(cameraState.cinematicTargetId)
      : null;

    if (!targetNode || !Number.isFinite(targetNode.x)) return;

    const desiredTarget = new THREE.Vector3(targetNode.x, targetNode.y, targetNode.z);
    cameraState.target.lerp(desiredTarget, 0.035);

    cameraState.orbitAngle += dtMs * VISUAL_CONFIG.camera.cinematicOrbitSpeed;

    const radiusBase = VISUAL_CONFIG.camera.defaultDistance;
    const radius = radiusBase * (0.88 + 0.17 * Math.sin(nowMs * 0.00017));
    const height = cameraState.target.y
      + VISUAL_CONFIG.camera.cinematicHeight
      + Math.sin(nowMs * 0.00023) * VISUAL_CONFIG.camera.cinematicBob;

    const nextPos = {
      x: cameraState.target.x + Math.cos(cameraState.orbitAngle) * radius,
      y: height,
      z: cameraState.target.z + Math.sin(cameraState.orbitAngle) * radius,
    };

    graph.cameraPosition(nextPos, {
      x: cameraState.target.x,
      y: cameraState.target.y,
      z: cameraState.target.z,
    }, 0);
  }

  function setupInputListeners() {
    dom.graph.addEventListener("pointermove", (evt) => {
      updatePointerNDC(evt);
    });

    dom.graph.addEventListener("wheel", handleCursorDolly, { passive: false });

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

    if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || !Number.isFinite(node.z)) return false;

    const dx = cameraPos.x - node.x;
    const dy = cameraPos.y - node.y;
    const dz = cameraPos.z - node.z;
    const distance = Math.sqrt((dx * dx) + (dy * dy) + (dz * dz));

    return distance <= VISUAL_CONFIG.labels.nearDistance;
  }

  function updateLabelVisibility() {
    if (!graph) return;

    const now = performance.now();
    if ((now - labelState.lastUpdate) < VISUAL_CONFIG.labels.updateThrottleMs) return;
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

      if (node.type === "domain") {
        label.visible = true;
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
    performanceState.frameAvgMs = (performanceState.frameAvgMs * 0.92) + (dtMs * 0.08);

    if (performanceState.frameAvgMs > VISUAL_CONFIG.performance.degradeMs) {
      performanceState.particleFactor = clamp(
        performanceState.particleFactor - VISUAL_CONFIG.performance.stepDown,
        VISUAL_CONFIG.performance.floorFactor,
        1
      );
      performanceState.ambientOpacityFactor = clamp(
        performanceState.ambientOpacityFactor - VISUAL_CONFIG.performance.stepDown,
        VISUAL_CONFIG.performance.floorFactor,
        1
      );
    } else if (performanceState.frameAvgMs < VISUAL_CONFIG.performance.recoverMs) {
      performanceState.particleFactor = clamp(
        performanceState.particleFactor + VISUAL_CONFIG.performance.stepUp,
        VISUAL_CONFIG.performance.floorFactor,
        1
      );
      performanceState.ambientOpacityFactor = clamp(
        performanceState.ambientOpacityFactor + VISUAL_CONFIG.performance.stepUp,
        VISUAL_CONFIG.performance.floorFactor,
        1
      );
    }

    if (sceneLayers.ambientPoints && sceneLayers.ambientPoints.material) {
      sceneLayers.ambientPoints.material.opacity = VISUAL_CONFIG.ambient.pointOpacity * performanceState.ambientOpacityFactor;
    }

    if (sceneLayers.ambientLinks && sceneLayers.ambientLinks.material) {
      sceneLayers.ambientLinks.material.opacity = VISUAL_CONFIG.ambient.linkOpacity * performanceState.ambientOpacityFactor;
    }
  }

  function updateAmbientMotion(dtMs) {
    if (sceneLayers.ambientPoints) {
      sceneLayers.ambientPoints.rotation.y += dtMs * VISUAL_CONFIG.ambient.motionY;
      sceneLayers.ambientPoints.rotation.x += dtMs * VISUAL_CONFIG.ambient.motionX;
    }

    if (sceneLayers.ambientLinks) {
      sceneLayers.ambientLinks.rotation.y += dtMs * (VISUAL_CONFIG.ambient.motionY * 0.9);
      sceneLayers.ambientLinks.rotation.x += dtMs * (VISUAL_CONFIG.ambient.motionX * 0.9);
    }
  }

  function updateNodeBreathing(nowMs) {
    graphData.nodes.forEach((node) => {
      if (!node.__threeObj || node.__visible === false) return;

      const data = node.__threeObj.userData;
      if (!data) return;

      const activity = node.__activityNormalized || 0;
      const pulse = 0.5 + (0.5 * Math.sin((nowMs * VISUAL_CONFIG.motion.nodePulseSpeed) + data.pulsePhase));

      const maxScale = VISUAL_CONFIG.motion.nodePulseMaxScale;
      const minScale = VISUAL_CONFIG.motion.nodePulseMinScale;
      const scale = minScale + ((maxScale - minScale) * pulse * (0.35 + activity * 0.65));

      node.__threeObj.scale.set(scale, scale, scale);

      if (data.coreMaterial) {
        data.coreMaterial.opacity = data.baseCoreOpacity * (0.90 + (pulse * 0.14));
      }
      if (data.innerGlowMaterial) {
        data.innerGlowMaterial.opacity = data.baseInnerOpacity * (0.86 + (pulse * 0.22));
      }
      if (data.outerGlowMaterial) {
        data.outerGlowMaterial.opacity = data.baseOuterOpacity * (0.88 + (pulse * 0.18));
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

      const scale = 1 + (t * VISUAL_CONFIG.bursts.scale);
      burst.scale.set(scale, scale, scale);

      if (burst.material) {
        burst.material.opacity = burst.userData.baseOpacity * Math.pow(1 - t, 1.35);
      }
    }
  }

  function applyContainment() {
    const radius = VISUAL_CONFIG.layout.containmentRadius;
    const pull = VISUAL_CONFIG.layout.containmentPull;
    const damping = VISUAL_CONFIG.layout.velocityDamping;

    graphData.nodes.forEach((node) => {
      if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || !Number.isFinite(node.z)) {
        return;
      }

      const dist = Math.sqrt((node.x * node.x) + (node.y * node.y) + (node.z * node.z));
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

  function frameLoop(nowMs) {
    const dtMs = Math.min(80, nowMs - cameraState.lastFrameTs);
    cameraState.lastFrameTs = nowMs;
    performanceState.runningMs += dtMs;

    updatePerformanceBudget(dtMs);
    updateAmbientMotion(dtMs);
    updateNodeBreathing(nowMs);
    updateEventBursts(dtMs);
    applyContainment();

    if (cameraState.cinematicEnabled && !cameraState.userInteracted) {
      updateCinematicCamera(dtMs, nowMs);
      scheduleLabelUpdate();
    }

    requestAnimationFrame(frameLoop);
  }

  function startFrameLoop() {
    if (cameraState.renderStarted) return;
    cameraState.renderStarted = true;
    cameraState.lastFrameTs = performance.now();
    requestAnimationFrame(frameLoop);
  }

  // ---- Fetch and initialization ----
  async function loadGraph() {
    const res = await fetch("/api/graph");
    graphData = await res.json();
    computeDerivedMetrics();
    initGraph();
    updateStats();
    loadHistory();
  }

  async function loadHistory() {
    const res = await fetch("/api/graph/history");
    const data = await res.json();
    historyEvents = data.events || [];

    if (historyEvents.length > 0) {
      const timestamps = historyEvents.map((e) => new Date(e.timestamp).getTime());
      timelineRange.min = Math.min(...timestamps);
      timelineRange.max = Math.max(...timestamps, Date.now());
    }

    updateTimelineLabel(1000);
  }

  function setupBloom() {
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
      VISUAL_CONFIG.bloom.threshold
    );
    composer.addPass(bloomPass);

    graph.postProcessingComposer(composer);
  }

  function initGraph() {
    graph = ForceGraph3D()(dom.graph)
      .graphData(graphData)
      .backgroundColor(VISUAL_CONFIG.background)
      .showNavInfo(false)
      .nodeRelSize(1)
      .nodeVal((node) => {
        if (node.type === "domain") return 40;
        return Math.max(3, 3 + ((node.__activityNormalized || 0) * 10));
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
        cameraState.hoveredNodeId = node ? node.id : null;
        scheduleLabelUpdate();
      })
      .d3Force("charge").strength((node) => {
        if (node.type === "domain") return -900;
        return -220;
      });

    graph.d3Force("link").distance((link) => {
      if (link.type === "cross") return 130;
      return 72;
    });

    const centerForce = graph.d3Force("center");
    if (centerForce && centerForce.x && centerForce.y && centerForce.z) {
      centerForce.x(0).y(0).z(0);
    }

    setupBloom();
    ensureEventBurstLayer();
    setupInputListeners();

    // Startup camera move for drama.
    graph.cameraPosition({ x: 0, y: 0, z: 860 }, { x: 0, y: 0, z: 0 }, 0);
    setTimeout(() => {
      graph.cameraPosition({ x: 0, y: 90, z: VISUAL_CONFIG.camera.defaultDistance }, { x: 0, y: 0, z: 0 }, 2400);
    }, 200);

    scheduleAmbientRebuild(1200);
    scheduleLabelUpdate();
    startFrameLoop();
  }

  // ---- Detail panel ----
  function updateDetailPanel(node, confidence, runCount, actionsHtml, tracesRows) {
    dom.detailTitle.textContent = node.type === "domain" ? node.domain : node.task;
    dom.detailDomain.textContent = node.type === "domain" ? "DOMAIN" : node.domain;

    dom.detailConfidenceBar.style.width = `${(confidence * 100).toFixed(2)}%`;
    dom.detailConfidenceBar.style.background =
      `linear-gradient(90deg, rgb(100, 105, 115) 0%, ${confidenceColor(confidence)} 100%)`;

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
    const ambientVisuals = VISUAL_CONFIG.ambient.pointsCount + VISUAL_CONFIG.ambient.linksCount;

    if (firstLoad) {
      animateValue(dom.statDomains, domains.length, 1200, false);
      animateValue(dom.statTasks, tasks.length, 1200, false);
      animateValue(dom.statRuns, totalRuns, 1800, false);
      animateValue(dom.statConfidence, Math.round(avgConfidence * 100), 1200, true);
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

    if (event.type === "node_added" || event.type === "node_updated" || event.type === "step_recorded") {
      refreshGraph().then(() => {
        const node = findNodeFromEvent(event);
        spawnBurstAtNode(node);
      });
    }
  }

  // ---- Graph refresh ----
  function refreshGraph() {
    if (refreshPending) return Promise.resolve();
    refreshPending = true;

    return new Promise((resolve) => {
      setTimeout(async () => {
        try {
          const res = await fetch("/api/graph");
          const newData = await res.json();

          const posMap = {};
          graphData.nodes.forEach((node) => {
            if (Number.isFinite(node.x) && Number.isFinite(node.y) && Number.isFinite(node.z)) {
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
              (d) => d.type === "domain" && d.domain === node.domain
            );

            if (domainNode && Number.isFinite(domainNode.x)) {
              node.x = domainNode.x + ((Math.random() - 0.5) * 20);
              node.y = domainNode.y + ((Math.random() - 0.5) * 20);
              node.z = domainNode.z + ((Math.random() - 0.5) * 20);
            }
          });

          graphData = newData;
          computeDerivedMetrics();

          graph.graphData(graphData);
          updateStats();

          if (currentTimeValue < 1000) {
            applyTimeFilter(currentTimeValue);
          }

          scheduleAmbientRebuild(450);
          scheduleLabelUpdate();
        } finally {
          refreshPending = false;
          resolve();
        }
      }, 260);
    });
  }

  // ---- Controls ----
  dom.btnSimulate.addEventListener("click", async () => {
    dom.btnSimulate.disabled = true;
    dom.btnSimulate.textContent = "RUNNING...";

    try {
      await fetch("/api/simulate", { method: "POST" });
      await refreshGraph();
    } catch (err) {
      console.error("Simulate failed:", err);
    }

    dom.btnSimulate.disabled = false;
    dom.btnSimulate.textContent = "Simulate Agent Run";
  });

  dom.chkAuto.addEventListener("change", async (evt) => {
    const action = evt.target.checked ? "start" : "stop";
    await fetch(`/api/auto-simulate/${action}`, { method: "POST" });
  });

  dom.detailClose.addEventListener("click", () => {
    dom.detailPanel.classList.remove("open");
  });

  // ---- Timeline ----
  dom.timelineSlider.addEventListener("input", () => {
    currentTimeValue = parseInt(dom.timelineSlider.value, 10);
    applyTimeFilter(currentTimeValue);
    updateTimelineLabel(currentTimeValue);

    if (isPlaying) togglePlay();
  });

  dom.timelinePlay.addEventListener("click", togglePlay);

  function togglePlay() {
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
    const ts = timelineRange.min + (t * (timelineRange.max - timelineRange.min));
    const date = new Date(ts);
    dom.timelineDate.textContent = value >= 1000 ? "LIVE" : date.toLocaleString();
  }

  function applyTimeFilter(value) {
    if (!historyEvents.length || !graph) return;

    const t = value / 1000;
    const cutoffTs = timelineRange.min + (t * (timelineRange.max - timelineRange.min));

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
          (task) => task.type === "task"
            && task.domain === node.domain
            && visibleTaskIds.has(task.id)
        );
        node.__visible = value >= 1000 || hasVisibleTasks;
      } else {
        node.__visible = value >= 1000 || visibleTaskIds.has(node.id);
        if (taskConfidence[node.id] !== undefined && value < 1000) {
          node.__displayConfidence = taskConfidence[node.id];
        } else {
          node.__displayConfidence = node.confidence;
        }
      }

      if (node.__threeObj) {
        node.__threeObj.visible = node.__visible !== false;
      }
    });

    graphData.links.forEach((link) => {
      const source = nodeById.get(safeNodeId(link.source));
      const target = nodeById.get(safeNodeId(link.target));
      link.__visible = (source?.__visible !== false) && (target?.__visible !== false);
    });

    graph
      .nodeVisibility((node) => node.__visible !== false)
      .linkVisibility((link) => link.__visible !== false);

    scheduleLabelUpdate();
  }

  // ---- Boot ----
  loadGraph().then(() => {
    connectWS();
  });
})();

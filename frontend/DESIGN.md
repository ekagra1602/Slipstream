# DomBot Frontend — Obsidian Route Atlas (Living Design Doc)

Last updated: 2026-03-01

This document is now the iteration baseline for the cinematic "routing brain for web agents" frontend. It captures what is currently implemented and what we should change next.

---

## 1. Product Framing

DomBot is a live route-optimization brain for web agents:
- Like Waze for browser workflows.
- Real run history is the truth layer.
- Ambient visuals provide internet-scale context without claiming fake truth.

Narrative priorities:
1. Reliability is the primary signal.
2. Continuous network motion implies a living system.
3. Viewers can distinguish real data from ambient cinematic density.

---

## 2. Current Baseline (Implemented)

### 2.1 Visual language
- Monochromatic obsidian/industrial palette is active.
- Confidence color mapping is cool-gray to warm amber-gray:
  - low `rgb(100, 105, 115)`
  - mid `rgb(140, 138, 130)`
  - high `rgb(180, 165, 130)`
- Domain nodes are wireframe silver-gray with subtle white fill.
- Link/particle styling is restrained and non-neon.
- Branding subtitle is `LIVE ROUTING BRAIN // OPTIMIZING`.

### 2.2 Motion and camera
- Cinematic mode toggle exists (`#btn-cinematic`).
- Guided orbit is enabled by default and disables on user interaction.
- Cursor-aware dolly zoom is implemented.
- Event bursts render on websocket updates and self-dispose.

### 2.3 Scale strategy
- Truth layer: real graph data from `/api/graph`.
- Ambient layer: visual-only points/links for scale.
- Stats panel exposes:
  - `Real Nodes`
  - `Ambient Visuals`

### 2.4 Topology/data rebalance
- Domains are canonicalized (`www.*` collapsed, root-domain normalization).
- Reseed produces balanced volume:
  - 10 canonical domains
  - 100 tasks/domain
  - 1000 task nodes (+10 domain nodes)
- Truth graph is centered with containment guard to reduce off-screen drift.
- Connected-component target is met via shared action signatures.

---

## 3. Design Constraints (Do Not Break)

1. No backend API contract changes (`/api/graph`, `/api/graph/history`, `/api/simulate`, `/api/auto-simulate/*`).
2. No layout repositioning of existing panels.
3. No regressions in:
   - node click -> detail panel
   - timeline replay/filtering
   - websocket refresh behavior
   - simulate/auto-simulate controls
4. Keep visual distinction between truth and ambient layers explicit.

---

## 4. Current Tunables (Source of Truth)

Primary tuning surface: `VISUAL_CONFIG` in `frontend/app.js`

Key groups:
- `confidence` (color interpolation)
- `links` and `particles` (readability vs subtlety)
- `ambient` (point/link counts and opacity)
- `camera` (cinematic and manual navigation feel)
- `layout` (containment radius/pull/damping)
- `performance` (adaptive degradation and recovery)

---

## 5. Iteration Backlog (Next Pass)

### 5.1 Network shape polish
Goal: more "Obsidian-like" global structure while preserving truth.
- Add mild radial shell bias for domain anchors.
- Reduce perceived lopsidedness under high activity skew.
- Keep center of mass near origin during long runtime.

### 5.2 Readability in dense scenes
Goal: retain wow without label clutter.
- Add confidence-weighted label priority (in addition to activity/distance).
- Soften low-priority task labels earlier at far zoom.

### 5.3 Reliability storytelling
Goal: make route quality legible in 3 seconds.
- Add optional legend chip for confidence temperature.
- Add quick CTA text near branding for "real routes vs ambient context."

### 5.4 Performance guardrails
Goal: maintain smooth demo FPS on 1080p laptop hardware.
- Make ambient entity budget adaptive, not just opacity.
- Cap event bursts spawned per second.

---

## 6. Verification Checklist (Per Iteration)

1. Static checks
- No cyan/neon literals introduced in `frontend/style.css` or `frontend/app.js`.
- `VISUAL_CONFIG` remains single source for visual constants.

2. Data/topology checks
- Reseed: `./venv/bin/python frontend/seed_data.py`
- Validate: `node scripts/check_graph_topology.js`
- Expect:
  - ~1000 task nodes
  - 10 domain nodes
  - no `www.*` domains
  - dominant connected component >95%

3. Runtime checks
- Start server: `./venv/bin/python -m uvicorn frontend.server:app --port 8000`
- Confirm:
  - centered truth graph (no persistent far-off islands)
  - real-vs-ambient stats are visible and accurate
  - node click, timeline, simulate, websocket updates still work

---

## 7. File Ownership

| File | Responsibility |
|------|----------------|
| `frontend/style.css` | Atmosphere, panel/control styling, non-neon visual language |
| `frontend/app.js` | 3D rendering, motion/camera, truth-vs-ambient logic, stats wiring |
| `frontend/index.html` | Fixed UI structure + control/stat slots |
| `frontend/seed_data.py` | Balanced demo truth dataset generation |
| `dombot/domain_utils.py` | Canonical domain normalization rules |
| `scripts/check_graph_topology.js` | Non-mutating topology sanity checks |

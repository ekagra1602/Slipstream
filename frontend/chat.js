/* ================================================================
   Slipstream Chat — Warp-speed entrance + glassmorphic modal
   ================================================================ */

(function () {
  "use strict";

  const runtimeParams = new window.URLSearchParams(window.location.search);
  const demoMockEnabled = runtimeParams.get("demoMock") === "1";

  const askBar = document.getElementById("ask-bar");
  const askInput = document.getElementById("ask-input");
  const warpCanvas = document.getElementById("warp-canvas");
  const chatBackdrop = document.getElementById("chat-backdrop");
  const chatModal = document.getElementById("chat-modal");
  const chatClose = document.getElementById("chat-close");
  const chatMessages = document.getElementById("chat-messages");
  const chatInput = document.getElementById("chat-input");
  const chatSend = document.getElementById("chat-send");

  if (
    !askBar ||
    !askInput ||
    !warpCanvas ||
    !chatBackdrop ||
    !chatModal ||
    !chatClose ||
    !chatMessages ||
    !chatInput ||
    !chatSend
  ) {
    return;
  }

  if (!demoMockEnabled) {
    askBar.style.display = "none";
    return;
  }

  const ctx = warpCanvas.getContext("2d");
  if (!ctx) return;

  let isOpen = false;
  let warpAnimId = null;

  // ---- Warp-speed star field ----
  const STAR_COUNT = 600;
  const stars = [];

  function resizeCanvas() {
    warpCanvas.width = window.innerWidth;
    warpCanvas.height = window.innerHeight;
  }
  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();

  function initStars() {
    stars.length = 0;
    for (let i = 0; i < STAR_COUNT; i += 1) {
      stars.push({
        x: (Math.random() - 0.5) * warpCanvas.width * 2,
        y: (Math.random() - 0.5) * warpCanvas.height * 2,
        z: Math.random() * 1500 + 500,
        pz: 0,
      });
    }
  }

  function drawWarp(speed) {
    const w = warpCanvas.width;
    const h = warpCanvas.height;
    const cx = w / 2;
    const cy = h / 2;

    ctx.fillStyle = "rgba(10, 10, 12, 0.15)";
    ctx.fillRect(0, 0, w, h);

    stars.forEach((star) => {
      star.pz = star.z;
      star.z -= speed;

      if (star.z <= 0) {
        star.x = (Math.random() - 0.5) * w * 2;
        star.y = (Math.random() - 0.5) * h * 2;
        star.z = 1500;
        star.pz = 1500;
      }

      const sx = (star.x / star.z) * 300 + cx;
      const sy = (star.y / star.z) * 300 + cy;
      const px = (star.x / star.pz) * 300 + cx;
      const py = (star.y / star.pz) * 300 + cy;
      const brightness = Math.min(1, (1500 - star.z) / 1000);
      const alpha = brightness * 0.9;

      const r = 180 + Math.floor(brightness * 40);
      const g = 165 + Math.floor(brightness * 30);
      const b = 130 + Math.floor(brightness * 20);

      ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
      ctx.lineWidth = brightness * 2;
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(sx, sy);
      ctx.stroke();

      if (brightness > 0.6) {
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha * 0.5})`;
        ctx.beginPath();
        ctx.arc(sx, sy, brightness * 1.5, 0, Math.PI * 2);
        ctx.fill();
      }
    });
  }

  // ---- Warp animation sequence ----
  function playWarpEntrance(callback) {
    warpCanvas.classList.remove("chat-hidden");
    initStars();

    ctx.fillStyle = "rgba(10, 10, 12, 1)";
    ctx.fillRect(0, 0, warpCanvas.width, warpCanvas.height);

    let frame = 0;
    const totalFrames = 45;
    const easeOut = (t) => 1 - Math.pow(1 - t, 3);

    function animate() {
      frame += 1;
      const t = Math.min(frame / totalFrames, 1);
      const easedT = easeOut(t);
      const speed = 20 + easedT * 60;
      drawWarp(speed);

      if (t < 1) {
        warpAnimId = requestAnimationFrame(animate);
        return;
      }

      let holdFrames = 0;
      function holdAndFade() {
        holdFrames += 1;
        drawWarp(40 - holdFrames * 2);
        if (holdFrames < 12) {
          warpAnimId = requestAnimationFrame(holdAndFade);
          return;
        }
        if (typeof callback === "function") callback();
        fadeOutWarp();
      }
      warpAnimId = requestAnimationFrame(holdAndFade);
    }
    warpAnimId = requestAnimationFrame(animate);
  }

  function fadeOutWarp() {
    let opacity = 1;
    function fade() {
      opacity -= 0.06;
      warpCanvas.style.opacity = Math.max(0, opacity);
      if (opacity > 0) {
        warpAnimId = requestAnimationFrame(fade);
        return;
      }
      warpCanvas.classList.add("chat-hidden");
      warpCanvas.style.opacity = "";
      if (warpAnimId) cancelAnimationFrame(warpAnimId);
      warpAnimId = null;
    }
    warpAnimId = requestAnimationFrame(fade);
  }

  // ---- Open / Close ----
  function openChat(initialQuery) {
    if (isOpen) return;
    isOpen = true;

    playWarpEntrance(() => {});
    setTimeout(() => {
      chatBackdrop.classList.remove("chat-hidden");
      chatModal.classList.remove("chat-hidden");
    }, 400);

    chatMessages.innerHTML = "";
    if (initialQuery) {
      setTimeout(() => {
        addMessage("user", initialQuery);
        sendToBackend(initialQuery);
      }, 600);
    }

    setTimeout(() => chatInput.focus(), 700);
  }

  function closeChat() {
    if (!isOpen) return;
    isOpen = false;
    chatModal.classList.add("chat-hidden");
    chatBackdrop.classList.add("chat-hidden");
    warpCanvas.classList.add("chat-hidden");
    if (warpAnimId) {
      cancelAnimationFrame(warpAnimId);
      warpAnimId = null;
    }
  }

  // ---- Messages ----
  function addMessage(role, text) {
    const div = document.createElement("div");
    div.className = `chat-msg ${role}`;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
  }

  function addThinking() {
    const div = document.createElement("div");
    div.className = "chat-msg thinking";
    div.textContent = "Querying knowledge base";
    div.id = "chat-thinking";
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function removeThinking() {
    const el = document.getElementById("chat-thinking");
    if (el) el.remove();
  }

  function buildChatRequest(query) {
    const sourceGetter = window.__slipstreamGetDataSource;
    const snapshotGetter = window.__slipstreamGetAnDemoSnapshot;

    const source =
      typeof sourceGetter === "function" ? sourceGetter() : "demoMock";
    const demoSnapshot =
      source === "demoMock" && typeof snapshotGetter === "function"
        ? snapshotGetter()
        : null;

    return {
      message: query,
      source,
      demoSnapshot,
    };
  }

  // ---- Backend call ----
  async function sendToBackend(query) {
    addThinking();
    const minDelay = new Promise((resolve) => setTimeout(resolve, 800));

    try {
      const [, res] = await Promise.all([
        minDelay,
        fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildChatRequest(query)),
        }),
      ]);

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      removeThinking();
      addMessage("assistant", data.reply || "No response.");
    } catch (err) {
      removeThinking();
      addMessage(
        "assistant",
        "Could not reach insights backend. Verify frontend server is running.",
      );
    }
  }

  // ---- Event listeners ----
  askInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && askInput.value.trim()) {
      const initialQuery = askInput.value.trim();
      askInput.value = "";
      askInput.blur();
      openChat(initialQuery);
    }
  });

  chatClose.addEventListener("click", closeChat);
  chatBackdrop.addEventListener("click", closeChat);

  chatSend.addEventListener("click", () => {
    const value = chatInput.value.trim();
    if (!value) return;
    addMessage("user", value);
    chatInput.value = "";
    sendToBackend(value);
  });

  chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && chatInput.value.trim()) {
      chatSend.click();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen) closeChat();
  });
})();

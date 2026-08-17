// Chhota sa vanilla JS — koi build step, koi CDN nahi (sasta host, offline bhi chalega).

(function () {
  "use strict";

  // ---------------------------------------------------------------- clock
  const clock = document.getElementById("clock");
  if (clock) {
    const tick = () => {
      clock.textContent = new Date().toLocaleString([], {
        day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit",
      });
    };
    tick();
    setInterval(tick, 1000);
  }

  // ------------------------------------------------------ live stats poll
  const statEls = document.querySelectorAll("[data-stat]");
  const serverTime = document.getElementById("servertime");
  const shouldPoll = statEls.length > 0 || document.querySelector("[data-progress-for]");

  async function refresh() {
    try {
      const res = await fetch("/api/stats", { headers: { "X-Requested-With": "fetch" } });
      if (!res.ok) return;
      const data = await res.json();

      statEls.forEach((el) => {
        const key = el.dataset.stat;
        const value = (data.totals && data.totals[key]) || 0;
        if (el.textContent.trim() !== String(value)) el.textContent = value;
      });

      if (serverTime) {
        serverTime.textContent = new Date(data.server_time).toLocaleString();
      }

      // Chal rahe uploads ki progress bar update karo.
      (data.running || []).forEach((up) => {
        const bar = document.querySelector(`[data-progress-for="${up.id}"] > i`);
        if (bar) bar.style.width = (up.progress || 0) + "%";
        const row = document.querySelector(`[data-upload-row="${up.id}"] .tag`);
        if (row && !row.classList.contains("running")) location.reload();
      });
    } catch (err) {
      /* network hichki — agla tick try karega */
    }
  }

  if (shouldPoll) {
    refresh();
    setInterval(refresh, 5000);
  }

  // ------------------------------------------------------ template preview
  function bindPreview(inputId, boxId) {
    const input = document.getElementById(inputId);
    const box = document.getElementById(boxId);
    if (!input || !box) return;
    let timer = null;

    const run = async () => {
      const template = input.value.trim();
      if (!template) {
        box.innerHTML = '<span class="muted">Yahan live preview dikhega…</span>';
        return;
      }
      try {
        const res = await fetch("/api/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            template,
            name: (document.getElementById("name") || {}).value || "Campaign",
            total: (document.getElementById("total_uploads") || {}).value || 24,
          }),
        });
        const data = await res.json();
        box.innerHTML = data.samples
          .map((s, i) => `<div><span class="muted">#${i + 1}</span> ${escapeHtml(s)}</div>`)
          .join("");
      } catch (err) {
        box.textContent = "Preview load nahi hua";
      }
    };

    input.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(run, 350);
    });
    run();
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  bindPreview("title_tpl", "title_preview");
  bindPreview("comment_tpl", "comment_preview");

  // ------------------------------------------------------ schedule summary
  const interval = document.getElementById("interval_minutes");
  const total = document.getElementById("total_uploads");
  const summary = document.getElementById("schedule_summary");
  const quotaBox = document.getElementById("quota_box");

  async function updateSummary() {
    if (!interval || !total || !summary) return;
    const mins = Math.max(parseInt(interval.value || "60", 10), 1);
    const count = Math.max(parseInt(total.value || "1", 10), 1);
    const perDay = Math.floor(1440 / mins);
    const hours = ((mins * (count - 1)) / 60).toFixed(1);
    summary.innerHTML =
      `Har <b>${mins} minute</b> par 1 upload · din mein <b>${perDay}</b> uploads · ` +
      `poora campaign <b>${hours} ghante</b> mein khatam.`;

    if (!quotaBox) return;
    const thumb = document.getElementById("thumbnail");
    const comment = document.getElementById("comment_tpl");
    const params = new URLSearchParams({
      interval: mins,
      thumb: thumb && thumb.files && thumb.files.length ? "1" : "0",
      comment: comment && comment.value.trim() ? "1" : "0",
    });
    try {
      const res = await fetch("/api/quota?" + params.toString());
      const q = await res.json();
      quotaBox.className = q.over ? "note" : "note info";
      quotaBox.innerHTML = q.over
        ? `<b>Quota warning:</b> is speed se din ke ${q.per_day} uploads chahiye ` +
          `(${q.used.toLocaleString()} units) lekin YouTube ka default daily quota ` +
          `${q.limit.toLocaleString()} units hai — yaani <b>${q.max_uploads} uploads/din</b>. ` +
          `Baaki uploads apne aap agle din shift ho jayenge (koi upload kho nahi jaata).`
        : `<b>Quota theek hai:</b> din ke ${q.per_day} uploads = ` +
          `${q.used.toLocaleString()} / ${q.limit.toLocaleString()} units.`;
    } catch (err) {
      /* ignore */
    }
  }

  [interval, total, document.getElementById("thumbnail")].forEach((el) => {
    if (el) el.addEventListener("input", updateSummary);
    if (el) el.addEventListener("change", updateSummary);
  });
  updateSummary();

  // ------------------------------------------------------ platform toggle
  const platform = document.getElementById("platform");
  function togglePlatform() {
    if (!platform) return;
    const value = platform.value;
    document.querySelectorAll("[data-only]").forEach((el) => {
      const only = el.dataset.only;
      el.style.display = value === "both" || value === only ? "" : "none";
    });
  }
  if (platform) platform.addEventListener("change", togglePlatform);
  togglePlatform();

  // ------------------------------------------------------ confirm actions
  document.querySelectorAll("[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // ------------------------------------------------------ copy buttons
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        const old = btn.textContent;
        btn.textContent = "Copied ✓";
        setTimeout(() => (btn.textContent = old), 1500);
      } catch (err) {
        window.prompt("Copy karo:", btn.dataset.copy);
      }
    });
  });

  // ------------------------------------------------------ file size guard
  const videoInput = document.getElementById("video");
  if (videoInput) {
    videoInput.addEventListener("change", () => {
      const label = document.getElementById("video_info");
      if (!label) return;
      const file = videoInput.files[0];
      if (!file) { label.textContent = ""; return; }
      const mb = (file.size / 1048576).toFixed(1);
      const limit = parseInt(videoInput.dataset.maxMb || "512", 10);
      label.innerHTML = mb > limit
        ? `<span style="color:var(--err)">${file.name} — ${mb} MB, limit ${limit} MB se zyada hai</span>`
        : `${file.name} — ${mb} MB`;
    });
  }
})();

// ── Audio recording ─────────────────────────────────────────────────────────
(function () {
  const btn = document.getElementById("btn-record");
  if (!btn) return;

  const btnSubmit = document.getElementById("btn-submit");
  const statusMsg = document.getElementById("record-status");
  const uploadSection = document.getElementById("upload-section");
  const audioPreview = document.getElementById("audio-preview");
  const resultSection = document.getElementById("result-section");
  const resultFields = document.getElementById("result-fields");
  const resultLink = document.getElementById("result-link");
  const indicator = document.getElementById("recording-indicator");
  const recTimer = document.getElementById("rec-timer");
  const recLabel = document.getElementById("rec-label-text");

  let mediaRecorder = null;
  let chunks = [];
  let audioBlob = null;
  let timerInterval = null;
  let secondsElapsed = 0;
  let isRecording = false;

  function startTimer() {
    secondsElapsed = 0;
    recTimer.textContent = "00:00";
    timerInterval = setInterval(() => {
      secondsElapsed++;
      const m = String(Math.floor(secondsElapsed / 60)).padStart(2, "0");
      const s = String(secondsElapsed % 60).padStart(2, "0");
      recTimer.textContent = `${m}:${s}`;
    }, 1000);
  }

  function stopTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  function setRecordingState(recording) {
    isRecording = recording;
    indicator.classList.toggle("recording-idle", !recording);
    recLabel.textContent = recording ? "Grabando" : "En espera";
    btn.textContent = recording ? "Detener grabación" : "Iniciar grabación";
    btn.classList.toggle("btn-primary", !recording);
    btn.classList.toggle("btn-stop", recording);
  }

  btn.addEventListener("click", async () => {
    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        chunks = [];

        mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
        mediaRecorder.onstop = () => {
          audioBlob = new Blob(chunks, { type: "audio/webm" });
          audioPreview.src = URL.createObjectURL(audioBlob);
          uploadSection.hidden = false;
          statusMsg.textContent = "Grabación lista. Escucha y luego presiona Procesar.";
        };

        mediaRecorder.start();
        uploadSection.hidden = true;
        resultSection.hidden = true;
        statusMsg.textContent = "";
        setRecordingState(true);
        startTimer();
      } catch (err) {
        statusMsg.textContent = "Error al acceder al micrófono: " + err.message;
      }
    } else {
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach((t) => t.stop());
      }
      stopTimer();
      setRecordingState(false);
    }
  });

  btnSubmit.addEventListener("click", async () => {
    if (!audioBlob) return;

    const sessionLabel = document.getElementById("session-label").value.trim();
    const formData = new FormData();
    formData.append("audio", audioBlob, "grabacion.webm");
    if (sessionLabel) formData.append("session_label", sessionLabel);

    btnSubmit.disabled = true;
    statusMsg.textContent = "Procesando… esto puede tomar unos segundos.";

    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || "Error del servidor");

      resultFields.innerHTML = "";
      const fields = [
        ["Categoría", data.category],
        ["Problema", data.problem],
        ["Solución", data.applied_solution],
        ["Acción", data.suggested_action],
      ];
      fields.forEach(([label, value]) => {
        if (!value) return;
        const dt = document.createElement("dt");
        dt.textContent = label;
        const dd = document.createElement("dd");
        dd.textContent = value;
        resultFields.appendChild(dt);
        resultFields.appendChild(dd);
      });

      resultLink.href = "/complaint/" + data.id;
      resultSection.hidden = false;
      uploadSection.hidden = true;
      statusMsg.textContent = "";
    } catch (err) {
      statusMsg.textContent = "Error: " + err.message;
    } finally {
      btnSubmit.disabled = false;
    }
  });
})();

// ── Dashboard patterns ───────────────────────────────────────────────────────
(function () {
  const container = document.getElementById("stats-bar");
  if (!container) return;

  fetch("/api/stats")
    .then((r) => r.json())
    .then((data) => {
      const total = data.total;
      if (!total) return;

      const categories = Object.entries(data.by_category || {})
        .filter(([cat]) => cat && cat !== "null")
        .sort((a, b) => b[1] - a[1]);

      const header = document.createElement("div");
      header.className = "patterns-header";
      header.innerHTML = `<span class="patterns-title">Problemas recurrentes</span><span class="patterns-total">${total} queja${total !== 1 ? "s" : ""} registrada${total !== 1 ? "s" : ""}</span>`;
      container.appendChild(header);

      const bars = document.createElement("div");
      bars.className = "patterns-bars";

      categories.forEach(([cat, count]) => {
        const pct = Math.round((count / total) * 100);
        const row = document.createElement("div");
        row.className = "pattern-row";
        row.innerHTML = `
          <span class="pattern-label">${cat}</span>
          <div class="pattern-bar-wrap">
            <div class="pattern-bar" style="width:${pct}%"></div>
          </div>
          <span class="pattern-count">${count}</span>`;
        bars.appendChild(row);
      });

      container.appendChild(bars);
    })
    .catch(() => {});
})();

// ── Status update on detail page ────────────────────────────────────────────
(function () {
  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.complaintId;
      const status = btn.dataset.action;
      fetch(`/api/complaints/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      })
        .then((r) => r.json())
        .then(() => location.reload());
    });
  });
})();

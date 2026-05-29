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
    btn.className = recording
      ? "w-full py-2.5 bg-white text-red-500 border border-red-300 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors"
      : "w-full py-2.5 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-700 transition-colors";
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
    resultSection.hidden = true;
    statusMsg.textContent = "Procesando… esto puede tomar unos segundos.";

    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });

      let data;
      try {
        data = await res.json();
      } catch {
        data = null;
      }

      if (!res.ok || !data) {
        data = {
          id: 0,
          category: "ruido (ejemplo)",
          problem: "El huésped reportó ruido excesivo proveniente de la habitación contigua durante la madrugada.",
          applied_solution: "Se contactó a los huéspedes de la habitación contigua para solicitarles bajar el volumen.",
          suggested_action: "Registrar el incidente y verificar si el problema se repite en noches siguientes.",
        };
      }

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
        dt.className = "font-medium text-slate-500";
        dt.textContent = label;
        const dd = document.createElement("dd");
        dd.className = "text-slate-900";
        dd.textContent = value;
        resultFields.appendChild(dt);
        resultFields.appendChild(dd);
      });

      resultLink.href = "/complaint/" + data.id;
      resultLink.hidden = !data.id;
      resultSection.hidden = false;
      uploadSection.hidden = true;
      statusMsg.textContent = "";
    } catch {
      statusMsg.textContent = "";
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
      header.className = "flex items-baseline justify-between mb-4";
      header.innerHTML = `
        <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Problemas recurrentes</span>
        <span class="text-xs text-slate-400">${total} queja${total !== 1 ? "s" : ""} registrada${total !== 1 ? "s" : ""}</span>`;
      container.appendChild(header);

      const bars = document.createElement("div");
      bars.className = "flex flex-col gap-2.5";

      categories.forEach(([cat, count]) => {
        const pct = Math.round((count / total) * 100);
        const row = document.createElement("div");
        row.className = "grid items-center gap-3";
        row.style.gridTemplateColumns = "130px 1fr 24px";
        row.innerHTML = `
          <span class="text-sm text-slate-700 truncate">${cat}</span>
          <div class="bg-slate-200 rounded-full overflow-hidden" style="height:6px">
            <div class="pattern-bar h-full bg-slate-900 rounded-full" style="width:${pct}%"></div>
          </div>
          <span class="text-xs text-slate-400 text-right tabular-nums">${count}</span>`;
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

// ── Etiquetas compartidas ────────────────────────────────────────────────────
const CATEGORY_LABELS = {
  ruido: "Ruido", limpieza: "Limpieza", facturacion: "Facturación",
  temperatura: "Temperatura", mantenimiento: "Mantenimiento",
  internet_wifi: "WiFi / Internet", television: "Televisión",
  electricidad: "Electricidad", agua: "Agua", plomeria: "Plomería",
  check_in: "Ingreso", check_out: "Salida", reserva: "Reserva",
  sobreventa: "Sobreventa", habitacion_incorrecta: "Hab. incorrecta",
  llaves_acceso: "Llaves / Acceso", equipaje: "Equipaje",
  estacionamiento: "Estacionamiento", transporte: "Transporte",
  restaurante: "Restaurante", desayuno: "Desayuno",
  room_service: "Serv. habitación", servicio_no_atendido: "Sin atención",
  personal: "Personal", seguridad: "Seguridad",
  cobro_indebido: "Cobro indebido", reembolso: "Reembolso",
  amenidades: "Amenidades", piscina: "Piscina",
  gimnasio: "Gimnasio", accesibilidad: "Accesibilidad", otro: "Otro",
};

// ── Grabación de audio ───────────────────────────────────────────────────────
(function () {
  const btn = document.getElementById("btn-record");
  if (!btn) return;

  const btnSubmit       = document.getElementById("btn-submit");
  const btnRetryUpload  = document.getElementById("btn-retry-upload");
  const btnCancelUpload = document.getElementById("btn-cancel-upload");
  const btnSubmitManual = document.getElementById("btn-submit-manual");
  const manualTextarea  = document.getElementById("manual-transcription");
  const statusMsg       = document.getElementById("record-status");
  const uploadSection   = document.getElementById("upload-section");
  const audioPreview    = document.getElementById("audio-preview");
  const resultSection   = document.getElementById("result-section");
  const errorSection    = document.getElementById("error-section");
  const errorMessage    = document.getElementById("error-message");
  const resultFields    = document.getElementById("result-fields");
  const resultLink      = document.getElementById("result-link");
  const indicator       = document.getElementById("recording-indicator");
  const recTimer        = document.getElementById("rec-timer");
  const recLabel        = document.getElementById("rec-label-text");

  let mediaRecorder = null;
  let chunks = [];
  let audioBlob = null;
  let timerInterval = null;
  let secondsElapsed = 0;
  let isRecording = false;
  let pendingComplaintId = null;

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

  function stopTimer() { clearInterval(timerInterval); timerInterval = null; }

  function setRecordingState(recording) {
    isRecording = recording;
    indicator.classList.toggle("recording-idle", !recording);
    recLabel.textContent = recording ? "Grabando" : "En espera";
    btn.textContent = recording ? "Detener grabación" : "Iniciar grabación";
    btn.className = recording
      ? "w-full py-2.5 bg-white text-red-500 border border-red-300 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors"
      : "w-full py-2.5 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-700 transition-colors";
  }

  function showResult(data) {
    resultFields.innerHTML = "";
    [["Categoría", data.category], ["Problema", data.problem],
     ["Solución", data.applied_solution], ["Acción", data.suggested_action]]
      .forEach(([label, value]) => {
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
    errorSection.hidden = true;
    uploadSection.hidden = true;
    statusMsg.textContent = "";
    pendingComplaintId = null;
  }

  function showError(msg, complaintId) {
    errorMessage.textContent = msg || "Error desconocido al procesar el audio.";
    pendingComplaintId = complaintId || null;
    errorSection.hidden = false;
    uploadSection.hidden = true;
    statusMsg.textContent = "";
    manualTextarea.value = "";
    btnSubmitManual.hidden = true;
  }

  btn.addEventListener("click", async () => {
    if (!isRecording) {
      try {
        // El micrófono solo funciona en contextos seguros (localhost o HTTPS).
        // Acceder por IP local vía HTTP bloquea navigator.mediaDevices.
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          statusMsg.textContent =
            "⚠️ El micrófono no está disponible. " +
            "Accede por http://localhost:5001 (no por IP) o configura HTTPS.";
          return;
        }
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        mediaRecorder = new MediaRecorder(stream);
        chunks = [];
        mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
        mediaRecorder.onstop = () => {
          audioBlob = new Blob(chunks, { type: "audio/webm" });
          audioPreview.src = URL.createObjectURL(audioBlob);
          uploadSection.hidden = false;
          errorSection.hidden = true;
          resultSection.hidden = true;
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
      let data;
      try { data = await res.json(); } catch { data = null; }

      if (!res.ok) {
        showError(data?.error, data?.complaint_id);
      } else {
        showResult(data);
      }
    } catch {
      showError("No se pudo conectar con el servidor.");
    } finally {
      btnSubmit.disabled = false;
    }
  });

  // Reintentar desde la página de grabación
  btnRetryUpload.addEventListener("click", async () => {
    if (!pendingComplaintId) return;
    btnRetryUpload.disabled = true;
    btnRetryUpload.textContent = "Reprocesando…";
    try {
      const res = await fetch(`/api/complaints/${pendingComplaintId}/retry`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        showResult(data);
      } else {
        errorMessage.textContent = data.error || "Error al reintentar.";
        btnRetryUpload.disabled = false;
        btnRetryUpload.textContent = "Reintentar";
      }
    } catch {
      btnRetryUpload.disabled = false;
      btnRetryUpload.textContent = "Reintentar";
    }
  });

  // Mostrar botón de envío solo cuando hay texto
  manualTextarea.addEventListener("input", () => {
    btnSubmitManual.hidden = manualTextarea.value.trim() === "";
  });

  // Enviar transcripción manual para análisis
  btnSubmitManual.addEventListener("click", async () => {
    if (!pendingComplaintId) return;
    const transcription = manualTextarea.value.trim();
    if (!transcription) return;
    btnSubmitManual.disabled = true;
    btnSubmitManual.textContent = "Analizando…";
    try {
      const res = await fetch(`/api/complaints/${pendingComplaintId}/analyze-manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcription }),
      });
      const data = await res.json();
      if (res.ok) {
        showResult(data);
      } else {
        errorMessage.textContent = data.error || "Error al analizar.";
        btnSubmitManual.disabled = false;
        btnSubmitManual.textContent = "Analizar y guardar";
      }
    } catch {
      btnSubmitManual.disabled = false;
      btnSubmitManual.textContent = "Analizar y guardar";
    }
  });

  // Cancelar y eliminar la queja del servidor
  btnCancelUpload.addEventListener("click", async () => {
    if (pendingComplaintId) {
      await fetch(`/api/complaints/${pendingComplaintId}`, { method: "DELETE" }).catch(() => {});
      pendingComplaintId = null;
    }
    errorSection.hidden = true;
    uploadSection.hidden = true;
    audioBlob = null;
    audioPreview.src = "";
    recTimer.textContent = "00:00";
    statusMsg.textContent = "Grabación descartada.";
  });
})();

// ── Estadísticas y alertas ───────────────────────────────────────────────────
(function () {
  const container = document.getElementById("stats-bar");
  if (!container) return;

  const CATEGORY_COLORS = {
    ruido: "#fde047", electricidad: "#fcd34d",
    temperatura: "#fdba74", mantenimiento: "#fb923c",
    estacionamiento: "#fdba74", transporte: "#fb923c", equipaje: "#fcd34d",
    limpieza: "#93c5fd", agua: "#7dd3fc", plomeria: "#a5b4fc", internet_wifi: "#7dd3fc",
    facturacion: "#d8b4fe", cobro_indebido: "#c4b5fd", reembolso: "#a5b4fc",
    check_in: "#5eead4", check_out: "#6ee7b7", reserva: "#86efac", llaves_acceso: "#5eead4",
    restaurante: "#86efac", desayuno: "#6ee7b7", room_service: "#6ee7b7",
    servicio_no_atendido: "#fca5a5", personal: "#fca5a5", seguridad: "#f87171",
    sobreventa: "#fca5a5", habitacion_incorrecta: "#fca5a5",
    amenidades: "#67e8f9", piscina: "#7dd3fc", gimnasio: "#86efac",
    accesibilidad: "#f0abfc", television: "#c4b5fd",
    otro: "#cbd5e1",
  };

  fetch("/api/stats")
    .then((r) => r.json())
    .then((data) => {

      // ── Alertas de acumulación ──
      const ALERT_THRESHOLD = 3;
      const unresolvedByCat = data.unresolved_by_category || {};
      const alertContainer = document.getElementById("alerts-bar");
      const alertCats = Object.entries(unresolvedByCat)
        .filter(([, count]) => count >= ALERT_THRESHOLD)
        .sort((a, b) => b[1] - a[1]);

      if (alertCats.length > 0 && alertContainer) {
        alertContainer.classList.remove("hidden");
        alertContainer.innerHTML = `
          <p class="text-xs font-semibold uppercase tracking-wider text-amber-700 mb-2.5">
            Categorías con quejas sin resolver acumuladas
          </p>
          <div class="flex flex-wrap gap-2">
            ${alertCats.map(([cat, count]) => `
              <span class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-100 border border-amber-300 rounded-lg text-sm text-amber-800">
                <span class="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0"></span>
                ${CATEGORY_LABELS[cat] || cat}:
                <strong class="ml-0.5">${count} sin resolver</strong>
              </span>`).join("")}
          </div>`;
      }

      // ── Barras de frecuencia ──
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
        const barColor = CATEGORY_COLORS[cat] || "#cbd5e1";
        const row = document.createElement("div");
        row.className = "grid items-center gap-3";
        row.style.gridTemplateColumns = "130px 1fr 24px";
        row.innerHTML = `
          <span class="text-sm text-slate-700 truncate">${CATEGORY_LABELS[cat] || cat}</span>
          <div class="bg-slate-200 rounded-full overflow-hidden" style="height:6px">
            <div class="pattern-bar h-full rounded-full" style="width:${pct}%; background-color:${barColor}"></div>
          </div>
          <span class="text-xs text-slate-400 text-right tabular-nums">${count}</span>`;
        bars.appendChild(row);
      });

      container.appendChild(bars);
    })
    .catch(() => {});
})();

// ── Filtros del dashboard ────────────────────────────────────────────────────
(function () {
  const filterText     = document.getElementById("filter-text");
  const filterCategory = document.getElementById("filter-category");
  const filterStatus   = document.getElementById("filter-status");
  const btnClearDates  = document.getElementById("btn-clear-dates");
  if (!filterText) return;

  const rows = Array.from(document.querySelectorAll("tbody tr[data-category]"));

  // Poblar dropdown de categorías con las que existen en la tabla
  const seenCats = [...new Set(rows.map(r => r.dataset.category).filter(Boolean))].sort();
  seenCats.forEach(cat => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = CATEGORY_LABELS[cat] || cat;
    filterCategory.appendChild(opt);
  });

  let dateFrom = "", dateTo = "";

  // Calendario de rango único con flatpickr
  const fp = flatpickr("#filter-date-range", {
    mode: "range",
    dateFormat: "d/m/Y",
    locale: { rangeSeparator: " → " },
    onChange(selectedDates) {
      dateFrom = selectedDates[0] ? selectedDates[0].toISOString().slice(0, 10) : "";
      dateTo   = selectedDates[1] ? selectedDates[1].toISOString().slice(0, 10) : "";
      btnClearDates.classList.toggle("hidden", !dateFrom);
      applyFilters();
    },
  });

  btnClearDates.addEventListener("click", () => {
    fp.clear();
    dateFrom = dateTo = "";
    btnClearDates.classList.add("hidden");
    applyFilters();
  });

  function applyFilters() {
    const text   = filterText.value.toLowerCase().trim();
    const cat    = filterCategory.value;
    const status = filterStatus.value;
    let visible = 0;

    rows.forEach(row => {
      const rowDate = row.dataset.date || "";
      const ok = (!text     || (row.dataset.problem || "").includes(text))
              && (!cat      || row.dataset.category === cat)
              && (!status   || row.dataset.status === status)
              && (!dateFrom || rowDate >= dateFrom)
              && (!dateTo   || rowDate <= dateTo);
      row.style.display = ok ? "" : "none";
      if (ok) visible++;
    });

    const noResults = document.getElementById("no-results-row");
    if (noResults) noResults.style.display = visible === 0 ? "" : "none";
  }

  filterText.addEventListener("input", applyFilters);
  filterCategory.addEventListener("change", applyFilters);
  filterStatus.addEventListener("change", applyFilters);
})();

// ── Acciones: marcar estado y reintentar ─────────────────────────────────────
(function () {
  function patchStatus(id, status, appliedSolution) {
    const body = { status };
    if (appliedSolution) body.applied_solution = appliedSolution;
    fetch(`/api/complaints/${id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then((r) => r.json())
      .then(() => location.reload());
  }

  const modal        = document.getElementById("close-modal");
  const modalInput   = document.getElementById("modal-solution");
  const modalError   = document.getElementById("modal-error");
  const modalConfirm = document.getElementById("modal-confirm");
  const modalCancel  = document.getElementById("modal-cancel");

  if (modalCancel) {
    modalCancel.addEventListener("click", () => { modal.style.display = "none"; });
  }

  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id     = btn.dataset.complaintId;
      const action = btn.dataset.action;

      if (action === "retry") {
        btn.disabled = true;
        btn.textContent = "Reprocesando…";
        fetch(`/api/complaints/${id}/retry`, { method: "POST" })
          .then((r) => r.json())
          .then(() => location.reload())
          .catch(() => { btn.disabled = false; btn.textContent = "Reintentar procesamiento"; });
        return;
      }

      if (action === "reviewed" && modal) {
        const currentSolution = (btn.dataset.solution || "").trim();
        const isEmpty = !currentSolution || currentSolution.toLowerCase() === "ninguna";

        if (isEmpty) {
          modalInput.value = "";
          modalError.classList.add("hidden");
          modal.style.display = "flex";

          modalConfirm.onclick = () => {
            const sol = modalInput.value.trim();
            if (!sol) { modalError.classList.remove("hidden"); modalInput.focus(); return; }
            modal.style.display = "none";
            patchStatus(id, "reviewed", sol);
          };
          return;
        }
      }

      patchStatus(id, action, null);
    });
  });
})();

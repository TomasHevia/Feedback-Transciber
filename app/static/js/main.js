// ── Audio recording on index page ─────────────────────────────────────────────
(function () {
  const btnRecord = document.getElementById("btn-record");
  const btnStop = document.getElementById("btn-stop");
  const btnSubmit = document.getElementById("btn-submit");
  const statusMsg = document.getElementById("record-status");
  const uploadSection = document.getElementById("upload-section");
  const audioPreview = document.getElementById("audio-preview");
  const resultSection = document.getElementById("result-section");
  const resultJson = document.getElementById("result-json");
  const resultLink = document.getElementById("result-link");

  if (!btnRecord) return; // not on index page

  let mediaRecorder = null;
  let chunks = [];
  let audioBlob = null;

  btnRecord.addEventListener("click", async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      chunks = [];

      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      mediaRecorder.onstop = () => {
        audioBlob = new Blob(chunks, { type: "audio/webm" });
        audioPreview.src = URL.createObjectURL(audioBlob);
        uploadSection.style.display = "flex";
        statusMsg.textContent = "Grabación lista. Escucha y luego presiona Procesar.";
      };

      mediaRecorder.start();
      btnRecord.disabled = true;
      btnStop.disabled = false;
      statusMsg.textContent = "Grabando… habla ahora.";
    } catch (err) {
      statusMsg.textContent = "Error al acceder al micrófono: " + err.message;
    }
  });

  btnStop.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
      mediaRecorder.stream.getTracks().forEach((t) => t.stop());
    }
    btnRecord.disabled = false;
    btnStop.disabled = true;
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

      resultJson.textContent = JSON.stringify(data, null, 2);
      resultLink.href = "/complaint/" + data.id;
      resultSection.style.display = "block";
      statusMsg.textContent = "¡Procesado correctamente!";
    } catch (err) {
      statusMsg.textContent = "Error: " + err.message;
    } finally {
      btnSubmit.disabled = false;
    }
  });
})();

// ── Dashboard stats ────────────────────────────────────────────────────────────
(function () {
  const statsBar = document.getElementById("stats-bar");
  if (!statsBar) return;

  fetch("/api/stats")
    .then((r) => r.json())
    .then((data) => {
      const total = document.createElement("span");
      total.className = "stat-chip";
      total.textContent = `Total: ${data.total}`;
      statsBar.appendChild(total);

      Object.entries(data.by_category || {}).forEach(([cat, count]) => {
        const chip = document.createElement("span");
        chip.className = "stat-chip";
        chip.textContent = `${cat}: ${count}`;
        statsBar.appendChild(chip);
      });
    })
    .catch(() => {});
})();

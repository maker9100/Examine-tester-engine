let materials = [];
let selectedMaterial = null;
let currentQuiz = null;
let demoMode = location.hostname.endsWith("github.io");

const $ = (id) => document.getElementById(id);

const esc = (s) => String(s ?? "")
  .replaceAll("&","&amp;")
  .replaceAll("<","&lt;")
  .replaceAll(">","&gt;")
  .replaceAll('"',"&quot;")
  .replaceAll("'","&#039;");

function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }

async function api(url, options = {}) {
  if (demoMode) return demoApi(url, options);

  try {
    const res = await fetch(url, options);
    let data = null;
    try { data = await res.json(); } catch {}
    if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
    return data;
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error("백엔드 서버에 연결할 수 없습니다.");
    }
    throw err;
  }
}

function setActiveNav(target) {
  document.querySelectorAll(".bottom-tab").forEach((b) => b.classList.remove("active"));
  document.querySelector(`.bottom-tab[data-target="${target}"]`)?.classList.add("active");
}

function showHome() {
  $("homeView").classList.remove("hidden");
  $("materialsView").classList.add("hidden");
  setActiveNav("home");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showMaterials() {
  $("homeView").classList.add("hidden");
  $("materialsView").classList.remove("hidden");
  setActiveNav("materials");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function goToQuizSection() {
  $("homeView").classList.remove("hidden");
  $("materialsView").classList.add("hidden");
  setActiveNav("quiz");
  $("homeQuizSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function goToAnalysisSection() {
  $("homeView").classList.remove("hidden");
  $("materialsView").classList.add("hidden");
  setActiveNav("analysis");
  $("homeFeedbackSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

document.querySelectorAll(".bottom-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.target;
    if (target === "materials") showMaterials();
    else if (target === "quiz") goToQuizSection();
    else if (target === "analysis") goToAnalysisSection();
    else showHome();
  });
});

document.querySelectorAll("[data-action='open-materials']").forEach((btn) => {
  btn.addEventListener("click", showMaterials);
});

$("goUpload").addEventListener("click", () => {
  showMaterials();
  $("fileInput2").click();
});

$("mcqPercent").addEventListener("input", (e) => {
  $("mcqLabel").textContent = `${Number(e.target.value)}%`;
});

async function loadMaterials() {
  materials = await api("/api/materials");
  renderMaterials();
  fillQuizSelect();
}

function renderMaterials() {
  if (!materials.length) {
    $("recentMaterials").innerHTML = '<div class="simple-list empty ui-center">아직 자료가 없다.</div>';
    $("materialsList").innerHTML = '<div class="simple-list empty ui-center">자료가 없다.</div>';
    return;
  }

  const makeRow = (m) => `
    <div class="material-row">
      <button data-open-material="${m.id}">${esc(m.title || m.filename)}</button>
      <span class="badge">${esc(m.status || "uploaded")}</span>
    </div>
  `;

  $("recentMaterials").innerHTML = materials.slice(0, 5).map(makeRow).join("");
  $("materialsList").innerHTML = materials.map(makeRow).join("");

  document.querySelectorAll("[data-open-material]").forEach((btn) => {
    btn.addEventListener("click", () => openMaterial(Number(btn.dataset.openMaterial)));
  });
}

function fillQuizSelect() {
  const ready = materials.filter((m) => m.status === "ready");
  $("quizMaterial").innerHTML = ready.length
    ? ready.map((m) => `<option value="${m.id}">${esc(m.title || m.filename)}</option>`).join("")
    : '<option value="">먼저 자료를 분석해라</option>';
}

async function uploadFromInput(inputEl, statusEl) {
  const file = inputEl.files?.[0];
  if (!file) return;

  statusEl.textContent = "업로드 중...";

  try {
    if (demoMode) {
      const id = Date.now();
      const item = {
        id,
        filename: file.name,
        title: file.name,
        mime_type: file.type || "image/jpeg",
        status: "uploaded",
        _previewUrl: URL.createObjectURL(file)
      };
      materials.unshift(item);
      window.__eduDemoFiles = window.__eduDemoFiles || {};
      window.__eduDemoFiles[id] = item._previewUrl;
      renderMaterials();
      fillQuizSelect();
      statusEl.textContent = "데모 업로드 완료.";
      showMaterials();
      return;
    }

    const fd = new FormData();
    fd.append("file", file);
    await api("/api/materials", { method: "POST", body: fd });
    statusEl.textContent = "업로드 완료.";
    await loadMaterials();
    showMaterials();
  } catch (err) {
    statusEl.textContent = `업로드 실패: ${err.message}`;
  } finally {
    inputEl.value = "";
  }
}

$("fileInput").addEventListener("change", () => uploadFromInput($("fileInput"), $("uploadStatus")));
$("fileInput2").addEventListener("change", () => uploadFromInput($("fileInput2"), $("uploadStatus")));

async function openMaterial(id) {
  if (demoMode) {
    selectedMaterial = materials.find(m => Number(m.id) === Number(id));
  } else {
    selectedMaterial = await api(`/api/materials/${id}`);
  }

  if (!selectedMaterial) return;

  showMaterials();
  $("workspace").classList.remove("hidden");
  $("selectedFilename").textContent = selectedMaterial.filename || "";

  if (demoMode) {
    const url = window.__eduDemoFiles?.[id] || selectedMaterial._previewUrl;
    if (url) {
      $("preview").innerHTML = (selectedMaterial.mime_type || "").startsWith("image/")
        ? `<img src="${url}" alt="학습자료">`
        : `<iframe src="${url}" title="PDF"></iframe>`;
    } else {
      $("preview").innerHTML = '<div class="simple-list empty ui-center">데모 원본 미리보기를 불러올 수 없다.</div>';
    }
  } else {
    const fileUrl = `/api/materials/${id}/file`;
    $("preview").innerHTML = selectedMaterial.mime_type.startsWith("image/")
      ? `<img src="${fileUrl}" alt="학습자료">`
      : `<iframe src="${fileUrl}" title="PDF"></iframe>`;
  }

  if (selectedMaterial.summary) {
    renderNote(selectedMaterial.summary);
  } else {
    $("note").className = "note empty study-content";
    $("note").textContent = "자료를 선택하고 AI 분석을 눌러라.";
  }
}

$("analyzeBtn").addEventListener("click", async () => {
  if (!selectedMaterial) {
    alert("먼저 자료를 선택해라.");
    return;
  }

  const btn = $("analyzeBtn");
  btn.disabled = true;
  btn.textContent = "분석 중...";

  try {
    let note;

    if (demoMode) {
      await sleep(450);
      note = {
        title: selectedMaterial.filename || "데모 학습자료",
        subject: "데모 과목",
        chapter: "UI 테스트",
        summary: "GitHub Pages 데모 모드에서 표시하는 요약 노트다. 실제 FastAPI 서버에서는 업로드한 자료를 Gemini가 분석해 이 영역에 요약한다.",
        key_points: [
          "요약 노트는 좌측 정렬",
          "문제와 오답노트도 좌측 정렬",
          "나머지 UI 텍스트는 가운데 정렬"
        ],
        formulas: [],
        terms: [
          { term: "EDU AI", definition: "요약·문제 생성·오답 분석을 연결하는 학습 웹앱" }
        ],
        study_tips: [
          "실제 AI 분석은 FastAPI 백엔드 실행 시 동작한다."
        ]
      };
      selectedMaterial.summary = note;
      selectedMaterial.status = "ready";
      selectedMaterial.title = note.title;
      renderMaterials();
      fillQuizSelect();
    } else {
      note = await api(`/api/materials/${selectedMaterial.id}/analyze`, { method: "POST" });
      await loadMaterials();
    }

    renderNote(note);
  } catch (err) {
    alert(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "AI 분석";
  }
});

function renderNote(n) {
  $("note").className = "note study-content";
  $("note").innerHTML = `
    <h2>${esc(n.title || "요약노트")}</h2>
    <p class="muted">${esc(n.subject || "")}${n.chapter ? ` · ${esc(n.chapter)}` : ""}</p>
    <p>${esc(n.summary || "")}</p>

    <h3>핵심 개념</h3>
    <ul>${(n.key_points || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>

    ${(n.formulas || []).length ? `
      <h3>공식 / 법칙</h3>
      ${n.formulas.map((f) => `
        <div class="note-box">
          <strong>${esc(f.name)}</strong><br>
          ${esc(f.expression)}<br>
          <span class="muted">${esc(f.meaning)}</span>
        </div>
      `).join("")}
    ` : ""}

    ${(n.terms || []).length ? `
      <h3>용어</h3>
      <ul>${n.terms.map((t) => `<li><strong>${esc(t.term)}</strong> — ${esc(t.definition)}</li>`).join("")}</ul>
    ` : ""}

    <h3>시험에서 주의할 점</h3>
    <ul>${(n.study_tips || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
  `;
}

$("generateQuiz").addEventListener("click", async () => {
  const material_id = Number($("quizMaterial").value);

  if (!material_id) {
    $("quizStatus").textContent = "분석된 자료가 필요하다.";
    return;
  }

  $("generateQuiz").disabled = true;
  $("quizStatus").textContent = "문제 생성 중...";

  try {
    if (demoMode) {
      await sleep(350);
      const count = Math.min(Math.max(Number($("quizCount").value) || 5, 1), 10);
      const mcq = Number($("mcqPercent").value);

      const questions = Array.from({ length: count }, (_, i) => {
        const multiple = i < Math.round(count * (mcq / 100));
        return {
          id: `q${i + 1}`,
          type: multiple ? "multiple_choice" : "short_answer",
          concept: i % 2 ? "핵심 개념" : "자료 이해",
          difficulty: (i % 3) + 1,
          question: multiple
            ? `${i + 1}번 데모 문제: EDU AI의 주요 학습 흐름으로 가장 적절한 것은?`
            : `${i + 1}번 데모 서술형: EDU AI의 학습 흐름을 간단히 설명하시오.`,
          choices: multiple ? [
            "영상 편집 → 저장",
            "자료 → 요약 → 문제 → 오답 분석",
            "게임 실행 → 점수 저장",
            "음악 재생 → 추천"
          ] : []
        };
      });

      currentQuiz = {
        quiz_id: 1,
        title: "EDU AI 데모 문제",
        questions
      };
    } else {
      currentQuiz = await api("/api/quizzes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          material_id,
          count: Number($("quizCount").value),
          mcq_percent: Number($("mcqPercent").value),
          difficulty: $("difficulty").value
        })
      });
    }

    renderQuiz();
    $("quizStatus").textContent = "";
    goToQuizSection();

  } catch (err) {
    $("quizStatus").textContent = err.message;
  } finally {
    $("generateQuiz").disabled = false;
  }
});

function renderQuiz() {
  const form = $("quizForm");
  form.classList.remove("hidden");

  $("resultPanel").className = "result-wrap study-content";
  $("resultPanel").innerHTML = "";

  form.innerHTML = `
    <div class="question-card">
      <h2>${esc(currentQuiz.title)}</h2>
      <p class="muted">${currentQuiz.questions.length}문제</p>
    </div>

    ${currentQuiz.questions.map((q, i) => `
      <div class="question-card">
        <h3>${i + 1}. ${esc(q.question)}</h3>
        <p class="muted">${esc(q.concept || "")} · 난이도 ${esc(q.difficulty || "")}</p>

        ${q.type === "multiple_choice"
          ? (q.choices || []).map((c, j) => `
            <label class="choice">
              <input type="radio" name="${esc(q.id)}" value="${j}">
              <span>${j + 1}. ${esc(c)}</span>
            </label>
          `).join("")
          : `<textarea name="${esc(q.id)}" rows="5" placeholder="답안을 입력"></textarea>`
        }
      </div>
    `).join("")}

    <button type="submit" class="primary-btn">채점하기</button>
  `;
}

$("quizForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!currentQuiz) return;

  const fd = new FormData(e.currentTarget);
  const answers = {};

  for (const q of currentQuiz.questions) {
    const v = fd.get(q.id);
    answers[q.id] = q.type === "multiple_choice" && v !== null ? Number(v) : (v ?? "");
  }

  const btn = e.currentTarget.querySelector('button[type="submit"]');
  btn.disabled = true;
  btn.textContent = "채점 중...";

  try {
    let data;

    if (demoMode) {
      await sleep(300);

      const results = currentQuiz.questions.map((q) => {
        const a = answers[q.id];
        const correct = q.type === "multiple_choice"
          ? Number(a) === 1
          : String(a || "").trim().length >= 6;

        return {
          id: q.id,
          concept: q.concept,
          correct,
          score: correct ? 1 : 0,
          feedback: correct
            ? "정답이다."
            : "핵심 학습 흐름을 다시 확인해라.",
          explanation: "자료 → 요약 → 문제 → 오답 분석의 흐름을 기억하면 된다.",
          error_type: correct ? null : "개념 이해 부족"
        };
      });

      const percentage = Math.round(
        results.filter(r => r.correct).length / Math.max(results.length, 1) * 100
      );

      data = { percentage, results };

      const grouped = {};
      results.forEach((r) => {
        grouped[r.concept] ??= [];
        grouped[r.concept].push(r.score);
      });

      const mastery = Object.entries(grouped).map(([concept, scores]) => ({
        concept,
        score: scores.reduce((a,b) => a+b, 0) / scores.length
      }));

      localStorage.setItem("edu_ai_demo_mastery", JSON.stringify(mastery));

    } else {
      data = await api("/api/quizzes/grade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quiz_id: currentQuiz.quiz_id,
          answers
        })
      });
    }

    renderResult(data);
    await loadMastery();

  } catch (err) {
    alert(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "채점하기";
  }
});

function renderResult(d) {
  const panel = $("resultPanel");
  panel.className = "result-wrap study-content";

  panel.innerHTML = `
    <h2>채점 결과</h2>
    <div class="score">${d.percentage}점</div>

    ${d.results.map((r, i) => `
      <div class="feedback-row">
        <strong>${i + 1}번 · ${r.correct ? "정답" : "오답"}</strong>
        <div>${esc(r.feedback || r.explanation || "")}</div>
        ${!r.correct && r.error_type
          ? `<div class="muted">오류 유형: ${esc(r.error_type)}</div>`
          : ""
        }
      </div>
    `).join("")}
  `;

  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadMastery() {
  let rows;

  if (demoMode) {
    rows = JSON.parse(localStorage.getItem("edu_ai_demo_mastery") || "[]");
  } else {
    rows = await api("/api/mastery");
  }

  if (!rows.length) {
    $("masteryList").innerHTML = '<div class="simple-list empty ui-center">아직 분석 데이터가 없다.</div>';
    $("weakConcepts").innerHTML = '<div class="simple-list empty ui-center">문제를 풀면 분석된다.</div>';
    return;
  }

  $("masteryList").innerHTML = rows.map((r) => {
    const pct = Math.round(Number(r.score) * 100);
    return `
      <div class="mastery-row">
        <strong>${esc(r.concept)}</strong>
        <div class="bar"><i style="--w:${pct}%"></i></div>
        <span>${pct}%</span>
      </div>
    `;
  }).join("");

  $("weakConcepts").innerHTML = rows.slice(0, 5).map((r) => {
    const pct = Math.round(Number(r.score) * 100);
    return `
      <div class="material-row">
        <strong>${esc(r.concept)}</strong>
        <span>${pct}%</span>
      </div>
    `;
  }).join("");
}

(async () => {
  if (demoMode) {
    materials = [];
    renderMaterials();
    fillQuizSelect();
    await loadMastery();
    return;
  }

  await loadMaterials();
  await loadMastery();

})().catch((err) => {
  console.error(err);
});

let materials = [];
let selectedMaterial = null;
let currentQuiz = null;

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "")
  .replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
  .replaceAll('"',"&quot;").replaceAll("'","&#039;");

async function api(url, options={}) {
  if (location.hostname.endsWith("github.io")) {
    throw new Error("GitHub Pages에서는 AI 백엔드가 실행되지 않습니다. 실제 AI 기능은 FastAPI 서버 연결 후 사용할 수 있습니다.");
  }
  const res = await fetch(url, options);
  let data = null;
  try { data = await res.json(); } catch {}
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
  return data;
}

function switchView(name){
  document.querySelectorAll(".view").forEach(v=>v.classList.add("hidden"));
  document.querySelectorAll(".nav").forEach(v=>v.classList.remove("active"));
  $(`${name}View`).classList.remove("hidden");
  document.querySelector(`.nav[data-view="${name}"]`)?.classList.add("active");
  const names={home:"홈",materials:"내 자료",quiz:"문제 풀기",analysis:"학습 분석"};
  $("pageTitle").textContent=names[name]||"Study AI";
}
document.querySelectorAll(".nav").forEach(b=>b.onclick=()=>switchView(b.dataset.view));
$("goUpload").onclick=()=>{switchView("materials");$("fileInput").click()};

$("mcqPercent").oninput=e=>{
  const v=Number(e.target.value);
  $("mcqLabel").textContent=`객관식 ${v}% / 서술형 ${100-v}%`;
};

async function loadMaterials(){
  materials=await api("/api/materials");
  renderMaterials();
  fillQuizSelect();
}
function renderMaterials(){
  const html=materials.length?materials.map(m=>`
    <div class="material-row">
      <button data-id="${m.id}">${esc(m.title||m.filename)}</button>
      <span class="badge">${esc(m.status)}</span>
    </div>`).join(""):`<div class="empty">자료가 없다.</div>`;
  $("materialsList").innerHTML=html;
  $("recentMaterials").innerHTML=html;
  document.querySelectorAll("[data-id]").forEach(b=>b.onclick=()=>openMaterial(Number(b.dataset.id)));
}
function fillQuizSelect(){
  const ready=materials.filter(m=>m.status==="ready");
  $("quizMaterial").innerHTML=ready.length
    ? ready.map(m=>`<option value="${m.id}">${esc(m.title||m.filename)}</option>`).join("")
    : `<option value="">먼저 자료를 분석해라</option>`;
}

$("fileInput").onchange=async e=>{
  const file=e.target.files?.[0];
  if(!file)return;
  const fd=new FormData();fd.append("file",file);
  $("uploadStatus").textContent="업로드 중...";
  try{
    await api("/api/materials",{method:"POST",body:fd});
    $("uploadStatus").textContent="업로드 완료.";
    await loadMaterials();
  }catch(err){$("uploadStatus").textContent=`업로드 실패: ${err.message}`}
  e.target.value="";
};

async function openMaterial(id){
  selectedMaterial=await api(`/api/materials/${id}`);
  switchView("materials");
  $("workspace").classList.remove("hidden");
  $("selectedFilename").textContent=selectedMaterial.filename;
  const fileUrl=`/api/materials/${id}/file`;
  $("preview").innerHTML=selectedMaterial.mime_type.startsWith("image/")
    ? `<img src="${fileUrl}" alt="학습자료">`
    : `<iframe src="${fileUrl}" title="PDF"></iframe>`;
  if(selectedMaterial.summary)renderNote(selectedMaterial.summary);
  else {$("note").className="note empty";$("note").textContent="분석하면 여기에 요약노트가 나온다."}
}

$("analyzeBtn").onclick=async()=>{
  if(!selectedMaterial)return;
  const btn=$("analyzeBtn");btn.disabled=true;btn.textContent="분석 중...";
  try{
    const note=await api(`/api/materials/${selectedMaterial.id}/analyze`,{method:"POST"});
    renderNote(note);await loadMaterials();
  }catch(err){alert(err.message)}
  finally{btn.disabled=false;btn.textContent="AI 분석"}
};

function renderNote(n){
  $("note").className="note";
  $("note").innerHTML=`
    <h2>${esc(n.title||"요약노트")}</h2>
    <p class="muted">${esc(n.subject||"")}${n.chapter?` · ${esc(n.chapter)}`:""}</p>
    <p>${esc(n.summary||"")}</p>
    <h3>핵심 개념</h3>
    <ul>${(n.key_points||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul>
    ${(n.formulas||[]).length?`<h3>공식 / 법칙</h3>${n.formulas.map(f=>`
      <div class="note-box"><strong>${esc(f.name)}</strong><br>${esc(f.expression)}
      <br><span class="muted">${esc(f.meaning)}</span></div>`).join("")}`:""}
    ${(n.terms||[]).length?`<h3>용어</h3><ul>${n.terms.map(t=>`<li><strong>${esc(t.term)}</strong> — ${esc(t.definition)}</li>`).join("")}</ul>`:""}
    <h3>시험에서 주의할 점</h3>
    <ul>${(n.study_tips||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
}

$("generateQuiz").onclick=async()=>{
  const material_id=Number($("quizMaterial").value);
  if(!material_id){$("quizStatus").textContent="분석된 자료가 필요하다.";return}
  $("generateQuiz").disabled=true;$("quizStatus").textContent="문제 생성 중...";
  try{
    currentQuiz=await api("/api/quizzes",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        material_id,
        count:Number($("quizCount").value),
        mcq_percent:Number($("mcqPercent").value),
        difficulty:$("difficulty").value
      })
    });
    renderQuiz();$("quizStatus").textContent="";
  }catch(err){$("quizStatus").textContent=err.message}
  finally{$("generateQuiz").disabled=false}
};

function renderQuiz(){
  const f=$("quizForm");f.classList.remove("hidden");$("resultPanel").classList.add("hidden");
  f.innerHTML=`
    <div class="panel"><h2>${esc(currentQuiz.title)}</h2><p class="muted">${currentQuiz.questions.length}문제</p></div>
    ${currentQuiz.questions.map((q,i)=>`
      <div class="panel question">
        <h3>${i+1}. ${esc(q.question)}</h3>
        <p class="muted">${esc(q.concept||"")} · 난이도 ${esc(q.difficulty||"")}</p>
        ${q.type==="multiple_choice"
          ?(q.choices||[]).map((c,j)=>`<label class="choice"><input type="radio" name="${esc(q.id)}" value="${j}"><span>${j+1}. ${esc(c)}</span></label>`).join("")
          :`<textarea name="${esc(q.id)}" rows="5" placeholder="답안을 입력"></textarea>`}
      </div>`).join("")}
    <button type="submit" class="primary">채점하기</button>`;
}

$("quizForm").onsubmit=async e=>{
  e.preventDefault();
  const fd=new FormData(e.target),answers={};
  for(const q of currentQuiz.questions){
    const v=fd.get(q.id);
    answers[q.id]=q.type==="multiple_choice"&&v!==null?Number(v):(v??"");
  }
  const btn=e.target.querySelector('button[type="submit"]');btn.disabled=true;btn.textContent="채점 중...";
  try{
    const data=await api("/api/quizzes/grade",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({quiz_id:currentQuiz.quiz_id,answers})
    });
    renderResult(data);await loadMastery();
  }catch(err){alert(err.message)}
  finally{btn.disabled=false;btn.textContent="채점하기"}
};

function renderResult(d){
  const p=$("resultPanel");p.classList.remove("hidden");
  p.innerHTML=`<h2>채점 결과</h2><div class="score">${d.percentage}점</div>
  ${d.results.map((r,i)=>`<div class="feedback">
    <strong>${i+1}번 · ${r.correct?"정답":"오답"}</strong>
    <div>${esc(r.feedback||r.explanation||"")}</div>
    ${!r.correct&&r.error_type?`<div class="muted">오류 유형: ${esc(r.error_type)}</div>`:""}
  </div>`).join("")}`;
  p.scrollIntoView({behavior:"smooth"});
}

async function loadMastery(){
  const rows=await api("/api/mastery");
  if(!rows.length){
    $("masteryList").innerHTML=`<div class="empty">아직 분석 데이터가 없다.</div>`;
    $("weakConcepts").innerHTML=`<div class="empty">문제를 풀면 분석된다.</div>`;
    return;
  }
  $("masteryList").innerHTML=rows.map(r=>{
    const pct=Math.round(Number(r.score)*100);
    return `<div class="mastery-row"><strong>${esc(r.concept)}</strong><div class="bar"><i style="--w:${pct}%"></i></div><span>${pct}%</span></div>`;
  }).join("");
  $("weakConcepts").innerHTML=rows.slice(0,5).map(r=>{
    const pct=Math.round(Number(r.score)*100);
    return `<div class="material-row"><strong>${esc(r.concept)}</strong><span>${pct}%</span></div>`;
  }).join("");
}

(async()=>{
  if (location.hostname.endsWith("github.io")) {
    materials=[]; renderMaterials(); fillQuizSelect();
    $("masteryList").innerHTML='<div class="empty">AI 서버 연결 후 학습 분석이 표시된다.</div>';
    $("weakConcepts").innerHTML='<div class="empty">AI 서버 연결 후 취약 개념이 표시된다.</div>';
    return;
  }
  await loadMaterials(); await loadMastery();
})().catch(console.error);

document.querySelectorAll("[data-go]").forEach(b=>{
  b.addEventListener("click",()=>switchView(b.dataset.go));
});

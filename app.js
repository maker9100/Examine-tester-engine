let materials=[], selectedMaterial=null, currentQuiz=null, currentResearch=null;
const demoMode=location.hostname.endsWith("github.io");
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
const sleep=ms=>new Promise(r=>setTimeout(r,ms));

async function api(url,opt={}){
  if(demoMode) return demoApi(url,opt);
  const r=await fetch(url,opt);
  let d=null; try{d=await r.json()}catch{}
  if(!r.ok) throw new Error(d?.detail||`HTTP ${r.status}`);
  return d;
}

function setNav(n){
  document.querySelectorAll("[data-nav]").forEach(b=>b.classList.toggle("active",b.dataset.nav===n));
}
function showHome(){
  $("home").classList.remove("hidden"); $("materialsPage").classList.add("hidden");
  setNav("home"); scrollTo({top:0,behavior:"smooth"});
}
function showMaterials(){
  $("home").classList.add("hidden"); $("materialsPage").classList.remove("hidden");
  setNav("materials"); scrollTo({top:0,behavior:"smooth"});
}
function gotoQuiz(){ showHome(); setNav("quiz"); $("quizSection").scrollIntoView({behavior:"smooth"}); }
function gotoAnalysis(){ showHome(); setNav("analysis"); $("feedbackSection").scrollIntoView({behavior:"smooth"}); }

document.querySelectorAll("[data-nav]").forEach(b=>b.onclick=()=>{
  const n=b.dataset.nav;
  n==="materials"?showMaterials():n==="quiz"?gotoQuiz():n==="analysis"?gotoAnalysis():showHome();
});
$("startBtn").onclick=()=>{showMaterials();$("file2").click()};
$("allMaterialsBtn").onclick=showMaterials;
$("mcqPercent").oninput=e=>$("mcqLabel").textContent=`${e.target.value}%`;

async function loadMaterials(){
  materials=await api("/api/materials");
  renderMaterials(); fillSelect();
}
function renderMaterials(){
  if(!materials.length){
    $("recentMaterials").innerHTML="아직 자료가 없다.";
    $("materialsList").innerHTML="자료가 없다.";
    return;
  }
  const row=m=>`<div class="material"><button data-open="${m.id}">${esc(m.title||m.filename)}</button><span class="badge">${esc(m.status||"uploaded")}</span></div>`;
  $("recentMaterials").innerHTML=materials.slice(0,4).map(row).join("");
  $("materialsList").innerHTML=materials.map(row).join("");
  document.querySelectorAll("[data-open]").forEach(b=>b.onclick=()=>openMaterial(+b.dataset.open));
}
function fillSelect(){
  const ready=materials.filter(m=>m.status==="ready");
  $("quizMaterial").innerHTML=`<option value="">업로드 자료 없이 시험범위로 생성</option>`+
    ready.map(m=>`<option value="${m.id}">${esc(m.title||m.filename)}</option>`).join("");
}

async function upload(inp){
  const f=inp.files?.[0]; if(!f)return;
  $("uploadStatus").textContent="업로드 중...";
  try{
    if(demoMode){
      const id=Date.now(),url=URL.createObjectURL(f);
      materials.unshift({id,filename:f.name,title:f.name,mime_type:f.type||"image/jpeg",status:"uploaded",_url:url});
      renderMaterials(); fillSelect();
    }else{
      const fd=new FormData(); fd.append("file",f);
      await api("/api/materials",{method:"POST",body:fd});
      await loadMaterials();
    }
    $("uploadStatus").textContent="업로드 완료.";
  }catch(e){
    $("uploadStatus").textContent=e.message;
  }
  inp.value="";
}
$("file1").onchange=()=>upload($("file1"));
$("file2").onchange=()=>upload($("file2"));

async function openMaterial(id){
  selectedMaterial=demoMode?materials.find(m=>m.id===id):await api(`/api/materials/${id}`);
  if(!selectedMaterial)return;
  showMaterials(); $("workspace").classList.remove("hidden");
  $("selectedFilename").textContent=selectedMaterial.filename||"";
  const url=demoMode?selectedMaterial._url:`/api/materials/${id}/file`;
  $("preview").innerHTML=(selectedMaterial.mime_type||"").startsWith("image/")
    ?`<img src="${url}" alt="학습자료">`
    :`<iframe src="${url}" title="PDF"></iframe>`;
  selectedMaterial.summary?renderNote(selectedMaterial.summary):$("note").innerHTML="자료를 선택하고 GPT 분석을 눌러라.";
}

$("analyzeBtn").onclick=async()=>{
  if(!selectedMaterial)return alert("먼저 자료를 선택해라.");
  $("analyzeBtn").disabled=true; $("analyzeBtn").textContent="분석 중...";
  try{
    let note;
    if(demoMode){
      await sleep(350);
      note={
        title:selectedMaterial.filename,subject:"데모 과목",chapter:"GPT UI 테스트",
        summary:"GitHub Pages 데모 요약이다. 실제 서버에서는 OpenAI GPT가 업로드 자료를 분석한다.",
        key_points:["문제·오답노트·요약노트 좌측 정렬","나머지 UI 가운데 정렬"],
        formulas:[],terms:[{term:"EDU AI",definition:"GPT 기반 학습 웹앱"}],
        study_tips:["실제 GPT 분석은 FastAPI/Render에서 실행한다."]
      };
      selectedMaterial.summary=note; selectedMaterial.status="ready";
      renderMaterials(); fillSelect();
    }else{
      note=await api(`/api/materials/${selectedMaterial.id}/analyze`,{method:"POST"});
      await loadMaterials();
    }
    renderNote(note);
  }catch(e){alert(e.message)}
  finally{$("analyzeBtn").disabled=false;$("analyzeBtn").textContent="GPT 분석"}
};

function renderNote(n){
  $("note").className="note left";
  $("note").innerHTML=`<h2>${esc(n.title||"요약노트")}</h2>
  <p class="muted">${esc(n.subject||"")}${n.chapter?` · ${esc(n.chapter)}`:""}</p>
  <p>${esc(n.summary||"")}</p>
  <h3>핵심 개념</h3><ul>${(n.key_points||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul>
  ${(n.formulas||[]).length?`<h3>공식 / 법칙</h3>${n.formulas.map(f=>`<div class="note-box"><strong>${esc(f.name)}</strong><br>${esc(f.expression)}<br><span class="muted">${esc(f.meaning)}</span></div>`).join("")}`:""}
  ${(n.terms||[]).length?`<h3>용어</h3><ul>${n.terms.map(t=>`<li><strong>${esc(t.term)}</strong> — ${esc(t.definition)}</li>`).join("")}</ul>`:""}
  <h3>시험에서 주의할 점</h3><ul>${(n.study_tips||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
}

$("researchBtn").onclick=async()=>{
  const grade=$("grade").value, subject=$("subject").value.trim(), scope=$("scope").value.trim();
  if(!subject||!scope){
    $("researchStatus").textContent="과목과 시험범위를 입력해라.";
    return;
  }
  $("researchBtn").disabled=true;
  $("researchStatus").textContent="공개 기출·모의고사 경향 검색 중...";
  try{
    currentResearch=await api("/api/research",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({grade,subject,scope})
    });
    renderResearch(currentResearch);
    $("researchStatus").textContent="웹 분석 완료.";
  }catch(e){
    $("researchStatus").textContent=e.message;
  }finally{
    $("researchBtn").disabled=false;
  }
};

function renderResearch(r){
  $("researchResult").classList.remove("hidden");
  const concepts=(r.important_concepts||[]).slice(0,5)
    .map(x=>`${esc(x.concept)} (${esc(x.reason||"")})`).join("<br>");
  const sources=(r.sources||[]).slice(0,6)
    .map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title||s.url)}</a>`).join("");
  $("researchResult").innerHTML=`<h3>웹 분석 결과</h3>
    <div>${esc(r.summary||"")}</div>
    ${concepts?`<div class="concepts"><strong>중요 개념</strong><br>${concepts}</div>`:""}
    ${sources?`<div class="source-list"><strong>확인한 공개 출처</strong>${sources}</div>`:""}
    <div style="margin-top:8px;color:#6f7b75">${esc(r.copyright_note||"문제 원문 복제 대신 기출 유형을 변형한다.")}</div>`;
}

$("generateQuiz").onclick=async()=>{
  const material_id=+$("quizMaterial").value||null;
  const research_id=currentResearch?.research_id||null;
  if(!material_id&&!research_id){
    $("quizStatus").textContent="자료를 분석하거나 시험범위 웹 분석을 먼저 실행해라.";
    return;
  }
  $("generateQuiz").disabled=true;
  $("quizStatus").textContent="GPT가 문제 생성 중...";
  try{
    if(demoMode){
      const n=Math.min(+$("quizCount").value||5,10),m=+$("mcqPercent").value;
      currentQuiz={
        quiz_id:1,title:"EDU AI GPT 데모 문제",
        questions:Array.from({length:n},(_,i)=>({
          id:`q${i+1}`,
          type:i<Math.round(n*m/100)?"multiple_choice":"short_answer",
          concept:i%2?"핵심 개념":"시험범위",
          difficulty:(i%3)+1,
          origin:i%3===0?"공개 기출 유형 변형":"AI 신규",
          source_hint:"공개 출제 경향 기반 데모",
          question:i<Math.round(n*m/100)
            ?`${i+1}번. EDU AI의 학습 흐름으로 맞는 것은?`
            :`${i+1}번. 시험범위 학습 흐름을 간단히 설명하시오.`,
          choices:i<Math.round(n*m/100)
            ?["영상 편집","자료 → 분석 → 문제 → 오답 분석","게임 실행","음악 재생"]:[]
        }))
      };
    }else{
      currentQuiz=await api("/api/quizzes",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          material_id,research_id,
          count:+$("quizCount").value,
          mcq_percent:+$("mcqPercent").value,
          difficulty:$("difficulty").value
        })
      });
    }
    renderQuiz(); $("quizStatus").textContent=""; gotoQuiz();
  }catch(e){
    $("quizStatus").textContent=e.message;
  }finally{
    $("generateQuiz").disabled=false;
  }
};

function renderQuiz(){
  $("quizForm").classList.remove("hidden");
  $("resultPanel").innerHTML="";
  $("quizForm").innerHTML=`<div class="qcard"><h2>${esc(currentQuiz.title)}</h2><p class="muted">${currentQuiz.questions.length}문제</p></div>
  ${currentQuiz.questions.map((q,i)=>`<div class="qcard">
    <h3>${i+1}. ${esc(q.question)}</h3>
    <span class="origin">${esc(q.origin||"AI 신규")}</span>
    <p class="muted">${esc(q.concept||"")} · 난이도 ${q.difficulty}${q.source_hint?` · ${esc(q.source_hint)}`:""}</p>
    ${q.type==="multiple_choice"
      ?(q.choices||[]).map((c,j)=>`<label class="choice"><input type="radio" name="${q.id}" value="${j}"><span>${j+1}. ${esc(c)}</span></label>`).join("")
      :`<textarea class="study-answer" name="${q.id}" placeholder="답안을 입력"></textarea>`}
  </div>`).join("")}
  <button type="submit" class="primary">채점하기</button>`;
}

$("quizForm").onsubmit=async e=>{
  e.preventDefault();
  const fd=new FormData(e.target),answers={};
  currentQuiz.questions.forEach(q=>{
    const v=fd.get(q.id);
    answers[q.id]=q.type==="multiple_choice"&&v!==null?+v:(v??"");
  });
  const b=e.target.querySelector("[type=submit]");
  b.disabled=true; b.textContent="채점 중...";
  try{
    let d;
    if(demoMode){
      await sleep(250);
      const results=currentQuiz.questions.map(q=>{
        const a=answers[q.id], ok=q.type==="multiple_choice"?+a===1:String(a||"").trim().length>5;
        return {
          id:q.id,concept:q.concept,correct:ok,score:ok?1:0,
          feedback:ok?"정답이다.":"핵심 개념을 다시 확인해라.",
          explanation:"데모 해설",error_type:ok?null:"개념 이해 부족"
        };
      });
      d={percentage:Math.round(results.filter(x=>x.correct).length/results.length*100),results};
      const g={};
      results.forEach(r=>(g[r.concept]??=[]).push(r.score));
      localStorage.setItem("edu_mastery",JSON.stringify(
        Object.entries(g).map(([concept,s])=>({concept,score:s.reduce((a,b)=>a+b,0)/s.length}))
      ));
    }else{
      d=await api("/api/quizzes/grade",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({quiz_id:currentQuiz.quiz_id,answers})
      });
    }
    renderResult(d); await loadMastery();
  }catch(e){alert(e.message)}
  finally{b.disabled=false;b.textContent="채점하기"}
};

function renderResult(d){
  $("resultPanel").innerHTML=`<h2>채점 결과</h2><div class="score">${d.percentage}점</div>
  ${d.results.map((r,i)=>`<div class="feedback">
    <strong>${i+1}번 · ${r.correct?"정답":"오답"}</strong>
    <div>${esc(r.feedback||r.explanation||"")}</div>
    ${!r.correct&&r.error_type?`<div class="muted">오류 유형: ${esc(r.error_type)}</div>`:""}
  </div>`).join("")}`;
}

async function loadMastery(){
  const rows=demoMode?JSON.parse(localStorage.getItem("edu_mastery")||"[]"):await api("/api/mastery");
  if(!rows.length){
    $("masteryList").innerHTML="아직 분석 데이터가 없다.";
    $("weakConcepts").innerHTML="문제를 풀면 분석된다.";
    return;
  }
  $("masteryList").innerHTML=rows.map(r=>{
    const p=Math.round(+r.score*100);
    return `<div class="mastery"><strong>${esc(r.concept)}</strong><div class="bar"><i style="--w:${p}%"></i></div><span>${p}%</span></div>`;
  }).join("");
  $("weakConcepts").innerHTML=rows.slice(0,5).map(r=>
    `<div class="material"><strong>${esc(r.concept)}</strong><span>${Math.round(+r.score*100)}%</span></div>`
  ).join("");
}

async function demoApi(url,opt={}){
  await sleep(200);
  if(url==="/api/research"){
    return {
      research_id:1,
      summary:"데모: 시험범위에서 자주 나오는 공개 기출·모의고사 유형을 분석한 결과다.",
      important_concepts:[
        {concept:"핵심 개념 A",importance:3,reason:"반복 출제"},
        {concept:"핵심 개념 B",importance:2,reason:"응용 출제"}
      ],
      patterns:[{name:"기본 개념 적용",concept:"핵심 개념 A",difficulty:2,description:"기본 개념을 계산에 적용",recommended_weight:40}],
      pitfalls:["조건 누락"],
      search_notes:["데모 모드"],
      copyright_note:"상업 교재 원문은 복제하지 않고 유형만 참고한다.",
      sources:[{title:"한국교육과정평가원 예시",url:"https://www.kice.re.kr/"}]
    };
  }
  return [];
}

(async()=>{
  if(demoMode){
    renderMaterials(); fillSelect(); await loadMastery();
  }else{
    await loadMaterials(); await loadMastery();
  }
})();

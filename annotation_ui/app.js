const categories = [
  "unsupported_claim",
  "contradiction",
  "evidence_conflict",
  "insufficient_evidence",
  "entity_ambiguity",
  "temporal_conflict",
  "numeric_error",
  "over_specific_answer",
  "answer_format_issue",
  "benchmark_ambiguous",
  "other",
];

const categoryZh = {
  answer_format_issue: "回答格式问题",
  benchmark_ambiguous: "基准/题目歧义",
  contradiction: "与证据矛盾",
  entity_ambiguity: "实体歧义",
  evidence_conflict: "证据冲突",
  insufficient_evidence: "证据不足",
  numeric_error: "数字错误",
  other: "其他",
  over_specific_answer: "回答过于具体",
  temporal_conflict: "时间冲突",
  unsupported_claim: "无证据支持",
};

const labelZh = {
  faithful: "忠实",
  unfaithful: "不忠实",
  insufficient: "证据不足",
  tie: "平票",
};

let items = [];
let currentIndex = 0;
let dirty = false;

const el = (id) => document.getElementById(id);

function annotationOf(item) {
  return item.saved_annotation || {
    annotator_label: "",
    annotator_confidence: "",
    issue_categories: [],
    notes: "",
  };
}

function isDone(item) {
  return Boolean(annotationOf(item).annotator_label);
}

function setStatus(text, cls = "") {
  const node = el("saveStatus");
  node.textContent = text;
  node.className = `saveStatus ${cls}`;
}

function mainText(item, key) {
  return item[`${key}_zh`] || item[key] || "";
}

function appendOriginal(parent, label, text) {
  if (!text) return;
  const details = document.createElement("details");
  details.className = "originalBlock";
  const summary = document.createElement("summary");
  summary.textContent = label;
  const body = document.createElement("div");
  body.textContent = text;
  details.appendChild(summary);
  details.appendChild(body);
  parent.appendChild(details);
}

function markDirty() {
  dirty = true;
  setStatus("有未保存修改", "dirty");
}

function renderList() {
  const list = el("itemList");
  list.innerHTML = "";
  items.forEach((item, index) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `itemButton ${index === currentIndex ? "current" : ""} ${isDone(item) ? "done" : ""}`;
    btn.innerHTML = `<span>${index + 1}. ${item.audit_id}</span><span class="status">${isDone(item) ? "已保存" : ""}</span>`;
    btn.addEventListener("click", () => {
      if (dirty && !confirm("当前条目有未保存修改，确认离开吗？")) return;
      currentIndex = index;
      dirty = false;
      render();
    });
    list.appendChild(btn);
  });
}

function renderEvidence(item) {
  const node = el("evidence");
  node.innerHTML = "";
  const docs = item.evidence || [];
  docs.forEach((doc, index) => {
    const div = document.createElement("div");
    div.className = "evidenceDoc";

    const title = document.createElement("div");
    title.className = "docTitle";
    title.textContent = `[${index + 1}] ${doc.doc_id || ""}`;
    div.appendChild(title);

    const text = document.createElement("div");
    text.textContent = doc.text_zh || doc.text || "";
    div.appendChild(text);

    appendOriginal(div, "英文原文", doc.text || "");
    node.appendChild(div);
  });
}

function labelClass(label) {
  if (label === "faithful") return "faithful";
  if (label === "unfaithful") return "unfaithful";
  if (label === "insufficient") return "insufficient";
  return "";
}

function issueDisplay(issues, issuesZh) {
  const raw = issues || [];
  const zh = issuesZh || [];
  if (!raw.length) return "无";
  return raw.map((issue, index) => `${issue}${zh[index] ? ` / ${zh[index]}` : ""}`).join("；");
}

function renderAiReviews(item) {
  const node = el("aiReviews");
  node.innerHTML = "";
  const info = item.ai_weak_reviews || {};
  const reviews = info.model_reviews || [];

  const summary = document.createElement("div");
  summary.className = "aiSummary";
  const majority = info.ai_majority_label || "";
  const majorityZh = info.ai_majority_label_zh || labelZh[majority] || majority || "无";
  const voteFraction = info.ai_top_label_vote_fraction ? `，最高票比例 ${info.ai_top_label_vote_fraction}` : "";
  summary.textContent = `五模型多数意见：${majority || "无"} / ${majorityZh}${voteFraction}`;
  node.appendChild(summary);

  if (!reviews.length) {
    const empty = document.createElement("div");
    empty.className = "categoryEmpty";
    empty.textContent = "没有加载到 AI 参考理由。";
    node.appendChild(empty);
    return;
  }

  reviews.forEach((review) => {
    const card = document.createElement("div");
    card.className = "aiReview";

    const head = document.createElement("div");
    head.className = "aiReviewHead";

    const model = document.createElement("strong");
    model.textContent = review.model || review.model_slug || "";
    head.appendChild(model);

    const label = document.createElement("span");
    label.className = `aiLabel ${labelClass(review.label)}`;
    label.textContent = `${review.label || "missing"} / ${review.label_zh || labelZh[review.label] || ""}`;
    head.appendChild(label);

    const confidence = document.createElement("span");
    confidence.className = "aiConfidence";
    confidence.textContent = `置信度 ${review.confidence || "无"}`;
    head.appendChild(confidence);

    card.appendChild(head);

    const issues = document.createElement("div");
    issues.className = "aiIssues";
    issues.textContent = `类别：${issueDisplay(review.issues || [], review.issues_zh || [])}`;
    card.appendChild(issues);

    const reason = document.createElement("div");
    reason.className = "aiReason";
    reason.textContent = review.reason_zh || review.reason || "";
    card.appendChild(reason);

    appendOriginal(card, "英文理由", review.reason || "");
    node.appendChild(card);
  });
}

function categoryLabel(cat, selected, counts = {}) {
  const label = document.createElement("label");
  const checked = selected.includes(cat) ? "checked" : "";
  const count = counts[cat] ? `<em>${counts[cat]}/5</em>` : "";
  label.innerHTML = `<input type="checkbox" value="${cat}" ${checked} /> <span>${cat}</span>${count}<small>${categoryZh[cat] || ""}</small>`;
  return label;
}

function renderCategories(selected, suggestionInfo = {}) {
  const node = el("categories");
  node.innerHTML = "";

  const suggested = suggestionInfo.suggested_issue_categories || [];
  const counts = suggestionInfo.issue_category_counts || {};
  const primary = Array.from(new Set([...suggested, ...selected]));
  const other = categories.filter((cat) => !primary.includes(cat));

  const suggestedBox = document.createElement("div");
  suggestedBox.className = "categorySection";
  const title = document.createElement("div");
  title.className = "categorySectionTitle";
  title.textContent = "AI 建议类别（仅供参考）";
  suggestedBox.appendChild(title);

  if (primary.length) {
    primary.forEach((cat) => suggestedBox.appendChild(categoryLabel(cat, selected, counts)));
  } else {
    const empty = document.createElement("div");
    empty.className = "categoryEmpty";
    empty.textContent = "五个模型没有建议问题类别；如果你认为有问题，可以展开下面的其他类别。";
    suggestedBox.appendChild(empty);
  }
  node.appendChild(suggestedBox);

  const details = document.createElement("details");
  details.className = "categoryOther";
  const summary = document.createElement("summary");
  summary.textContent = "其他类别";
  details.appendChild(summary);
  const otherGrid = document.createElement("div");
  otherGrid.className = "categorySection otherGrid";
  other.forEach((cat) => {
    otherGrid.appendChild(categoryLabel(cat, selected, counts));
  });
  details.appendChild(otherGrid);
  node.appendChild(details);

  node.querySelectorAll("input").forEach((input) => input.addEventListener("change", markDirty));
}

function renderTranslatedBlock(node, item, key) {
  node.innerHTML = "";
  node.appendChild(document.createTextNode(mainText(item, key)));
  appendOriginal(node, "英文原文", item[key] || "");
}

function render() {
  const item = items[currentIndex];
  const ann = annotationOf(item);
  el("progressText").textContent = `${items.filter(isDone).length}/${items.length} 已标注`;
  el("auditId").textContent = `${currentIndex + 1} / ${items.length} · ${item.audit_id}`;
  renderTranslatedBlock(el("question"), item, "question");
  renderTranslatedBlock(el("answer"), item, "answer");
  renderEvidence(item);
  renderAiReviews(item);

  document.querySelectorAll("input[name='label']").forEach((input) => {
    input.checked = input.value === (ann.annotator_label || "");
  });
  el("confidence").value = ann.annotator_confidence ?? "";
  el("notes").value = ann.notes || "";
  renderCategories(ann.issue_categories || [], item.ai_issue_suggestions || {});
  setStatus(ann.updated_at ? `已保存 ${ann.updated_at}` : "未保存", ann.updated_at ? "saved" : "");
  renderList();
}

function collectAnnotation() {
  const label = document.querySelector("input[name='label']:checked")?.value || "";
  const selectedCategories = Array.from(el("categories").querySelectorAll("input:checked")).map((x) => x.value);
  return {
    audit_id: items[currentIndex].audit_id,
    annotator_label: label,
    annotator_confidence: el("confidence").value === "" ? "" : Number(el("confidence").value),
    issue_categories: selectedCategories,
    notes: el("notes").value,
  };
}

async function saveCurrent() {
  const payload = collectAnnotation();
  const response = await fetch("/api/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!data.ok) {
    alert(data.error || "保存失败");
    return false;
  }
  items[currentIndex].saved_annotation = data.annotation;
  dirty = false;
  setStatus(`已保存 ${data.annotation.updated_at}`, "saved");
  renderList();
  el("progressText").textContent = `${items.filter(isDone).length}/${items.length} 已标注`;
  return true;
}

function nextItem() {
  if (currentIndex < items.length - 1) {
    currentIndex += 1;
    dirty = false;
    render();
  }
}

function prevItem() {
  if (currentIndex > 0) {
    currentIndex -= 1;
    dirty = false;
    render();
  }
}

async function init() {
  categories.sort();
  const response = await fetch("/api/items");
  const data = await response.json();
  items = data.items || [];

  document.querySelectorAll("input[name='label']").forEach((input) => input.addEventListener("change", markDirty));
  el("confidence").addEventListener("input", markDirty);
  el("notes").addEventListener("input", markDirty);
  el("saveBtn").addEventListener("click", saveCurrent);
  el("saveNextBtn").addEventListener("click", async () => {
    if (await saveCurrent()) nextItem();
  });
  el("nextBtn").addEventListener("click", () => {
    if (dirty && !confirm("当前条目有未保存修改，确认离开吗？")) return;
    nextItem();
  });
  el("prevBtn").addEventListener("click", () => {
    if (dirty && !confirm("当前条目有未保存修改，确认离开吗？")) return;
    prevItem();
  });
  el("jumpBtn").addEventListener("click", () => {
    const target = Number(el("jumpInput").value);
    if (!target || target < 1 || target > items.length) return;
    if (dirty && !confirm("当前条目有未保存修改，确认离开吗？")) return;
    currentIndex = target - 1;
    dirty = false;
    render();
  });
  document.addEventListener("keydown", async (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      await saveCurrent();
    }
  });

  render();
}

init().catch((error) => {
  console.error(error);
  document.body.textContent = String(error);
});

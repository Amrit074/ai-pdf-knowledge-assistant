const $ = (id) => document.getElementById(id);
let token = sessionStorage.getItem("folio_token"),
  demo = !token,
  caps = {},
  poll,
  pdfUrl;
const hash = new URLSearchParams(location.hash.slice(1));
if (hash.has("token")) {
  token = hash.get("token");
  sessionStorage.setItem("folio_token", token);
  demo = false;
  history.replaceState(null, "", location.pathname);
}
localStorage.removeItem("access_token");
const notice = (text) => ($("notice").textContent = text);
function el(tag, text, cls) {
  const e = document.createElement(tag);
  e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
async function api(path, options = {}) {
  const r = await fetch(path, {
    ...options,
    headers: {
      ...(token && !demo ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!r.ok) {
    let msg = `Request failed (${r.status}).`;
    try {
      const b = await r.json();
      if (typeof b.detail === "string") msg = b.detail;
    } catch {}
    throw Error(msg);
  }
  return r;
}
function mode() {
  $("workspace-type").textContent = demo
    ? "Read-only sample workspace"
    : "Your private documents";
  $("mode-badge").textContent = demo ? "SAMPLE WORKSPACE" : "PRIVATE WORKSPACE";
  $("login").hidden = !demo;
  $("logout").hidden = demo;
  $("pdf-file").disabled = demo;
  $("upload-limit").textContent = demo
    ? "Sign in to upload your own PDFs"
    : `Up to ${caps.max_upload_mb || 10} MB · selectable text`;
}
async function openPdf(doc, page = 1) {
  try {
    const r = await api(
      `/api/documents/${encodeURIComponent(doc.document_id)}/file`,
    );
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    pdfUrl = URL.createObjectURL(await r.blob());
    $("pdf-title").textContent = doc.filename;
    $("pdf-view").src = `${pdfUrl}#page=${page}`;
    $("pdf-dialog").showModal();
  } catch (e) {
    notice(e.message);
  }
}
async function loadDocuments() {
  const data = await (
      await api(demo ? "/api/demo/documents" : "/api/documents")
    ).json(),
    docs = data.documents,
    selected = $("document-select").value;
  $("documents").replaceChildren();
  $("document-select").replaceChildren(new Option("All documents", ""));
  $("doc-count").textContent = docs.length;
  $("library-count").textContent = String(docs.length).padStart(2, "0");
  for (const doc of docs) {
    $("document-select").add(new Option(doc.filename, doc.document_id));
    const card = el("article", "", "document-card");
    card.append(
      el("span", "PDF", "file-type"),
      el("h3", doc.filename),
      el("p", `${doc.pages} pages · ${doc.chunks} searchable passages`),
    );
    const actions = el("div", "", "document-actions"),
      view = el(
        "button",
        demo ? "Ask this document ↗" : "Open PDF ↗",
        "quiet",
      );
    view.onclick = () => {
      if (demo) {
        $("document-select").value = doc.document_id;
        $("question").focus();
      } else openPdf(doc);
    };
    actions.append(view);
    if (!demo) {
      const remove = el("button", "Delete", "quiet");
      remove.onclick = async () => {
        if (!confirm(`Delete ${doc.filename} and its passages?`)) return;
        try {
          await api(`/api/documents/${encodeURIComponent(doc.document_id)}`, {
            method: "DELETE",
          });
          await loadDocuments();
          notice("Document deleted.");
        } catch (e) {
          notice(e.message);
        }
      };
      actions.append(remove);
    }
    card.append(actions);
    $("documents").append(card);
  }
  if (docs.some((d) => d.document_id === selected))
    $("document-select").value = selected;
  if (!docs.length)
    $("documents").append(
      el("p", "Your library is empty. Upload a PDF to begin.", "library-empty"),
    );
}
async function loadHistory() {
  $("history-list").replaceChildren();
  if (demo) {
    $("history-list").append(el("p", "Sign in to save your questions."));
    return;
  }
  const data = await (await api("/api/chat-history")).json();
  for (const item of data.conversations.slice(0, 15)) {
    const b = el("button", item.question, "quiet");
    b.onclick = () => {
      $("question").value = item.question;
      $("question").focus();
    };
    $("history-list").append(b);
  }
  if (!data.conversations.length)
    $("history-list").append(el("p", "No questions yet."));
}
async function loadJobs() {
  clearTimeout(poll);
  if (demo) return;
  const data = await (await api("/api/ingestions")).json();
  $("jobs").replaceChildren();
  for (const job of data.jobs.slice(0, 5)) {
    const row = el("div", "", "job");
    row.append(el("strong", job.filename), el("span", job.status));
    if (job.error) row.append(el("p", job.error));
    $("jobs").append(row);
  }
  await loadDocuments();
  if (data.jobs.some((j) => !["ready", "failed"].includes(j.status)))
    poll = setTimeout(() => loadJobs().catch((e) => notice(e.message)), 1500);
}
async function upload(file) {
  if (demo) {
    notice("Sign in with Google to upload your own documents.");
    return;
  }
  if (!file) return;
  if (
    !file.name.toLowerCase().endsWith(".pdf") ||
    file.size > (caps.max_upload_mb || 10) * 1024 * 1024
  ) {
    notice("Choose a PDF within the upload size limit.");
    return;
  }
  const data = new FormData();
  data.append("file", file);
  $("pdf-file").disabled = true;
  notice("Sending your PDF…");
  try {
    await api("/api/ingestions", { method: "POST", body: data });
    notice("Upload accepted. Processing stages appear below your library.");
    await loadJobs();
  } catch (e) {
    notice(e.message);
  } finally {
    $("pdf-file").disabled = false;
    $("pdf-file").value = "";
  }
}
$("ask-form").onsubmit = async (event) => {
  event.preventDefault();
  const question = $("question").value.trim();
  if (question.length < 3) return;
  $("ask-button").disabled = true;
  notice("Finding relevant passages…");
  try {
    const data = await (
      await api(demo ? "/api/demo/ask" : "/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          document_id: $("document-select").value || null,
          top_k: 4,
        }),
      })
    ).json();
    $("answer-section").hidden = false;
    $("answer-question").textContent = question;
    $("answer").textContent = data.answer;
    $("evidence-state").textContent =
      {
        insufficient: "Insufficient evidence",
        retrieval_only: "Retrieved excerpts",
        retrieved: "Sources retrieved",
      }[data.evidence_status] || "Sources retrieved";
    $("answer-meta").textContent =
      `${data.elapsed_ms} ms · ${data.retrieval_mode} retrieval`;
    $("source-count").textContent = `${data.sources.length} sources`;
    $("sources").replaceChildren();
    data.sources.forEach((s, i) => {
      const card = el("article", "", "source");
      card.append(
        el("span", `[S${i + 1}] · Page ${s.page}`, "source-label"),
        el("h4", s.filename),
        el("p", s.text),
        el("small", `Similarity ${s.score.toFixed(3)}`),
      );
      if (!demo) {
        const b = el("button", "View original page ↗", "quiet");
        b.onclick = () => openPdf(s, s.page);
        card.append(b);
      }
      $("sources").append(card);
    });
    if (!data.sources.length)
      $("sources").append(
        el(
          "p",
          "No passage met the retrieval threshold. Try another question or document.",
        ),
      );
    notice(
      demo
        ? "Sample results use fictional documents and local retrieval; no AI provider is called."
        : "Check the excerpts before relying on the answer.",
    );
    await loadHistory();
  } catch (e) {
    notice(e.message);
  } finally {
    $("ask-button").disabled = false;
  }
};
$("login").onclick = () => {
  if (caps.google_login) location.href = "/api/auth/google/login";
  else
    notice(
      "Google sign-in is not configured. The sample workspace is available.",
    );
};
$("logout").onclick = () => {
  sessionStorage.removeItem("folio_token");
  location.href = "/";
};
$("try-demo").onclick = () => {
  demo = true;
  mode();
  loadDocuments()
    .then(() => notice("Explore three fictional sample documents."))
    .catch((e) => notice(e.message));
};
$("refresh").onclick = () => loadDocuments().catch((e) => notice(e.message));
$("new-question").onclick = () => {
  $("question").value = "";
  $("answer-section").hidden = true;
  $("question").focus();
};
$("history-toggle").onclick = () => {
  $("history-list").hidden = !$("history-list").hidden;
  loadHistory().catch((e) => notice(e.message));
};
$("pdf-file").onchange = (e) => upload(e.target.files[0]);
$("dropzone").ondragover = (e) => e.preventDefault();
$("dropzone").ondrop = (e) => {
  e.preventDefault();
  upload(e.dataTransfer.files[0]);
};
$("close-pdf").onclick = () => $("pdf-dialog").close();
$("pdf-dialog").addEventListener("close", () => {
  $("pdf-view").src = "about:blank";
  if (pdfUrl) URL.revokeObjectURL(pdfUrl);
  pdfUrl = null;
});
$("copy-answer").onclick = async () => {
  try {
    await navigator.clipboard.writeText($("answer").textContent);
    notice("Answer copied.");
  } catch {
    notice("Select the answer text to copy it.");
  }
};
document.querySelectorAll("[data-question]").forEach(
  (b) =>
    (b.onclick = () => {
      $("question").value = b.dataset.question;
      $("ask-form").requestSubmit();
    }),
);
(async () => {
  try {
    caps = await (await api("/api/capabilities")).json();
    $("api-status").textContent = "Workspace online";
    mode();
    $("provider-note").textContent = demo
      ? "Local sample · no provider key needed"
      : `${caps.retrieval_mode} retrieval · ${caps.answer_mode} answers`;
    if (!demo) {
      const user = await (await api("/api/auth/me")).json();
      $("workspace-name").textContent = user.name;
      notice("Your workspace is ready.");
      await loadJobs();
    } else await loadDocuments();
  } catch (e) {
    $("api-status").textContent = "Needs attention";
    notice(e.message);
  }
})();

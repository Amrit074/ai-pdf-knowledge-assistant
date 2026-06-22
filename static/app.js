const statusPill = document.querySelector("#status-pill");
const uploadForm = document.querySelector("#upload-form");
const uploadMessage = document.querySelector("#upload-message");
const fileInput = document.querySelector("#pdf-file");
const documentList = document.querySelector("#document-list");
const documentSelect = document.querySelector("#document-select");
const refreshDocs = document.querySelector("#refresh-docs");
const askForm = document.querySelector("#ask-form");
const questionInput = document.querySelector("#question");
const topKInput = document.querySelector("#top-k");
const answerCard = document.querySelector("#answer-card");
const answerBox = document.querySelector("#answer");
const sourcesBox = document.querySelector("#sources");
const googleLogin = document.querySelector("#google-login");
const logoutButton = document.querySelector("#logout");
const userName = document.querySelector("#user-name");
const workspace = document.querySelector("#workspace");
const loginWelcome = document.querySelector("#login-welcome");
const welcomeGoogleLogin = document.querySelector("#welcome-google-login");
let accessToken = localStorage.getItem("access_token");

function captureOAuthToken() {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get("token");
  if (token) {
    localStorage.setItem("access_token", token);
    accessToken = token;
    history.replaceState({}, document.title, window.location.pathname);
  }
}

function renderMarkdown(markdown) {
  const html = marked.parse(markdown, { breaks: true, gfm: true });
  return DOMPurify.sanitize(html);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    localStorage.removeItem("access_token");
    accessToken = null;
    showLoggedOut();
  }
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function showLoggedOut() {
  googleLogin.classList.remove("hidden");
  logoutButton.classList.add("hidden");
  userName.classList.add("hidden");
  workspace.classList.add("hidden");
  loginWelcome.classList.remove("hidden");
}

function showLoggedIn(user) {
  googleLogin.classList.add("hidden");
  logoutButton.classList.remove("hidden");
  userName.textContent = user.name;
  userName.classList.remove("hidden");
  loginWelcome.classList.add("hidden");
  workspace.classList.remove("hidden");
}

async function loadProfile() {
  if (!accessToken) return showLoggedOut();
  try {
    showLoggedIn(await api("/api/auth/me"));
  } catch {
    showLoggedOut();
  }
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  if (label) {
    button.textContent = busy ? "Working..." : label;
  }
}

async function checkHealth() {
  try {
    await api("/api/health");
    statusPill.textContent = "API online";
    statusPill.classList.add("online");
  } catch {
    statusPill.textContent = "API offline";
    statusPill.classList.remove("online");
  }
}

function renderDocuments(documents) {
  documentList.innerHTML = "";
  documentSelect.innerHTML = '<option value="">All documents</option>';

  if (!documents.length) {
    documentList.innerHTML = '<p class="message">No PDFs uploaded yet.</p>';
    return;
  }

  documents.forEach((doc) => {
    const option = document.createElement("option");
    option.value = doc.document_id;
    option.textContent = doc.filename;
    documentSelect.appendChild(option);

    const item = document.createElement("article");
    item.className = "document-item";
    item.innerHTML = `
      <div class="document-title"></div>
      <div class="document-meta">${doc.pages} pages · ${doc.chunks} chunks</div>
      <button class="delete-button" type="button" data-id="${doc.document_id}">Delete</button>
    `;
    item.querySelector(".document-title").textContent = doc.filename;
    documentList.appendChild(item);
  });
}

async function loadDocuments() {
  const data = await api("/api/documents");
  renderDocuments(data.documents);
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) return;

  const button = uploadForm.querySelector("button");
  const formData = new FormData();
  formData.append("file", file);
  uploadMessage.textContent = "Uploading and embedding PDF...";
  setBusy(button, true, "Upload and Index");

  try {
    const data = await api("/api/documents", { method: "POST", body: formData });
    uploadMessage.textContent = data.message;
    fileInput.value = "";
    await loadDocuments();
  } catch (error) {
    uploadMessage.textContent = error.message;
  } finally {
    setBusy(button, false, "Upload and Index");
  }
});

documentList.addEventListener("click", async (event) => {
  const button = event.target.closest(".delete-button");
  if (!button) return;

  setBusy(button, true, "Delete");
  try {
    await api(`/api/documents/${button.dataset.id}`, { method: "DELETE" });
    await loadDocuments();
  } catch (error) {
    alert(error.message);
    setBusy(button, false, "Delete");
  }
});

refreshDocs.addEventListener("click", loadDocuments);

askForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = askForm.querySelector("button");
  answerCard.classList.remove("hidden");
  answerBox.textContent = "Retrieving context and generating answer...";
  sourcesBox.innerHTML = "";
  setBusy(button, true, "Ask");

  try {
    const payload = {
      question: questionInput.value.trim(),
      document_id: documentSelect.value || null,
      top_k: Number(topKInput.value || 5),
    };
    const data = await api("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    answerBox.innerHTML = renderMarkdown(data.answer);
    sourcesBox.innerHTML = "";
    data.sources.forEach((source) => {
      const item = document.createElement("article");
      item.className = "source";
      item.innerHTML = `
        <div class="source-header"></div>
        <p class="source-text"></p>
      `;
      item.querySelector(".source-header").textContent =
        `${source.filename} · page ${source.page} · score ${source.score.toFixed(3)}`;
      item.querySelector(".source-text").textContent = source.text;
      sourcesBox.appendChild(item);
    });
  } catch (error) {
    answerBox.textContent = error.message;
  } finally {
    setBusy(button, false, "Ask");
  }
});

function beginGoogleLogin() {
  window.location.href = "/api/auth/google/login";
}

googleLogin.addEventListener("click", beginGoogleLogin);
welcomeGoogleLogin.addEventListener("click", beginGoogleLogin);
logoutButton.addEventListener("click", () => {
  localStorage.removeItem("access_token");
  accessToken = null;
  showLoggedOut();
  renderDocuments([]);
});

captureOAuthToken();
checkHealth();
loadProfile().then(() => accessToken ? loadDocuments().catch(() => renderDocuments([])) : renderDocuments([]));

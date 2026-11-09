const chatList = document.getElementById("chat-list");
const messagesEl = document.getElementById("messages");
const factList = document.getElementById("fact-list");
const titleEl = document.getElementById("chat-title");
const deleteBtn = document.getElementById("delete-chat");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const demosEl = document.getElementById("demos");
const statusEl = document.getElementById("status");
const authModal = document.getElementById("auth-modal");
const authForm = document.getElementById("auth-form");
const authNameWrap = document.getElementById("auth-name-wrap");
const authNicknameWrap = document.getElementById("auth-nickname-wrap");
const authName = document.getElementById("auth-name");
const authNickname = document.getElementById("auth-nickname");
const authEmail = document.getElementById("auth-email");
const authPassword = document.getElementById("auth-password");
const authError = document.getElementById("auth-error");
const authSubmit = document.getElementById("auth-submit");
const guestBtn = document.getElementById("guest-btn");
const signinBtn = document.getElementById("signin-btn");
const authClose = document.getElementById("auth-close");
const authBackdrop = document.getElementById("auth-backdrop");
const userDock = document.getElementById("user-dock");
const userMenu = document.getElementById("user-menu");
const avatarBtn = document.getElementById("avatar-btn");
const avatarInitial = document.getElementById("avatar-initial");
const avatarName = document.getElementById("avatar-name");
const menuSettings = document.getElementById("menu-settings");
const menuLogout = document.getElementById("menu-logout");
const settingsModal = document.getElementById("settings-modal");
const settingsBackdrop = document.getElementById("settings-backdrop");
const settingsClose = document.getElementById("settings-close");
const profileForm = document.getElementById("profile-form");
const settingsName = document.getElementById("settings-name");
const settingsNickname = document.getElementById("settings-nickname");
const settingsEmail = document.getElementById("settings-email");
const profileMsg = document.getElementById("profile-msg");
const passwordForm = document.getElementById("password-form");
const settingsCurrentPw = document.getElementById("settings-current-pw");
const settingsNewPw = document.getElementById("settings-new-pw");
const passwordMsg = document.getElementById("password-msg");
const settingsDeletePw = document.getElementById("settings-delete-pw");
const deleteMsg = document.getElementById("delete-msg");
const deleteAccountBtn = document.getElementById("delete-account-btn");
const drawerBackdrop = document.getElementById("drawer-backdrop");
const openChatsBtn = document.getElementById("open-chats");
const closeChatsBtn = document.getElementById("close-chats");
const openFactsBtn = document.getElementById("open-facts");
const closeFactsBtn = document.getElementById("close-facts");

const DEMOS = [
  ["Test 1 · save", "The project codeword is ORANGE-17."],
  ["Test 1 · ask", "What is the project codeword?"],
  ["Test 2 · old", "I study at Campus North."],
  ["Test 2 · new", "I transferred to Campus South."],
  ["Test 2 · ask", "Which campus am I on?"],
  ["Test 3 · save", "Remember the temporary research ID is BLUE-88."],
  ["Test 3 · ask", "What is my research ID?"],
];

let currentChatId = null;
let busy = false;
let authMode = "login";
let currentUser = null;

function setStatus(message, isError = false) {
  if (!message) {
    statusEl.hidden = true;
    statusEl.textContent = "";
    statusEl.classList.remove("error");
    return;
  }
  statusEl.hidden = false;
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function setBusy(on) {
  busy = on;
  sendBtn.disabled = on;
  input.disabled = on;
  sendBtn.textContent = on ? "Sending…" : "Send";
}

function setAuthError(message) {
  if (!message) {
    authError.hidden = true;
    authError.textContent = "";
    return;
  }
  authError.hidden = false;
  authError.textContent = message;
}

function setMsg(el, message, isError = false) {
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    el.classList.remove("error", "ok");
    return;
  }
  el.hidden = false;
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.toggle("ok", !isError);
}

function clearAuthForm() {
  authName.value = "";
  authNickname.value = "";
  authEmail.value = "";
  authPassword.value = "";
  setAuthError("");
}

function openAuthModal() {
  clearAuthForm();
  setAuthTab("login");
  authModal.hidden = false;
  document.body.classList.add("modal-open");
  closeUserMenu();
  authEmail.focus();
}

function closeAuthModal() {
  authModal.hidden = true;
  if (settingsModal.hidden) document.body.classList.remove("modal-open");
  clearAuthForm();
  setAuthTab("login");
}

function closeUserMenu() {
  userMenu.hidden = true;
  avatarBtn.setAttribute("aria-expanded", "false");
}

function toggleUserMenu() {
  const open = userMenu.hidden;
  userMenu.hidden = !open;
  avatarBtn.setAttribute("aria-expanded", open ? "true" : "false");
}

function openSettings() {
  if (!currentUser) return;
  closeUserMenu();
  setMsg(profileMsg, "");
  setMsg(passwordMsg, "");
  setMsg(deleteMsg, "");
  settingsName.value = currentUser.display_name || "";
  settingsNickname.value = currentUser.nickname || "";
  settingsEmail.value = currentUser.email || "";
  settingsCurrentPw.value = "";
  settingsNewPw.value = "";
  settingsDeletePw.value = "";
  settingsModal.hidden = false;
  document.body.classList.add("modal-open");
  settingsName.focus();
}

function closeSettings() {
  settingsModal.hidden = true;
  if (authModal.hidden) document.body.classList.remove("modal-open");
}

function updateHeader(me) {
  if (me.mode === "user" && me.user) {
    currentUser = me.user;
    signinBtn.hidden = true;
    userDock.hidden = false;
    avatarInitial.textContent = me.user.initial || "U";
    avatarName.textContent = me.user.nickname || me.user.display_name || "Account";
    avatarBtn.title = me.user.display_name
      ? `${me.user.display_name} · ${me.user.email}`
      : me.user.email;
  } else {
    currentUser = null;
    signinBtn.hidden = false;
    userDock.hidden = true;
    closeUserMenu();
    closeSettings();
    clearAuthForm();
  }
}

async function api(url, options) {
  const res = await fetch(url, options);
  let data = {};
  try {
    data = await res.json();
  } catch (_) {
    data = {};
  }
  if (!res.ok) {
    const err = new Error(data.error || `Request failed (${res.status})`);
    err.authRequired = !!data.auth_required;
    throw err;
  }
  return data;
}

async function ensureSession() {
  const me = await api("/api/auth/me");
  // Logged-in users keep chats/facts across refresh and reopen.
  if (me.mode === "user") return me;
  // Guests always start clean on each page load / refresh / reopen.
  await api("/api/auth/guest", { method: "POST" });
  return api("/api/auth/me");
}

function closeDrawers() {
  document.body.classList.remove("chats-open", "facts-open");
  drawerBackdrop.hidden = true;
}

function openChatsDrawer() {
  document.body.classList.remove("facts-open");
  document.body.classList.add("chats-open");
  drawerBackdrop.hidden = false;
  closeUserMenu();
}

function openFactsDrawer() {
  document.body.classList.remove("chats-open");
  document.body.classList.add("facts-open");
  drawerBackdrop.hidden = false;
  closeUserMenu();
}

async function bootstrap() {
  try {
    const me = await ensureSession();
    updateHeader(me);
    closeAuthModal();
    // Fresh welcome screen — do not auto-open the last chat.
    await load(null);
  } catch (err) {
    setStatus(err.message, true);
  }
}

async function load(chatId) {
  const url =
    chatId != null ? `/api/state?chat_id=${chatId}` : "/api/state";
  try {
    const data = await api(url);
    currentChatId = data.chat ? data.chat.id : null;
    renderChats(data.chats);
    renderMessages(data.chat, data.messages);
    renderFacts(data.facts);
  } catch (err) {
    if (err.authRequired) {
      await api("/api/auth/guest", { method: "POST" });
      updateHeader({ mode: "guest" });
      await load(chatId);
      return;
    }
    setStatus(err.message, true);
  }
}

function renderChats(chats) {
  chatList.innerHTML = "";
  chats.forEach((chat) => {
    const li = document.createElement("li");
    li.textContent = chat.title;
    if (chat.id === currentChatId) li.classList.add("active");
    li.onclick = async () => {
      closeDrawers();
      await load(chat.id);
    };
    chatList.appendChild(li);
  });
}

function renderMessages(chat, messages) {
  messagesEl.innerHTML = "";
  if (!chat) {
    titleEl.textContent = "New chat";
    deleteBtn.hidden = true;
    const welcome = document.createElement("div");
    welcome.className = "welcome";
    const nick = currentUser?.nickname || currentUser?.display_name;
    const heading = nick
      ? `Nice to see you, ${nick}`
      : "Welcome to HAM-C";
    welcome.innerHTML = `<h3>${escapeHtml(heading)}</h3><p>Ready when you are. Type a message to start.</p>`;
    messagesEl.appendChild(welcome);
    return;
  }
  titleEl.textContent = chat.title;
  deleteBtn.hidden = false;
  messages.forEach((msg) => {
    const div = document.createElement("div");
    div.className = `bubble ${msg.role}`;
    div.textContent = msg.content;
    messagesEl.appendChild(div);
    if (msg.role === "assistant" && msg.used_facts && msg.used_facts.length) {
      const used = document.createElement("div");
      used.className = "used";
      used.textContent =
        "Fact used: " +
        msg.used_facts.map((f) => `${f.key} = ${f.value}`).join("; ");
      messagesEl.appendChild(used);
    }
  });
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderFacts(facts) {
  factList.innerHTML = "";
  if (!facts.length) {
    const empty = document.createElement("li");
    empty.textContent = "No active facts.";
    factList.appendChild(empty);
    return;
  }
  facts.forEach((fact) => {
    const li = document.createElement("li");
    li.className = "fact-row";
    li.innerHTML = `<div><strong>${escapeHtml(fact.key)}</strong><span>${escapeHtml(fact.value)}</span></div>`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Delete";
    btn.onclick = async () => {
      try {
        setStatus("");
        await api(`/api/facts/${fact.id}/delete`, { method: "POST" });
        await load(currentChatId);
      } catch (err) {
        setStatus(err.message, true);
      }
    };
    li.appendChild(btn);
    factList.appendChild(li);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function appendBubble(role, content) {
  const welcome = messagesEl.querySelector(".welcome");
  if (welcome) welcome.remove();
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  div.textContent = content;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function showThinking() {
  const existing = document.getElementById("thinking-bubble");
  if (existing) existing.remove();
  const wrap = document.createElement("div");
  wrap.id = "thinking-bubble";
  wrap.className = "bubble assistant thinking";
  wrap.setAttribute("aria-live", "polite");
  wrap.innerHTML =
    '<span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span>' +
    '<span class="thinking-label">Thinking…</span>';
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrap;
}

function clearThinking() {
  const el = document.getElementById("thinking-bubble");
  if (el) el.remove();
}

async function sendText(text) {
  if (busy) return;
  setBusy(true);
  setStatus("");
  appendBubble("user", text);
  if (!currentChatId) {
    titleEl.textContent = text.slice(0, 48) || "New chat";
    deleteBtn.hidden = false;
  }
  showThinking();
  try {
    if (!currentChatId) {
      const chat = await api("/api/chats", { method: "POST" });
      currentChatId = chat.id;
    }
    await api(`/api/chats/${currentChatId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    await load(currentChatId);
  } catch (err) {
    clearThinking();
    setStatus(err.message, true);
  } finally {
    setBusy(false);
  }
}

function renderDemos() {
  demosEl.innerHTML = "";
  DEMOS.forEach(([label, text]) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "demo-btn";
    btn.innerHTML = `<span class="demo-label">${label}</span>${text}`;
    btn.onclick = () => {
      closeDrawers();
      sendText(text);
    };
    demosEl.appendChild(btn);
  });
}

function setAuthTab(mode) {
  authMode = mode;
  const isRegister = mode === "register";
  document.querySelectorAll(".auth-tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === mode);
  });
  authSubmit.textContent = isRegister ? "Create account" : "Sign in";
  authNameWrap.hidden = !isRegister;
  authNicknameWrap.hidden = !isRegister;
  authName.required = isRegister;
  authNickname.required = isRegister;
  if (!isRegister) {
    authName.value = "";
    authNickname.value = "";
  }
  setAuthError("");
}

document.querySelectorAll(".auth-tab").forEach((tab) => {
  tab.onclick = () => setAuthTab(tab.dataset.tab);
});

authForm.onsubmit = async (event) => {
  event.preventDefault();
  setAuthError("");
  const email = authEmail.value.trim();
  const password = authPassword.value;
  const path = authMode === "login" ? "/api/auth/login" : "/api/auth/register";
  const body = { email, password };
  if (authMode === "register") {
    body.display_name = authName.value.trim();
    body.nickname = authNickname.value.trim();
  }
  try {
    const me = await api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    closeAuthModal();
    updateHeader(me);
    currentChatId = null;
    await load(null);
  } catch (err) {
    setAuthError(err.message);
  }
};

guestBtn.onclick = async () => {
  setAuthError("");
  try {
    const me = await api("/api/auth/guest", { method: "POST" });
    closeAuthModal();
    updateHeader(me);
    currentChatId = null;
    await load(null);
  } catch (err) {
    setAuthError(err.message);
  }
};

signinBtn.onclick = () => openAuthModal();
authClose.onclick = () => closeAuthModal();
authBackdrop.onclick = () => closeAuthModal();

avatarBtn.onclick = (event) => {
  event.stopPropagation();
  toggleUserMenu();
};

menuSettings.onclick = () => openSettings();

menuLogout.onclick = async () => {
  closeUserMenu();
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch (_) {
    /* ignore */
  }
  currentChatId = null;
  clearAuthForm();
  setAuthTab("login");
  const me = await ensureSession();
  updateHeader(me);
  await load(null);
};

settingsClose.onclick = () => closeSettings();
settingsBackdrop.onclick = () => closeSettings();

profileForm.onsubmit = async (event) => {
  event.preventDefault();
  setMsg(profileMsg, "");
  try {
    const data = await api("/api/account/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        display_name: settingsName.value.trim(),
        nickname: settingsNickname.value.trim(),
      }),
    });
    updateHeader({ mode: "user", user: data.user });
    setMsg(profileMsg, "Profile saved.");
  } catch (err) {
    setMsg(profileMsg, err.message, true);
  }
};

passwordForm.onsubmit = async (event) => {
  event.preventDefault();
  setMsg(passwordMsg, "");
  try {
    await api("/api/account/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: settingsCurrentPw.value,
        new_password: settingsNewPw.value,
      }),
    });
    settingsCurrentPw.value = "";
    settingsNewPw.value = "";
    setMsg(passwordMsg, "Password updated.");
  } catch (err) {
    setMsg(passwordMsg, err.message, true);
  }
};

deleteAccountBtn.onclick = async () => {
  setMsg(deleteMsg, "");
  const password = settingsDeletePw.value;
  if (!password) {
    setMsg(deleteMsg, "Enter your password to confirm.", true);
    return;
  }
  if (!confirm("Delete your account permanently? Your chats and facts will be removed.")) {
    return;
  }
  try {
    await api("/api/account/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    closeSettings();
    currentChatId = null;
    const me = await ensureSession();
    updateHeader(me);
    await load(null);
  } catch (err) {
    setMsg(deleteMsg, err.message, true);
  }
};

document.addEventListener("click", (event) => {
  if (!userDock.contains(event.target)) closeUserMenu();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeUserMenu();
    if (!drawerBackdrop.hidden) closeDrawers();
    else if (!settingsModal.hidden) closeSettings();
    else if (!authModal.hidden) closeAuthModal();
  }
});

document.getElementById("new-chat").onclick = async () => {
  try {
    setStatus("");
    closeDrawers();
    currentChatId = null;
    await load(null);
    input.focus();
  } catch (err) {
    setStatus(err.message, true);
  }
};

deleteBtn.onclick = async () => {
  if (!currentChatId) return;
  if (!confirm("Delete this chat and the facts that came from it?")) return;
  try {
    setStatus("");
    await api(`/api/chats/${currentChatId}/delete`, { method: "POST" });
    currentChatId = null;
    await load(null);
  } catch (err) {
    setStatus(err.message, true);
  }
};

openChatsBtn.onclick = () => openChatsDrawer();
closeChatsBtn.onclick = () => closeDrawers();
openFactsBtn.onclick = () => openFactsDrawer();
closeFactsBtn.onclick = () => closeDrawers();
drawerBackdrop.onclick = () => closeDrawers();

form.onsubmit = async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  await sendText(text);
};

renderDemos();
bootstrap();

const installBtn = document.getElementById("install-btn");
let deferredInstall = null;
const installed =
  window.matchMedia("(display-mode: standalone)").matches ||
  window.navigator.standalone === true;

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstall = event;
  if (!installed) installBtn.hidden = false;
});

window.addEventListener("appinstalled", () => {
  deferredInstall = null;
  installBtn.hidden = true;
});

const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
if (ios && !installed) installBtn.hidden = false;

installBtn.onclick = async () => {
  if (deferredInstall) {
    deferredInstall.prompt();
    await deferredInstall.userChoice;
    deferredInstall = null;
    installBtn.hidden = true;
    return;
  }
  if (ios) {
    setStatus("On iPhone, tap Share, then Add to Home Screen.");
  }
};

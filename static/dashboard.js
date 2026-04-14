const LOGIN_PAGE_PATH = "/";

const state = {
  user: null,
};

const els = {
  headerUser: document.getElementById("header-user"),
  btnLogout: document.getElementById("btn-logout"),
  globalMessage: document.getElementById("global-message"),
};

function setGlobalMessage(text, type = "") {
  els.globalMessage.textContent = text || "";
  els.globalMessage.className = "status-banner";
  if (type) {
    els.globalMessage.classList.add(type);
  }
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const isFormData = options.body instanceof FormData;
  if (!isFormData && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers,
  });

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = payload && typeof payload === "object" ? payload.detail : payload;
    throw new Error(detail || "请求失败");
  }

  return payload;
}

function redirectToLogin() {
  window.location.replace(LOGIN_PAGE_PATH);
}

async function logout() {
  try {
    await api("/auth/logout", { method: "POST" });
  } finally {
    redirectToLogin();
  }
}

async function bootstrap() {
  els.btnLogout.onclick = logout;

  try {
    state.user = await api("/auth/me");
  } catch {
    redirectToLogin();
    return;
  }

  els.headerUser.textContent = `${state.user.name}（${state.user.student_id}）`;
  setGlobalMessage("已登录。课表工作台壳子已就绪，后续可在此页继续接入接口和渲染逻辑。", "success");

  window.scheduleDashboard = {
    api,
    user: state.user,
    setGlobalMessage,
    redirectToLogin,
  };
}

bootstrap();

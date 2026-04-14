const DASHBOARD_PATH = "/dashboard";

const state = {
  isRegister: false,
};

const els = {
  authTitle: document.getElementById("auth-title"),
  authToggle: document.getElementById("btn-toggle-auth"),
  authSubmit: document.getElementById("btn-submit-auth"),
  authMessage: document.getElementById("auth-message"),
  fieldName: document.getElementById("field-name"),
  fieldScnuAccount: document.getElementById("field-scnu-account"),
  inputName: document.getElementById("input-name"),
  inputScnuAccount: document.getElementById("input-scnu-account"),
  inputSid: document.getElementById("input-sid"),
  inputPwd: document.getElementById("input-pwd"),
};

function setMessage(element, text, type = "") {
  element.textContent = text || "";
  element.className = "message";
  if (type) {
    element.classList.add(type);
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

function redirectToDashboard() {
  window.location.replace(DASHBOARD_PATH);
}

function toggleAuthMode() {
  state.isRegister = !state.isRegister;
  els.authTitle.textContent = state.isRegister ? "注册本地账号" : "登录";
  els.authSubmit.textContent = state.isRegister ? "注册并进入工作台" : "登录并进入工作台";
  els.authToggle.textContent = state.isRegister ? "已有账号？返回登录" : "没有账号？去注册";
  els.fieldName.classList.toggle("hidden", !state.isRegister);
  els.fieldScnuAccount.classList.toggle("hidden", !state.isRegister);
  setMessage(els.authMessage, "");
}

async function submitAuth() {
  const studentId = els.inputSid.value.trim();
  const password = els.inputPwd.value;
  const name = els.inputName.value.trim();
  const scnuAccount = els.inputScnuAccount.value.trim();

  if (!studentId || !password) {
    setMessage(els.authMessage, "请填写学号和密码", "error");
    return;
  }

  try {
    if (state.isRegister) {
      if (!name) {
        setMessage(els.authMessage, "注册时需要填写姓名", "error");
        return;
      }
      await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          student_id: studentId,
          name,
          password,
          scnu_account: scnuAccount || null,
        }),
      });
    }

    await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ student_id: studentId, password }),
    });
    redirectToDashboard();
  } catch (error) {
    setMessage(els.authMessage, error.message, "error");
  }
}

async function bootstrap() {
  els.authToggle.onclick = toggleAuthMode;
  els.authSubmit.onclick = submitAuth;

  try {
    await api("/auth/me");
    redirectToDashboard();
  } catch {
    setMessage(els.authMessage, "");
  }
}

bootstrap();

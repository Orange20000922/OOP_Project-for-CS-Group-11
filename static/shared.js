(function initScheduleFrontend(global) {
  const LOGIN_PATH = "/login";
  const DASHBOARD_PATH = "/dashboard";

  function extractErrorMessage(payload) {
    if (!payload) {
      return "Request failed";
    }
    if (typeof payload === "string") {
      return payload;
    }
    if (typeof payload === "object") {
      return payload.detail || payload.error || payload.message || "Request failed";
    }
    return "Request failed";
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
      const error = new Error(extractErrorMessage(payload));
      error.status = response.status;
      error.payload = payload;
      throw error;
    }

    return payload;
  }

  function redirectToLogin() {
    global.location.replace(LOGIN_PATH);
  }

  function redirectToDashboard() {
    global.location.replace(DASHBOARD_PATH);
  }

  function createEmptyWeekCourses() {
    return {
      "1": [],
      "2": [],
      "3": [],
      "4": [],
      "5": [],
      "6": [],
      "7": [],
    };
  }

  function weekdayLabel(weekday) {
    return ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"][weekday] || "";
  }

  function formatWeeks(weeks) {
    if (!Array.isArray(weeks) || !weeks.length) {
      return "未设置";
    }
    return weeks.join(", ");
  }

  function formatWeekLabel(offset) {
    if (offset === 0) {
      return "本周课表";
    }
    if (offset > 0) {
      return `未来第 ${offset} 周`;
    }
    return `过去第 ${Math.abs(offset)} 周`;
  }

  global.scheduleFrontend = {
    api,
    createEmptyWeekCourses,
    formatWeekLabel,
    formatWeeks,
    redirectToDashboard,
    redirectToLogin,
    weekdayLabel,
  };
})(window);

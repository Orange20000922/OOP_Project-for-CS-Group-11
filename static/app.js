const state = {
  isRegister: false,
  user: null,
  schedule: null,
  weekOffset: 0,
  editingCourseId: null,
  fetchTaskId: null,
  fetchPollTimer: null,
};
const STORAGE_KEY = "course_edit_draft_" + (Math.random().toString(36).substr(2, 8));
let hasUnsavedDraft = false;

const els = {
  authView: document.getElementById("view-auth"),
  appView: document.getElementById("view-app"),
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
  headerUser: document.getElementById("header-user"),
  btnLogout: document.getElementById("btn-logout"),
  globalMessage: document.getElementById("global-message"),
  inputSemester: document.getElementById("input-semester"),
  inputSemesterStart: document.getElementById("input-semester-start"),
  btnSaveScheduleMeta: document.getElementById("btn-save-schedule-meta"),
  uploadFile: document.getElementById("input-upload-file"),
  btnUpload: document.getElementById("btn-upload"),
  fetchAccount: document.getElementById("fetch-account"),
  fetchPassword: document.getElementById("fetch-password"),
  fetchSemester: document.getElementById("fetch-semester"),
  fetchPreferPlaywright: document.getElementById("fetch-prefer-playwright"),
  btnFetch: document.getElementById("btn-fetch"),
  fetchStatus: document.getElementById("fetch-status"),
  nowCard: document.getElementById("now-card"),
  weekLabel: document.getElementById("week-label"),
  btnPrevWeek: document.getElementById("btn-prev-week"),
  btnNextWeek: document.getElementById("btn-next-week"),
  timetableBody: document.getElementById("timetable-body"),
  courseCount: document.getElementById("course-count"),
  courseList: document.getElementById("course-list"),
  courseFormTitle: document.getElementById("course-form-title"),
  courseForm: document.getElementById("course-form"),
  btnCancelEdit: document.getElementById("btn-cancel-edit"),
  courseName: document.getElementById("course-name"),
  courseTeacher: document.getElementById("course-teacher"),
  courseLocation: document.getElementById("course-location"),
  courseWeekday: document.getElementById("course-weekday"),
  courseStart: document.getElementById("course-period-start"),
  courseEnd: document.getElementById("course-period-end"),
  courseWeeks: document.getElementById("course-weeks"),
  courseWeekType: document.getElementById("course-week-type"),
};

function setMessage(element, text, type = "") {
  element.textContent = text || "";
  element.className = "message";
  if (type) {
    element.classList.add(type);
  }
}

function setGlobalMessage(text, type = "") {
  els.globalMessage.textContent = text || "";
  els.globalMessage.className = "status-banner";
  if (type) {
    els.globalMessage.classList.add(type);
  }

}
function withLoading(button, fn) {
  return async (...args) => {
    if (button.disabled) return;
    button.disabled = true;
    button.textContent = "处理中...";
    try {
      await fn(...args);
    } finally {
      button.disabled = false;
      button.textContent = button.dataset.text;
    }
  };
}

const requestLoading = new Set();
async function api(path, options = {}) {
  const BASE_URL = "http://127.0.0.1:8000";
  const fullPath = `${BASE_URL}${path}`;
  const requestKey = `${fullPath}-${options.method || "GET"}`;

  if (requestLoading.has(requestKey)) return;
  requestLoading.add(requestKey);

  const requestId = Symbol(path + Date.now());
  requestLoading.add(requestId);

  try {
    const headers = new Headers(options.headers || {});
    const isFormData = options.body instanceof FormData;
    if (!isFormData && options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    const response = await fetch(fullPath, {
      credentials: "include",
      ...options,
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);



    if (response.status === 204) {
      return null;
    }

    const contentType = response.headers.get("content-type") || "";
    let payload;

    if (contentType.includes("application/json")) {
      try {
        payload = await response.json();
      } catch {
        payload = await response.text();
      }
    } else {
      payload = await response.text();
    }

    if (!response.ok) {
      let errorMessage;
      if (payload && typeof payload === "object") {
        errorMessage = payload.detail || payload.message || JSON.stringify(payload);
      } else if (typeof payload === "string") {
        errorMessage = payload.length > 200 ? payload.substring(0, 200) + "..." : payload;
      } else {
        errorMessage = "请求失败";
      }
      throw new Error(errorMessage);
    }

    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("请求超时，请检查网络或重试");
    } else if (!navigator.onLine) {
      throw new Error("网络已断开，请检查网络连接");
    } else {
      throw new Error(error.message || "网络请求失败，请重试");
    }
  } finally {
    requestLoading.delete(requestKey);
    requestLoading.delete(requestId);
  }
}

function toggleAuthMode() {
  state.isRegister = !state.isRegister;
  els.authTitle.textContent = state.isRegister ? "注册本地账号" : "登录";
  els.authSubmit.textContent = state.isRegister ? "注册并进入" : "登录";
  els.authToggle.textContent = state.isRegister ? "已有账号？返回登录" : "没有账号？去注册";
  els.fieldName.classList.toggle("hidden", !state.isRegister);
  els.fieldScnuAccount.classList.toggle("hidden", !state.isRegister);
  setMessage(els.authMessage, "");
}

function showAuthView() {
  state.user = null;
  state.schedule = null;
  state.editingCourseId = null;
  els.authView.classList.remove("hidden");
  els.appView.classList.add("hidden");
  els.btnLogout.classList.add("hidden");
  els.headerUser.textContent = "";
}

function showAppView() {
  els.authView.classList.add("hidden");
  els.appView.classList.remove("hidden");
  els.btnLogout.classList.remove("hidden");
}

function parseWeeksInput(raw) {
  const parts = raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  const weeks = new Set();
  for (const part of parts) {
    const [startRaw, endRaw] = part.split("-").map((item) => item.trim());
    const start = Number(startRaw);
    const end = endRaw ? Number(endRaw) : start;
    if (!Number.isInteger(start) || !Number.isInteger(end) || start <= 0 || end <= 0 || end < start) {
      throw new Error("周次格式应为 1-4,6,8 这种形式");
    }
    for (let week = start; week <= end; week += 1) {
      weeks.add(week);
    }
  }
  return [...weeks].sort((a, b) => a - b);
}

function formatWeeks(weeks) {
  return (weeks || []).join(",");
}

function formatCourseSummary(course) {
  return `周${course.weekday} 第${course.period_start}-${course.period_end}节 | 周次 ${formatWeeks(course.weeks) || "未设置"}`;
}

function populateScheduleMeta() {
  if (!state.schedule) {
    return;
  }
  els.inputSemester.value = state.schedule.semester || "";
  els.inputSemesterStart.value = state.schedule.semester_start || "";
  els.fetchSemester.value = state.schedule.semester || "";
}

function resetCourseForm(skipConfirm = false) {
  if (hasUnsavedDraft && !skipConfirm) {
    const confirmReset = window.confirm("当前编辑的课程数据尚未保存，确认清空并退出编辑吗？");
    if (!confirmReset) return false; 
  }
  state.editingCourseId = null;
  els.courseForm.reset();
  els.courseWeekday.value = "1";
  els.courseStart.value = "1";
  els.courseEnd.value = "2";
  els.courseWeekType.value = "all";
  els.courseFormTitle.textContent = "手动录入课程";
  els.btnCancelEdit.classList.add("hidden");
  localStorage.removeItem(STORAGE_KEY);
  hasUnsavedDraft = false;
  return true;
}


function saveCourseDraft() {
  if (!state.editingCourseId && !els.courseName.value.trim()) {
    return;
  }

  const draftData = {
    editingCourseId: state.editingCourseId,
    name: els.courseName.value.trim(),
    teacher: els.courseTeacher.value.trim(),
    location: els.courseLocation.value.trim(),
    weekday: els.courseWeekday.value,
    period_start: els.courseStart.value,
    period_end: els.courseEnd.value,
    weeks: els.courseWeeks.value.trim(),
    week_type: els.courseWeekType.value,
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(draftData));

  hasUnsavedDraft = Object.values(draftData).some(val => val);
}


function restoreCourseDraft() {
  const draftStr = localStorage.getItem(STORAGE_KEY);
  if (!draftStr) return;

  try {
    const draft = JSON.parse(draftStr);
    state.editingCourseId = draft.editingCourseId;
    els.courseFormTitle.textContent = draft.editingCourseId ? "编辑课程" : "手动录入课程";
    els.courseName.value = draft.name;
    els.courseTeacher.value = draft.teacher;
    els.courseLocation.value = draft.location;
    els.courseWeekday.value = draft.weekday;
    els.courseStart.value = draft.period_start;
    els.courseEnd.value = draft.period_end;
    els.courseWeeks.value = draft.weeks;
    els.courseWeekType.value = draft.week_type;
    els.btnCancelEdit.classList.remove("hidden");
    
    hasUnsavedDraft = true;
  } catch (e) {
    localStorage.removeItem(STORAGE_KEY);
    console.error("恢复课程草稿失败：", e);
  }
}
function validateCourseForm() {
  const errors = [];
  const name = els.courseName.value.trim();
  const start = Number(els.courseStart.value);
  const end = Number(els.courseEnd.value);
  const weekday = Number(els.courseWeekday.value);
  const semesterStart = els.inputSemesterStart.value;

  if (!name) errors.push("课程名称不能为空");
  if (start > end) errors.push("开始节次不能大于结束节次");
  if (start < 1 || end > 12) errors.push("节次范围必须在 1-12 之间");
  if (weekday < 1 || weekday > 7) errors.push("星期必须在 1-7 之间");
  if (semesterStart && !/^\d{4}-\d{2}-\d{2}$/.test(semesterStart)) {
    errors.push("开学日期格式必须为 YYYY-MM-DD");
  }

  if (errors.length) {
    throw new Error(errors.join("；"));
  }
}

function checkCourseConflict(newCourse) {
  if (!state.schedule?.courses) return;

  const newWeeks = new Set(newCourse.weeks);
  const newWeekday = Number(newCourse.weekday);
  const newStart = Number(newCourse.period_start);
  const newEnd = Number(newCourse.period_end);

  for (const course of state.schedule.courses) {
    if (course.id === state.editingCourseId) continue;

    if (Number(course.weekday) !== newWeekday) continue;

    const existingWeeks = new Set(course.weeks);
    const hasWeekOverlap = [...newWeeks].some(week => existingWeeks.has(week));
    if (!hasWeekOverlap) continue;

    const existingStart = Number(course.period_start);
    const existingEnd = Number(course.period_end);
    const hasPeriodOverlap = !(newEnd < existingStart || newStart > existingEnd);
    
    if (hasPeriodOverlap) {
      throw new Error(
        `课程冲突：与「${course.name}」在 周${course.weekday} 第${course.period_start}-${course.period_end}节（周次${formatWeeks(course.weeks)}）重复`
      );
    }
  }
}

async function submitCourseForm(e) {
  e.preventDefault(); 
  try {
    validateCourseForm();
    const weeks = parseWeeksInput(els.courseWeeks.value.trim());
    const courseData = {
      name: els.courseName.value.trim(),
      teacher: els.courseTeacher.value.trim(),
      location: els.courseLocation.value.trim(),
      weekday: Number(els.courseWeekday.value),
      period_start: Number(els.courseStart.value),
      period_end: Number(els.courseEnd.value),
      weeks,
      week_type: els.courseWeekType.value,
    };

    checkCourseConflict({ ...courseData, id: state.editingCourseId });

    let apiPath, method;
    if (state.editingCourseId) {
      apiPath = `/schedule/course/${state.editingCourseId}`;
      method = "PUT";
    } else {
      apiPath = "/schedule/course";
      method = "POST";
    }

    await api(apiPath, {
      method,
      body: JSON.stringify(courseData),
    });

    setGlobalMessage(state.editingCourseId ? "课程已更新" : "课程已添加", "success");
    resetCourseForm(true); 
    localStorage.removeItem(STORAGE_KEY);
    hasUnsavedDraft = false;
    await refreshSchedule(); 

  } catch (error) {
    setGlobalMessage(error.message, "error");
  }
}

function startEditCourse(course) {
  localStorage.removeItem(STORAGE_KEY);
  hasUnsavedDraft = false;
  state.editingCourseId = course.id;
  els.courseFormTitle.textContent = "编辑课程";
  els.courseName.value = course.name;
  els.courseTeacher.value = course.teacher;
  els.courseLocation.value = course.location;
  els.courseWeekday.value = String(course.weekday);
  els.courseStart.value = String(course.period_start);
  els.courseEnd.value = String(course.period_end);
  els.courseWeeks.value = formatWeeks(course.weeks);
  els.courseWeekType.value = course.week_type;
  els.btnCancelEdit.classList.remove("hidden");
  saveCourseDraft();
}

function renderCourseList() {
  const courses = state.schedule?.courses || [];
  els.courseCount.textContent = `${courses.length} 门`;
  els.courseList.innerHTML = "";

  if (!courses.length) {
    const empty = document.createElement("div");
    empty.className = "helper";
    empty.textContent = "当前还没有课程，可以手动录入或导入 JSON/PDF。";
    els.courseList.appendChild(empty);
    return;
  }

  for (const course of courses) {
    const item = document.createElement("article");
    item.className = "course-item";
    item.innerHTML = `
      <h4>${course.name}</h4>
      <div class="course-meta">
        <div>${course.teacher || "未填写教师"} | ${course.location || "未填写地点"}</div>
        <div>${formatCourseSummary(course)}</div>
      </div>
    `;

    const actions = document.createElement("div");
    actions.className = "button-row";

    const editButton = document.createElement("button");
    editButton.className = "button secondary small";
    editButton.textContent = "编辑";
    editButton.onclick = () => startEditCourse(course);

    const deleteButton = document.createElement("button");
    deleteButton.className = "button danger small";
    deleteButton.textContent = "删除";
    deleteButton.onclick = async () => {
      if (!window.confirm(`确认删除课程“${course.name}”？`)) {
        return;
      }
      try {
        await api(`/schedule/course/${course.id}`, { method: "DELETE" });
        await refreshSchedule();
        setGlobalMessage("课程已删除", "success");
      } catch (error) {
        setGlobalMessage(error.message, "error");
      }
    };

    actions.append(editButton, deleteButton);
    item.appendChild(actions);
    els.courseList.appendChild(item);
  }
}

function renderEmptyTable() {
  els.timetableBody.innerHTML = "";
  for (let period = 1; period <= 12; period += 1) {
    const row = document.createElement("tr");
    const label = document.createElement("td");
    label.className = "period-label";
    label.textContent = `第${period}节`;
    row.appendChild(label);
    for (let day = 1; day <= 7; day += 1) {
      row.appendChild(document.createElement("td"));
    }
    els.timetableBody.appendChild(row);
  }
}

function renderTable(data) {
  const occupied = Array.from({ length: 13 }, () => Array(8).fill(false));
  els.timetableBody.innerHTML = "";

  for (let period = 1; period <= 12; period += 1) {
    const row = document.createElement("tr");
    const label = document.createElement("td");
    label.className = "period-label";
    label.textContent = `第${period}节`;
    row.appendChild(label);

    for (let day = 1; day <= 7; day += 1) {
      if (occupied[period][day]) {
        continue;
      }

      const courses = (data[String(day)] || []).filter((course) => course.period_start === period);
      if (courses.length) {
        const course = courses[0];
        const cell = document.createElement("td");
        cell.rowSpan = course.period_end - course.period_start + 1;
        cell.innerHTML = `
          <div class="course-card">
            <strong>${course.name}</strong>
            <span>${course.teacher || "未填写教师"}</span>
            <span>${course.location || "未填写地点"}</span>
            <span>周次 ${formatWeeks(course.weeks)}</span>
          </div>
        `;
        row.appendChild(cell);
        for (let next = period + 1; next <= course.period_end; next += 1) {
          occupied[next][day] = true;
        }
      } else {
        row.appendChild(document.createElement("td"));
      }
    }

    els.timetableBody.appendChild(row);
  }
}

async function loadWeek() {
  if (!state.schedule) {
    renderEmptyTable();
    return;
  }
  const label = state.weekOffset === 0
    ? "本周课表"
    : state.weekOffset > 0
      ? `第 +${state.weekOffset} 周偏移`
      : `第 ${state.weekOffset} 周偏移`;
  els.weekLabel.textContent = label;

  try {
    const path = state.weekOffset === 0 ? "/query/week" : `/query/week/${state.weekOffset}`;
    const data = await api(path);
    renderTable(data);
  } catch (error) {
    renderEmptyTable();
    setGlobalMessage(error.message, "error");
  }
}

async function loadNow() {
  if (!state.schedule) {
    els.nowCard.textContent = "请先初始化学期并录入课表。";
    return;
  }

  try {
    const current = await api("/query/now");
    if (!current) {
      els.nowCard.textContent = "当前节次没有课程。";
      return;
    }
    els.nowCard.innerHTML = `
      <strong>${current.name}</strong><br>
      ${current.teacher || "未填写教师"} | ${current.location || "未填写地点"}<br>
      周${current.weekday} 第${current.period_start}-${current.period_end}节
    `;
  } catch (error) {
    els.nowCard.textContent = error.message;
  }
}

async function refreshSchedule() {
  try {
    state.schedule = await api("/schedule");
    populateScheduleMeta();
    renderCourseList();
    await Promise.all([loadWeek(), loadNow()]);
  } catch (error) {
    state.schedule = null;
    renderEmptyTable();
    renderCourseList();
    els.nowCard.textContent = "请先初始化学期并录入课表。";
    setGlobalMessage(error.message, "error");
  }
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

    state.user = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ student_id: studentId, password }),
    });
    await enterAppView();
  } catch (error) {
    setMessage(els.authMessage, error.message, "error");
  }
}

async function enterAppView() {
  state.user = await api("/auth/me");
  showAppView();
  els.headerUser.textContent = `${state.user.name}（${state.user.student_id}）`;
  els.fetchAccount.value = state.user.scnu_account || state.user.student_id;
  setGlobalMessage("已登录，可以初始化学期、录入课程或导入文件。");
  await refreshSchedule();
}

async function saveScheduleMeta() {
  try {
    validateCourseForm();

    state.schedule = await api("/schedule", {
      method: "POST",
      body: JSON.stringify({
        semester: els.inputSemester.value.trim(),
        semester_start: els.inputSemesterStart.value,
      }),
    });
    populateScheduleMeta();
    await Promise.all([loadWeek(), loadNow()]);
    setGlobalMessage("学期信息已保存", "success");
  } catch (error) {
    setGlobalMessage(error.message, "error");
  }
}

async function uploadScheduleFile() {
  const file = els.uploadFile.files[0];
  if (!file) {
    setGlobalMessage("请先选择 JSON 或 PDF 文件", "error");
    return;
  }

  const form = new FormData();
  form.append("file", file);

  try {
    state.schedule = await api("/schedule/upload", { method: "POST", body: form });
    renderCourseList();
    populateScheduleMeta();
    await Promise.all([loadWeek(), loadNow()]);
    setGlobalMessage(`已导入文件 ${file.name}`, "success");
    els.uploadFile.value = "";
  } catch (error) {
    setGlobalMessage(error.message, "error");
  }
}

function stopFetchPolling() {
  if (state.fetchPollTimer) {
    window.clearInterval(state.fetchPollTimer);
    state.fetchPollTimer = null;
  }
}

async function pollFetchTask(taskId) {
  try {
    const task = await api(`/schedule/fetch/${taskId}`);
    els.fetchStatus.textContent = `${task.status} | ${task.message}`;
    if (task.status === "succeeded" || task.status === "failed") {
      stopFetchPolling();
      if (task.status === "succeeded") {
        await refreshSchedule();
        setGlobalMessage(task.message, "success");
      } else {
        setGlobalMessage(task.message, "error");
      }
    }
  } catch (error) {
    stopFetchPolling();
    els.fetchStatus.textContent = error.message;
  }
}

async function submitFetchTask() {
  const password = els.fetchPassword.value;
  if (!password) {
    setGlobalMessage("抓取前需要填写教务系统密码", "error");
    return;
  }

  try {
    const task = await api("/schedule/fetch", {
      method: "POST",
      body: JSON.stringify({
        scnu_account: els.fetchAccount.value.trim() || null,
        scnu_password: password,
        semester_id: els.fetchSemester.value.trim() || null,
        prefer_playwright: els.fetchPreferPlaywright.checked,
      }),
    });
    state.fetchTaskId = task.task_id;
    els.fetchStatus.textContent = `${task.status} | ${task.message}`;
    stopFetchPolling();
    state.fetchPollTimer = window.setInterval(() => pollFetchTask(task.task_id), 2500);
    await pollFetchTask(task.task_id);
  } catch (error) {
    setGlobalMessage(error.message, "error");
  }
}

async function submitCourseForm(event) {
  event.preventDefault();

  try {
    validateCourseForm();

    const wasEditing = Boolean(state.editingCourseId);
    const weeks = parseWeeksInput(els.courseWeeks.value);
    const payload = {
      name: els.courseName.value.trim(),
      teacher: els.courseTeacher.value.trim(),
      location: els.courseLocation.value.trim(),
      weekday: Number(els.courseWeekday.value),
      period_start: Number(els.courseStart.value),
      period_end: Number(els.courseEnd.value),
      weeks: weeks,
      week_type: els.courseWeekType.value,
    };


    checkCourseConflict(payload);

    if (wasEditing) {
      await api(`/schedule/course/${state.editingCourseId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setGlobalMessage("课程已更新", "success");
    } else {
      await api("/schedule/course", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setGlobalMessage("课程已添加", "success");
    }

    resetCourseForm();
    await refreshSchedule();

  } catch (error) {
    setGlobalMessage(error.message, "error");
  }
}


if (els.authToggle) els.authToggle.addEventListener("click", toggleAuthMode);
if (els.authSubmit) els.authSubmit.addEventListener("click", submitAuth);
if (els.btnLogout) els.btnLogout.addEventListener("click", showAuthView);
if (els.btnSaveScheduleMeta) els.btnSaveScheduleMeta.addEventListener("click", withLoading(els.btnSaveScheduleMeta, saveScheduleMeta));
if (els.btnUpload) els.btnUpload.addEventListener("click", withLoading(els.btnUpload, uploadScheduleFile));
if (els.btnFetch) els.btnFetch.addEventListener("click", withLoading(els.btnFetch, submitFetchTask));
if (els.btnCancelEdit) els.btnCancelEdit.addEventListener("click", resetCourseForm);
if (els.courseForm) els.courseForm.addEventListener("submit", submitCourseForm);
if (els.btnPrevWeek) els.btnPrevWeek.addEventListener("click", () => {
  state.weekOffset -= 1;
  loadWeek();
});
if (els.btnNextWeek) els.btnNextWeek.addEventListener("click", () => {
  state.weekOffset += 1;
  loadWeek();
});


document.addEventListener("DOMContentLoaded", async () => {
  try {
    state.user = await api("/auth/me");
    await enterAppView();
  } catch {
    showAuthView();
  }
});

document.addEventListener("DOMContentLoaded", function() {
  restoreCourseDraft();

  const courseFormInputs = [
    els.courseName, els.courseTeacher, els.courseLocation,
    els.courseWeekday, els.courseStart, els.courseEnd,
    els.courseWeeks, els.courseWeekType
  ];

  courseFormInputs.forEach(input => {
    if (input) {
      input.addEventListener("input", saveCourseDraft);
      input.addEventListener("change", saveCourseDraft);
    }
  });

  if (els.btnCancelEdit) {
    els.btnCancelEdit.onclick = function() {
      const isReset = resetCourseForm();
      if (isReset) {
        localStorage.removeItem(STORAGE_KEY);
        hasUnsavedDraft = false;
      }
    };
  }
  if (els.courseForm) {
    els.courseForm.addEventListener("submit", submitCourseForm);
  }

  window.addEventListener("beforeunload", function(e) {
    if (hasUnsavedDraft) {
      e.preventDefault();
      e.returnValue = "当前编辑的课程数据尚未保存，确定离开吗？";
      return e.returnValue;
    }
  });
});
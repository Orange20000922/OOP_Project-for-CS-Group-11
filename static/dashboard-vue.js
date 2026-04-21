const dashboardFrontend = window.scheduleFrontend;

new Vue({
  el: "#dashboard-app",
  data() {
    return {
      loading: true,
      statusText: "正在加载工作台数据",
      statusType: "",
      user: null,
      schedule: null,
      currentCourse: null,
      todayCourses: [],
      weekCourses: dashboardFrontend.createEmptyWeekCourses(),
      weekOffset: 0,
      fetchTaskId: null,
      fetchPollTimer: null,
      fetchStatusText: "",
      semesterForm: {
        semester: "",
        semesterStart: "",
      },
      fetchForm: {
        account: "",
        password: "",
        semesterId: "",
        preferPlaywright: false,
      },
      courseForm: {
        name: "",
        teacher: "",
        location: "",
        weekday: 1,
        periodStart: 1,
        periodEnd: 2,
        weeks: "",
        weekType: "all",
      },
      editingCourseId: null,
    };
  },
  computed: {
    statusClass() {
      return ["status-banner", this.statusType].filter(Boolean);
    },
    weekLabel() {
      return dashboardFrontend.formatWeekLabel(this.weekOffset);
    },
    hasSchedule() {
      return !!this.schedule;
    },
    courseCount() {
      return this.sortedCourses.length;
    },
    sortedCourses() {
      if (!this.schedule || !Array.isArray(this.schedule.courses)) {
        return [];
      }
      return this.schedule.courses.slice().sort(function (left, right) {
        return (
          left.weekday - right.weekday ||
          left.period_start - right.period_start ||
          left.period_end - right.period_end ||
          left.name.localeCompare(right.name)
        );
      });
    },
    timetableRows() {
      const occupied = Array.from({ length: 13 }, function () {
        return Array(8).fill(false);
      });
      const rows = [];

      for (let period = 1; period <= 12; period += 1) {
        const row = {
          period,
          cells: [],
        };

        for (let day = 1; day <= 7; day += 1) {
          if (occupied[period][day]) {
            row.cells.push({
              key: `${period}-${day}`,
              skip: true,
            });
            continue;
          }

          const courses = (this.weekCourses[String(day)] || []).filter(function (course) {
            return course.period_start === period;
          });

          if (courses.length) {
            const course = courses[0];
            const rowspan = course.period_end - course.period_start + 1;
            row.cells.push({
              key: `${period}-${day}`,
              course,
              rowspan,
              skip: false,
              empty: false,
            });
            for (let next = period + 1; next <= course.period_end; next += 1) {
              occupied[next][day] = true;
            }
            continue;
          }

          row.cells.push({
            key: `${period}-${day}`,
            skip: false,
            empty: true,
          });
        }

        rows.push(row);
      }

      return rows;
    },
  },
  methods: {
    setStatus(text, type) {
      this.statusText = text || "";
      this.statusType = type || "";
    },
    syncDashboardData(payload) {
      this.user = payload.user || null;
      this.schedule = payload.schedule || null;
      this.currentCourse = payload.current_course || null;
      this.todayCourses = payload.today_courses || [];
      this.weekCourses = payload.week_courses || dashboardFrontend.createEmptyWeekCourses();

      if (this.user) {
        this.fetchForm.account = this.user.scnu_account || this.user.student_id || "";
      }

      if (this.schedule) {
        this.semesterForm.semester = this.schedule.semester || "";
        this.semesterForm.semesterStart = this.schedule.semester_start || "";
        this.fetchForm.semesterId = this.schedule.semester || "";
      } else {
        this.semesterForm.semester = "";
        this.semesterForm.semesterStart = "";
        this.fetchForm.semesterId = "";
      }
    },
    async loadOverview(options = {}) {
      const silent = !!options.silent;
      try {
        const payload = await dashboardFrontend.api(`/query/overview?week_offset=${this.weekOffset}`);
        this.syncDashboardData(payload);
        if (!silent) {
          if (payload.has_schedule) {
            this.setStatus("工作台已同步最新课表数据", "success");
          } else {
            this.setStatus("已登录，请先初始化学期后再录入或导入课表", "");
          }
        }
      } catch (error) {
        if (error.status === 401) {
          dashboardFrontend.redirectToLogin();
          return;
        }
        this.setStatus(error.message, "error");
      } finally {
        this.loading = false;
      }
    },
    weekdayLabel(weekday) {
      return dashboardFrontend.weekdayLabel(weekday);
    },
    formatWeeks(weeks) {
      return dashboardFrontend.formatWeeks(weeks);
    },
    courseSummary(course) {
      return `${this.weekdayLabel(course.weekday)} 第${course.period_start}-${course.period_end}节 | 周次 ${this.formatWeeks(course.weeks)}`;
    },
    knowledgeWorkspaceUrl(courseId) {
      return `/knowledge-workspace?course_id=${encodeURIComponent(courseId)}`;
    },
    parseWeeksInput(raw) {
      const normalized = raw
        .replace(/[，、；;]/g, ",")
        .replace(/[－–—~～]/g, "-");

      const parts = normalized
        .split(",")
        .map(function (item) {
          return item.trim();
        })
        .filter(Boolean);

      const weeks = new Set();
      for (let index = 0; index < parts.length; index += 1) {
        const part = parts[index];
        const range = part.split("-").map(function (item) {
          return item.trim();
        });
        const start = Number(range[0]);
        const end = range[1] ? Number(range[1]) : start;
        if (!Number.isInteger(start) || !Number.isInteger(end) || start <= 0 || end <= 0 || end < start) {
          throw new Error("周次格式应为 1-4,6,8 这种形式");
        }
        for (let week = start; week <= end; week += 1) {
          weeks.add(week);
        }
      }
      return Array.from(weeks).sort(function (left, right) {
        return left - right;
      });
    },
    resetCourseForm() {
      this.editingCourseId = null;
      this.courseForm = {
        name: "",
        teacher: "",
        location: "",
        weekday: 1,
        periodStart: 1,
        periodEnd: 2,
        weeks: "",
        weekType: "all",
      };
    },
    startEditCourse(course) {
      this.editingCourseId = course.id;
      this.courseForm = {
        name: course.name,
        teacher: course.teacher,
        location: course.location,
        weekday: course.weekday,
        periodStart: course.period_start,
        periodEnd: course.period_end,
        weeks: Array.isArray(course.weeks) ? course.weeks.join(",") : "",
        weekType: course.week_type,
      };
      this.setStatus(`正在编辑课程：${course.name}`, "");
    },
    async saveScheduleMeta() {
      try {
        await dashboardFrontend.api("/schedule", {
          method: "POST",
          body: JSON.stringify({
            semester: this.semesterForm.semester.trim(),
            semester_start: this.semesterForm.semesterStart,
          }),
        });
        await this.loadOverview({ silent: true });
        this.setStatus("学期信息已保存", "success");
      } catch (error) {
        this.setStatus(error.message, "error");
      }
    },
    async uploadScheduleFile() {
      const input = this.$refs.scheduleFileInput;
      const file = input && input.files ? input.files[0] : null;
      if (!file) {
        this.setStatus("请先选择 JSON 或 PDF 文件", "error");
        return;
      }

      const form = new FormData();
      form.append("file", file);

      try {
        await dashboardFrontend.api("/schedule/upload", {
          method: "POST",
          body: form,
        });
        if (input) {
          input.value = "";
        }
        await this.loadOverview({ silent: true });
        this.setStatus(`已导入文件：${file.name}`, "success");
      } catch (error) {
        this.setStatus(error.message, "error");
      }
    },
    stopFetchPolling() {
      if (this.fetchPollTimer) {
        window.clearInterval(this.fetchPollTimer);
        this.fetchPollTimer = null;
      }
    },
    async pollFetchTask(taskId) {
      try {
        const task = await dashboardFrontend.api(`/schedule/fetch/${taskId}`);
        this.fetchStatusText = `${task.status} | ${task.message}`;
        if (task.status === "succeeded" || task.status === "failed") {
          this.stopFetchPolling();
          if (task.status === "succeeded") {
            await this.loadOverview({ silent: true });
            this.fetchForm.password = "";
            this.setStatus(task.message, "success");
          } else {
            this.setStatus(task.message, "error");
          }
        }
      } catch (error) {
        this.stopFetchPolling();
        this.fetchStatusText = error.message;
        this.setStatus(error.message, "error");
      }
    },
    async submitFetchTask() {
      if (!this.fetchForm.password) {
        this.setStatus("抓取前需要填写统一身份认证密码", "error");
        return;
      }

      try {
        const task = await dashboardFrontend.api("/schedule/fetch", {
          method: "POST",
          body: JSON.stringify({
            scnu_account: this.fetchForm.account.trim() || null,
            scnu_password: this.fetchForm.password,
            semester_id: this.fetchForm.semesterId.trim() || null,
            prefer_playwright: this.fetchForm.preferPlaywright,
          }),
        });
        this.fetchTaskId = task.task_id;
        this.fetchStatusText = `${task.status} | ${task.message}`;
        this.stopFetchPolling();
        this.fetchPollTimer = window.setInterval(() => {
          this.pollFetchTask(task.task_id);
        }, 2500);
        await this.pollFetchTask(task.task_id);
      } catch (error) {
        this.setStatus(error.message, "error");
      }
    },
    async submitCourseForm() {
      try {
        const payload = {
          name: this.courseForm.name.trim(),
          teacher: this.courseForm.teacher.trim(),
          location: this.courseForm.location.trim(),
          weekday: Number(this.courseForm.weekday),
          period_start: Number(this.courseForm.periodStart),
          period_end: Number(this.courseForm.periodEnd),
          weeks: this.parseWeeksInput(this.courseForm.weeks.trim()),
          week_type: this.courseForm.weekType,
        };

        const editing = !!this.editingCourseId;
        const path = editing ? `/schedule/course/${this.editingCourseId}` : "/schedule/course";
        const method = editing ? "PUT" : "POST";

        await dashboardFrontend.api(path, {
          method,
          body: JSON.stringify(payload),
        });
        this.resetCourseForm();
        await this.loadOverview({ silent: true });
        this.setStatus(editing ? "课程已更新" : "课程已新增", "success");
      } catch (error) {
        this.setStatus(error.message, "error");
      }
    },
    async deleteCourse(course) {
      if (!window.confirm(`确认删除课程“${course.name}”吗？`)) {
        return;
      }

      try {
        await dashboardFrontend.api(`/schedule/course/${course.id}`, {
          method: "DELETE",
        });
        await this.loadOverview({ silent: true });
        this.setStatus("课程已删除", "success");
      } catch (error) {
        this.setStatus(error.message, "error");
      }
    },
    changeWeek(delta) {
      this.weekOffset += delta;
      this.loadOverview({ silent: true });
    },
    async logout() {
      try {
        await dashboardFrontend.api("/auth/logout", { method: "POST" });
      } finally {
        this.stopFetchPolling();
        dashboardFrontend.redirectToLogin();
      }
    },
  },
  mounted() {
    this.resetCourseForm();
    this.loadOverview();
  },
  beforeDestroy() {
    this.stopFetchPolling();
  },
});

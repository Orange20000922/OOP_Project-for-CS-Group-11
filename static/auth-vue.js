const authFrontend = window.scheduleFrontend;

new Vue({
  el: "#auth-app",
  data() {
    return {
      isRegister: false,
      loading: false,
      messageText: "",
      messageType: "",
      form: {
        studentId: "",
        password: "",
        name: "",
        scnuAccount: "",
      },
    };
  },
  computed: {
    panelTitle() {
      return this.isRegister ? "注册本地账号" : "登录";
    },
    submitLabel() {
      return this.isRegister ? "注册并进入工作台" : "登录并进入工作台";
    },
    toggleLabel() {
      return this.isRegister ? "已有账号，返回登录" : "没有账号，立即注册";
    },
    messageClass() {
      return ["message", this.messageType].filter(Boolean);
    },
  },
  methods: {
    setMessage(text, type = "") {
      this.messageText = text || "";
      this.messageType = type;
    },
    toggleMode() {
      this.isRegister = !this.isRegister;
      this.setMessage("");
    },
    async submit() {
      const studentId = this.form.studentId.trim();
      const password = this.form.password;
      const name = this.form.name.trim();
      const scnuAccount = this.form.scnuAccount.trim();

      if (!studentId || !password) {
        this.setMessage("请填写学号和密码", "error");
        return;
      }

      if (this.isRegister && !name) {
        this.setMessage("注册时需要填写姓名", "error");
        return;
      }

      this.loading = true;
      this.setMessage("");

      try {
        if (this.isRegister) {
          await authFrontend.api("/auth/register", {
            method: "POST",
            body: JSON.stringify({
              student_id: studentId,
              password,
              name,
              scnu_account: scnuAccount || null,
            }),
          });
        }

        await authFrontend.api("/auth/login", {
          method: "POST",
          body: JSON.stringify({
            student_id: studentId,
            password,
          }),
        });
        authFrontend.redirectToDashboard();
      } catch (error) {
        this.setMessage(error.message, "error");
      } finally {
        this.loading = false;
      }
    },
  },
  async mounted() {
    try {
      await authFrontend.api("/auth/me");
      authFrontend.redirectToDashboard();
    } catch (error) {
      if (error.status && error.status !== 401) {
        this.setMessage(error.message, "error");
      }
    }
  },
});

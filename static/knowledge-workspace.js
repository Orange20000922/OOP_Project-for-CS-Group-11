(function initKnowledgeWorkspace(global) {
  const frontend = global.scheduleFrontend;

  function cloneEmptyTree() {
    return {
      root_ids: [],
      topics: {},
    };
  }

  function createEmptyGraphData() {
    return {
      nodes: [],
      links: [],
      total_nodes: 0,
      total_links: 0,
      selected_topic_ids: [],
      routing_applied: false,
    };
  }

  function createEmptyNoteForm() {
    return {
      title: "",
      summary: "",
      courseId: "",
    };
  }

  function createEmptyTopicForm() {
    return {
      name: "",
      summary: "",
      keywords: "",
      parentId: "",
    };
  }

  function buildQuery(params) {
    const search = new URLSearchParams();

    Object.keys(params || {}).forEach(function appendParam(key) {
      const value = params[key];
      if (value === undefined || value === null || value === "") {
        return;
      }
      search.set(key, String(value));
    });

    const queryString = search.toString();
    return queryString ? "?" + queryString : "";
  }

  function normalizeTree(tree) {
    if (!tree || typeof tree !== "object") {
      return cloneEmptyTree();
    }

    return {
      root_ids: Array.isArray(tree.root_ids) ? tree.root_ids.slice() : [],
      topics: tree.topics && typeof tree.topics === "object" ? tree.topics : {},
    };
  }

  function flattenTree(tree) {
    const normalized = normalizeTree(tree);
    const rows = [];
    const topics = normalized.topics || {};
    const visited = {};

    function walk(topicId, depth) {
      if (visited[topicId]) {
        return;
      }
      visited[topicId] = true;

      const topic = topics[topicId];
      if (!topic) {
        return;
      }

      rows.push({
        depth: depth,
        topic: topic,
      });

      (topic.child_ids || []).forEach(function visitChild(childId) {
        walk(childId, depth + 1);
      });
    }

    normalized.root_ids.forEach(function visitRoot(rootId) {
      walk(rootId, 0);
    });

    Object.keys(topics).forEach(function visitLooseTopic(topicId) {
      walk(topicId, 0);
    });

    return rows;
  }

  function collectDescendantIds(topics, startId) {
    if (!startId || !topics[startId]) {
      return [];
    }

    const stack = [startId];
    const ordered = [];
    const seen = {};

    while (stack.length) {
      const currentId = stack.pop();
      if (seen[currentId]) {
        continue;
      }
      seen[currentId] = true;

      const topic = topics[currentId];
      if (!topic) {
        continue;
      }

      ordered.push(currentId);

      const children = Array.isArray(topic.child_ids) ? topic.child_ids.slice() : [];
      for (let index = children.length - 1; index >= 0; index -= 1) {
        stack.push(children[index]);
      }
    }

    return ordered;
  }

  function buildAggregateCounts(tree) {
    const normalized = normalizeTree(tree);
    const counts = {};
    const topics = normalized.topics || {};

    function countFor(topicId) {
      if (!topics[topicId]) {
        return 0;
      }
      if (counts[topicId] !== undefined) {
        return counts[topicId];
      }

      const topic = topics[topicId];
      let total = Array.isArray(topic.note_ids) ? topic.note_ids.length : 0;
      (topic.child_ids || []).forEach(function addChild(childId) {
        total += countFor(childId);
      });
      counts[topicId] = total;
      return total;
    }

    Object.keys(topics).forEach(function compute(topicId) {
      countFor(topicId);
    });

    return counts;
  }

  function sortCourses(courses) {
    return (Array.isArray(courses) ? courses.slice() : []).sort(function compareCourses(left, right) {
      return (
        left.weekday - right.weekday ||
        left.period_start - right.period_start ||
        left.period_end - right.period_end ||
        String(left.name || "").localeCompare(String(right.name || ""))
      );
    });
  }

  function sortNotes(notes) {
    return (Array.isArray(notes) ? notes.slice() : []).sort(function compareNotes(left, right) {
      return (
        String(right.updated_at || right.created_at || "").localeCompare(String(left.updated_at || left.created_at || "")) ||
        String(left.filename || "").localeCompare(String(right.filename || ""))
      );
    });
  }

  function splitKeywords(raw) {
    const seen = {};
    return String(raw || "")
      .split(/[\n,，]/)
      .map(function trimItem(item) {
        return item.trim();
      })
      .filter(function filterItem(item) {
        if (!item) {
          return false;
        }
        const key = item.toLowerCase();
        if (seen[key]) {
          return false;
        }
        seen[key] = true;
        return true;
      });
  }

  function formatDateTime(value) {
    if (!value) {
      return "刚刚";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }

    try {
      return new Intl.DateTimeFormat("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
    } catch (error) {
      return value;
    }
  }

  async function fetchArrayBuffer(url) {
    const response = await fetch(url, {
      credentials: "include",
    });

    if (!response.ok) {
      const contentType = response.headers.get("content-type") || "";
      let payload;
      if (contentType.includes("application/json")) {
        payload = await response.json();
      } else {
        payload = await response.text();
      }
      const message = typeof payload === "object"
        ? payload.detail || payload.error || payload.message || "Request failed"
        : String(payload || "Request failed");
      const error = new Error(message);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }

    return response.arrayBuffer();
  }

  new Vue({
    el: "#knowledge-app",
    data: function data() {
      return {
        loading: true,
        statusText: "正在载入知识工作台",
        statusType: "",
        user: null,
        schedule: null,
        courseId: "",
        notes: [],
        tree: cloneEmptyTree(),
        noteDetail: null,
        selectedNoteId: "",
        selectedChunkId: "",
        noteForm: createEmptyNoteForm(),
        uploadBusy: false,
        previewLoading: false,
        previewKind: "",
        previewUrl: "",
        previewHtml: "",
        activeTopicId: "",
        topicCreateForm: createEmptyTopicForm(),
        topicEditForm: createEmptyTopicForm(),
        askQuestion: "",
        askAnswer: "",
        askSources: [],
        askBusy: false,
        searchQuery: "",
        searchLimit: 8,
        searchResults: [],
        searchBusy: false,
        graphQuery: "",
        graphTopK: 3,
        graphMinScore: 0.55,
        graphTopicLimit: 3,
        graphLoading: false,
        graphError: "",
        graphData: createEmptyGraphData(),
        graphRenderer: null,
      };
    },
    computed: {
      statusClass: function statusClass() {
        return ["status-banner", this.statusType].filter(Boolean);
      },
      sortedCourses: function sortedCoursesComputed() {
        if (!this.schedule || !Array.isArray(this.schedule.courses)) {
          return [];
        }
        return sortCourses(this.schedule.courses);
      },
      selectedCourse: function selectedCourseComputed() {
        const courseId = String(this.courseId || "");
        return this.sortedCourses.find(function findCourse(course) {
          return String(course.id) === courseId;
        }) || null;
      },
      pageTitle: function pageTitle() {
        return this.selectedCourse ? this.selectedCourse.name + " 知识工作台" : "知识工作台";
      },
      pageSubtitle: function pageSubtitle() {
        if (this.selectedCourse) {
          return "保持课程维度独立，左侧维护知识树，中间管理笔记，右侧负责检索、问答与图谱。";
        }
        return "这里保留完整的知识工作流，用于跨课程演示整体能力。";
      },
      courseScopeLabel: function courseScopeLabel() {
        return this.selectedCourse ? "当前课程视图" : "全局视图";
      },
      treeRows: function treeRowsComputed() {
        return flattenTree(this.tree);
      },
      topicOptions: function topicOptionsComputed() {
        return this.treeRows;
      },
      topicAggregateCounts: function topicAggregateCountsComputed() {
        return buildAggregateCounts(this.tree);
      },
      selectedTopic: function selectedTopicComputed() {
        return this.tree && this.tree.topics ? this.tree.topics[this.activeTopicId] || null : null;
      },
      editableParentOptions: function editableParentOptionsComputed() {
        const topics = (this.tree && this.tree.topics) || {};
        if (!this.selectedTopic) {
          return this.treeRows;
        }
        const excluded = {};
        collectDescendantIds(topics, this.selectedTopic.id).forEach(function mark(topicId) {
          excluded[topicId] = true;
        });
        return this.treeRows.filter(function filterRow(row) {
          return !excluded[row.topic.id];
        });
      },
      noteTopicsById: function noteTopicsByIdComputed() {
        const mapping = {};
        const topics = (this.tree && this.tree.topics) || {};

        Object.keys(topics).forEach(function collectTopic(topicId) {
          const topic = topics[topicId];
          (topic.note_ids || []).forEach(function assignNote(noteId) {
            if (!mapping[noteId]) {
              mapping[noteId] = [];
            }
            mapping[noteId].push({
              id: topic.id,
              name: topic.name,
            });
          });
        });

        return mapping;
      },
      activeTopicDescendantIds: function activeTopicDescendantIdsComputed() {
        return collectDescendantIds((this.tree && this.tree.topics) || {}, this.activeTopicId);
      },
      activeTopicNoteIdSet: function activeTopicNoteIdSetComputed() {
        if (!this.activeTopicId) {
          return null;
        }

        const noteIds = new Set();
        const topics = (this.tree && this.tree.topics) || {};

        this.activeTopicDescendantIds.forEach(function addTopicNotes(topicId) {
          const topic = topics[topicId];
          if (!topic) {
            return;
          }
          (topic.note_ids || []).forEach(function addNoteId(noteId) {
            noteIds.add(noteId);
          });
        });

        return noteIds;
      },
      visibleNotes: function visibleNotesComputed() {
        const sorted = sortNotes(this.notes);
        if (!this.activeTopicNoteIdSet) {
          return sorted;
        }

        return sorted.filter(function filterByTopic(note) {
          return this.activeTopicNoteIdSet.has(note.id);
        }, this);
      },
      selectedNote: function selectedNoteComputed() {
        const selectedNoteId = String(this.selectedNoteId || "");
        return this.notes.find(function findNote(note) {
          return String(note.id) === selectedNoteId;
        }) || null;
      },
      selectedNoteInActiveTopic: function selectedNoteInActiveTopicComputed() {
        if (!this.selectedNoteId || !this.selectedTopic) {
          return false;
        }
        return (this.selectedTopic.note_ids || []).indexOf(this.selectedNoteId) >= 0;
      },
      totalChunks: function totalChunksComputed() {
        return this.notes.reduce(function sumChunks(total, note) {
          return total + Number(note.chunk_count || 0);
        }, 0);
      },
      routedTopicNames: function routedTopicNamesComputed() {
        const topics = (this.tree && this.tree.topics) || {};
        return (this.graphData.selected_topic_ids || [])
          .map(function mapTopicName(topicId) {
            return topics[topicId] ? topics[topicId].name : "";
          })
          .filter(Boolean);
      },
      previewLabel: function previewLabelComputed() {
        if (this.previewLoading) {
          return "预览加载中";
        }
        if (this.previewKind === "pdf") {
          return "PDF 在线预览";
        }
        if (this.previewKind === "docx") {
          return "DOCX HTML 预览";
        }
        return "暂无预览";
      },
    },
    methods: {
      setStatus: function setStatus(text, type) {
        this.statusText = text || "";
        this.statusType = type || "";
      },
      handleApiError: function handleApiError(error, fallbackMessage) {
        if (error && error.status === 401) {
          frontend.redirectToLogin();
          return;
        }
        this.setStatus((error && error.message) || fallbackMessage || "请求失败", "error");
      },
      buildCoursePath: function buildCoursePath(path, extraParams) {
        const params = Object.assign({}, extraParams || {});
        if (this.courseId) {
          params.course_id = this.courseId;
        }
        return path + buildQuery(params);
      },
      courseNameById: function courseNameById(courseId) {
        if (!courseId) {
          return "未关联课程";
        }
        const course = this.sortedCourses.find(function findCourse(item) {
          return String(item.id) === String(courseId);
        });
        return course ? course.name : courseId;
      },
      courseSummary: function courseSummary(course) {
        if (!course) {
          return "";
        }
        return frontend.weekdayLabel(course.weekday) + " 第" + course.period_start + "-" + course.period_end + "节 · " + (course.location || "未填写地点");
      },
      noteDisplayTitle: function noteDisplayTitle(note) {
        if (!note) {
          return "";
        }
        return String(note.title || "").trim() || String(note.filename || "").trim() || "未命名笔记";
      },
      formatDateTime: function formatDateTimeMethod(value) {
        return formatDateTime(value);
      },
      formatFileType: function formatFileType(fileType) {
        return String(fileType || "").toUpperCase() || "FILE";
      },
      scoreLabel: function scoreLabel(score) {
        return "相似度 " + Number(score || 0).toFixed(2);
      },
      topicOptionLabel: function topicOptionLabel(row) {
        return new Array(row.depth + 1).join("　") + row.topic.name;
      },
      syncNoteForm: function syncNoteForm(detail) {
        const note = detail && detail.note ? detail.note : null;
        if (!note) {
          this.noteForm = createEmptyNoteForm();
          return;
        }
        this.noteForm = {
          title: note.title || "",
          summary: note.summary || "",
          courseId: note.course_id || "",
        };
      },
      syncTopicEditForm: function syncTopicEditForm() {
        if (!this.selectedTopic) {
          this.topicEditForm = createEmptyTopicForm();
          return;
        }

        this.topicEditForm = {
          name: this.selectedTopic.name || "",
          summary: this.selectedTopic.summary || "",
          keywords: (this.selectedTopic.keywords || []).join(", "),
          parentId: this.selectedTopic.parent_id || "",
        };
      },
      resetTopicCreateForm: function resetTopicCreateForm() {
        this.topicCreateForm = createEmptyTopicForm();
        if (this.activeTopicId) {
          this.topicCreateForm.parentId = this.activeTopicId;
        }
      },
      useActiveTopicAsParent: function useActiveTopicAsParent() {
        this.topicCreateForm.parentId = this.activeTopicId || "";
      },
      updateUrlCourseId: function updateUrlCourseId() {
        const url = new URL(global.location.href);
        if (this.courseId) {
          url.searchParams.set("course_id", this.courseId);
        } else {
          url.searchParams.delete("course_id");
        }
        global.history.replaceState({}, "", url.pathname + url.search + url.hash);
      },
      applyTree: function applyTree(tree, options) {
        const normalized = normalizeTree(tree);
        const preferredTopicId = options && options.preferTopicId ? options.preferTopicId : "";
        const previousTopicId = this.activeTopicId;

        this.tree = normalized;

        if (preferredTopicId && normalized.topics[preferredTopicId]) {
          this.activeTopicId = preferredTopicId;
        } else if (previousTopicId && normalized.topics[previousTopicId]) {
          this.activeTopicId = previousTopicId;
        } else {
          this.activeTopicId = normalized.root_ids[0] || Object.keys(normalized.topics)[0] || "";
        }

        this.syncTopicEditForm();
        if (!this.topicCreateForm.parentId || !normalized.topics[this.topicCreateForm.parentId]) {
          this.topicCreateForm.parentId = this.activeTopicId || "";
        }
      },
      async initializePage() {
        this.loading = true;

        try {
          await Promise.all([
            this.loadOverview(),
            this.loadNotes({ preserveSelection: false }),
            this.loadTree({ preserveSelection: false }),
          ]);

          if (this.selectedNoteId) {
            await this.openNote(this.selectedNoteId, { force: true, silentStatus: true });
          } else if (this.notes.length) {
            await this.openNote(this.notes[0].id, { force: true, silentStatus: true });
          } else {
            this.clearSelectedNote();
          }

          await this.loadGraph({ silentStatus: true });

          if (this.notes.length) {
            this.setStatus("知识工作台已同步完成", "success");
          } else {
            this.setStatus("当前还没有笔记，可以先上传 PDF 或 DOCX", "");
          }
        } catch (error) {
          this.handleApiError(error, "加载知识工作台失败");
        } finally {
          this.loading = false;
        }
      },
      async loadOverview() {
        const payload = await frontend.api("/query/overview?week_offset=0");
        this.user = payload.user || null;
        this.schedule = payload.schedule || null;
        document.title = this.pageTitle + " | 学生课表管理系统";
      },
      async loadNotes(options) {
        const payload = await frontend.api(this.buildCoursePath("/note/list"));
        const preserveSelection = !!(options && options.preserveSelection);
        const preferredNoteId = options && options.preferredNoteId ? options.preferredNoteId : "";
        const sorted = sortNotes(payload);

        this.notes = sorted;

        if (preferredNoteId && sorted.some(function hasPreferred(note) { return note.id === preferredNoteId; })) {
          this.selectedNoteId = preferredNoteId;
          return;
        }

        if (preserveSelection && sorted.some(function hasSelection(note) { return note.id === this.selectedNoteId; }, this)) {
          return;
        }

        this.selectedNoteId = sorted.length ? sorted[0].id : "";
      },
      async loadTree(options) {
        const preserveSelection = !!(options && options.preserveSelection);
        const preferredTopicId = options && options.preferredTopicId ? options.preferredTopicId : "";
        const payload = await frontend.api(this.buildCoursePath("/knowledge/tree"));

        if (preserveSelection) {
          this.applyTree(payload, { preferTopicId: preferredTopicId || this.activeTopicId });
          return;
        }

        this.tree = cloneEmptyTree();
        this.activeTopicId = "";
        this.applyTree(payload, { preferTopicId: preferredTopicId });
      },
      clearSelectedNote: function clearSelectedNote() {
        this.selectedNoteId = "";
        this.noteDetail = null;
        this.selectedChunkId = "";
        this.noteForm = createEmptyNoteForm();
        this.previewLoading = false;
        this.previewKind = "";
        this.previewUrl = "";
        this.previewHtml = "";
      },
      selectNote: function selectNote(noteId) {
        this.openNote(noteId, {
          force: true,
          silentStatus: true,
        });
      },
      async openNote(noteId, options) {
        const force = !!(options && options.force);
        const chunkId = options && options.chunkId ? options.chunkId : "";
        const silentStatus = !!(options && options.silentStatus);

        try {
          if (!noteId) {
            this.clearSelectedNote();
            return;
          }

          this.selectedNoteId = noteId;
          this.selectedChunkId = chunkId;

          if (!force && this.noteDetail && this.noteDetail.note && this.noteDetail.note.id === noteId) {
            if (chunkId) {
              this.scrollChunkIntoView(chunkId);
            }
            return;
          }

          const detail = await frontend.api("/note/" + encodeURIComponent(noteId));
          this.noteDetail = detail;
          this.syncNoteForm(detail);
          await this.loadPreview(detail.note);

          if (chunkId) {
            this.scrollChunkIntoView(chunkId);
          }

          if (!silentStatus) {
            this.setStatus("已打开笔记：" + this.noteDisplayTitle(detail.note), "success");
          }
        } catch (error) {
          this.handleApiError(error, "加载笔记详情失败");
        }
      },
      async loadPreview(note) {
        this.previewLoading = true;
        this.previewKind = "";
        this.previewUrl = "";
        this.previewHtml = "";

        try {
          if (!note) {
            return;
          }

          if (note.file_type === "pdf") {
            this.previewKind = "pdf";
            this.previewUrl = "/note/" + encodeURIComponent(note.id) + "/file";
            return;
          }

          if (note.file_type === "docx") {
            const buffer = await fetchArrayBuffer("/note/" + encodeURIComponent(note.id) + "/file");
            if (!global.mammoth || typeof global.mammoth.convertToHtml !== "function") {
              throw new Error("DOCX 预览库未加载");
            }
            const result = await global.mammoth.convertToHtml({ arrayBuffer: buffer });
            this.previewKind = "docx";
            this.previewHtml = result.value || "<p>文档为空。</p>";
            return;
          }

          this.previewKind = "";
        } catch (error) {
          this.handleApiError(error, "加载预览失败");
        } finally {
          this.previewLoading = false;
        }
      },
      selectChunk: function selectChunk(chunkId) {
        this.selectedChunkId = chunkId;
        this.scrollChunkIntoView(chunkId);
      },
      scrollChunkIntoView: function scrollChunkIntoView(chunkId) {
        if (!chunkId) {
          return;
        }

        this.$nextTick(function afterTick() {
          const container = this.$refs.chunkList;
          if (!container || !container.querySelector) {
            return;
          }
          const target = container.querySelector('[data-chunk-id="' + chunkId + '"]');
          if (target && target.scrollIntoView) {
            target.scrollIntoView({
              behavior: "smooth",
              block: "nearest",
            });
          }
        });
      },
      isCurrentSelectionVisible: function isCurrentSelectionVisible() {
        if (!this.selectedNoteId) {
          return false;
        }
        return this.visibleNotes.some(function hasSelected(note) {
          return note.id === this.selectedNoteId;
        }, this);
      },
      setActiveTopic: function setActiveTopic(topicId) {
        this.activeTopicId = topicId || "";
        this.syncTopicEditForm();

        if (this.selectedNoteId && !this.isCurrentSelectionVisible()) {
          if (this.visibleNotes.length) {
            this.openNote(this.visibleNotes[0].id, { force: true, silentStatus: true });
          } else {
            this.clearSelectedNote();
          }
        }
      },
      clearActiveTopic: function clearActiveTopic() {
        this.setActiveTopic("");
      },
      async handleCourseChange() {
        this.updateUrlCourseId();
        this.askAnswer = "";
        this.askSources = [];
        this.searchResults = [];
        this.graphData = createEmptyGraphData();
        this.graphError = "";
        this.clearSelectedNote();
        await this.initializePage();
      },
      async submitUpload() {
        const input = this.$refs.uploadInput;
        const file = input && input.files ? input.files[0] : null;

        if (!file) {
          this.setStatus("请先选择 PDF 或 DOCX 文件", "error");
          return;
        }

        this.uploadBusy = true;

        try {
          const form = new FormData();
          form.append("file", file);

          const detail = await frontend.api(this.buildCoursePath("/note/upload"), {
            method: "POST",
            body: form,
          });

          if (input) {
            input.value = "";
          }

          await Promise.all([
            this.loadNotes({ preserveSelection: false, preferredNoteId: detail.note.id }),
            this.loadTree({ preserveSelection: true }),
          ]);
          await this.openNote(detail.note.id, { force: true, silentStatus: true });
          await this.loadGraph({ silentStatus: true });

          this.setStatus("已上传并索引文件：" + file.name, "success");
        } catch (error) {
          this.handleApiError(error, "上传笔记失败");
        } finally {
          this.uploadBusy = false;
        }
      },
      async saveNoteMeta() {
        if (!this.selectedNoteId) {
          this.setStatus("请先选择一份笔记", "error");
          return;
        }

        try {
          const payload = {
            title: this.noteForm.title,
            summary: this.noteForm.summary,
            course_id: this.noteForm.courseId || null,
          };

          const updated = await frontend.api("/note/" + encodeURIComponent(this.selectedNoteId), {
            method: "PUT",
            body: JSON.stringify(payload),
          });

          await Promise.all([
            this.loadNotes({ preserveSelection: true }),
            this.loadTree({ preserveSelection: true }),
          ]);

          if (this.notes.some(function hasUpdatedNote(note) { return note.id === updated.id; })) {
            await this.openNote(updated.id, { force: true, silentStatus: true });
          } else {
            this.clearSelectedNote();
          }

          await this.loadGraph({ silentStatus: true });

          if (this.courseId && String(updated.course_id || "") !== String(this.courseId)) {
            this.setStatus("笔记信息已保存，但它已经移出当前课程视图", "success");
          } else {
            this.setStatus("笔记信息已保存", "success");
          }
        } catch (error) {
          this.handleApiError(error, "保存笔记信息失败");
        }
      },
      async deleteSelectedNote() {
        if (!this.selectedNoteId || !this.selectedNote) {
          this.setStatus("请先选择一份笔记", "error");
          return;
        }

        const confirmed = global.confirm("确认删除笔记“" + this.noteDisplayTitle(this.selectedNote) + "”吗？");
        if (!confirmed) {
          return;
        }

        const deletedNoteId = this.selectedNoteId;

        try {
          await frontend.api("/note/" + encodeURIComponent(deletedNoteId), {
            method: "DELETE",
          });

          await Promise.all([
            this.loadNotes({ preserveSelection: false }),
            this.loadTree({ preserveSelection: true }),
          ]);

          if (this.selectedNoteId && this.selectedNoteId !== deletedNoteId) {
            await this.openNote(this.selectedNoteId, { force: true, silentStatus: true });
          } else if (this.notes.length) {
            await this.openNote(this.notes[0].id, { force: true, silentStatus: true });
          } else {
            this.clearSelectedNote();
          }

          await this.loadGraph({ silentStatus: true });
          this.setStatus("笔记已删除", "success");
        } catch (error) {
          this.handleApiError(error, "删除笔记失败");
        }
      },
      async createTopic() {
        const name = String(this.topicCreateForm.name || "").trim();
        if (!name) {
          this.setStatus("请输入主题名称", "error");
          return;
        }

        const previousIds = new Set(Object.keys((this.tree && this.tree.topics) || {}));

        try {
          const tree = await frontend.api("/knowledge/tree/topic", {
            method: "POST",
            body: JSON.stringify({
              course_id: this.courseId || null,
              name: name,
              parent_id: this.topicCreateForm.parentId || null,
              summary: this.topicCreateForm.summary || "",
              keywords: splitKeywords(this.topicCreateForm.keywords),
            }),
          });

          const nextTopicId = Object.keys((tree && tree.topics) || {}).find(function findNewTopic(topicId) {
            return !previousIds.has(topicId);
          }) || "";

          this.applyTree(tree, { preferTopicId: nextTopicId });
          this.resetTopicCreateForm();
          await this.loadGraph({ silentStatus: true });
          this.setStatus("主题已创建", "success");
        } catch (error) {
          this.handleApiError(error, "创建主题失败");
        }
      },
      async saveActiveTopic() {
        if (!this.selectedTopic) {
          this.setStatus("请先选择主题", "error");
          return;
        }

        try {
          const tree = await frontend.api(
            "/knowledge/tree/topic/" + encodeURIComponent(this.selectedTopic.id) + buildQuery({
              course_id: this.courseId || null,
            }),
            {
              method: "PUT",
              body: JSON.stringify({
                name: this.topicEditForm.name,
                parent_id: this.topicEditForm.parentId || null,
                summary: this.topicEditForm.summary || "",
                keywords: splitKeywords(this.topicEditForm.keywords),
              }),
            }
          );

          this.applyTree(tree, { preferTopicId: this.selectedTopic.id });
          await this.loadGraph({ silentStatus: true });
          this.setStatus("主题已保存", "success");
        } catch (error) {
          this.handleApiError(error, "保存主题失败");
        }
      },
      async deleteActiveTopic() {
        if (!this.selectedTopic) {
          this.setStatus("请先选择主题", "error");
          return;
        }

        const parentId = this.selectedTopic.parent_id || "";
        const confirmed = global.confirm("确认删除主题“" + this.selectedTopic.name + "”吗？其子主题会自动上移。");
        if (!confirmed) {
          return;
        }

        try {
          const tree = await frontend.api(
            "/knowledge/tree/topic/" + encodeURIComponent(this.selectedTopic.id) + buildQuery({
              course_id: this.courseId || null,
            }),
            {
              method: "DELETE",
            }
          );

          this.applyTree(tree, { preferTopicId: parentId });
          await this.loadGraph({ silentStatus: true });
          this.setStatus("主题已删除", "success");
        } catch (error) {
          this.handleApiError(error, "删除主题失败");
        }
      },
      async assignSelectedNoteToTopic() {
        if (!this.selectedNoteId || !this.activeTopicId) {
          this.setStatus("请先选择笔记和主题", "error");
          return;
        }

        try {
          const tree = await frontend.api("/knowledge/tree/topic/" + encodeURIComponent(this.activeTopicId) + "/assign", {
            method: "POST",
            body: JSON.stringify({
              course_id: this.courseId || null,
              note_id: this.selectedNoteId,
            }),
          });

          this.applyTree(tree, { preferTopicId: this.activeTopicId });
          await this.loadGraph({ silentStatus: true });
          this.setStatus("笔记已关联到当前主题", "success");
        } catch (error) {
          this.handleApiError(error, "关联笔记失败");
        }
      },
      async unassignSelectedNoteFromTopic() {
        if (!this.selectedNoteId || !this.activeTopicId) {
          this.setStatus("请先选择笔记和主题", "error");
          return;
        }

        try {
          const tree = await frontend.api(
            "/knowledge/tree/topic/" + encodeURIComponent(this.activeTopicId) + "/assign/" + encodeURIComponent(this.selectedNoteId) + buildQuery({
              course_id: this.courseId || null,
            }),
            {
              method: "DELETE",
            }
          );

          this.applyTree(tree, { preferTopicId: this.activeTopicId });
          await this.loadGraph({ silentStatus: true });
          this.setStatus("笔记已从当前主题移除", "success");
        } catch (error) {
          this.handleApiError(error, "移除主题关联失败");
        }
      },
      async submitAsk() {
        const question = String(this.askQuestion || "").trim();
        if (!question) {
          this.setStatus("请输入问题", "error");
          return;
        }

        this.askBusy = true;

        try {
          const payload = await frontend.api("/knowledge/ask", {
            method: "POST",
            body: JSON.stringify({
              question: question,
              course_id: this.courseId || null,
            }),
          });

          this.askAnswer = payload.answer || "";
          this.askSources = Array.isArray(payload.sources) ? payload.sources : [];
          this.setStatus("问答结果已更新", "success");
        } catch (error) {
          this.handleApiError(error, "问答失败");
        } finally {
          this.askBusy = false;
        }
      },
      async runSearch() {
        const query = String(this.searchQuery || "").trim();
        if (!query) {
          this.setStatus("请输入检索语句", "error");
          return;
        }

        this.searchBusy = true;

        try {
          const payload = await frontend.api("/knowledge/search", {
            method: "POST",
            body: JSON.stringify({
              query: query,
              limit: this.searchLimit,
              course_id: this.courseId || null,
            }),
          });

          this.searchResults = Array.isArray(payload) ? payload : [];
          this.setStatus("检索完成，共返回 " + this.searchResults.length + " 条结果", "success");
        } catch (error) {
          this.handleApiError(error, "检索失败");
        } finally {
          this.searchBusy = false;
        }
      },
      openSearchResult: function openSearchResult(result) {
        if (!result || !result.chunk) {
          return;
        }

        const noteId = result.chunk.note_id;
        const chunkId = result.chunk.chunk_id;
        const topicEntries = this.noteTopicsById[noteId] || [];
        if (topicEntries.length) {
          this.setActiveTopic(topicEntries[0].id);
        }
        this.openNote(noteId, {
          force: true,
          chunkId: chunkId,
          silentStatus: true,
        });
      },
      async loadGraph(options) {
        this.graphLoading = true;
        this.graphError = "";

        const silentStatus = !!(options && options.silentStatus);
        const minScore = Math.max(0, Math.min(1, Number(this.graphMinScore || 0)));
        const topK = Math.max(1, Math.min(10, Number(this.graphTopK || 1)));
        const topicLimit = Math.max(1, Math.min(10, Number(this.graphTopicLimit || 1)));

        this.graphMinScore = Number(minScore.toFixed(2));
        this.graphTopK = topK;
        this.graphTopicLimit = topicLimit;

        try {
          const topicId = this.graphQuery ? undefined : (this.activeTopicId || undefined);
          const graph = await frontend.api(this.buildCoursePath("/knowledge/graph", {
            query: this.graphQuery || undefined,
            topic_id: topicId,
            top_k: topK,
            min_score: this.graphMinScore,
            max_nodes: 120,
            topic_limit: topicLimit,
          }));

          this.graphData = Object.assign(createEmptyGraphData(), graph || {});
          if (this.graphRenderer) {
            this.graphRenderer.render(this.graphData);
          }

          if (!silentStatus) {
            this.setStatus("图谱已刷新", "success");
          }
        } catch (error) {
          this.graphError = (error && error.message) || "图谱加载失败";
          this.graphData = createEmptyGraphData();
          if (this.graphRenderer) {
            this.graphRenderer.render(this.graphData);
          }
          if (!silentStatus) {
            this.handleApiError(error, "图谱生成失败");
          }
        } finally {
          this.graphLoading = false;
        }
      },
      handleGraphNodeSelect: function handleGraphNodeSelect(node) {
        if (!node || !node.note_id) {
          return;
        }

        if (node.topic_id) {
          this.setActiveTopic(node.topic_id);
        }

        this.openNote(node.note_id, {
          force: true,
          chunkId: node.id,
          silentStatus: true,
        });
      },
      handleGraphResize: function handleGraphResize() {
        if (this.graphRenderer && typeof this.graphRenderer.resize === "function") {
          this.graphRenderer.resize();
        }
      },
      initializeGraph: function initializeGraph() {
        if (!this.$refs.graphCanvas) {
          return;
        }
        this.graphRenderer = global.knowledgeGraph.create(this.$refs.graphCanvas, {
          onSelect: this.handleGraphNodeSelect,
        });
      },
    },
    mounted: function mounted() {
      const params = new URLSearchParams(global.location.search);
      this.courseId = params.get("course_id") || "";
      this.resetTopicCreateForm();
      this.initializeGraph();
      global.addEventListener("resize", this.handleGraphResize);
      this.initializePage();
    },
    beforeDestroy: function beforeDestroy() {
      global.removeEventListener("resize", this.handleGraphResize);
      if (this.graphRenderer && typeof this.graphRenderer.destroy === "function") {
        this.graphRenderer.destroy();
      }
    },
  });
})(window);

# 学生课表管理系统 - 框架设计文档

## 项目概述

基于 FastAPI 的学生课表管理系统，支持：
- Cookie/Session 用户注册与登录
- 从华南师范大学教务平台抓取课表（或手动上传为回退路径）
- 根据系统时间查询当前/今日/本周课程
- 自定义文件存储层（不使用数据库 ORM/API）
- 课程要求：手动实现双向链表、二叉查找树、哈希表、队列
- **扩展功能**：课程笔记上传、语义检索、RAG 问答、知识图谱可视化

---

## 目录结构

```
OOP_project/                     # 项目根目录
├── app/                         # 主应用源码
│   ├── main.py                  # FastAPI 入口，挂载路由和静态文件
│   ├── config.py                # 配置常量（数据目录路径、密钥、节次时间表等）
│   │
│   ├── core/                    # 自定义数据结构（课程要求）
│   │   ├── __init__.py
│   │   ├── doubly_linked_list.py   # 双向链表
│   │   ├── bst.py                  # 二叉查找树（Binary Search Tree）
│   │   ├── hash_table.py           # 哈希表（链地址法）
│   │   └── queue.py                # 队列（用于异步任务调度）
│   │
│   ├── models/                  # Pydantic 数据模型（用于请求/响应校验）
│   │   ├── user.py              # User, UserCreate, UserLogin
│   │   ├── course.py            # Course, Schedule, QueryResult
│   │   ├── note.py              # Note, NoteChunk, SearchResult
│   │   └── knowledge.py         # KnowledgeTopic, KnowledgeTree
│   │
│   ├── storage/                 # 文件存储层（替代数据库）
│   │   ├── file_io.py           # JSON 文件原子读写基础操作
│   │   ├── user_store.py        # 用户持久化（哈希表索引 + 文件）
│   │   ├── schedule_store.py    # 课表持久化（BST + 双向链表 + 文件）
│   │   ├── schedule_index.py    # 课表索引层（DLL + BST 封装）
│   │   ├── note_store.py        # 笔记元数据（SQLite）
│   │   └── knowledge_tree_store.py # 知识树持久化（JSON）
│   │
│   ├── services/                # 业务逻辑层
│   │   ├── auth_service.py      # Cookie/Session 认证逻辑
│   │   ├── schedule_service.py  # 课表 CRUD、当前课程查询逻辑
│   │   ├── scnu_scraper.py      # SCNU 强智 API 抓取 + PDF 解析（次选）
│   │   ├── fetch_queue.py       # 抓取任务队列（Queue 实现）
│   │   ├── note_service.py      # 笔记上传、文本提取、切片
│   │   ├── knowledge_service.py # 向量检索、RAG、知识图谱
│   │   └── topic_vector_store.py # 主题向量索引
│   │
│   └── routers/                 # FastAPI 路由（薄层，调用 services）
│       ├── auth.py              # /auth/*
│       ├── schedule.py          # /schedule/*
│       ├── query.py             # /query/*
│       ├── note.py              # /note/*
│       └── knowledge.py         # /knowledge/*
│
├── data/                        # 持久化文件（运行时自动生成）
│   ├── users.json               # 所有用户记录
│   ├── schedules/
│   │   └── {student_id}.json    # 每个用户的课表
│   ├── notes.db                 # SQLite（笔记元数据 + 切片）
│   ├── note_files/              # 原始上传文件
│   ├── knowledge_trees/         # 知识树 JSON
│   └── qdrant_db/               # Qdrant 向量库（本地磁盘模式）
│
├── static/                      # 前端页面（登录页 + 课表工作台 + 知识工作台）
│   ├── index.html               # /login，登录/注册入口
│   ├── dashboard.html           # /dashboard，课表工作台
│   ├── knowledge_workspace.html # /knowledge-workspace，笔记/知识图谱工作台
│   ├── style.css
│   ├── vue.css
│   ├── auth-vue.js
│   ├── dashboard-vue.js
│   └── knowledge-workspace.js
│
├── tests/                       # 单元测试和集成测试
│   ├── test_bst.py              # BST 测试
│   ├── test_doubly_linked_list.py # 双向链表测试
│   ├── test_hash_table.py       # 哈希表测试
│   ├── test_queue.py            # 队列测试
│   ├── test_schedule_index.py   # 索引层集成测试
│   └── test_fetch_queue.py      # 任务队列测试
│
└── requirements.txt
```

---

## 数据结构用途分配

| 数据结构 | 绑定场景 | 说明 | 实现状态 |
|---------|---------|------|---------|
| **哈希表** | Session 管理 `token → {student_id, expires}`；用户索引 `学号 → User`；课表索引缓存 `student_id → ScheduleIndex` | O(1) 身份验证，适合每次请求都需要的认证查找 | ✅ 已集成 |
| **双向链表** | 每个用户的课程列表（按周-天-节次排序） | 支持前后周导航，插入/删除节点 O(1)，遍历今日课程 | ✅ 已集成 |
| **二叉查找树** | 课程时间索引，key = `weekday * 100 + period_start` | O(log n) 查找"当前节次有哪门课" | ✅ 已集成 |
| **队列** | SCNU 教务平台抓取任务队列（生产者-消费者模式） | 有限并发（2 workers），限速、防并发，避免被教务系统封 IP | ✅ 已集成 |

---

## 核心数据模型

### Course（课程）

```python
class Course:
    id: str            # UUID，主键
    name: str          # 课程名称
    teacher: str       # 任课教师
    location: str      # 上课地点（教室）
    weekday: int       # 星期几（1=周一，7=周日）
    period_start: int  # 第几节开始（1-12）
    period_end: int    # 第几节结束
    weeks: list[int]   # 上课的周次列表，如 [1,2,3,...,16]
    week_type: str     # "all"=每周 | "odd"=单周 | "even"=双周
```

### Schedule（学期课表）

```python
class Schedule:
    student_id: str       # 学号
    semester: str         # 学期标识，如 "2025-2026-2"
    semester_start: str   # 学期第一周周一日期，ISO 格式，如 "2026-02-24"
    courses: list[Course]
```

### User（用户）

```python
class User:
    student_id: str    # 学号（主键，唯一）
    name: str          # 姓名
    password_hash: str # bcrypt 或 SHA-256 哈希
```

### 持久化文件格式

**data/users.json**
```json
{
  "users": [
    {
      "student_id": "202301234",
      "name": "张三",
      "password_hash": "sha256:abc123..."
    }
  ]
}
```

**data/schedules/{student_id}.json**
```json
{
  "student_id": "202301234",
  "semester": "2025-2026-2",
  "semester_start": "2026-02-24",
  "courses": [
    {
      "id": "uuid-xxxx",
      "name": "面向对象程序设计",
      "teacher": "李老师",
      "location": "理工楼 A101",
      "weekday": 1,
      "period_start": 1,
      "period_end": 2,
      "weeks": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
      "week_type": "all"
    }
  ]
}
```

---

## API 设计

### 认证 `/auth`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 注册（学号 + 姓名 + 密码） |
| POST | `/auth/login` | 登录 → 响应头 `Set-Cookie: session_token=...` |
| POST | `/auth/logout` | 清除 Cookie，从 Session 哈希表移除 |
| GET  | `/auth/me` | 返回当前登录用户信息（依赖 Cookie） |

### 课表 CRUD `/schedule`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/schedule` | 获取完整课表（JSON） |
| POST | `/schedule/upload` | 上传 JSON 课表文件（手动回退路径） |
| POST | `/schedule/fetch` | 触发统一身份认证课表抓取任务（进入任务队列） |
| POST | `/schedule/course` | 手动新增单门课程 |
| PUT  | `/schedule/course/{id}` | 修改某门课程 |
| DELETE | `/schedule/course/{id}` | 删除某门课程 |

### 查询 `/query`（依赖系统时间 + 登录态）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/query/overview` | 工作台总览（用户 + 当前课表 + 当前课 + 今日课程 + 指定周课表） |
| GET | `/query/now` | 当前节次正在上的课（BST 查找） |
| GET | `/query/today` | 今天全部课程（双向链表遍历当天节点） |
| GET | `/query/week` | 本周课表 |
| GET | `/query/week/{offset}` | 指定周（0=本周，-1=上周，+1=下周） |

---

## 数据结构与存储层连接方式

```
服务启动
  └─ 读取 data/users.json
       └─ 反序列化 → 填充 HashTable(users)  key=学号, value=User

登录请求
  └─ 验证密码 → 生成 session_token (secrets.token_hex(32))
       └─ 存入 HashTable(sessions)  key=token, value={student_id, expires}
       └─ 响应 Set-Cookie: session_token=...

GET /query/now（查询当前课程）
  └─ 读 Cookie → HashTable(sessions).get(token) → student_id
       └─ ScheduleStore.get_index(student_id) → ScheduleIndex
       └─ 计算当前周次、星期、节次
       └─ BST.search(weekday*100 + period) → Course（O(log n)）
       └─ 验证课程是否在当前周次上课

GET /query/today（查询今日课程）
  └─ ScheduleStore.get_index(student_id) → ScheduleIndex
       └─ DoublyLinkedList 遍历当天课程（按时间排序）
       └─ 过滤周次匹配的课程

POST /schedule/fetch (SCNU 强智 API 抓取)
  └─ 创建 FetchTask {task_id, student_id, handler}
       └─ 提交到 FetchQueue（Queue 实现）
       └─ 2 个 worker 线程并发消费队列
       └─ 每个任务间隔 2 秒（防止被封）
       └─ SCNUScraper.fetch() → 解析课程
       └─ 更新 ScheduleStore → 重建 DoublyLinkedList + BST 索引

课表文件加载（懒加载）
  └─ 首次访问 ScheduleStore.get(student_id)
       └─ 读 data/schedules/{student_id}.json
       └─ 反序列化为 Course 列表
       └─ 构建 ScheduleIndex：
            ├─ 按 (weekday, period_start) 排序后插入 DoublyLinkedList
            └─ 同步建立 BST 时间索引
       └─ 缓存到 HashTable(index_cache)
```

---

## Session/Cookie 认证流程

```
注册/登录
  Client                          Server
    │── POST /auth/login ────────→ │ 1. 查 HashTable(users) 验证密码
    │                              │ 2. token = secrets.token_hex(32)
    │                              │ 3. HashTable(sessions)[token] = {id, exp}
    │←── 200 + Set-Cookie: st=... ─│

每次后续请求
    │── GET /query/now ──────────→ │ 1. 从 Cookie 取 token
    │                              │ 2. HashTable(sessions).get(token)
    │                              │ 3. 未找到或已过期 → 401 Unauthorized
    │                              │ 4. 找到 → 继续处理业务逻辑
```

---

## SCNU 教务平台课表获取（scnu_scraper.py）

SCNU（华南师范大学）在 `jwxt.scnu.edu.cn` 上使用**强智教务系统**，该系统自带 `app.do` JSON API，**无需 Playwright 模拟浏览器**，直接用 `requests` 调用即可。

社区已有开源参考项目：[iscnu/scnu-schedule-ical-jwxt](https://github.com/iscnu/scnu-schedule-ical-jwxt)

### 强智 API 调用流程

```
Step 1: 获取加密盐
  GET /Logon.do?method=logon&flag=sess
  → 返回 dataStr（用于密码加密）

Step 2: 加密密码并登录
  GET /app.do?method=authUser&xh={学号}&pwd={加密后密码}
  → 响应 Header 中取 token

Step 3: 获取学年学期 ID
  GET /app.do?method=getXnxq&xh={学号}
  → 返回 xnxqid

Step 4: 获取课表（按周次）
  GET /app.do?method=getKbcxAzc&xh={学号}&xnxqid={xnxqid}&zc={周次}
  → 返回 JSON，字段：kcmc(课程名) jsxm(教师) jsmc(教室) kssj(开始节) jssj(结束节) kkzc(上课周次)
```

```python
class SCNUScraper:
    BASE = "https://jwxt.scnu.edu.cn"

    def get_session_key(self) -> str:
        """GET /Logon.do?method=logon&flag=sess → 返回 dataStr"""

    def encrypt_password(self, password: str, data_str: str) -> str:
        """强智密码加密（AES 或位移拼接，参考社区实现）"""

    def login(self, student_id: str, password: str) -> str:
        """返回 token 字符串，后续请求带入 Header"""

    def fetch_schedule(self, token: str, student_id: str, semester_id: str) -> list[Course]:
        """调用 getKbcxAzc，遍历所有周次，去重合并，返回标准化 Course 列表"""
```

### 获取路径优先级

```
优先：强智 JSON API（requests，无需 Playwright）
  ↓ 若登录失败（密码错误、接口变动）
次选：用户从教务系统手动下载 PDF → 上传到系统 → 后端解析
  ↓ 若 PDF 结构变化解析失败
兜底：用户手动填写 / 上传标准 JSON 课表
```

### PDF 课表解析思路（次选路径）

SCNU 课表 PDF 是固定格式的大表格（行=节次，列=星期）。社区有参考实现：[lgbgbl/Timetable-PDF-ICS](https://github.com/lgbgbl/Timetable-PDF-ICS)

```python
import pdfplumber  # 或 pdfminer.six

def parse_pdf_schedule(pdf_path: str) -> list[Course]:
    """
    1. pdfplumber 提取表格（table extraction）
    2. 按行（节次）× 列（星期）遍历单元格
    3. 正则匹配：课程名 / 教师 / 教室 / 周次（如"1-16周"、"单周"）
    4. 标准化为 Course 对象列表
    """
```

关键正则模式（强智 PDF 单元格文本格式通常为）：
```
面向对象程序设计
李老师
理工楼A101
1-16周
```

---

## 前端结构（多页面）

```
/login
  └─ static/index.html
      └─ Vue2 登录/注册面板（本地账号 + 可选统一身份认证账号）

/dashboard
  └─ static/dashboard.html
      ├─ 当前课程卡片
      ├─ 今日课程列表
      ├─ 周课表格（7列 × 12节）
      ├─ 学期初始化 / 文件导入 / 统一身份认证抓取
      └─ 课程 CRUD 表单

/knowledge-workspace
  └─ static/knowledge_workspace.html
      └─ 课程笔记、知识聚类、图谱等工作区

核心交互流程：
  1. 页面加载 → `/login` 检查 Cookie → 已登录则重定向到 `/dashboard`
  2. `/dashboard` 加载 → GET `/query/overview` → 同步用户、课表、当前课程、今日课程、本周课表
  3. 周导航按钮 → GET `/query/overview?week_offset={offset}` → 重渲染工作台
  4. 上传按钮 → `<input type="file">` → POST `/schedule/upload`
  5. “通过统一身份认证抓取课表”按钮 → POST `/schedule/fetch`
  6. 课程卡片 / 当前课程 / 今日课程可跳转 `/knowledge-workspace?course_id=...`
```

---

## 关键依赖

```
fastapi
uvicorn[standard]
pydantic
requests          # 强智 API HTTP 请求
pdfplumber        # PDF 课表解析（次选路径）
python-multipart  # 文件上传支持
passlib[bcrypt]   # 密码哈希（可替换为 hashlib + SHA-256）
```

---

## 实现优先级

1. `core/` 四个数据结构 → 写测试验证正确性 ✅
2. `storage/` 存储层（文件读写 + 数据结构封装）✅
3. 认证路由 `/auth/register` `/auth/login` ✅
4. 课表 CRUD（手动上传优先）✅
5. 查询路由 `/query/now` `/query/today` `/query/week` ✅
6. 前端页面 ✅
7. SCNU 强智 API 抓取（参考 iscnu/scnu-schedule-ical-jwxt；最后做，受接口变动影响）✅
8. PDF 解析（次选路径，参考 lgbgbl/Timetable-PDF-ICS；使用 pdfplumber + 正则）✅
9. 笔记知识库模块（扩展功能）✅

---

## 笔记知识库模块（扩展功能）

### 概述

在课表管理基础上扩展了"课程笔记 + 知识检索"功能。用户可上传课程笔记（PDF/DOCX），系统自动提取文本、按标题切片、建立向量索引，支持语义检索、RAG 问答和知识图谱可视化。

### 核心功能

1. **笔记管理** (`/note/*`)
   - 上传 PDF/DOCX 文件，自动提取文本并切片
   - 关联到课程，支持编辑元信息和删除
   - 原始文件下载和预览

2. **知识检索** (`/knowledge/search`)
   - 基于 Qdrant 向量库的语义搜索
   - 使用 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 生成 384 维向量
   - 按学生和课程隔离数据

3. **RAG 问答** (`/knowledge/ask`)
   - 检索相关切片 + DeepSeek Chat API 生成回答
   - LLM 不可用时降级为返回检索结果原文

4. **知识图谱** (`/knowledge/graph`)
   - 计算切片间语义相似度构建图结构
   - 前端使用 Cytoscape.js 力导向布局渲染
   - 支持按主题着色分组

5. **知识树管理** (`/knowledge/tree/*`)
   - 层级主题结构（支持父子关系）
   - 笔记关联到主题，支持查询路由优化
   - 主题向量索引用于智能匹配

### 技术栈

- **向量库**: Qdrant（本地磁盘模式）
- **向量管理**: mem0 库（统一 embedding 生成和向量 CRUD）
- **Embedding 模型**: sentence-transformers（384 维，支持中文）
- **LLM**: DeepSeek Chat（OpenAI 兼容接口）
- **文本提取**: pdfplumber（PDF）、python-docx（DOCX）
- **前端图谱**: Cytoscape.js、mammoth.js（DOCX 预览）

### 数据模型

- **Note**: 笔记元数据（标题、摘要、文件类型、关联课程）
- **NoteChunk**: 笔记切片（标题、内容、索引位置）
- **KnowledgeTopic**: 知识主题（名称、父子关系、关联笔记、关键词）
- **KnowledgeTree**: 知识树（按课程隔离的主题层级结构）

### 存储方案

- 笔记元数据和切片：SQLite (`data/notes.db`)
- 原始文件：文件系统 (`data/note_files/`)
- 向量索引：Qdrant (`data/qdrant_db/`)
- 知识树：JSON 文件 (`data/knowledge_trees/`)

### 文本切片策略

1. 标题识别：正则匹配 Markdown 标题、中文章节标记、数字序号等
2. 按标题拆分文档为段落组
3. 超长段落（>500 字）按空行拆分，仍超长则硬截断（50 字重叠）
4. 无标题时按固定窗口（500 字 + 50 字重叠）切片

详细设计见 `docs/NOTE_KNOWLEDGE_DESIGN.md`

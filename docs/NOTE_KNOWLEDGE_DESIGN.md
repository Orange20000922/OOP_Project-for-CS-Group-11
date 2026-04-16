# 笔记知识库模块 — 设计方案

## 背景

在现有课表管理系统基础上，新增一个"课程笔记 + 知识检索"模块。用户在到达上课地点后，可以上传课程笔记（PDF/DOCX），系统自动提取文本、生成摘要、建立向量索引，支持基于自然语言的知识检索和 AI 问答。

---

## 模块总览

```
用户到达教室（位置签到）
  → 课程信息卡片（可点击跳转）
    → 笔记页面
      ├── 上传 PDF/DOCX → 文本提取 → 正则/LLM 切片 → 向量索引
      ├── PDF 在线预览（pdf.js）
      ├── 知识检索 → kNN 相似度 → D3 知识图谱
      └── AI 问答 → 检索相关片段 → DeepSeek 生成回答
```

---

## 一、数据模型

### 1.1 Note（笔记记录）

```python
class Note(BaseModel):
    id: str                      # UUID
    student_id: str              # 所属学生
    course_id: str | None        # 关联课程（可选）
    filename: str                # 原始文件名
    file_type: str               # "pdf" / "docx"
    title: str                   # LLM 提取或用户填写
    summary: str                 # LLM 生成摘要
    chunk_count: int             # 切片数量
    created_at: str              # ISO 时间戳
    updated_at: str
```

### 1.2 NoteChunk（笔记切片，存于向量库）

```python
class NoteChunk(BaseModel):
    chunk_id: str                # UUID
    note_id: str                 # 所属笔记
    heading: str                 # 切片标题（正则提取）
    content: str                 # 切片文本
    chunk_index: int             # 在文档中的顺序
    # embedding 向量由 mem0/Qdrant 管理，不存于此模型
```

### 1.3 Location（教室位置，硬编码少量数据）

```python
# 直接在 config 中定义，不需要单独模型
CLASSROOM_LOCATIONS: dict[str, tuple[float, float]] = {
    "理工楼A101": (23.0567, 113.3521),
    "南B216":     (23.0559, 113.3530),
    "教C303":     (23.0572, 113.3515),
    # ... 5-10 个常用教室
}
LOCATION_THRESHOLD_METERS = 200  # 签到判定半径
```

---

## 二、API 路由

### 2.1 笔记管理 `/note`

| 方法 | 路径 | 功能 | 说明 |
|------|------|------|------|
| POST | `/note/upload` | 上传笔记 | 接收 PDF/DOCX 文件 + 可选 course_id，返回 Note |
| GET | `/note/list` | 笔记列表 | 当前用户所有笔记，支持 ?course_id= 过滤 |
| GET | `/note/{note_id}` | 笔记详情 | 返回 Note + chunks 列表 |
| GET | `/note/{note_id}/file` | 下载原始文件 | 返回原始 PDF/DOCX 用于前端预览 |
| PUT | `/note/{note_id}` | 编辑笔记元信息 | 修改标题、摘要等 |
| DELETE | `/note/{note_id}` | 删除笔记 | 同时清理向量索引 |

### 2.2 知识检索 `/knowledge`

| 方法 | 路径 | 功能 | 说明 |
|------|------|------|------|
| POST | `/knowledge/search` | 语义搜索 | `{"query": "...", "limit": 10}` → 返回相关切片列表 + 相似度分数 |
| POST | `/knowledge/ask` | AI 问答 | `{"question": "..."}` → 检索相关切片 + DeepSeek 生成回答 |
| GET | `/knowledge/graph` | 知识图谱数据 | 返回 D3.js 力导向图所需的 nodes + links JSON |

### 2.3 位置 `/location`

| 方法 | 路径 | 功能 | 说明 |
|------|------|------|------|
| POST | `/location/checkin` | 位置签到 | `{"lat": 23.05, "lng": 113.35}` → 判断是否在教室附近 |

---

## 三、后端架构

### 3.1 新增文件

```
app/
├── models/
│   └── note.py                  # Note, NoteCreate, NoteChunk, SearchResult 等
├── storage/
│   └── note_store.py            # 笔记元数据 JSON 持久化
├── services/
│   ├── note_service.py          # 上传、文本提取、切片、摘要生成
│   ├── knowledge_service.py     # 向量索引（mem0+Qdrant）、检索、RAG 问答
│   └── location_service.py      # 坐标距离计算、签到判定
└── routers/
    ├── note.py                  # /note/* 路由
    └── knowledge.py             # /knowledge/* + /location/* 路由

data/
├── notes/                       # 笔记元数据 JSON（按 student_id）
│   └── {student_id}.json
├── note_files/                  # 原始上传文件
│   └── {note_id}.pdf
└── qdrant_db/                   # Qdrant 向量库（本地磁盘）
```

### 3.2 核心流程

#### 上传处理流程

```
POST /note/upload (PDF/DOCX文件)
  │
  ├─ 1. 保存原始文件 → data/note_files/{note_id}.pdf
  │
  ├─ 2. 文本提取
  │     ├─ PDF → pdfplumber（已有依赖）
  │     └─ DOCX → python-docx
  │
  ├─ 3. 文本切片（note_service.py）
  │     ├─ 正则匹配标题行（# 标题 / 一、xxx / 第x章 / 加粗行）
  │     ├─ 按标题拆分为 chunks
  │     ├─ 超长 chunk 按段落或固定长度二次切分（上限约 500 字/片）
  │     └─ 保留 heading + content + chunk_index
  │
  ├─ 4. LLM 摘要提取（knowledge_service.py，可异步）
  │     ├─ 拼接前几个 chunks → DeepSeek API
  │     ├─ prompt: "提取标题和一段50字以内的摘要，返回JSON"
  │     └─ 结果写回 note.title / note.summary
  │
  └─ 5. 向量索引（knowledge_service.py）
        ├─ 每个 chunk 的 content 作为文本
        ├─ mem0.add() 写入 Qdrant
        └─ metadata 中存 note_id, chunk_id, heading
```

#### RAG 问答流程

```
POST /knowledge/ask {"question": "什么是多态？"}
  │
  ├─ 1. mem0.search(query=question, limit=5)
  │     → 返回最相关的 5 个 chunks + 相似度分数
  │
  ├─ 2. 组装 prompt
  │     context = "\n---\n".join(chunk.content for chunk in results)
  │     prompt = f"根据以下笔记内容回答问题。\n\n{context}\n\n问题：{question}"
  │
  └─ 3. DeepSeek API → 返回回答
```

#### 知识图谱数据

```
GET /knowledge/graph
  │
  ├─ 1. 从 Qdrant 取出所有 chunks 的 embedding 向量
  │
  ├─ 2. 计算 chunk 间两两余弦相似度
  │     （或用 kNN: 每个 chunk 取 top-k 近邻）
  │
  ├─ 3. 构造 D3 力导向图 JSON:
  │     nodes: [{id, label(heading), group(note_id)}]
  │     links: [{source, target, value(similarity)}]
  │     只保留相似度 > 阈值的边
  │
  └─ 4. 返回 JSON → 前端 D3.js 渲染
```

---

## 四、向量存储方案（mem0 + Qdrant）

直接复用 MyNeuroLikeSystem 的配置模式：

```python
# knowledge_service.py

from mem0 import Memory

mem0_config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "course_notes",
            "path": str(DATA_DIR / "qdrant_db"),
            "embedding_model_dims": 384,
            "on_disk": True,
        },
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        },
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": "deepseek-chat",
            "api_key": DEEPSEEK_API_KEY,
            "openai_base_url": "https://api.deepseek.com/v1",
        },
    },
}

memory = Memory.from_config(mem0_config)
```

**存储隔离**：用 `user_id=student_id` 隔离不同用户的笔记向量。

**关键操作**：
- 写入：`memory.add(messages=[{"role":"user", "content": chunk_text}], user_id=sid, metadata={...})`
- 检索：`memory.search(query=question, user_id=sid, limit=k)`
- 删除：`memory.delete_all(user_id=sid)` 或按 metadata 过滤

---

## 五、前端页面

### 5.1 新增页面

| 文件 | 功能 |
|------|------|
| `static/note.html` | 笔记主页面（上传 + 列表 + 预览 + 问答） |
| `static/note.js` | 笔记页面逻辑 |
| `static/js/pdf-preview.js` | pdf.js 集成封装 |
| `static/js/knowledge-graph.js` | D3.js 力导向图渲染 |

### 5.2 课程卡片跳转

在现有 dashboard 页面中，当前课程信息卡片改为可点击，点击后跳转到：
```
/static/note.html?course_id={course_id}
```

### 5.3 笔记页面布局

```
┌────────────────────────────────────────────────────┐
│  ← 返回    [课程名称] 笔记                          │
├────────────────────────────────────────────────────┤
│                                                    │
│  ┌─ 上传区 ──────────────────────────────────────┐ │
│  │  [选择文件]  支持 PDF / DOCX          [上传]  │ │
│  └───────────────────────────────────────────────┘ │
│                                                    │
│  ┌─ 笔记列表 ────────────────────────────────────┐ │
│  │  面向对象笔记-第3章.pdf   2026-04-15   [预览] │ │
│  │  数据结构期中复习.docx    2026-04-10   [预览] │ │
│  └───────────────────────────────────────────────┘ │
│                                                    │
│  ┌─ AI 问答 ─────────────────────────────────────┐ │
│  │  输入问题：[________________________] [提问]   │ │
│  │                                               │ │
│  │  回答：多态是面向对象编程的核心概念之一...      │ │
│  │  ─────────────────────────────────            │ │
│  │  参考来源：                                    │ │
│  │  - 面向对象笔记-第3章 > 3.2 多态              │ │
│  │  - 数据结构复习 > 继承与多态                   │ │
│  └───────────────────────────────────────────────┘ │
│                                                    │
│  ┌─ 知识图谱 ────────────────────────────────────┐ │
│  │                                               │ │
│  │        (D3.js 力导向图)                        │ │
│  │     [类] ──── [继承] ──── [多态]               │ │
│  │      │                     │                  │ │
│  │   [封装]               [接口]                 │ │
│  │                                               │ │
│  └───────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

### 5.4 PDF 预览

使用 Mozilla pdf.js（CDN 引入），在模态弹窗或侧边栏中渲染：
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
```
DOCX 预览使用 mammoth.js 转为 HTML 渲染（排版会简化，但满足预览需求）。

### 5.5 知识图谱

使用 D3.js 力导向图：
```html
<script src="https://d3js.org/d3.v7.min.js"></script>
```
- 每个节点 = 一个笔记切片，标签为 heading
- 节点颜色按所属笔记分组
- 边 = 两个切片的语义相似度超过阈值
- 节点大小 = 被引用/关联次数
- 支持拖拽、缩放

---

## 六、位置签到

### 6.1 方案

MVP 阶段不调用外部地图 API，采用硬编码坐标 + Haversine 公式：

```python
import math

def haversine(lat1, lng1, lat2, lng2) -> float:
    """返回两点间距离（米）"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
```

前端通过 `navigator.geolocation.getCurrentPosition()` 获取 GPS 坐标，POST 到后端判定。

### 6.2 流程

```
前端获取 GPS → POST /location/checkin {lat, lng}
  → 后端遍历 CLASSROOM_LOCATIONS
    → haversine(用户坐标, 教室坐标) < 200m ?
      → 匹配成功 → 返回 {matched: true, location: "理工楼A101"}
      → 无匹配   → 返回 {matched: false}
```

dashboard 页面收到匹配结果后，在当前课程卡片上启用"进入笔记"按钮。

### 6.3 后续扩���（可选）

如需更精确的位置或室内定位，可接入百度地图 Geocoding API：
- 免费额度：个人开发者 5000 次/天
- 接口：`https://api.map.baidu.com/reverse_geocoding/v3/`
- 用途：将 GPS 坐标反查为建筑名称，与课程地点文本匹配

---

## 七、文本切片策略

### 7.1 正则标题识别

```python
HEADING_PATTERNS = [
    r'^#{1,3}\s+.+',                    # Markdown: # 标题
    r'^第[一二三四五六七八九十\d]+[章节部分]',  # 第一章、第3节
    r'^[一二三四五六七八九十]+[、.]\s*.+',     # 一、概述
    r'^\d+[.\s].+',                      # 1. 概述 / 1 概述
    r'^[A-Z][A-Za-z\s]{2,}$',            # 英文大写开头的独立行
]
```

### 7.2 切片逻辑

```
1. 按标题正则将文档拆分为段落组
2. 每个段落组 = heading + 下方所有正文（直到下一个标题）
3. 如果单个 chunk > 500 字：
   - 按空行（双换行）拆分为子段落
   - 子段落仍超长时按 500 字硬截断，保留上下文重叠 50 字
4. 如果无法匹配到任何标题（纯文本）：
   - 按 500 字固定窗口 + 50 字重叠 切片
5. 最终每个 chunk 带 heading（标题）和 content（正文）
```

---

## 八、LLM 调用（DeepSeek API）

### 8.1 配置

```python
# config.py 新增
DEEPSEEK_API_KEY = ""          # 由用户在启动时设置或写入 .env
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
```

DeepSeek API 兼容 OpenAI SDK，直接用 `openai` 库调用：

```python
from openai import OpenAI

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
resp = client.chat.completions.create(
    model=DEEPSEEK_MODEL,
    messages=[...],
)
```

### 8.2 调用场景

| 场景 | 输入 | 输出 | 预估 token |
|------|------|------|-----------|
| 摘要提取 | 前 3 个 chunks（~1500 字） | JSON `{title, summary}` | ~2000 |
| RAG 问答 | 5 个相关 chunks + 问题 | 自然语言回答 | ~3000 |

DeepSeek-chat 价格：约 ¥1/百万 token，每次问答成本 < ¥0.01。

---

## 九、新增依赖

```
# requirements.txt 新增
python-docx          # DOCX 文本提取
mem0ai               # 向量记忆管理（封装 Qdrant + embedding）
qdrant-client        # 向量数据库（本地磁盘模式）
sentence-transformers # embedding 模型
openai               # 调用 DeepSeek API（兼容接口）
```

注：`pdfplumber` 和 `requests` 已在现有依赖中。

---

## 十、实现顺序

| 阶段 | 内容 | 产出 |
|------|------|------|
| **1** | 数据模型 + 笔记存储层 | `models/note.py` + `storage/note_store.py` |
| **2** | 文本提取 + 切片逻辑 | `services/note_service.py` 核心功能 |
| **3** | mem0 + Qdrant 向量索引 | `services/knowledge_service.py` 写入/检索 |
| **4** | 笔记上传 + 列表 API | `routers/note.py` |
| **5** | RAG 问答 API | `routers/knowledge.py` + DeepSeek 调用 |
| **6** | 前端笔记页面 + 上传 + 问答 | `static/note.html` + `static/note.js` |
| **7** | PDF 预览（pdf.js） | `static/js/pdf-preview.js` |
| **8** | LLM 摘要提取 | `note_service.py` 补充异步摘要 |
| **9** | 知识图谱 API + D3 可视化 | `knowledge.py` graph 端点 + `static/js/knowledge-graph.js` |
| **10** | 位置签到 | `services/location_service.py` + 前端 GPS 获取 |

建议前 5 个阶段（后端核心）优先完成并可独立测试，第 6-10 阶段可以并行或按需添加。

---

## 十一、测试计划

| 测试目标 | 方法 |
|---------|------|
| 文本提取正确性 | 准备 2-3 个样例 PDF/DOCX，验证提取文本完整 |
| 切片逻辑 | 单元测试：不同格式文档的标题识别和切片数量 |
| 向量索引 | 写入 3-5 个 chunks → search → 验证返回相关性排序 |
| RAG 问答 | 上传一份笔记 → 提问笔记中的内容 → 验证回答引用了正确切片 |
| 位置签到 | 单元测试：已知坐标距离计算 + 阈值判定 |
| 前端预览 | 手动测试：上传 PDF → 点击预览 → 确认渲染正确 |
| 知识图谱 | 上传 2+ 份笔记 → 检查图谱节点和边的合理性 |

# 笔记知识库模块 — 设计文档

## 概述

笔记知识库模块在课表管理系统基础上扩展了"课程笔记 + 知识检索"功能。用户可上传课程笔记（PDF/DOCX），系统自动提取文本、按标题切片、建立向量索引，支持语义检索、RAG 问答和知识图谱可视化。

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

### 1.2 NoteChunk（笔记切片）

```python
class NoteChunk(BaseModel):
    chunk_id: str                # UUID
    note_id: str                 # 所属笔记
    heading: str                 # 切片标题（正则提取）
    content: str                 # 切片文本
    chunk_index: int             # 在文档中的顺序
```

Embedding 向量由 mem0/Qdrant 管理，不存于此模型。

### 1.3 KnowledgeTopic（知识主题）

```python
class KnowledgeTopic(BaseModel):
    id: str
    name: str                    # 主题名称
    parent_id: str | None        # 父主题（支持层级结构）
    child_ids: list[str]         # 子主题列表
    note_ids: list[str]          # 关联的笔记 ID
    summary: str                 # 主题摘要
    keywords: list[str]          # 关键词
    created_at: str
    updated_at: str
```

### 1.4 KnowledgeTree（知识树）

```python
class KnowledgeTree(BaseModel):
    version: int = 1
    student_id: str
    course_id: str | None        # 按课程隔离
    root_ids: list[str]          # 顶层主题
    topics: dict[str, KnowledgeTopic]
```

---

## 二、API 路由

### 2.1 笔记管理 `/note`

| 方法 | 路径 | 功能 | 说明 |
|------|------|------|------|
| POST | `/note/upload` | 上传笔记 | 接收 PDF/DOCX + 可选 course_id，返回 NoteDetail |
| GET | `/note/list` | 笔记列表 | 支持 `?course_id=` 过滤 |
| GET | `/note/{note_id}` | 笔记详情 | 返回 Note + chunks 列表 |
| GET | `/note/{note_id}/file` | 下载原始文件 | 用于前端预览 |
| PUT | `/note/{note_id}` | 编辑笔记元信息 | 修改标题、摘要、课程关联 |
| DELETE | `/note/{note_id}` | 删除笔记 | 同时清理向量索引和主题关联 |

### 2.2 知识检索与问答 `/knowledge`

| 方法 | 路径 | 功能 | 说明 |
|------|------|------|------|
| POST | `/knowledge/search` | 语义搜索 | 返回相关切片 + 相似度分数 |
| POST | `/knowledge/ask` | RAG 问答 | 检索相关切片 + LLM 生成回答 |
| GET | `/knowledge/graph` | 知识图谱 | 返回力导向图所需的 nodes + links |
| GET | `/knowledge/tree` | 获取知识树 | 按课程返回主题层级结构 |
| POST | `/knowledge/tree/topic` | 创建主题 | 支持指定父主题 |
| PUT | `/knowledge/tree/topic/{id}` | 更新主题 | 修改名称、摘要、关键词、父节点 |
| DELETE | `/knowledge/tree/topic/{id}` | 删除主题 | 子主题提升至父级，笔记归还父主题 |
| POST | `/knowledge/tree/topic/{id}/assign` | 关联笔记到主题 | |
| DELETE | `/knowledge/tree/topic/{id}/assign` | 取消关联 | |

---

## 三、后端架构

### 3.1 模块文件

```
app/
├── models/
│   ├── note.py                  # Note, NoteChunk, SearchResult, GraphResponse 等
│   └── knowledge.py             # KnowledgeTopic, KnowledgeTree 等
├── storage/
│   ├── note_store.py            # SQLite 存储笔记元数据和切片
│   └── knowledge_tree_store.py  # JSON 持久化知识树
├── services/
│   ├── note_service.py          # 上传、文本提取、切片
│   ├── knowledge_service.py     # 向量索引、检索、RAG、图谱、主题管理
│   └── topic_vector_store.py    # 主题向量索引（用于查询路由）
└── routers/
    ├── note.py                  # /note/* 路由
    └── knowledge.py             # /knowledge/* 路由

data/
├── notes.db                     # SQLite（笔记元数据 + 切片）
├── note_files/                  # 原始上传文件
│   └── {note_id}.{ext}
└── qdrant_db/                   # Qdrant 向量库（本地磁盘模式）
    ├── course_notes/            # 切片向量集合
    └── topic_vectors/           # 主题向量集合
```

### 3.2 上传处理流程

```
POST /note/upload (PDF/DOCX)
  ├─ 保存原始文件 → data/note_files/{note_id}.{ext}
  ├─ 文本提取（pdfplumber / python-docx）
  ├─ 标题感知切片（正则匹配标题行，按标题拆分，超长段落二次切分）
  ├─ 元数据 + 切片写入 SQLite
  ├─ 切片向量索引写入 Qdrant（best-effort）
  ├─ LLM 摘要生成（best-effort）
  └─ 自动匹配最相关主题并关联（best-effort）
```

### 3.3 RAG 问答流程

```
POST /knowledge/ask {"question": "什么是多态？"}
  ├─ 向量检索 top-5 相关切片（或词法检索降级）
  ├─ 组装上下文 prompt
  ├─ 调用 DeepSeek Chat API 生成回答
  └─ 返回回答 + 来源切片列表
```

LLM 不可用时，返回降级结果（检索到的切片原文）。

### 3.4 知识图谱构建

```
GET /knowledge/graph?course_id=...&query=...
  ├─ 加载该课程下所有切片
  ├─ 主题路由：根据 query 选择相关主题，缩小切片范围
  ├─ 计算切片间语义相似度（向量余弦 / 词法重叠降级）
  ├─ 过滤低于阈值的边
  └─ 返回 {nodes, links} JSON → 前端 Cytoscape.js 渲染
```

---

## 四、向量存储方案

### 4.1 技术选型

- **向量库**: Qdrant（本地磁盘模式，无需外部服务）
- **封装层**: mem0 库（统一管理 embedding 生成和向量 CRUD）
- **Embedding 模型**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`（384 维，支持中文）
- **LLM**: DeepSeek Chat（OpenAI 兼容接口）

### 4.2 配置

```python
mem0_config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "course_notes",
            "path": str(QDRANT_DB_DIR / "course_notes"),
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
```

### 4.3 数据隔离

- 切片向量按 `user_id=student_id` 隔离
- 检索时通过 `filters={"user_id": student_id}` 限定范围
- 按 `course_id` 进一步过滤（应用层实现）

### 4.4 主题向量索引

独立于切片向量，维护一个主题级别的向量集合：
- 每个主题的文本 = 名称 + 摘要 + 关键词 + 关联笔记标题
- 用于查询路由：收到搜索/图谱请求时，先匹配最相关主题，再在该主题关联的笔记范围内检索

---

## 五、文本切片策略

### 5.1 标题识别

使用正则模式匹配常见标题格式：

```python
HEADING_PATTERNS = [
    r'^#{1,3}\s+.+',                    # Markdown 标题
    r'^第[一二三四五六七八九十\d]+[章节部分]',  # 中文章节标记
    r'^[一二三四五六七八九十]+[、.]\s*.+',     # 中文序号标题
    r'^\d+[.\s].+',                      # 数字序号标题
    r'^[A-Z][A-Za-z\s]{2,50}$',          # 英文大写标题行
]
```

### 5.2 切片逻辑

1. 按标题正则将文档拆分为段落组
2. 每个段落组 = heading + 下方正文（直到下一个标题）
3. 超长段落（> 500 字）按空行拆分为子段落，仍超长则硬截断（50 字重叠）
4. 无标题匹配时（纯文本），按 500 字固定窗口 + 50 字重叠切片

---

## 六、前端页面

### 6.1 知识工作台

文件：`static/knowledge_workspace.html` + `static/knowledge-workspace.js`

布局：
- 左侧：知识主题树（可创建/编辑/删除主题）
- 中间：笔记列表 + 笔记详情（切片预览、DOCX 渲染）
- 右侧：语义检索 + 知识图谱 + RAG 问答

### 6.2 文档预览

- DOCX：使用 mammoth.js 转为 HTML 渲染
- 切片高亮：点击检索结果可定位到对应切片

### 6.3 知识图谱

- 使用 Cytoscape.js（CoSE 力导向布局）
- 节点 = 切片，按所属主题着色分组
- 边 = 语义相似度超过阈值的切片对
- 支持拖拽、缩放、点击节点查看详情

---

## 七、LLM 调用

### 7.1 接口配置

DeepSeek API 兼容 OpenAI SDK：

```python
from openai import OpenAI

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
```

### 7.2 调用场景

| 场景 | 输入 | 输出 |
|------|------|------|
| 摘要提取 | 前 3 个 chunks（~1500 字） | JSON `{title, summary}` |
| RAG 问答 | 5 个相关 chunks + 问题 | 自然语言回答 |

### 7.3 降级策略

- LLM 不可用时，摘要提取回退为取第一个 heading 作为标题、前 100 字作为摘要
- RAG 问答回退为返回检索结果原文，前缀 `(LLM 不可用，以下为检索结果)`

---

## 八、依赖

```
python-docx          # DOCX 文本提取
mem0ai (>=2.0.0)     # 向量记忆管理（封装 Qdrant + embedding）
qdrant-client        # 向量数据库客户端
sentence-transformers # embedding 模型
openai               # DeepSeek API 调用（兼容接口）
```

`pdfplumber` 和 `requests` 已在课表模块依赖中。

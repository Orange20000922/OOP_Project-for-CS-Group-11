# 学生课表管理系统 — 开发指南

本文档是项目的开发公约和操作手册。在动手写代码之前请通读一遍，遇到问题随时在群里问。

---

## 目录

1. [项目简介与环境搭建](#1-项目简介与环境搭建)
2. [项目结构](#2-项目结构)
3. [接口文档（作业要求）](#3-接口文档作业要求)
4. [测试要求](#4-测试要求)
5. [Git 操作指南](#5-git-操作指南)
6. [代码风格约定](#6-代码风格约定)
7. [常见问题](#7-常见问题)

---

## 1. 项目简介与环境搭建

**技术栈**：Python 3.11+ / FastAPI / Vue2前端

**搭建步骤**（只需做一次）：

```bash
# 1. 克隆仓库
git clone <仓库地址>
cd OOP_project

# 2. 创建虚拟环境
python -m venv python_env

# Windows 激活：
python_env\Scripts\activate

# macOS / Linux 激活：
source python_env/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动开发服务器
python -m uvicorn app.main:app --reload --port 8000
```

启动后访问 http://127.0.0.1:8000 即可看到页面，访问 http://127.0.0.1:8000/docs 可以看到 Swagger 自动生成的接口测试界面。

---

## 2. 项目结构

```
OOP_project/
├── app/                     # 后端源码（主要工作目录）
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置常量
│   ├── core/                # 手写数据结构（作业核心要求）
│   │   ├── doubly_linked_list.py
│   │   ├── bst.py
│   │   ├── hash_table.py
│   │   └── queue.py
│   ├── models/              # Pydantic 数据模型
│   ├── storage/             # 文件存储层
│   ├── services/            # 业务逻辑
│   └── routers/             # API 路由（薄层，调 services）
├── static/                  # 前端页面
├── data/                    # 运行时 JSON 数据（自动生成，不提交）
├── docs/
│   └── DESIGN.md            # 完整设计文档
├── tests/                   # 测试用例
└── requirements.txt         # Python 依赖
```

---

## 3. 接口文档（作业要求）

> **这是作业要求的一部分**，答辩/检查时需要能说清楚每个接口的用途、参数、返回值。下面的表格就是我们的接口文档，后续有改动请同步更新这里和 `docs/DESIGN.md`。

### 3.1 认证 `/auth`

所有接口无需登录即可访问。

| 方法 | 路径 | 功能 | 请求体 | 返回 |
|------|------|------|--------|------|
| POST | `/auth/register` | 注册 | `{"student_id": "学号", "name": "姓名", "password": "密码"}` | `{"student_id": "...", "name": "..."}` |
| POST | `/auth/login` | 登录 | `{"student_id": "学号", "password": "密码"}` | 同上 + `Set-Cookie: session_token=...` |
| POST | `/auth/logout` | 登出 | 无 | 204 无内容 |
| GET | `/auth/me` | 当前用户信息 | 无（读 Cookie） | `{"student_id": "...", "name": "..."}` |

### 3.2 课表管理 `/schedule`

以下接口均需要先登录（Cookie 中带 `session_token`），否则返回 `401`。

| 方法 | 路径 | 功能 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/schedule` | 获取完整课表 | 无 | Schedule 对象 |
| POST | `/schedule` | 初始化学期 | `{"semester": "2025-2026-2", "semester_start": "2026-02-24"}` | Schedule 对象 |
| POST | `/schedule/upload` | 上传课表文件 | JSON 或 PDF 文件 | Schedule 对象 |
| POST | `/schedule/fetch` | 从教务系统抓取 | `{"scnu_password": "密码"}` | `{"task_id": "...", "status": "queued"}` |
| GET | `/schedule/fetch/{task_id}` | 查询抓取进度 | 无 | `{"status": "succeeded/failed/running", ...}` |
| POST | `/schedule/course` | 新增一门课 | Course 字段 | Course 对象 |
| PUT | `/schedule/course/{id}` | 修改某门课 | Course 字段 | Course 对象 |
| DELETE | `/schedule/course/{id}` | 删除某门课 | 无 | 204 无内容 |

### 3.3 查询 `/query`

需要登录。根据系统时间自动计算当前周次和节次。

| 方法 | 路径 | 功能 | 返回 |
|------|------|------|------|
| GET | `/query/now` | 当前正在上的课 | Course 或 `null` |
| GET | `/query/today` | 今天所有课 | Course 列表 |
| GET | `/query/week` | 本周课表 | 按星期分组的课表 |
| GET | `/query/week/{offset}` | 指定周课表 | 同上（0=本周，-1=上周，+1=下周） |

### 3.4 数据模型

```
Course: {
  id: str,             // UUID
  name: str,           // 课程名
  teacher: str,        // 教师
  location: str,       // 教室
  weekday: int,        // 1-7（周一到周日）
  period_start: int,   // 第几节开始（1-12）
  period_end: int,     // 第几节结束
  weeks: [int],        // 上课周次列表
  week_type: str       // "all" / "odd" / "even"
}
```

---

## 4. 测试要求

### 4.1 基本要求

测试不用写得多复杂，但**你写的每个功能至少要有一个对应的测试**。检查标准：

- 正常情况能不能跑通（happy path）
- 边界情况会不会崩（比如传空、传错参数）

### 4.2 怎么写测试

测试文件放在 `tests/` 目录下，文件名以 `test_` 开头。用 `pytest` 运行：

```bash
# 确保激活了虚拟环境
python_env\Scripts\activate

# 运行全部测试
python -m pytest tests/ -v

# 只跑某个测试文件
python -m pytest tests/test_hash_table.py -v
```

一个最简单的测试长这样：

```python
# tests/test_hash_table.py
from app.core.hash_table import HashTable

def test_set_and_get():
    ht = HashTable()
    ht.set("name", "张三")
    assert ht.get("name") == "张三"

def test_get_missing_key():
    ht = HashTable()
    assert ht.get("不存在") is None
```

### 4.3 测试覆盖范围参考

| 模块 | 建议测试点 |
|------|-----------|
| `core/hash_table.py` | 增删查、碰撞处理、空表操作 |
| `core/bst.py` | 插入、查找、删除、空树操作 |
| `core/doubly_linked_list.py` | 添加、删除、遍历、空链表 |
| `core/queue.py` | 入队、出队、空队列出队 |
| `services/auth_service.py` | 注册、登录、密码验证、过期 session |
| `services/schedule_service.py` | 增删改课程、查询当前课 |

### 4.4 运行测试的时机

**在提交代码之前跑一次测试**，确保没有把别人的东西弄坏：

```bash
python -m pytest tests/ -v
```

如果看到全部 `PASSED` 就可以放心提交了。

---

## 5. Git 操作指南

### 5.1 分支说明

| 分支 | 用途 |
|------|------|
| `master` | 稳定版本，不直接在上面改代码 |
| `feat/service` | 后端开发 |
| `feat/front` | 前端开发 |

### 5.2 日常开发流程

```bash
# 1. 开始工作前，先拉取最新代码
git checkout feat/service      # 切到你的开发分支
git pull origin feat/service   # 拉取远程最新

# 2. 写完一段代码后，提交
git add app/core/hash_table.py         # 添加你改过的文件
git commit -m "实现哈希表 insert 和 get"  # 写清楚做了什么
git push origin feat/service           # 推到远程

# 3. 功能完成后，在 GitHub 上创建 Pull Request 合并到 master
```

### 5.3 提交信息怎么写

不需要很正式，但要让别人一眼看懂，建议大家使用英文来写：

```
# 好的例子：
实现哈希表的 set/get/delete 方法
修复登录时密码验证失败的 bug
补充 BST 的单元测试

# 不好的例子：
update
aaa
修复
```

### 5.4 需要谨慎处理的情况

以下操作可能导致代码丢失或覆盖别人的工作，**做之前在群里说一声**：

```bash
# ❌ 不要用这些命令，除非你确定知道后果：
git push --force          # 强制推送，会覆盖远程的提交记录
git reset --hard          # 丢弃所有未提交的修改，找不回来
git checkout -- .         # 丢弃所有工作区的修改

# ❌ 不要直接在 master 上 commit 和 push
git checkout master
git commit -m "xxx"
git push origin master
```

### 5.5 万一出问题了

```bash
# 不小心改乱了，想恢复到上一次提交的状态：
git stash                 # 临时存起来（还能找回来）
# 或
git checkout -- 文件名    # 放弃某个文件的修改

# 合并冲突了：
# 打开冲突文件，找到 <<<<<<< HEAD 和 ======= 之间的内容
# 保留需要的部分，删除冲突标记，然后：
git add .
git commit -m "解决合并冲突"
```

### 5.6 不要提交的文件

以下文件/目录不应该出现在 git 中（已在 `.gitignore` 中排除）：

- `python_env/` — 虚拟环境
- `data/` — 运行时数据
- `__pycache__/` — Python 缓存
- `.env` — 环境变量（如果用到的话）

如果你发现有不该提交的文件已经被提交了，私我来处理。

---

## 6. 代码风格约定

不强求统一风格，但尽量遵守以下几条：

1. **函数和变量用英文命名**，注释可以用中文
2. **一个函数只做一件事**，如果超过 50 行考虑拆分
3. **写注释**：在复杂逻辑上方加一行注释说明在干什么，不用每行都写
4. **不要删别人的代码**，如果觉得有问题先在群里讨论
5. **import 顺序**：标准库 → 第三方库 → 项目内部（`app.xxx`），每组之间空一行

---

## 7. 常见问题

**Q: 启动报错 `ModuleNotFoundError: No module named 'xxx'`**
> 确认激活了虚拟环境并安装了依赖：`pip install -r requirements.txt`

**Q: 启动后页面空白**
> 确认 `static/` 目录下有 `index.html`

**Q: 测试报错找不到 `app` 模块**
> 在项目根目录下运行 `python -m pytest`，不要 `cd` 到子目录里运行

**Q: Git push 被拒绝**
> 先 `git pull` 再 `git push`。如果提示冲突看 [5.5 万一出问题了](#55-万一出问题了)

**Q: 不知道自己该做什么**
> 看 `docs/DESIGN.md` 的"实现优先级"章节，或者直接私我

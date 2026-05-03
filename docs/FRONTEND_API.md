# 前端 API 接口规范

> 本文档定义前后端之间的 HTTP 接口契约，包括 URL、请求方式、鉴权方式、请求参数和返回结构。前端开发和后端开发均以此文档为准。

## 1. 通用约定

### 1.1 页面路由

| 路径 | 页面 | 鉴权 |
|------|------|------|
| `/` | 重定向到 `/login` | 无 |
| `/login` | 登录/注册 | 已登录则重定向到 `/dashboard` |
| `/dashboard` | 课表工作台 | 未登录重定向到 `/login` |
| `/knowledge-workspace` | 知识工作台 | 未登录重定向到 `/login` |

静态资源通过 `/static/...` 暴露。

### 1.2 请求规范

- 所有接口基于同源访问，前端使用相对路径（如 `/auth/login`）
- 除文件上传外，请求体为 `application/json`
- 文件上传使用 `multipart/form-data`
- 登录态通过 Cookie 维护，Cookie 名称为 `session_token`
- 所有请求需携带 `credentials: "include"`

```js
fetch("/auth/me", {
  method: "GET",
  credentials: "include",
});
```

### 1.3 错误返回格式

```json
{
  "detail": "错误描述"
}
```

### 1.4 状态码约定

| 状态码 | 含义 |
|--------|------|
| `200` | 请求成功 |
| `201` | 创建成功 |
| `202` | 异步任务已接受 |
| `204` | 操作成功，无返回体 |
| `400` | 参数错误或业务校验失败 |
| `401` | 未登录、登录失效或认证失败 |
| `404` | 资源不存在 |
| `422` | 文件可读但解析失败 |

## 2. 主要数据结构

### 2.1 UserInfo

```json
{
  "student_id": "20250001",
  "name": "张三",
  "scnu_account": "20250001"
}
```

### 2.2 Course

```json
{
  "id": "course-id",
  "name": "面向对象程序设计",
  "teacher": "李老师",
  "location": "理工楼A101",
  "weekday": 1,
  "period_start": 1,
  "period_end": 2,
  "weeks": [1, 2, 3],
  "week_type": "all"
}
```

说明：

- `weekday`: `1-7`，分别表示周一到周日
- `period_start` / `period_end`: 节次范围，当前系统允许 `1-12`
- `week_type`: `all | odd | even`

### 2.3 Schedule

```json
{
  "student_id": "20250001",
  "semester": "2025-2026-2",
  "semester_start": "2026-03-02",
  "courses": []
}
```

### 2.4 DashboardOverview

```json
{
  "user": {
    "student_id": "20250001",
    "name": "张三",
    "scnu_account": "20250001"
  },
  "schedule": null,
  "current_course": null,
  "today_courses": [],
  "week_courses": {
    "1": [],
    "2": [],
    "3": [],
    "4": [],
    "5": [],
    "6": [],
    "7": []
  },
  "week_offset": 0,
  "has_schedule": false
}
```

### 2.5 FetchTaskStatus

```json
{
  "task_id": "task-id",
  "status": "queued",
  "message": "抓取任务已入队",
  "created_at": "2026-04-14T12:00:00",
  "updated_at": "2026-04-14T12:00:00",
  "schedule_updated": false
}
```

`status` 可能值：

- `queued`
- `running`
- `succeeded`
- `failed`

## 3. 认证接口 `/auth`

### 3.1 注册

- URL: `/auth/register`
- Method: `POST`
- 是否需要登录: 否
- 功能: 创建本地账号

请求体：

```json
{
  "student_id": "20250001",
  "name": "张三",
  "password": "password123",
  "scnu_account": "20250001"
}
```

字段说明：

- `student_id`: 本地系统学号
- `name`: 姓名
- `password`: 本地登录密码
- `scnu_account`: 可选，统一身份认证登录账号，通常与学号一致；不传时默认使用 `student_id`

成功返回：

- 状态码: `201`
- 返回体: `UserInfo`

### 3.2 登录

- URL: `/auth/login`
- Method: `POST`
- 是否需要登录: 否
- 功能: 登录并写入 `session_token` Cookie

请求体：

```json
{
  "student_id": "20250001",
  "password": "password123"
}
```

成功返回：

- 状态码: `200`
- 返回体: `UserInfo`
- 副作用: 响应头写入登录 Cookie

失败：

- `401`: 学号或密码错误

### 3.3 登出

- URL: `/auth/logout`
- Method: `POST`
- 是否需要登录: 否
- 功能: 清理服务端登录态并删除 Cookie

成功返回：

- 状态码: `204`
- 返回体: 无

### 3.4 获取当前登录用户

- URL: `/auth/me`
- Method: `GET`
- 是否需要登录: 是
- 功能: 返回当前登录用户信息

成功返回：

- 状态码: `200`
- 返回体: `UserInfo`

失败：

- `401`: 未登录或登录状态失效

## 4. 课表接口 `/schedule`

### 4.1 获取完整课表

- URL: `/schedule`
- Method: `GET`
- 是否需要登录: 是
- 功能: 获取当前用户完整课表

成功返回：

- 状态码: `200`
- 返回体: `Schedule`

失败：

- `401`: 未登录
- `404`: 尚未初始化课表

### 4.2 初始化或更新学期信息

- URL: `/schedule`
- Method: `POST`
- 是否需要登录: 是
- 功能: 初始化课表元信息，或更新当前学期和开学日期

请求体：

```json
{
  "semester": "2025-2026-2",
  "semester_start": "2026-03-02"
}
```

成功返回：

- 状态码: `201`
- 返回体: `Schedule`

失败：

- `400`: 日期格式错误等
- `401`: 未登录

### 4.3 上传课表文件

- URL: `/schedule/upload`
- Method: `POST`
- 是否需要登录: 是
- 功能: 上传 JSON 或 PDF 课表文件

请求方式：

- `multipart/form-data`
- 表单字段名: `file`

支持类型：

- `.json`
- `.pdf`

成功返回：

- 状态码: `201`
- 返回体: `Schedule`

失败：

- `400`: 文件类型不支持、JSON 格式不合法、学期信息缺失
- `401`: 未登录
- `422`: PDF 可上传但未解析出课程

JSON 上传说明：

- 可上传完整对象：

```json
{
  "semester": "2025-2026-2",
  "semester_start": "2026-03-02",
  "courses": [
    {
      "name": "面向对象程序设计",
      "teacher": "李老师",
      "location": "理工楼A101",
      "weekday": 1,
      "period_start": 1,
      "period_end": 2,
      "weeks": [1, 2, 3],
      "week_type": "all"
    }
  ]
}
```

- 也可上传课程数组，但前提是该用户已经初始化过课表：

```json
[
  {
    "name": "面向对象程序设计",
    "teacher": "李老师",
    "location": "理工楼A101",
    "weekday": 1,
    "period_start": 1,
    "period_end": 2,
    "weeks": [1, 2, 3],
    "week_type": "all"
  }
]
```

### 4.4 发起统一身份认证课表抓取任务

- URL: `/schedule/fetch`
- Method: `POST`
- 是否需要登录: 是
- 功能: 异步发起教务课表抓取任务

请求体：

```json
{
  "scnu_password": "your-password",
  "scnu_account": "20250001",
  "semester_id": "2025-2026-2",
  "prefer_playwright": false
}
```

字段说明：

- `scnu_password`: 必填，统一身份认证密码
- `scnu_account`: 可选，统一身份认证登录账号；通常与学号一致，不传时默认使用当前用户学号
- `semester_id`: 可选，不传时默认使用当前课表的 `semester`
- `prefer_playwright`: 可选，`true` 表示优先走 Playwright 统一身份认证回退路径

成功返回：

- 状态码: `202`
- 返回体: `FetchTaskStatus`

前端轮询方式：

- 记录返回的 `task_id`
- 定时轮询 `/schedule/fetch/{task_id}` 直到状态变为终态

### 4.5 查询抓取任务状态

- URL: `/schedule/fetch/{task_id}`
- Method: `GET`
- 是否需要登录: 是
- 功能: 查询异步抓取任务的执行状态

路径参数：

- `task_id`: 抓取任务 ID

成功返回：

- 状态码: `200`
- 返回体: `FetchTaskStatus`

失败：

- `401`: 未登录
- `404`: 任务不存在

### 4.6 手动新增课程

- URL: `/schedule/course`
- Method: `POST`
- 是否需要登录: 是
- 功能: 手动新增单门课程

请求体：

```json
{
  "name": "面向对象程序设计",
  "teacher": "李老师",
  "location": "理工楼A101",
  "weekday": 1,
  "period_start": 1,
  "period_end": 2,
  "weeks": [1, 2, 3],
  "week_type": "all"
}
```

成功返回：

- 状态码: `201`
- 返回体: `Course`

失败：

- `400`: 课表未初始化、节次非法、周次非法
- `401`: 未登录

### 4.7 更新课程

- URL: `/schedule/course/{course_id}`
- Method: `PUT`
- 是否需要登录: 是
- 功能: 修改一门已有课程

路径参数：

- `course_id`: 课程 ID

请求体：

- 与新增课程完全一致，使用 `CourseCreate` 结构

成功返回：

- 状态码: `200`
- 返回体: `Course`

失败：

- `400`: 课表未初始化、课程不存在、节次非法、周次非法
- `401`: 未登录

### 4.8 删除课程

- URL: `/schedule/course/{course_id}`
- Method: `DELETE`
- 是否需要登录: 是
- 功能: 删除一门课程

路径参数：

- `course_id`: 课程 ID

成功返回：

- 状态码: `204`
- 返回体: 无

失败：

- `400`: 课表未初始化或课程不存在
- `401`: 未登录

## 5. 查询接口 `/query`

### 5.1 查询工作台总览

- URL: `/query/overview`
- Method: `GET`
- 是否需要登录: 是
- 功能: 一次性返回当前用户、课表、当前课程、今日课程和指定周课表，供工作台和知识工作台初始化使用

查询参数：

- `week_offset`: 可选，整数，默认 `0`

成功返回：

- 状态码: `200`
- 返回体: `DashboardOverview`

失败：

- `401`: 未登录

### 5.2 查询当前正在上的课程

- URL: `/query/now`
- Method: `GET`
- 是否需要登录: 是
- 功能: 按系统当前时间计算“现在这节课”

成功返回：

- 状态码: `200`
- 返回体: `Course` 或 `null`

说明：

- 当前时段没有课时返回 `null`

失败：

- `401`: 未登录
- `404`: 课表未初始化

### 5.3 查询今天所有课程

- URL: `/query/today`
- Method: `GET`
- 是否需要登录: 是
- 功能: 返回今天全部课程

成功返回：

- 状态码: `200`
- 返回体: `Course[]`

失败：

- `401`: 未登录
- `404`: 课表未初始化

### 5.4 查询本周课表

- URL: `/query/week`
- Method: `GET`
- 是否需要登录: 是
- 功能: 返回本周的按星期分组课表

成功返回：

- 状态码: `200`
- 返回体:

```json
{
  "1": [],
  "2": [],
  "3": [],
  "4": [],
  "5": [],
  "6": [],
  "7": []
}
```

说明：

- 键为字符串 `"1"` 到 `"7"`
- 值为该天课程数组

失败：

- `401`: 未登录
- `404`: 课表未初始化

### 5.5 查询指定周偏移课表

- URL: `/query/week/{offset}`
- Method: `GET`
- 是否需要登录: 是
- 功能: 查询相对本周偏移后的课表

路径参数：

- `offset`: 整数
  - `0` 表示本周
  - `-1` 表示上周
  - `1` 表示下周

成功返回：

- 状态码: `200`
- 返回体: 与 `/query/week` 相同

失败：

- `401`: 未登录
- `404`: 课表未初始化

## 6. 典型调用流程

### 6.1 页面初始化

1. `GET /auth/me` — 检查登录态
2. 若 `200`，`GET /query/overview` — 加载工作台数据
3. 按需调用 `/query/week/{offset}` 切换周次

### 6.2 注册与登录

1. `POST /auth/register` — 创建账号
2. `POST /auth/login` — 登录，获取 Cookie
3. `GET /query/overview` — 判断是否已初始化学期

### 6.3 教务课表抓取

1. `POST /schedule/fetch` — 提交抓取任务
2. 每 2~3 秒轮询 `GET /schedule/fetch/{task_id}`
3. `status = succeeded` 后刷新 `/query/overview`


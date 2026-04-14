# 前端接口文档

本文档说明当前系统中前端会直接调用的 URL 接口、请求方式、鉴权方式、请求参数和返回结构。

## 1. 通用约定

### 1.0 页面入口

- 登录页：`/`
- 工作台页：`/dashboard.html`
- 前端登录成功后，应跳转到 `/dashboard.html`
- 若用户已登录，再访问 `/`，前端应直接跳转到 `/dashboard.html`
- 若用户未登录却直接访问 `/dashboard.html`，前端应跳回 `/`

### 1.1 基础说明

- 接口基于同源访问设计，前端可直接请求相对路径，例如 `/auth/login`
- 除文件上传接口外，请求体均为 `application/json`
- 文件上传接口使用 `multipart/form-data`
- 登录态通过 Cookie 维护，Cookie 名称为 `session_token`
- 前端请求时应带上 `credentials: "include"`

示例：

```js
fetch("/auth/me", {
  method: "GET",
  credentials: "include",
});
```

### 1.2 错误返回格式

接口报错时，统一返回：

```json
{
  "detail": "错误信息"
}
```

常见状态码：

- `200` 请求成功
- `201` 创建成功
- `202` 已接受异步任务
- `204` 删除成功，无返回体
- `400` 参数错误或业务校验失败
- `401` 未登录、登录失效或认证失败
- `404` 资源不存在
- `422` 上传文件可读但解析失败

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

### 2.4 FetchTaskStatus

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
- `scnu_account`: 可选，SCNU 教务账号；不传时默认使用 `student_id`

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

### 4.4 发起 SCNU 教务抓取任务

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

- `scnu_password`: 必填，SCNU 教务密码
- `scnu_account`: 可选，不传时默认使用当前用户学号
- `semester_id`: 可选，不传时默认使用当前课表的 `semester`
- `prefer_playwright`: 可选，`true` 表示优先走 Playwright SSO 回退路径

成功返回：

- 状态码: `202`
- 返回体: `FetchTaskStatus`

前端建议：

- 记录返回的 `task_id`
- 定时轮询 `/schedule/fetch/{task_id}`

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

### 5.1 查询当前正在上的课程

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

### 5.2 查询今天所有课程

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

### 5.3 查询本周课表

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

### 5.4 查询指定周偏移课表

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

## 6. 推荐前端调用顺序

### 6.1 首次进入页面

1. 调用 `/auth/me`
2. 若返回 `200`，进入应用页
3. 再调用 `/schedule`
4. 若课表存在，继续调用 `/query/week` 和 `/query/now`

### 6.2 注册/登录

1. 注册时先调用 `/auth/register`
2. 成功后调用 `/auth/login`
3. 登录成功后调用 `/schedule` 判断是否已初始化学期

### 6.3 从教务系统抓取课表

1. 调用 `/schedule/fetch`
2. 获取 `task_id`
3. 每隔 2~3 秒轮询 `/schedule/fetch/{task_id}`
4. 当 `status = succeeded` 时刷新 `/schedule` 与 `/query/week`

## 7. 当前前端实际使用到的接口

目前静态前端页面已使用以下接口：

- `/auth/register`
- `/auth/login`
- `/auth/logout`
- `/auth/me`
- `/schedule`
- `/schedule/upload`
- `/schedule/fetch`
- `/schedule/fetch/{task_id}`
- `/schedule/course`
- `/schedule/course/{course_id}`
- `/query/now`
- `/query/week`
- `/query/week/{offset}`

如果后续接口字段发生变化，应同步更新此文档与前端调用代码。

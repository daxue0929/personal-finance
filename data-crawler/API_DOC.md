# 基金数据爬虫 API 文档

## 概述

本文档描述基金数据爬虫服务提供的 REST API 接口，用于任务调度管理和基金数据爬取。

***

## 基础信息

- **服务地址**: `http://localhost:5001`
- **API 版本**: v1
- **Content-Type**: `application/json`

***

## 接口列表

### 1. 健康检查

**GET /health**

检查服务是否正常运行

**响应示例**:

```json
{
  "status": "ok",
  "service": "fund-crawler"
}
```

***

### 2. 获取调度器状态

**GET /api/status**

获取当前调度器运行状态和任务列表

**响应示例**:

```json
{
  "running": true,
  "message": "调度器运行中",
  "jobs": [
    {
      "id": "update_fund_net_values_task",
      "name": "基金净值更新任务",
      "next_run_time": "2026-05-20 10:00:00+08:00",
      "trigger": "cron[0 * * * *]"
    }
  ]
}
```

***

### 3. 触发基金爬取

**POST /api/crawl**

立即触发基金净值爬取任务

**响应示例**:

```json
{
  "success": true,
  "message": "任务 update_fund_net_values_task 已触发"
}
```

***

### 4. 获取所有任务配置

**GET /api/tasks**

获取数据库中所有定时任务配置

**响应示例**:

```json
[
  {
    "id": 1,
    "task_name": "基金净值更新任务",
    "task_func": "update_fund_net_values_task",
    "cron_expression": "0 * * * *",
    "enabled": true,
    "description": "每小时整点更新基金净值",
    "next_run_time": "2026-05-20 10:00:00+08:00",
    "create_time": "2026-05-20 09:30:00",
    "update_time": "2026-05-20 09:30:00"
  }
]
```

***

### 5. 获取单个任务配置

**GET /api/tasks/{task\_id}**

根据任务ID获取任务详情

**路径参数**:

| 参数       | 类型  | 说明   |
| -------- | --- | ---- |
| task\_id | int | 任务ID |

**响应示例**:

```json
{
  "id": 1,
  "task_name": "基金净值更新任务",
  "task_func": "update_fund_net_values_task",
  "cron_expression": "0 * * * *",
  "enabled": true,
  "description": "每小时整点更新基金净值",
  "next_run_time": "2026-05-20 10:00:00+08:00",
  "create_time": "2026-05-20 09:30:00",
  "update_time": "2026-05-20 09:30:00"
}
```

***

### 6. 创建新任务

**POST /api/tasks**

创建新的定时任务配置

**请求体**:

| 字段               | 类型      | 必填 | 说明           |
| ---------------- | ------- | -- | ------------ |
| task\_name       | string  | 是  | 任务名称         |
| task\_func       | string  | 是  | 任务函数名（需已注册）  |
| cron\_expression | string  | 是  | Cron 表达式     |
| enabled          | boolean | 否  | 是否启用（默认true） |
| description      | string  | 否  | 任务描述         |

**请求示例**:

```json
{
  "task_name": "每日统计任务",
  "task_func": "daily_statistics_task",
  "cron_expression": "0 23 * * *",
  "enabled": true,
  "description": "每天23点执行统计任务"
}
```

**响应示例**:

```json
{
  "success": true,
  "message": "任务创建成功",
  "task_id": 2
}
```

***

### 7. 更新任务配置

**PUT /api/tasks/{task\_id}**

更新指定任务的配置（支持热更新）

**路径参数**:

| 参数       | 类型  | 说明   |
| -------- | --- | ---- |
| task\_id | int | 任务ID |

**请求体**（可选字段）:

| 字段               | 类型      | 说明       |
| ---------------- | ------- | -------- |
| task\_name       | string  | 任务名称     |
| cron\_expression | string  | Cron 表达式 |
| enabled          | boolean | 是否启用     |
| description      | string  | 任务描述     |

**请求示例**:

```json
{
  "cron_expression": "0,30 * * * *",
  "description": "每30分钟更新一次基金净值"
}
```

**响应示例**:

```json
{
  "success": true,
  "message": "任务更新成功"
}
```

***

### 8. 删除任务

**DELETE /api/tasks/{task\_id}**

删除指定任务（软删除）

**路径参数**:

| 参数       | 类型  | 说明   |
| -------- | --- | ---- |
| task\_id | int | 任务ID |

**响应示例**:

```json
{
  "success": true,
  "message": "任务删除成功"
}
```

***

### 9. 立即执行任务

**POST /api/task/run/{task_func}**

根据任务函数名立即执行任务

**路径参数**:

| 参数         | 类型     | 说明    |
| ---------- | ------ | ----- |
| task_func | string | 任务函数名 |

**请求体**（可选）:

| 字段         | 类型      | 说明                          |
| ---------- | ------- | --------------------------- |
| force_run  | boolean | 是否强制执行（跳过交易时间检查），默认 false |

**请求示例**:

```json
{
  "force_run": true
}
```

**响应示例**:

```json
{
  "success": true,
  "message": "任务 fetch_kc100_index_task 已触发 (force_run)"
}
```

**说明**:

- 默认情况下，指数抓取任务仅在交易时间（周一至周五 9:00-15:05）内执行
- 设置 `force_run: true` 可跳过交易时间检查，强制执行任务
- 适用任务：`fetch_kc50_index_task`、`fetch_kc100_index_task`

**调用示例**:

```bash
# 普通执行（受交易时间限制）
curl -X POST http://localhost:5001/api/task/run/fetch_kc50_index_task \
  -H "Content-Type: application/json" \
  -d '{}'

# 强制执行（跳过交易时间检查）
curl -X POST http://localhost:5001/api/task/run/fetch_kc100_index_task \
  -H "Content-Type: application/json" \
  -d '{"force_run": true}'
```

***

### 10. 启动调度器

**POST /api/start**

启动任务调度器

**响应示例**:

```json
{
  "success": true,
  "message": "调度器已启动"
}
```

***

### 11. 停止调度器

**POST /api/stop**

停止任务调度器

**响应示例**:

```json
{
  "success": true,
  "message": "调度器已停止"
}
```

***

## Cron 表达式说明

### 格式

```
┌───────────── 分钟 (0-59)
│ ┌───────────── 小时 (0-23)
│ │ ┌───────────── 日期 (1-31)
│ │ │ ┌───────────── 月份 (1-12)
│ │ │ │ ┌───────────── 星期 (0-6)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

### 常用示例

| 表达式            | 说明         |
| -------------- | ---------- |
| `0 * * * *`    | 每小时整点      |
| `0,30 * * * *` | 每30分钟      |
| `0 0 * * *`    | 每天凌晨0点     |
| `0 23 * * *`   | 每天23点      |
| `0 9,15 * * *` | 每天9点和15点   |
| `0 9-18 * * *` | 每天9点到18点整点 |
| `0 0 * * 1`    | 每周一凌晨0点    |
| `0 0 1 * *`    | 每月1号凌晨0点   |

***

## 错误响应格式

```json
{
  "error": "错误描述信息"
}
```

### 常见错误码

| 状态码 | 说明             |
| --- | -------------- |
| 400 | 请求参数错误         |
| 404 | 资源不存在          |
| 409 | 资源冲突（如任务函数已存在） |
| 500 | 服务器内部错误        |
| 503 | 服务不可用（调度器未启动）  |


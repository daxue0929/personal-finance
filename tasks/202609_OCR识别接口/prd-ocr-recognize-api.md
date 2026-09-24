# PRD: OCR 图片识别对外开放接口（ocr-recognize-api）

**Feature slug**: `ocr-recognize-api`

## 1. 概述

已有支付宝基金交易记录 OCR 工具链（`PaddleOcrClient` 单例识别 → `AlipayRecordParser` 解析 → 导出 Excel），但只能本地跑脚本，没有 HTTP 入口。本功能在 **web 进程**新增一个对外开放接口 `POST /api/ocr/recognize`：外部调用方上传 Base64 图片，服务端 OCR 识别并解析为结构化交易记录 JSON，**直接随响应返回**，同时在日志中打印完整 JSON。

本期目的：先把接口链路打通，人工用 curl 验证**识别准确性**与**上传/解码环节是否有错**，故**不写数据库、不做前端页面、不保存原始图片**。

## 2. 已确认决策

| 项 | 决策 |
|---|---|
| 部署进程 | **web 进程**（5000 对外）；web 部署环境需安装 `requirements-ocr.txt` |
| 接口路径 | `POST /api/ocr/recognize`（不用 curl 示例中的 `/update`，遵循 RESTful 规范） |
| 请求体 | `{ "images": "<base64 字符串>" }`，**单张**图片 |
| 响应 | **返回完整识别结果** JSON（交易记录列表），不仅成功标志 |
| 认证 | Basic Auth：`Authorization: Basic base64(clientId:clientSecret)`，凭证配置在 `.env`（项目约定配置不硬编码） |
| 数据落库 | 本期不写数据库，仅日志打印 JSON |
| 原始文件 | 不持久化：base64 解码后写临时文件供 OCR 读取，识别完成立即删除（finally 兜底） |

## 3. 功能目标

- 外部系统可通过 HTTP + Basic Auth 调用 OCR 识别能力，无需登录会话。
- 识别结果以 JSON 返回并打印日志，便于人工核对准确性。
- 原始图片不落盘留存，临时文件必删。
- 不改动现有 OCR/解析代码的对外行为（`recognize`/`parse` 复用，不重写）。

## 4. 用户故事

- 作为外部系统调用方，我用 clientId/clientSecret 调 `/api/ocr/recognize` 上传一张支付宝交易记录截图，就能拿到结构化的交易记录 JSON，无需关心服务端 OCR 细节。
- 作为开发者（我），我在联调阶段通过响应体和 `system_log` 日志中的 JSON 核对识别准确性，用 trace_id 串联请求链路，快速定位是上传解码问题还是识别问题。

## 5. 功能需求

### 5.1 接口定义

```
POST /api/ocr/recognize
Content-Type: application/json
Authorization: Basic base64(clientId:clientSecret)

{
  "images": "<base64 编码的图片>"
}
```

成功响应（200）：

```json
{
  "count": 2,
  "records": [
    {
      "fund_name": "华夏科创50ETF联接C(011613)",
      "trade_type": "定投",
      "amount": 300.0,
      "status": "交易进行中",
      "trade_time": "2026-09-24 11:44:00"
    }
  ]
}
```

失败响应：统一 `{"error": message}` + 状态码（与项目现有错误处理一致）。

### 5.2 认证

- 请求头解析 `Authorization: Basic <token>`，base64 解码为 `clientId:clientSecret`，与 `.env` 中的 `OCR_API_CLIENT_ID` / `OCR_API_CLIENT_SECRET` 比对。
- 认证失败返回 401 `{"error": "认证失败"}`；缺少/格式非法的 Authorization 头同样 401。
- 比对用 `hmac.compare_digest`（防时序攻击）。
- 该接口**不走现有会话登录鉴权**（外部系统无 Cookie/Session），用独立的 Basic Auth 装饰器。

### 5.3 处理流程

1. 校验请求体：JSON 中存在 `images` 且为非空字符串 → 否则 400。
2. base64 解码 → 失败返回 400 `{"error": "images 不是合法的 base64"}`。兼容 data URI 前缀（`data:image/png;base64,...` 剥前缀）。
3. 校验解码后是图片（用文件魔数判断 png/jpeg 等常见格式）→ 否则 400。
4. 写入临时文件（`tempfile`，按魔数定后缀）→ 调 `get_paddle_ocr_client().recognize(tmp_path)` → `AlipayRecordParser().parse(blocks)`。
5. **finally 中删除临时文件**，无论识别成败。
6. 记录 JSON 序列化（`dataclasses.asdict`），`logger.info` 打印完整结果 JSON，随响应返回。
7. OCR 未安装（ImportError）→ 503 `{"error": "OCR 服务未启用"}`；识别过程异常 → 500。
8. 识别结果为 0 条**不算错误**（可能是图片不含交易记录），正常返回 `{"count": 0, "records": []}`。

### 5.4 请求体大小限制

- base64 字符串长度上限（建议 10MB 解码前 ≈ 13.3MB 字符串），超限返回 413。Flask `MAX_CONTENT_LENGTH` 全局配置即可。

### 5.5 日志

- 使用 `@log_request` 装饰器（trace_id 链路），日志 category 为 `api`。
- INFO 日志打印识别结果 JSON（含 trace_id，可在 `system_log` 表串联查询）。
- 日志**不打印 base64 原文**（体积大且无意义）。

## 6. 验收标准

- [ ] 无 Authorization / 错误凭证 → 401；正确凭证 → 200。
- [ ] `images` 缺失/空/非 base64/非图片 → 400，错误信息明确。
- [ ] 真实支付宝截图（两种布局各一张）→ 返回的 records 与图片内容一致（人工核对）。
- [ ] 识别后临时文件已删除（无残留）。
- [ ] 日志中可通过 trace_id 查到完整识别结果 JSON，且不含 base64 原文。
- [ ] 不写任何业务表（fund_buyer/fund_seller 等无新增记录）。
- [ ] 认证、参数校验、临时文件清理有单测（TDD，OCR 引擎 mock 掉，不依赖 paddleocr 安装）。
- [ ] `pytest tests/ -q` 无回归。

## 7. 非目标

- 不做任何前端页面/菜单。
- 不写数据库（识别结果不入 fund_buyer/fund_seller，后续单独功能再做）。
- 不支持一次多张图片（`images` 为单张字符串，多张需求后续迭代）。
- 不返回原始 OCR 文本块/坐标（只返回解析后的交易记录）。
- 不做调用方配额/限流/计费。
- 不改动 Excel 导出功能（`ocr_image_to_excel` 保持原样）。
- 凭证不做多组/数据库管理（本期 `.env` 单组写死）。

## 8. 依赖

- `app/utils/paddle_ocr_client.py`（`get_paddle_ocr_client().recognize`，单例惰性加载）。
- `app/parser/alipay_record_parser.py`（`AlipayRecordParser.parse`）。
- web 部署环境安装 `requirements-ocr.txt`（**部署注意**：当前生产镜像不含 OCR 依赖，Dockerfile 是否纳入见技术考虑）。
- `.env` 新增 `OCR_API_CLIENT_ID` / `OCR_API_CLIENT_SECRET`。

## 9. 技术考虑

- 新接口放 `app/web/api_server.py`（单文件现状，遵循最小化编辑；认证装饰器与参数校验拆成可单测的函数）。
- 临时文件用 `tempfile.NamedTemporaryFile(delete=False)` + finally `os.remove`（Windows 兼容写法，与 PaddleOCR 需要文件路径的现状匹配）。
- 图片魔数校验：png `\x89PNG`、jpeg `\xFF\xD8\xFF` 等前缀判断，纯函数可单测。
- **镜像权衡**：paddleocr 体积大（数百 MB），生产 web 镜像若纳入会显著变大。本期先按"web 环境安装 requirements-ocr.txt"处理（本地/服务器手动 pip install），是否进 Dockerfile 待联调通过后另议——PRD 不锁定。
- Flask `MAX_CONTENT_LENGTH` 设置为全局会影响其他接口，需确认现有接口无大请求体（现状均为小 JSON，风险低）。

## 10. 风险评估

| 风险 | 影响 | 缓解 |
|---|---|---|
| OCR 识别不准确 | 核心目的即验证准确性 | 响应+日志双输出 JSON，人工 curl 核对 |
| 凭证硬编码泄露 | 接口可被任意调用，消耗 CPU | `.env` 不入库；生产用强随机 secret；后续可迁移 secrets 管理 |
| 大图片/OCR 耗时阻塞 web worker | 其他接口变慢 | 限制请求体大小；OCR 单进程内串行执行（可接受，本期低频调用） |
| web 环境忘装 paddleocr | 接口 503 | 明确的 503 错误信息 + 文档说明 |
| MAX_CONTENT_LENGTH 全局生效影响存量接口 | 存量接口均为小 JSON，风险低 | 设置为 15MB 左右，远大于现有请求 |

## 11. 成功指标

- curl 联调通过：正确凭证 + 真实截图返回与图片一致的交易记录 JSON。
- 两种支付宝页面布局截图均能正确解析（复用 parser 已有能力）。
- 日志可通过 trace_id 串联，无 base64 刷屏。
- 服务器/本地无临时文件残留、无业务表写入。

## 12. 开放问题

- OCR 依赖是否纳入生产 web 镜像（Dockerfile），还是保持手动安装？（联调通过后决定）
- 后续多张图片、结果入库（对接买入/卖出流水）的迭代排期。

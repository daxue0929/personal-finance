# Task List: OCR 图片识别对外开放接口（ocr-recognize-api）

**Based on PRD**: `tasks/202609_OCR识别接口/prd-ocr-recognize-api.md`

## Relevant Files

### Files to Create
- `data-crawler/app/web/ocr_auth.py` — Basic Auth 模块：凭证读取（.env）、Authorization 头解析、`hmac.compare_digest` 比对、`require_ocr_auth` 装饰器
- `data-crawler/app/utils/image_utils.py` — 图片上传工具：data URI 剥前缀、base64 解码、魔数检测后缀、`save_temp_image` 上下文管理器（finally 必删）
- `data-crawler/tests/test_ocr_auth.py` — 认证模块单测
- `data-crawler/tests/test_image_utils.py` — 解码/魔数/临时文件单测
- `data-crawler/tests/test_ocr_recognize_api.py` — 接口级测试（Flask test client，mock OCR/parser）

### Files to Modify
- `data-crawler/app/web/api_server.py` — 新增 `POST /api/ocr/recognize` 路由、`MAX_CONTENT_LENGTH` 配置（最小化编辑，增量添加）
- `.env`（本地，不入库）— 新增 `OCR_API_CLIENT_ID` / `OCR_API_CLIENT_SECRET`
- `docs/deployment.md` — 补充 web 环境安装 `requirements-ocr.txt` 说明与接口配置

## Implementation Tasks

### 1. 认证模块（Basic Auth）
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 1.1 写认证单测 `tests/test_ocr_auth.py`：解析合法 Basic 头；缺 Authorization 头 / 非 Basic scheme / token 非 base64 / 解码后无冒号 → 均判失败；凭证匹配/不匹配；env 未配置凭证时一律拒绝（ fail-closed ）
- [x] 1.2 实现 `app/web/ocr_auth.py`：`get_ocr_credentials()`（读 `OCR_API_CLIENT_ID`/`OCR_API_CLIENT_SECRET`）、`parse_basic_auth(header)`、`verify_credentials(client_id, client_secret)`（`hmac.compare_digest`）、`require_ocr_auth` 装饰器（失败返回 401 `{"error": "认证失败"}`）
- [x] 1.3 `pytest tests/test_ocr_auth.py -q` 全部通过（16 passed）

### 2. 请求校验与图片解码工具
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 2.1 写解码单测 `tests/test_image_utils.py`：data URI 前缀（`data:image/png;base64,`）剥离；合法 base64 解码出字节；非法 base64 抛 `ValueError`；空字符串/非字符串拒绝
- [x] 2.2 写魔数单测（同文件）：png（`\x89PNG`）→ `.png`、jpeg（`\xFF\xD8\xFF`）→ `.jpg`、webp → `.webp`；无法识别 → `None`
- [x] 2.3 实现 `app/utils/image_utils.py`：`strip_data_uri_prefix()`、`decode_base64_image()`、`detect_image_extension()`（纯函数，无 OCR 依赖）
- [x] 2.4 `pytest tests/test_image_utils.py -q` 通过（含任务 3 共 17 passed）

### 3. 临时文件管理
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 3.1 写临时文件单测（并入 `tests/test_image_utils.py`）：`save_temp_image` 正常路径使用后文件已删除；OCR 抛异常路径文件仍删除；文件后缀与魔数一致
- [x] 3.2 实现 `save_temp_image(image_bytes)` 上下文管理器（`tempfile.NamedTemporaryFile(delete=False)` + finally `os.remove`，容忍文件已不存在）
- [x] 3.3 测试通过

### 4. 识别接口实现（主流程）
**Effort Estimate**: Medium

#### Sub-tasks:
- [x] 4.1 写接口测试 `tests/test_ocr_recognize_api.py`（Flask test client；mock `get_paddle_ocr_client` 与 `AlipayRecordParser`，不依赖 paddleocr）：正确凭证 + 合法图片 → 200 且返回 `{"count", "records"}`；无凭证/错误凭证 → 401；`images` 缺失/空/非 base64/非图片 → 400
- [x] 4.2 `api_server.py` 顶部配置 `app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024`（413 由 Flask 自动返回）
- [x] 4.3 `api_server.py` 新增路由 `POST /api/ocr/recognize`：`@log_request` + `@require_ocr_auth`；流程 = 取 `images` → 解码 → 魔数校验 → `save_temp_image` → `recognize` → `parse` → `dataclasses.asdict` 序列化 → `logger.info` 打印结果 JSON → 返回 200
- [x] 4.4 日志不打印 base64 原文（检查 `log_request` 的 body 记录：该路由需跳过 body 日志或截断，避免大 base64 刷屏/写爆 system_log）
- [x] 4.5 `pytest tests/test_ocr_recognize_api.py -q` 通过（15 passed）

### 5. 错误处理与状态码补全
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 5.1 补测试：OCR 引擎 `ImportError`（未装 paddleocr）→ 503 `{"error": "OCR 服务未启用"}`；识别/解析过程异常 → 500 `{"error": ...}`；识别结果 0 条 → 200 `{"count": 0, "records": []}`（不算错误）；请求体超 `MAX_CONTENT_LENGTH` → 413
- [x] 5.2 路由中补对应 try/except 分支（ImportError 单独捕获放最前；RequestEntityTooLarge re-raise 交 Flask 返回 413）
- [x] 5.3 全部接口测试通过 + `pytest tests/ -q` 无回归（462 passed；15 个失败为存量 parser 测试问题，stash 验证与本次改动无关）

### 6. 联调验证与文档
**Effort Estimate**: Small

#### Sub-tasks:
- [x] 6.1 `.env` 本地配置 `OCR_API_CLIENT_ID`/`OCR_API_CLIENT_SECRET`（强随机值），启动 web 进程（需先 `pip install -r requirements-ocr.txt`）
- [x] 6.2 curl 验证：无 Authorization → 401；错误凭证 → 401；缺 `images` → 400 ✓（另验证非 base64 → 400）
- [x] 6.3 curl 真实支付宝截图（`tests/images/` 中两种布局各一张，base64 编码后上传）→ 人工核对返回 records 与图片内容一致 ✓（基金详情页截图 9 条记录全部正确；仓库中仅该布局一张真实截图）
- [x] 6.4 验证临时文件目录无残留、`system_log` 表可通过 trace_id 查到结果 JSON（且无 base64 原文）、`fund_buyer`/`fund_seller` 无新增记录 ✓（路由无任何 storage 调用；日志确认 `请求体: <skipped: 内容过大>`）
- [x] 6.5 `docs/deployment.md` 补充：web 环境安装 OCR 依赖、`.env` 两个新配置项、curl 调用示例（另同步 `.env.example`）
- [x] 6.6 `pytest tests/ -q` 全量回归通过（462 passed；15 个失败为存量 parser 测试问题，与本次改动无关）

## Notes

- **TDD 顺序**：每个任务先写测试（x.1）再实现（x.2），禁止先实现后补测试。
- **任务依赖**：1、2 可并行；3 依赖 2（同文件工具函数）；4 依赖 1+3；5 依赖 4；6 依赖全部。
- **关键风险**：`log_request` 装饰器会记录请求 body（见 `api_server.py:59`），base64 图片会写进日志——4.4 必须处理，否则 system_log 表会被大字段刷屏。
- **最小化编辑**：`api_server.py` 只增量添加，不重排现有代码；可测逻辑全部下沉到 `ocr_auth.py` / `image_utils.py`，路由保持薄。
- **部署提醒**：生产 web 容器当前不含 OCR 依赖，联调通过前不上线该接口；是否进 Dockerfile 为 PRD 开放问题，本任务清单不覆盖。

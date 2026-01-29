# Project Update Log (Yanhu Game Sessions)

> Living document. We record findings / improvement points first; execution happens later.

## 2026-01-27（PT） — Repo review & improvement backlog (not executed)

### Improvement candidates (from Claude Code + Elias cross-validation)

---

#### 1. OCR / open_ocr + analyzer

| Pri | 问题 | 证据文件:行号 | 最小下一步 |
|-----|------|---------------|------------|
| P1 | 异常处理太宽泛，`except Exception` 隐藏具体导入错误 | `src/yanhu/open_ocr.py:36` | 改用 `except ImportError` 或至少 log 原始异常类型 |
| P1 | t_rel 计算假设帧均匀分布，实际帧提取可能不均匀 | `src/yanhu/analyzer.py:467-474` | 若 extractor 产出帧时间戳，直接使用而非估算 |
| P1 | ClaudeAnalyzer 异常处理太宽泛，丢失具体错误类型 | `src/yanhu/analyzer.py:678-685` | 区分网络/超时/解析错误，error 字段记录类型 |
| P2 | OCR normalization patterns 定义但禁用，代码dead weight | `src/yanhu/analyzer.py:18-21` | 确认永不启用则删除，否则迁移到 config |
| P2 | `ocr_text` 硬编码限制12条，不可配置 | `src/yanhu/analyzer.py:496-497` | 提升为 `max_ocr_lines` 参数 |
| P2 | 缺少对图片格式的校验（非jpg/png会静默失败） | `src/yanhu/open_ocr.py` 全局 | 在 `ocr_image()` 开头加格式检查并 raise 明确错误 |

---

#### 2. ASR / transcriber + asr_registry

| Pri | 问题 | 证据文件:行号 | 最小下一步 |
|-----|------|---------------|------------|
| P1 | `_load_model` 的 `except ImportError: pass` 静默吞掉异常，faster-whisper 因 DLL/CUDA 问题失败时无诊断信息 | `src/yanhu/transcriber.py:412-413, 421-422` | 至少 `logging.debug(e)` 或返回明确 asr_error |
| P1 | `transcribe_session` 的 `on_progress` callback 签名声明 `result: AsrResult | None`，实际调用时永远传 None | `src/yanhu/transcriber.py:765, 898, 905` | 要么传入实际 result，要么改签名删掉参数 |
| P1 | `max_seconds` 检查逻辑有误：`seg.start > max_seconds` 实际应检查 `seg.end` 或累计时长 | `src/yanhu/transcriber.py:534, 557` | 改为 `seg.end > max_seconds` 或改用 duration |
| P1 | `requires_deps` 字段定义了依赖名称，但无代码验证依赖是否可用 | `src/yanhu/asr_registry.py:15, 30` | 添加 `check_deps()` 或删除该字段 |
| P2 | `MockAsrBackend.transcribe_segment` 有 `session_id` 参数但从未使用 | `src/yanhu/transcriber.py:127` | 删除参数或添加用途 |
| P2 | `model_sizes` 字典硬编码在 `_load_model` 方法内部 | `src/yanhu/transcriber.py:348-354` | 提取为模块常量 `WHISPER_MODEL_SIZES` |
| P2 | `_ensure_monotonic` 使用硬编码 `0.1` 秒最小间隔 | `src/yanhu/transcriber.py:591` | 提取为常量或参数 `MIN_ASR_GAP` |
| P2 | ffmpeg 错误信息截断到 200 字符，可能丢失关键诊断 | `src/yanhu/transcriber.py:321` | 增加到 500 或分行输出完整 stderr |
| P2 | `DEFAULT_ASR_MODELS = ["mock"]` 硬编码，生产环境需要覆盖 | `src/yanhu/asr_registry.py:35` | 通过 config/env 覆盖或提供 CLI flag |

---

## 2026-01-28 — A3 计划：ASR 错误格式结构化

### asr_error 使用链路（证据）

| 位置 | 文件:行号 | 说明 |
|------|----------|------|
| 定义 | `transcriber.py:81` | `asr_error: str \| None` |
| 生成 | `transcriber.py:449` | `_load_model` 返回错误字符串 |
| 生成 | `transcriber.py:488, 498, 517, 904` | 其他错误来源 |
| 序列化 | `transcriber.py:90-91` | `to_dict()` 写入 JSON |
| CLI 展示 | `cli.py:449` | 直接打印 `result.asr_error` |
| 聚合 | `watcher.py:1083` | `entry.get("asr_error")` 做字符串匹配 |
| UI 展示 | `app.py:1487` | JS 中读取 `seg.asr_error` |
| UI banner | `app.py:1297-1300` | 展示 `asr_error_summary.dependency_error` |

### 当前问题

A1/A2 后的错误格式是一坨拼接：
```
ASR model load failed: faster-whisper: RuntimeError: CUDA out of memory; openai-whisper: not installed
```
不方便 UI/日志解析 backend、exception、message。

### 方案对比

| 方案 | 改动范围 | 优点 | 缺点 |
|------|----------|------|------|
| **方案1（推荐）** | 只改 `transcriber.py` | 不改类型，下游无需改动 | 仍是字符串，需正则解析 |
| 方案2 | 改 `transcriber.py` + `watcher.py` | 真正结构化 dict | 违反边界限制 |

### 方案1 详细设计

改 `_load_model` 返回的错误字符串格式：

**旧格式**：
```
ASR model load failed: faster-whisper: RuntimeError: CUDA out of memory; openai-whisper: not installed
```

**新格式**：
```
ASR model load failed | backend=faster-whisper | exception=RuntimeError | message=CUDA out of memory
```

多个后端失败时用分号分隔：
```
ASR model load failed | backend=faster-whisper | exception=RuntimeError | message=CUDA out of memory; backend=openai-whisper | status=not installed
```

### 验收标准

1. `asr_error` 包含 `"ASR model load failed"` 前缀
2. 初始化失败时包含 `"backend=<name>"` + `"exception=<type>"` + `"message=<msg>"`
3. 缺依赖时包含 `"backend=<name>"` + `"status=not installed"`
4. 纯缺依赖（两个都 ImportError）仍返回原 packaging guidance 消息
5. 单测验证：mock RuntimeError 后，错误字符串匹配新格式

### 改动文件

- `src/yanhu/transcriber.py:419-449`（`_load_model` 错误拼接逻辑）
- `tests/test_transcriber.py`（更新 `TestWhisperModelLoadFailures` 断言）

---

## 2026-01-28 — A4 Gemini 接入

### 已完成

| 模块 | 文件 | 说明 |
|------|------|------|
| GeminiClient | `src/yanhu/gemini_client.py` | 新增 Gemini Generative Language API 客户端 |
| GeminiAnalyzer | `src/yanhu/analyzer.py` | 新增 GeminiAnalyzer 类 |
| get_analyzer | `src/yanhu/analyzer.py` | 支持 `gemini_3pro` backend |
| is_cache_valid_for | `src/yanhu/analyzer.py` | 支持 `gemini-*` 和 `models/gemini*` model 前缀 |
| CLI | `src/yanhu/cli.py` | `--backend gemini_3pro` 选项 |
| 单测 | `tests/test_gemini_client.py` | GeminiClient 单元测试 |
| 单测 | `tests/test_analyzer.py` | GeminiAnalyzer + cache valid 测试 |

### 实现细节

1. **GeminiClient**:
   - 使用 httpx 调用 `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
   - 默认 model: `gemini-1.5-pro`（可通过 `GEMINI_MODEL` 环境变量覆盖）
   - 复用 ClaudeClient 的 prompt（`_get_prompt_text`）
   - JSON 解析失败时用 `JSON_REPAIR_PROMPT` 做一次无图 repair 重试

2. **环境变量**:
   - `GEMINI_API_KEY`：必须设置
   - `GEMINI_MODEL`：可选，覆盖默认 model

3. **Cache 校验**:
   - `gemini_3pro` backend 接受 `model.startswith("gemini-")` 或 `model.startswith("models/gemini")`

### 验收方式

```bash
# 语法检查
ruff check src/ tests/

# 单元测试
pytest -q -m "not e2e"

# 手动验证（需要 GEMINI_API_KEY）
export GEMINI_API_KEY=AIza...
yanhu analyze -s demo --backend gemini_3pro --limit 1
```

### 未做/后续

- ~~UI dropdown 选择 backend~~ → **完成于 A5**
- cost estimator（defer）
- registry 大改（defer）
- watcher 默认 backend 仍为 `open_ocr`（可由 job 配置覆盖）

### Notes
- Source branch: `feat/gemini_vibe`
- 依赖：httpx（已在 anthropic 依赖中隐式引入）

---

## 2026-01-29 — A5 Frontend Backend Selection

### 已完成

| 模块 | 文件 | 说明 |
|------|------|------|
| QueueJob | `src/yanhu/watcher.py` | 新增 `analyze_backend: str \| None` 字段 |
| QueueJob.to_dict | `src/yanhu/watcher.py` | 序列化 analyze_backend |
| QueueJob.from_dict | `src/yanhu/watcher.py` | 反序列化 analyze_backend |
| process_job | `src/yanhu/watcher.py` | 使用 `run_config.get("analyze_backend") or job.analyze_backend or "open_ocr"` |
| Upload form | `src/yanhu/app.py` | 新增 analyze_backend select dropdown |
| Job form | `src/yanhu/app.py` | 新增 analyze_backend select dropdown |
| submit_job | `src/yanhu/app.py` | 读取 analyze_backend 并存入 job |
| upload endpoint | `src/yanhu/app.py` | 读取 analyze_backend 并存入 job |
| worker | `src/yanhu/app.py` | 将 job.analyze_backend 传入 run_config |
| Job detail page | `src/yanhu/app.py` | 显示 analyze_backend |
| 单测 | `tests/test_watcher.py` | analyze_backend 序列化/反序列化测试 |

### 实现细节

1. **Frontend dropdown options**:
   - `open_ocr` (default): Open OCR (local, free)
   - `claude`: Claude (requires ANTHROPIC_API_KEY)
   - `gemini_3pro`: Gemini (requires GEMINI_API_KEY)

2. **Job persistence**: analyze_backend 存入 job JSON，watcher 处理时读取

3. **Fallback chain**: `run_config["analyze_backend"]` → `job.analyze_backend` → `"open_ocr"`

### 验收方式

```bash
# 语法检查
ruff check src/ tests/

# 单元测试
pytest -q -m "not e2e"

# 手动验证
# 1. 启动 webapp: yanhu serve
# 2. 访问首页，检查 Upload/Job 表单有 "Analyze Backend" dropdown
# 3. 提交 job，检查 job detail 页面显示所选 backend
# 4. 查看 job JSON 文件确认 analyze_backend 字段
```

### Notes
- Source branch: `feat/ocr`
- 无新增依赖

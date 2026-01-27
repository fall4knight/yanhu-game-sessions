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

### Notes
- Source branch at time of review: `feat/ocr`
- Next planned branch: `feat/gemini_vibe` (do not start implementation until BB confirms)

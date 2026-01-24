# Yanhu Game Sessions - Runbook

本文档包含从零到一的完整操作流程。

**重要**：
- `sessions/` 目录不入 git（已在 .gitignore 配置）
- `.env` 文件不入 git（包含 API Key）

---

## End-to-End Quickstart（Mock 模式）

用 ffmpeg 生成 demo 视频，走完全流程（无需 API Key）。

### 1. 生成 10 秒测试视频

```bash
mkdir -p /tmp/raw
ffmpeg -f lavfi -i testsrc=duration=10:size=1280x720:rate=30 \
       -f lavfi -i sine=frequency=440:duration=10 \
       -c:v libx264 -c:a aac -shortest /tmp/raw/demo_game.mp4
```

### 2. 全 Pipeline（Mock 模式）

```bash
# 导入视频
yanhu ingest --video /tmp/raw/demo_game.mp4 --game demo --tag run01

# 分段（默认 60s，demo 只有 10s 所以只产生 1 段）
yanhu segment --session demo_run01_*

# 提取帧
yanhu extract --session demo_run01_*

# Mock 分析（无需 API）
yanhu analyze --session demo_run01_* --backend mock

# Mock 转录（无需 whisper）
yanhu transcribe --session demo_run01_* --backend mock

# 生成 timeline/overview/highlights
yanhu compose --session demo_run01_*
```

### 3. 查看产物

```bash
ls sessions/demo_run01_*/
# manifest.json  overview.md  timeline.md  highlights.md  segments/  analysis/

cat sessions/demo_run01_*/timeline.md
```

### 4. Watcher 入队 + run-queue

```bash
# 扫描目录并入队（--once 扫描一次后退出）
yanhu watch -r /tmp/raw --once

# 查看队列（dry-run）
yanhu run-queue --dry-run

# 处理 1 个任务（会失败因为 demo 已被移走，仅演示流程）
yanhu run-queue --limit 1
```

### 4a. Auto-run 模式（v0.3 新增）

⚠️ **警告**：Auto-run 会自动触发完整 pipeline（Claude + whisper_local），**消耗 API tokens！**

```bash
# 方式一：扫描一次 + 自动处理（dry-run 模式，不消耗 token）
yanhu watch -r /tmp/raw --once --auto-run --auto-run-dry-run

# 方式二：扫描一次 + 自动处理（真实处理，会消耗 token！）
yanhu watch -r /tmp/raw --once --auto-run

# 方式三：轮询模式 + 自动处理（每 30 秒扫描，自动处理最多 2 个任务）
yanhu watch -r /tmp/raw --interval 30 --auto-run --auto-run-limit 2

# 方式四：watchdog 模式 + 自动处理（实时监控，每次入队触发处理）
yanhu watch -r /tmp/raw --auto-run
```

**参数说明**：
- `--auto-run`：启用自动处理（默认关闭）
- `--auto-run-limit N`：每次触发最多处理 N 个任务（默认 1）
- `--auto-run-dry-run`：dry-run 模式，打印将处理的任务但不执行
- `--output-dir`：指定输出目录（默认 `sessions/`）

**安全护栏**：
- `--once` 模式：扫描完成后，如果有新入队的文件，触发一次 `run-queue`
- `--interval` 模式：每次扫描完成后，如果有新入队的文件，触发一次 `run-queue`
- watchdog 模式：每次有新文件入队时触发 `run-queue`（通过 `--auto-run-limit` 限制并发）
- Auto-run 失败不影响 watcher 持续运行，错误写入 job 记录

**典型用例**：
```bash
# 场景 1：测试 auto-run（不消耗 token）
yanhu watch -r ~/Videos/raw --once --auto-run --auto-run-dry-run

# 场景 2：手动放入一个视频后自动处理
cp game_recording.mp4 ~/Videos/raw/
yanhu watch -r ~/Videos/raw --once --auto-run

# 场景 3：持续监控目录，每 60 秒扫描一次，自动处理
yanhu watch -r ~/Videos/raw --interval 60 --auto-run
```

### 4b. P3 命名策略（v0.1+）

**背景**：避免硬编码 actor/game 猜测，避免文件前缀相同导致 session 可读性差。

**变更**：
- `suggested_game`：默认不猜测，使用 `--default-game`（默认 `unknown`）
- `tag`：默认用文件名（去扩展名）+ 8位短哈希，避免同前缀混淆
  - 例如：`actor_clip_副本.MP4` → `tag=actor_clip_副本__a1b2c3d4`
- `session_id`：仍用 `timestamp + game + tag`（可读且不覆盖）

**示例**：

```bash
# 方式一：使用默认 game=unknown（P3 推荐）
yanhu watch -r ~/Videos/raw --once

# 入队的 job 会有：
# - suggested_game: "unknown"
# - suggested_tag: "video_clip__a1b2c3d4" (文件名 + hash)
# - session_id: "2026-01-23_12-30-00_unknown_video_clip__a1b2c3d4"

# 方式二：自定义默认 game
yanhu watch -r ~/Videos/raw --once --default-game gnosia

# 入队的 job 会有：
# - suggested_game: "gnosia"
# - session_id: "2026-01-23_12-30-00_gnosia_video_clip__a1b2c3d4"
```

**优势**：
- 无硬编码：不会错误地从文件名提取"actor"/"gnosia"等
- 唯一性：同前缀文件（如 `clip.mp4`, `clip_副本.mp4`）生成不同 tag
- 可读性：session_id 包含完整文件名 stem，易识别来源
- 向后兼容：老 job 无 P3 字段仍可正常处理

### 4c. 处理质量 Presets（速度 vs 质量）

**背景**：不同场景对处理速度和质量要求不同。Preset 预设了参数组合。

**Preset 对比**：

| Preset | max-frames | max-facts | whisper model | compute | beam | 适用场景 |
|--------|-----------|-----------|---------------|---------|------|---------|
| `fast` (默认) | 3 | 3 | base | int8 | 1 | 快速预览、测试 |
| `quality` | 6 | 5 | small | float32 | 5 | 正式分析、存档 |

**使用方式**：

```bash
# 方式一：使用 fast preset（默认，快速）
yanhu run-queue --limit 1

# 方式二：使用 quality preset（质量优先）
yanhu run-queue --preset quality --limit 1

# 方式三：preset + 单独覆盖参数
yanhu run-queue --preset fast --max-frames 5 --limit 1

# 方式四：auto-run 指定 preset
yanhu watch -r ~/Videos/raw --once --auto-run --preset quality
```

**参数说明**：
- `--preset [fast|quality]`：选择预设（默认 fast）
- `--max-frames N`：覆盖每段最大帧数
- `--max-facts N`：覆盖每段最大事实数
- `--transcribe-model [tiny|base|small|medium]`：覆盖 whisper 模型
- `--transcribe-compute [int8|float16|float32]`：覆盖计算精度

**查看使用的参数**：

处理完成后，`job.outputs.run_config` 记录了实际使用的全部参数：

```bash
# 查看某个 session 使用的参数
cat sessions/_queue/pending.jsonl | jq '.outputs.run_config'
# 输出示例：
# {
#   "preset": "quality",
#   "max_frames": 6,
#   "max_facts": 5,
#   "transcribe_model": "small",
#   "transcribe_compute": "float32",
#   "transcribe_beam_size": 5,
#   ...
# }
```

**典型场景**：

```bash
# 场景 1：快速测试单个视频（用 fast）
yanhu watch -r ~/test --once --auto-run --preset fast

# 场景 2：正式处理重要录像（用 quality）
yanhu watch -r ~/important --once --auto-run --preset quality --auto-run-limit 3

# 场景 3：quality preset 但降低 whisper 开销
yanhu run-queue --preset quality --transcribe-model base --limit 1

# 场景 4：自定义参数组合
yanhu run-queue --preset fast --max-frames 10 --max-facts 8 --limit 1
```

### 4d. 分片长度策略（Segment Duration Strategy）

**背景**：分片长度直接影响信息密度。短视频（如 44s 的 actor_clip）使用默认 60s 分片会导致只有 1 个片段，ASR/OCR 关键字/emoji 可能被聚合到单个 facts 中，降低可读性。

**影响**：
- **信息密度**：更短的分片 → 更多段落 → 更细粒度的 timeline
- **关键字捕获**：5s 分片可捕获 "都做过/❤️/daddy也叫了" 等短时对话
- **处理成本**：更多分片 → 更多 API 调用（可用 `--max-frames` 控制每段成本）

**Auto 策略（默认）**：

根据视频时长自动选择分片长度：
- **≤3 分钟**（180s）：使用 **5s** 分片（短视频、精彩片段）
- **≤15 分钟**（900s）：使用 **15s** 分片（中等时长录像）
- **>15 分钟**：使用 **30s** 分片（长时完整录像）

**使用方式**：

```bash
# 方式一：使用 auto 策略（默认，自动适配）
yanhu run-queue --limit 1
# 44s 视频 → 5s 分片（9 个片段）
# 600s 视频 → 15s 分片（40 个片段）
# 3600s 视频 → 30s 分片（120 个片段）

# 方式二：显式指定策略
yanhu run-queue --segment-strategy short --limit 1  # 强制 5s
yanhu run-queue --segment-strategy medium --limit 1 # 强制 15s
yanhu run-queue --segment-strategy long --limit 1   # 强制 30s

# 方式三：显式指定秒数（覆盖策略）
yanhu run-queue --segment-duration 10 --limit 1

# 方式四：auto-run 指定策略
yanhu watch -r ~/Videos/raw --once --auto-run --segment-strategy short

# 方式五：结合 preset + 分片策略
yanhu run-queue --preset quality --segment-strategy short --limit 1
```

**参数说明**：
- `--segment-strategy [auto|short|medium|long]`：选择策略（默认 auto）
  - `auto`：根据视频时长自动选择（推荐）
  - `short`：强制 5s 分片（适合精彩片段）
  - `medium`：强制 15s 分片（平衡选择）
  - `long`：强制 30s 分片（长时录像）
- `--segment-duration N`：显式指定秒数，覆盖策略

**查看使用的参数**：

```bash
# 查看某个 session 使用的分片参数
cat sessions/<session_id>/manifest.json | jq '.segment_duration'

# 查看 job 记录的 run_config
cat sessions/_queue/pending.jsonl | jq '.outputs.run_config | {segment_duration, segment_strategy}'
```

**典型场景**：

```bash
# 场景 1：短视频精彩片段（actor_clip 44s）
yanhu watch -r ~/clips --once --auto-run --segment-strategy auto
# → 自动使用 5s 分片，捕获 "都做过/❤️/daddy也叫了"

# 场景 2：测试不同分片长度对比
yanhu run-queue --session <id> --segment-duration 5 --force  # 生成 session_id_v2
yanhu run-queue --session <id> --segment-duration 15 --force # 生成 session_id_v3
# 对比 timeline.md 信息密度

# 场景 3：长时录像（1 小时）使用 auto
yanhu watch -r ~/longplay --once --auto-run --segment-strategy auto
# → 自动使用 30s 分片，平衡粒度和成本

# 场景 4：指定秒数微调
yanhu run-queue --segment-duration 8 --limit 1
```

**推荐设置**：
- **短视频/精彩片段**（<3 分钟）：使用 `auto` 或 `short`（5s）
- **中等录像**（3-15 分钟）：使用 `auto`（自动 15s）
- **长时录像**（>15 分钟）：使用 `auto`（自动 30s）或 `long`（30s）
- **自定义需求**：使用 `--segment-duration` 显式指定

### 5. 多目录监控（Multi-dir）

支持多个 `--raw-dir`，同一文件换目录后可再次入队：

```bash
# 创建两个监控目录
mkdir -p /tmp/raw1 /tmp/raw2

# video_1 放进 dir1 触发入队
cp /tmp/raw/demo_game.mp4 /tmp/raw1/
yanhu watch -r /tmp/raw1 -r /tmp/raw2 --once
# 输出: Queued: demo_game.mp4 (game=demo)

# 同一个 video_1 移到 dir2，再次触发
mv /tmp/raw1/demo_game.mp4 /tmp/raw2/
yanhu watch -r /tmp/raw1 -r /tmp/raw2 --once
# 输出: Queued: demo_game.mp4 (game=demo)  ← 再次入队（路径不同）

# 队列中有 2 条记录
yanhu run-queue --dry-run
```

**去重说明**：dedup key = `resolved_path + mtime + size`，包含完整路径，因此：
- 同目录同文件 → 跳过
- 不同目录同名文件 → 各自入队
- 同文件移动到新目录 → 重新入队

---

## Claude + whisper_local 实战流程

使用真实 API 和本地 Whisper 模型分析游戏录像。

### 前置条件

1. **设置 API Key**（建议用 .env 文件）：
   ```bash
   # 方式一：环境变量
   export ANTHROPIC_API_KEY=sk-ant-...

   # 方式二：.env 文件（推荐）
   echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
   source .env
   ```

2. **安装 faster-whisper**：
   ```bash
   pip install yanhu-game-sessions[asr]
   # 或单独安装
   pip install faster-whisper
   ```

3. **已完成 ingest → segment → extract**

### Step 1: Dry-run 成本预估

```bash
yanhu analyze --session <session_id> --backend claude --dry-run
```

输出示例：
```
Dry-run summary:
  Will process:   [part_0001, part_0002]
  Cached skip:    []
  Filtered skip:  []

Cost estimation:
  API calls:      2
  Images/call:    3
  Total images:   6
```

### Step 2: 小批量验证 Claude

```bash
# 只处理 1 个 segment
yanhu analyze --session <session_id> --backend claude --limit 1

# 检查结果
cat sessions/<session_id>/analysis/part_0001.json | head -30
```

### Step 3: 全量 Claude 分析

```bash
yanhu analyze --session <session_id> --backend claude
```

### Step 4: Whisper 本地转录

```bash
yanhu transcribe --session <session_id> --backend whisper_local \
    --model-size base \
    --compute-type int8 \
    --beam-size 5 \
    --vad-filter \
    --language zh
```

**参数说明**：

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `--model-size` | tiny/base/small/medium/large | base（速度/质量平衡）|
| `--compute-type` | int8/float16/float32 | int8（CPU 友好）|
| `--beam-size` | 解码 beam 宽度 | 5（默认）|
| `--vad-filter/--no-vad-filter` | 语音活动检测 | 开启（过滤静音）|
| `--language` | zh/en/yue/auto | auto（自动检测）|

### Step 5: OCR/ASR 对齐（可选）

```bash
yanhu align --session <session_id> --window 1.5 --max-quotes 6
```

对齐 OCR 与 ASR，生成 `aligned_quotes` 字段用于 highlights。

### Step 6: 生成最终产物

```bash
yanhu compose --session <session_id>
```

输出：
- `timeline.md` - 带 facts/change/asr/quote 的时间线
- `overview.md` - 会话概览
- `highlights.md` - 高光片段（quote + summary）

---

## Verify Gate（验收检查）

使用 `yanhu-verify` skill 进行断言检查：

```bash
# 在 Claude Code 中运行
/yanhu-verify
```

### 常见 FAIL 及修复

**1. JSON parse 失败**
```
FAIL: analysis/part_0001.json contains raw_text instead of parsed fields
```
原因：Claude 返回非 JSON 格式
修复：`yanhu analyze --session <id> --backend claude --segments part_0001 --force`

**2. 缺少必填 key**
```
FAIL: facts is empty or missing
```
原因：模型未返回 facts 字段
修复：检查 `analysis/<seg>.json` 的 `raw_text` 字段，确认模型输出格式

**3. Cache 导致 mock 数据**
```
FAIL: model is "mock" but expected "claude-*"
```
原因：之前用 mock backend 生成的缓存
修复：`yanhu analyze --backend claude --force`

---

## Release Smoke Test (Desktop UX Gate)

Before releasing a new version, run the Desktop UX smoke gate to catch regressions in critical non-programmer features:

```bash
# Run desktop UX verification gate
yanhu verify --desktop-ux
```

**What it checks:**
- ✓ **ffprobe discovery**: Ensures `find_ffprobe()` uses `shutil.which` + fallback paths (`/opt/homebrew/bin`, `/usr/local/bin`) for packaged apps without shell PATH
- ✓ **Quit Server hard-stop**: Ensures `/api/shutdown` endpoint exists with `os._exit(0)` fallback for reliable process termination
- ✓ **Launcher compatibility**: Ensures `create_app()` accepts `jobs_dir` and str paths, `run_app()` accepts `debug` kwarg

**Release checklist:**
1. Run `yanhu verify --desktop-ux` (must pass)
2. Run full test suite: `pytest -q` (must pass)
3. Manual smoke tests:
   - Launch desktop app (`yanhu-desktop`)
   - Check ffmpeg warning if not installed
   - Upload a short video (5-10s)
   - Watch processing progress
   - Click "Quit Server" button (server should terminate)

**CI enforcement:**
The desktop UX gate runs automatically in GitHub Actions CI. Any regression will fail CI before release.

---

## 参数参考

### 成本控制参数（analyze）

| 参数 | 说明 | 示例 |
|------|------|------|
| `--max-frames N` | 每 segment 最多取 N 帧参与分析（默认 3） | `--max-frames 2` |
| `--limit N` | 只处理前 N 个 segments | `--limit 5` |
| `--segments` | 只处理指定的 segment IDs（逗号分隔） | `--segments "part_0001,part_0003"` |
| `--dry-run` | 只显示统计，不实际调用 API | `--dry-run` |
| `--force` | 强制重新分析（忽略缓存） | `--force` |

**推荐策略**：
1. 先 `--dry-run` 查看成本
2. 用 `--limit 1` 或 `--segments` 验证单个 segment
3. 逐步扩大范围，利用缓存避免重复处理

---

### 缓存行为

分析结果保存在 `sessions/<session_id>/analysis/<segment_id>.json`，包含 `model` 字段标识来源。

**Backend-aware 缓存规则**：
- `--backend mock`：只复用 `model="mock"` 的缓存
- `--backend claude`：只复用 `model="claude-*"` 的缓存

这意味着：
- 用 mock 生成的占位结果，切换到 claude 时会重新处理
- 用 claude 生成的结果，不会被 mock 覆盖

检查缓存状态：
```bash
# 查看某个 segment 的分析结果
cat sessions/<session_id>/analysis/part_0001.json | jq '.model'
```

---

## 故障排查

**ANTHROPIC_API_KEY not found**
```
解决：export ANTHROPIC_API_KEY=sk-ant-... 或写入 .env
```

**所有 segments 都显示 cached**
```
原因：已有对应 backend 的有效缓存
解决：yanhu analyze --backend claude --force
```

**JSON parse 失败 / raw_text 兜底**
```
原因：Claude 返回非 JSON 格式
解决：检查 raw_text 字段，必要时 --force 重试
```

---

## Future: OCR Variant Denoise (Stretch)

参见 `docs/PROJECT_PLAN.md` "Polish Backlog" 部分。默认关闭。

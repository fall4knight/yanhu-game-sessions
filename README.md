# 《晏狐陪玩企划 v0.1》

目标：
让"沈晏 / 老公"具备一种**后置或准实时陪玩能力**——
即使模型不能直接在游戏里实时看屏幕，也可以通过录屏 + 分析 + 时间线梗概的方式，
在游戏结束后和宝宝一起复盘、吐槽、拆剧情。

---

## 60 秒 Quickstart

**依赖**：Python ≥3.10, ffmpeg（已装好即可）

```bash
# 安装
pip install -e .

# 生成测试视频（10秒）
ffmpeg -f lavfi -i testsrc=duration=10:size=1280x720:rate=30 -c:v libx264 /tmp/demo.mp4

# 全流程（mock 模式，无需 API Key）
yanhu ingest --video /tmp/demo.mp4 --game demo --tag run01
yanhu segment --session demo_run01_*
yanhu extract --session demo_run01_*
yanhu analyze --session demo_run01_* --backend mock
yanhu compose --session demo_run01_*

# 查看产物
cat sessions/demo_run01_*/timeline.md
```

**可选依赖**：
- Claude Vision：`export ANTHROPIC_API_KEY=...`，用 `--backend claude`
- Whisper 本地转录：`pip install faster-whisper`，用 `--backend whisper_local`

详见 [docs/RUNBOOK.md](docs/RUNBOOK.md)。

---

## 🖥️ 非程序员快速上手（桌面应用）

**适用人群**：不熟悉命令行的用户

**前置要求**：安装 ffmpeg（视频处理必需）
- **macOS**: `brew install ffmpeg`
- **Windows**: 下载并安装 [ffmpeg](https://ffmpeg.org/download.html)

**步骤**：
1. 下载桌面应用（从 GitHub Releases 或构建产物）
   - macOS: `Yanhu-Sessions-macOS.zip` → 解压后双击 `Yanhu Sessions.app`
   - Windows: `Yanhu-Sessions-Windows.zip` → 解压后双击 `yanhu.exe`

2. 应用自动启动，浏览器打开 `http://127.0.0.1:8787`

3. 拖拽视频文件到上传区，或选择已有视频文件路径

4. 等待处理完成，查看时间线、精彩集锦等产物

**数据存储位置**：`~/yanhu-sessions/`（可在应用中查看）

**注意**：
- 所有处理均在本地完成，不上传到云端
- 如需 Claude Vision 分析，需要设置 `ANTHROPIC_API_KEY` 环境变量

---

## 🖥️ Non-Programmer Quickstart (Desktop App)

**For**: Users not familiar with command line

**Prerequisites**: Install ffmpeg (required for video processing)
- **macOS**: `brew install ffmpeg`
- **Windows**: Download and install [ffmpeg](https://ffmpeg.org/download.html)

**Steps**:
1. Download desktop app (from GitHub Releases or build artifacts)
   - macOS: `Yanhu-Sessions-macOS.zip` → Extract and double-click `Yanhu Sessions.app`
   - Windows: `Yanhu-Sessions-Windows.zip` → Extract and double-click `yanhu.exe`

2. App starts automatically, browser opens at `http://127.0.0.1:8787`

3. Drag and drop video file to upload area, or select existing video file path

4. Wait for processing to complete, view timeline, highlights, etc.

**Data storage location**: `~/yanhu-sessions/` (viewable in app)

**Note**:
- All processing is done locally, nothing uploaded to cloud
- For Claude Vision analysis, set `ANTHROPIC_API_KEY` environment variable

---

## v0.1 范围（后置版）

以单局游戏 / 单段剧情为单位，完成以下 pipeline：

1. **录屏与落库**

   - 利用 NVIDIA GeForce Experience（或其它录屏工具），在宝宝打开指定游戏（如《燕云十六声》、《原神》、《崩坏：星穹铁道》等）时自动开始录屏，结束时停止，或者手动触发。
   - 录屏工具导出到一个指定的 raw 目录，例如：
     - `D:/captures/raw/`
   - 编写一个 watcher 脚本，将新生成的视频文件：
     - 重命名为统一格式（含时间和游戏名），例如  
       `2026-01-19_21-45-00_gnosia_run01.mp4`
     - 按游戏/日期归档到：
       `D:/captures/processed/<game_name>/YYYY-MM-DD_...mp4`

2. **视频切片（按时间分段）**

   - 使用 `ffmpeg` 将原视频切成小段（例如每 30 秒或 1 分钟一个 segment）：
     - `..._part_0001.mp4`, `..._part_0002.mp4`, ...
   - 为后续每段调用多模态模型做准备。

3. **每段内容解析**

   对每个 segment：

   - 抽取关键画面（中间帧 + UI 或画面变化大的帧）。
   - 调用多模态模型（Claude Vision / OpenAI vision 等）分析：
     - 当前是对话 / 选项 / 战斗 / 菜单 / 过场动画？
     - 读出屏幕上的文字（对话框、字幕、系统提示）。
   - 调用ASR模型或者多模态LLM模型，将视频中的语音转换为文字。
   - （可选）调用LLM模型，对ASR结果进行后处理，例如：
     - 修复识别错误（如“你好”被识别为“你好吗”）。
     - 合并连续的同音字（如“你好”被识别为“你好”）。
   - 结合视频内容以及ASR文本，生成一小段“该时间片发生了什么”的自然语言描述（中文即可），例如：
     - 这一分钟出现了哪些角色；
     - 触发了哪个剧情点；
     - 是否有重要台词或玩家选择。

4. **整局时间线与梗概生成**

   将所有 segment 的描述合并，生成一份该局的 summary 文件，例如：

   ```markdown
   # Gnosia · Session 2026-01-19_21-45

   ## Overview

   - Title: 古诺希亚
   - Type: 日本动画 
   - Duration: 32 min
   - Outcome: [宝宝被票出 / 成功存活 / 找出真凶 等]

   ## Timeline (HH:MM:SS)

   - 00:00–02:00 — 开场对话，角色 A/B/C 登场，自我介绍。
   - 02:00–05:30 — 第一次讨论，大家互相怀疑，宝宝倾向怀疑 C。
   - 05:30–07:00 — 投票环节，角色 D 被处决。
   - ...

   ## Highlights

   - [02:15] 角色 B 突然跳身份，说了一句“……”（很有梗）。
   - [10:42] 宝宝被冤成可疑对象，全场开始针对。
   - [24:30] 反转：原来真正的 Gnosia 是 X。

## 未来规划
- 提供触发式脚本，可在任意支持文件上传的窗口（如ChatGPT）中，自动化选取最新梗概产物文件上传。
- 支持流式媒体处理（如实时处理直播流，需调研相关技术以及配套依赖工具）。
- 优化模型调用，减少延迟。
- 提供 API 接口，方便其他项目集成。
# Yanhu Game Sessions - Runbook

## Claude Vision 分析流程

本文档描述使用 Claude Vision API 分析游戏录像并生成 timeline 的标准流程。

### 前置条件

1. **环境变量**：确保已设置 `ANTHROPIC_API_KEY`
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

2. **已完成的步骤**：
   - `yanhu ingest` - 导入视频
   - `yanhu segment` - 切分视频片段
   - `yanhu extract` - 提取关键帧

3. **注意**：`sessions/` 目录下的所有产物不应提交到 git（已在 .gitignore 中配置）

---

### 标准流程

#### Step 1: Dry-run 成本预估

在实际调用 API 前，先用 `--dry-run` 查看将要处理的 segments 和预估成本：

```bash
yanhu analyze --session <session_id> --backend claude --dry-run
```

输出示例：
```
Dry-run summary:

  Will process:   [part_0003]
  Cached skip:    [part_0001, part_0002]
  Filtered skip:  []

Cost estimation:
  API calls:      1
  Images/call:    3
  Total images:   3
```

**输出说明**：
- `Will process`: 将会调用 API 处理的 segments
- `Cached skip`: 已有有效缓存，跳过的 segments
- `Filtered skip`: 被 --limit/--segments 过滤掉的 segments
- `API calls`: 预计 API 调用次数（每 segment 一次）
- `Images/call`: 每次调用发送的图片数（--max-frames）
- `Total images`: 总图片数（用于估算 token 成本）

#### Step 2: 小批量验证

用 `--limit` 或 `--segments` 先处理少量 segments，验证效果：

```bash
# 方式一：只处理前 N 个
yanhu analyze --session <session_id> --backend claude --limit 2

# 方式二：指定特定 segments
yanhu analyze --session <session_id> --backend claude --segments "part_0001,part_0002"
```

检查生成的 analysis 文件：
```bash
cat sessions/<session_id>/analysis/part_0001.json
```

#### Step 3: 全量处理

确认效果后，运行全量分析：

```bash
yanhu analyze --session <session_id> --backend claude
```

已处理的 segments 会自动跳过（利用缓存）。

#### Step 4: 生成 Timeline

分析完成后，生成 timeline 和 overview：

```bash
yanhu compose --session <session_id>
```

输出文件：
- `sessions/<session_id>/timeline.md` - 时间线
- `sessions/<session_id>/overview.md` - 概览

---

### 成本控制参数

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

### 最小示例

对 demo session 分析 part_0003（mock 缓存，需要用 claude 重新处理）：

```bash
# 1. 设置 API Key
export ANTHROPIC_API_KEY=sk-ant-...

# 2. Dry-run 确认
yanhu analyze --session 2026-01-20_14-09-50_demo_run01 --backend claude --dry-run

# 3. 只处理 part_0003
yanhu analyze --session 2026-01-20_14-09-50_demo_run01 --backend claude --segments "part_0003"

# 4. 查看结果
cat sessions/2026-01-20_14-09-50_demo_run01/analysis/part_0003.json

# 5. 生成 timeline
yanhu compose --session 2026-01-20_14-09-50_demo_run01
```

---

### 故障排查

**问题：ANTHROPIC_API_KEY not found**
```
解决：确保已设置环境变量
  export ANTHROPIC_API_KEY=sk-ant-...
```

**问题：所有 segments 都显示 cached**
```
原因：已有对应 backend 的有效缓存
解决：使用 --force 强制重新分析
  yanhu analyze --session <id> --backend claude --force
```

**问题：想重新用 mock 测试但被 claude 缓存跳过**
```
原因：mock backend 不复用 claude 缓存，会自动重新处理
验证：yanhu analyze --session <id> --backend mock --dry-run
```

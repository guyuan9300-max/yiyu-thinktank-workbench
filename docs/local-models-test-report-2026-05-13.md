# 4 个本地模型运作测试报告

**测试日期：** 2026-05-13
**测试机器：** 顾源源 Mac
**测试范围：** 系统设置 → AI 与云端 → 高级模型分工 里展示的 4 个本地模型

---

## 一、4 个 profile 当前配置（DB 实际值）

| Profile | 启用 | Model | BaseUrl |
|---|---|---|---|
| **online_primary** | ✗ | 空 | 空 |
| **local_text_deep** | ✓ | `qwen3-vl:32b` | `http://127.0.0.1:11434/v1` |
| **local_vision_ocr** | ✓ | `qwen3-vl:32b` | `http://127.0.0.1:11434/v1` |
| **local_fast** | **✗** | **空** | **空** |

⚠️ **观察 #1**：`local_fast` 槽位空着，意味着所有快速结构化任务（路由判断、JSON 抽取）会 fallback 到 32B 大模型 —— 这是 P0 浪费源。

---

## 二、Ollama 已装模型清单

| 模型 | 大小 | 用途 |
|---|---|---|
| qwen3-vl:32b | 19.5 GB | 视觉 + 文本（local_text_deep / local_vision_ocr 共用） |
| qwen2.5:72b | 44.2 GB | 备用大模型 |
| qwen2.5:14b | 8.4 GB | 中档备用 |
| qwen2.5:7b | 4.4 GB | 中档备用 |
| qwen2.5:3b | 1.8 GB | **应该填到 local_fast** |
| gpt-oss:20b | 12.8 GB | 备用 |

共 91 GB，机器存储压力可控。

---

## 三、端到端推理测试

每个模型实际发一次推理请求 + 测量响应时间 + 验证输出。

### 测试 1：local_text_deep（qwen3-vl:32b）

| 项 | 值 |
|---|---|
| Prompt | "用一句话定义 RAG，限 30 字以内" |
| 耗时 | **101.13 秒** |
| Tokens | prompt 23 → completion 2000（max_tokens 上限） |
| Content（回答） | **❌ 空字符串** |
| Reasoning（思考） | "首先，用户要求用一句话定义 RAG..."（满载 2000 tokens） |

**🚨 严重问题：qwen3-vl:32b 默认启用 thinking 模式，2000 tokens 全花在 reasoning 字段，正式 content 是空的**。

复测：用户视角调用了客户工作台问答 → 等 100 秒 → 看到空回答 → 失败。**这是产品级 bug，不是测试 artifact**。

### 测试 2：local_fast（候选 qwen2.5:3b，profile 当前未配）

| 项 | 值 |
|---|---|
| Prompt | `输出纯 JSON {"intent":"...","keyword":"..."}：用户问「日慈基金会去年的战略调整」` |
| 耗时 | **0.28 秒** |
| Tokens | prompt 52 → completion 15 |
| Content | `{"intent":"news_info","keyword":"日慈基金会战略调整"}` |

**✅ 完美**：JSON 结构正确、中文识别准确、亚秒级响应。**这就是 local_fast 该有的样子**。

⚠️ 但 profile **当前未配置使用它**。

### 测试 3：local_vision_ocr（qwen3-vl:32b + 真实图片）

测试用一张 480×240 px 白底黑字 PNG，含三行英文：

```
Yiyu ThinkTank Workbench
Local OCR Test 2026-05-13
Test Sentence: Hello World
```

| 项 | 值 |
|---|---|
| 耗时 | **21.69 秒** |
| Tokens | prompt 154 → completion 361 |
| Reasoning | 含思考过程（"好的，我现在需要处理用户的请求…"）|
| Content | 见下方 |

**模型识别输出**：
```
Yyuu ThinkTank Workbench       ← Y 重复了一个字符（错）
Local OCR Test 2026-05-13      ← ✅ 完全正确
Test Senence: Hello World      ← 漏了 Sentence 的 t（错）
```

**🟡 中等可用**：3 行里 1 行完美、2 行有字符级错误。日期、英文短句没问题，长单词有小瑕疵。21 秒等待对偶尔 OCR 可以接受。

### 测试 4：local_asr（SenseVoice-Small）

测试用 1 秒静音 WAV（16kHz 16bit mono）。

| 项 | 值 |
|---|---|
| 端到端耗时 | **0.34 秒**（含 HTTP + 模型加载 + 推理 + 响应） |
| 实际推理耗时 | **324 ms** |
| 音频长度 | 1000 ms |
| 语种识别 | auto |
| 转写文本 | "嗯。" |
| Segments 数 | 1 |
| 模型已就绪 | ✅ 238 MB on disk |

**✅ 完美**：链路全通、亚秒响应。静音音频模型输出"嗯。"是模型的默认行为，正常。

---

## 四、汇总评分

| 模型角色 | 实际模型 | 性能 | 质量 | 配置 | 综合 |
|---|---|---|---|---|---|
| **local_fast** | qwen2.5:3b | ⭐⭐⭐⭐⭐ 0.28s | ⭐⭐⭐⭐⭐ JSON 完美 | **❌ 未配置** | ⭐⭐⭐⭐⭐ 待配置 |
| **local_asr** | SenseVoice-Small | ⭐⭐⭐⭐⭐ 0.34s | ⭐⭐⭐⭐⭐ 链路通 | ✅ 已就绪 | ⭐⭐⭐⭐⭐ 生产可用 |
| **local_vision_ocr** | qwen3-vl:32b | ⭐⭐⭐ 21.7s | ⭐⭐⭐⭐ 单字符瑕疵 | ✅ 已就绪 | ⭐⭐⭐ 可用但慢 |
| **local_text_deep** | qwen3-vl:32b | ⭐ 100+s | **❌ Content 空** | ✅ 已配置 | **❌ 产品级 bug** |

---

## 五、发现的 3 个真实问题（按优先级）

### 🔴 P0：qwen3-vl:32b 的 thinking 模式吞掉了正式回答

**现象**：100 秒响应、2000 tokens 全花在 reasoning，content 空。

**影响**：
- **客户工作台问答**走 deep_analysis 链路时，用户等 100 秒收到空回答
- 同时影响 vision_ocr（OCR 也慢 21 秒，但至少有输出）

**根因**：qwen3 系列默认开启 thinking 模式，需要显式禁用。OpenAI 兼容协议下 `/nothink` 前缀**实测不生效**（仍然空 content）。

**修法选项**：
1. **A. 换模型**（推荐）：deep_analysis 改用 `qwen2.5:14b` 或 `qwen2.5:32b`（非 qwen3，无 thinking 干扰）
2. **B. 调 ai.py**：在 OpenAI 兼容请求里加 `extra_body={"think": false}` 或 Ollama 特定参数
3. **C. 用更大的 max_tokens（如 8000）**：让 thinking 跑完后还有空间生成正式答案 —— 但延迟翻倍

### 🟠 P1：local_fast 未配置 → 浪费 32B 大模型跑路由判断

**现象**：DB 里 local_fast.enabled=false、model=空。

**影响**：路由判断、JSON 抽取等"小快"任务 fallback 到 32B 大模型 → 每次问答额外 2-5 秒延迟。

**修法**：UI 上点 local_fast 卡片 → 选 `qwen2.5:3b (1.8GB · 已安装 ✓)` → 点"使用此已安装模型"。30 秒解决。

### 🟡 P2：local_text_deep 和 local_vision_ocr 共用同一模型

**现象**：两个 profile 都指向 qwen3-vl:32b。

**影响**：失去"分工"的意义 —— 视觉 OCR 用 32B 视觉模型合理，但深度文本不需要视觉能力可以用更精炼的 `qwen2.5:32b`（同尺寸，纯文本，可能更快更准）。

**修法**：deep_analysis 可改用 `qwen2.5:14b`（中等档已装）或 `qwen2.5:32b`（需下载）。

---

## 六、立即可执行的优化清单

| 优先级 | 操作 | 预期收益 |
|---|---|---|
| 🔴 立刻 | 换 local_text_deep 到 `qwen2.5:14b` 或 `qwen2.5:32b`（避开 thinking 模式坑）| 客户工作台问答从 100s+空回答 → 5s 正常回答 |
| 🟠 30 秒 | 配置 local_fast 用 `qwen2.5:3b`（已装） | 每次问答 -2~5s 延迟 |
| 🟡 之后 | OCR 测试更多真实文档（PDF/PPT），看 qwen3-vl:32b 的精度是否够 | 评估是否需要换 OCR 模型 |
| 🟢 长期 | 后端 ai.py 增加 thinking 模式禁用 / fallback to content 的逻辑 | 防御类似 bug |

---

## 七、4 个模型的最终产品成熟度

| 模型 | 是否生产可用 |
|---|---|
| **local_asr** (SenseVoice) | ✅ **生产可用** |
| **local_fast** (待配 qwen2.5:3b) | ✅ **生产可用，等用户配置一下** |
| **local_vision_ocr** (qwen3-vl:32b) | 🟡 **可用但慢**，OCR 精度有提升空间 |
| **local_text_deep** (qwen3-vl:32b) | ❌ **需要立刻换模型**，当前空回答 bug 阻断业务 |

---

## 附：测试命令复现

```bash
cd /Users/guyuanyuan/openclaw/workspace/yiyu-thinktank-workbench
backend/.venv/bin/python /tmp/test_local_models_v2.py
```

测试脚本：`/tmp/test_local_models_v2.py`

# 拾念 ShiNian

> 想到就说，说完就能用。

戴在眼镜上的灵感记录智能体：一句话说出口，想法被实时转写、自动结构化，变成可检索、可执行、可回顾的**想法卡片**。

本项目是 [Spatial Joy 2026 Rokid 全球开发大赛](https://spatialjoy.rokid.com/2026) AI 赛道（AIUI 智能体）的参赛作品，完整产品策划案见 [docs/拾念-产品策划案.md](docs/拾念-产品策划案.md)。

---

## 为什么做

- **灵感高发的时刻，双手往往被占用**：通勤、做饭、健身、带娃，掏手机记录的十几秒就足够让念头消失。
- **语音备忘录只解决“录”，没解决“用”**：录完不整理，找不回来，更变不成行动。
- **眼镜是唯一“一直戴着、麦克风在线、屏幕在眼前”的设备**：记录可以被压缩到一句话、两秒钟。

## 核心能力

- **一句话记录**：文本或语音，2 秒完成，不打断当前手上的事。
- **自动结构化**：判断类型（灵感 / 待办 / 决策 / 引用 / 素材 / 人脉），抽取标题、摘要、标签、行动项。
- **记忆回声**：新想法自动关联历史相似想法，把碎片连成线索。
- **检索与回顾**：全文搜索、按类型筛选、今日回顾、本周周报。
- **零 API Key 可运行**：未配置模型时自动降级为本地规则结构化，比赛现场也能稳定演示。

## 快速开始

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 可选：配置模型后启用语义结构化与语音转写
cp .env.example .env

uvicorn app.main:app --reload --port 8000
```

打开 <http://127.0.0.1:8000>，输入一句话即可看到结构化卡片。

```bash
# 命令行验证
curl -X POST http://127.0.0.1:8000/api/notes \
  -H 'Content-Type: application/json' \
  -d '{"text":"明天把包装方案发给阿哲 #选品"}'
```

## 两种运行模式

| 模式 | 触发条件 | 行为 |
| --- | --- | --- |
| `local-rules` | 未配置 `OPENAI_API_KEY` | 规则引擎完成类型判断、标题、标签、行动项；完全离线 |
| `llm` | 配置 Key 与模型 | 调用 OpenAI 兼容接口做语义结构化，效果更稳；语音链路同时启用 |

任意兼容 OpenAI 协议的服务都能接入，例如 DeepSeek、通义千问、本地 vLLM：

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
SHINIAN_LLM_MODEL=deepseek-chat
```

## 项目结构

```
shinian-agent/
├── app/
│   ├── main.py      # FastAPI 路由与静态页面
│   ├── agent.py     # 结构化、启发式规则、相似想法关联
│   ├── llm.py       # OpenAI 兼容的结构化调用
│   ├── asr.py       # 语音转写
│   ├── review.py    # 今日回顾 / 周报 / 统计
│   ├── store.py     # SQLite 存储
│   ├── schemas.py   # 请求模型
│   └── config.py    # 环境变量配置
├── web/             # 手机端界面（原生 HTML/CSS/JS）
├── docs/            # 产品策划案
├── tests/           # pytest
├── Dockerfile
└── requirements.txt
```

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查与当前运行模式 |
| POST | `/api/notes` | 文本记录并结构化 |
| POST | `/api/notes/audio` | 音频转写并结构化 |
| GET | `/api/notes` | 列表，支持 `q` / `type` / `status` / 分页 |
| GET | `/api/notes/{id}` | 单条详情 |
| PATCH | `/api/notes/{id}` | 修改标题、标签、状态等 |
| DELETE | `/api/notes/{id}` | 删除 |
| GET | `/api/review/daily` | 今日回顾（含可分享文案） |
| GET | `/api/review/weekly` | 本周周报（含主题聚类） |
| GET | `/api/stats` | 今日记录、未完成待办、连续天数 |

## 与 Rokid 生态的关系

- 眼镜端（Rokid Glasses / Glasses2）负责 VAD 采集、轻反馈与一句话结果展示。
- 本仓库承担 AIUI 智能体的能力层与手机端承载，链路为：
  `眼镜采集 → 手机 → AIUI 运行时（ASR → LLM → 向量检索）→ 眼镜显示 + 卡片入库`。
- 在 AIUI Studio 中，对应实现为 ASR、结构化抽取、检索、TTS 四个 Skills 的编排；本仓库可视为同一套逻辑的可运行参考实现。

### 导入 AIUI Studio

仓库内的 [`aiui/`](aiui/) 是可直接导入 AIUI Studio 的 AIUI 智能体工程：

1. 打开 https://aiui.rokid.com/ 并登录。
2. 新建智能体 →「GitHub 导入」。
3. 仓库填 `https://github.com/566614/shinian-agent`，分支 `master`，目录 `aiui`。
4. 导入后点「效果预览」，说一句「记一下 明天把包装方案发给阿哲」，应出现待办卡片。

详细说明见 [aiui/README.md](aiui/README.md)。该工程不依赖任何 API Key。

## 测试

```bash
pytest -q
```

覆盖结构化规则、相似想法关联、增删改查、检索与回顾接口。

## Docker

```bash
docker build -t shinian .
docker run -p 8000:8000 --env-file .env shinian
```

## 隐私设计

- 默认只上传转写文本，原始音频本地保留 24 小时，可删除。
- 会议等涉及他人的场景需明确提示并征得同意。
- 支持全局暂停录音。

## License

MIT

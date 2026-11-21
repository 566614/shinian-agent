# 拾念 · AIUI Studio 工程

这个目录是可直接导入 AIUI Studio 的 AIUI 智能体工程。

## 目录结构

```
aiui/
├── AGENTS.md              # 智能体身份、触发词与行为规则
├── app.json               # 页面与生命周期声明
├── app.js                 # 应用入口
└── pages/index/index.ink  # 记录卡片页面（结构 + 逻辑 + 样式）
```

## 导入到 AIUI Studio

1. 打开 https://aiui.rokid.com/ 并登录 Rokid 账号。
2. 新建 AIUI 智能体，选择「GitHub 导入」。
3. 填写：
   - 仓库：`https://github.com/566614/shinian-agent`
   - 分支：`master`
   - 目录：`aiui`
4. 导入后点击「效果预览」，输入一句「记一下 明天把包装方案发给阿哲」，应出现一张待办卡片。
5. 预览通过后，进入「构建与提审」打包 AIX，再到 Rokid AI App 更新眼镜资源包。

## 交互说明

- 平台会把用户说出的话解析为 `text` 字段传入页面。
- 页面在本地完成标题、摘要、类型、标签、行动项的规则整理，并渲染卡片。
- 不依赖任何外部 API，也不需要 API Key。
- 智能体的语气和边界由 `AGENTS.md` 约束。

## 注意

- 不要把 `.env`、API Key 或任何密钥提交到这个目录。
- 比赛作品的运行时模型由 AIUI Studio 平台提供，与本地 FastAPI 服务的模型配置相互独立。

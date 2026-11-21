<script type="application/json" def>
{
  "navigationBarTitleText": "拾念",
  "description": "把用户随口说出的一句想法，整理成一张可回看的卡片。",
  "schema": {
    "data": {
      "type": "object",
      "properties": {
        "text": {
          "type": "string",
          "minLength": 1,
          "description": "用户刚刚说出的一句完整想法，保留原话，不要改写。"
        }
      },
      "required": [
        "text"
      ]
    }
  }
}
</script>

<script setup>
const TODO_WORDS = [
  "要",
  "得",
  "记得",
  "需要",
  "明天",
  "后天",
  "下周",
  "安排",
  "联系",
  "发给",
  "确认",
  "提醒",
  "别忘"
];
const DECISION_WORDS = ["决定", "定了", "确定用", "就选", "不做了", "改用"];
const QUOTE_WORDS = ["原话", "说过", "「", "」", "“", "”"];
const MATERIAL_WORDS = ["素材", "参考", "收藏", "案例", "资料", "链接"];
const PEOPLE_WORDS = ["朋友", "同事", "老师", "客户", "负责人", "合伙人", "认识"];

function containsAny(text, words) {
  for (let i = 0; i < words.length; i += 1) {
    if (text.indexOf(words[i]) >= 0) {
      return true;
    }
  }
  return false;
}

function cleanText(text) {
  return String(text || "")
    .replace(/^(拾念[，,、\s]*)/, "")
    .replace(/^(记一下[，,、\s]*)/, "")
    .replace(/^(帮我记(个|一下)?[，,、\s]*)/, "")
    .replace(/^(记个想法[，,、\s]*)/, "")
    .trim();
}

function pickType(text) {
  if (containsAny(text, TODO_WORDS)) {
    return "待办";
  }
  if (containsAny(text, DECISION_WORDS)) {
    return "决策";
  }
  if (containsAny(text, QUOTE_WORDS)) {
    return "引用";
  }
  if (containsAny(text, MATERIAL_WORDS)) {
    return "素材";
  }
  if (containsAny(text, PEOPLE_WORDS)) {
    return "人脉";
  }
  return "灵感";
}

function pickTitle(text) {
  const plain = text.replace(/[#\s]+/g, " ").replace(/[，。！？；、,.!?;:：]+$/g, "").trim();
  if (!plain) {
    return "一条新想法";
  }
  return plain.length > 12 ? plain.slice(0, 12) : plain;
}

function pickSummary(text) {
  if (text.length <= 50) {
    return text;
  }
  return text.slice(0, 50) + "…";
}

function pickTags(text, type) {
  const tags = [];
  const matched = text.match(/#([\u4e00-\u9fa5A-Za-z0-9]+)/g) || [];
  for (let i = 0; i < matched.length && tags.length < 3; i += 1) {
    tags.push(matched[i].slice(1));
  }
  if (tags.indexOf(type) < 0) {
    tags.push(type);
  }
  return tags.slice(0, 4);
}

function pickAction(text) {
  const parts = text.split(/[。；;\n]/);
  for (let i = 0; i < parts.length; i += 1) {
    const part = parts[i].trim();
    if (part && containsAny(part, TODO_WORDS)) {
      return part.length > 18 ? part.slice(0, 18) + "…" : part;
    }
  }
  return "";
}

function padNumber(value) {
  return value < 10 ? "0" + value : String(value);
}

function buildCard(text) {
  const clean = cleanText(text);
  const isUndo = typeof text === "string" && (text.indexOf("算了") >= 0 || text.indexOf("不记了") >= 0 || text.indexOf("取消") >= 0);
  if (isUndo) {
    const now = new Date();
    return {
      title: "已撤销",
      summary: "口口声声说算了，已撤销本次记录",
      type: "撤销",
      tags: ["撤销"],
      footer: "● 已撤销",
      time: padNumber(now.getHours()) + ":" + padNumber(now.getMinutes()),
      isUndo: true
    };
  }
  const content = clean || "想到什么，随口说一句";
  const type = pickType(content);
  const action = pickAction(content);
  const now = new Date();

  return {
    title: pickTitle(content),
    summary: pickSummary(content),
    type: type,
    tags: pickTags(content, type),
    footer: action ? "下一步：" + action : "已存入今日卡片",
    time: padNumber(now.getHours()) + ":" + padNumber(now.getMinutes()),
    isUndo: false
  };
}

export default {
  data: {
    card: buildCard("")
  },

  onLoad(query) {
    const input = query || {};
    this.setData({
      card: buildCard(input.text)
    });
  }
};
</script>

<page>
  <view class="screen">
    <view class="card">
      <view class="head">
        <text class="brand">拾念 SHI NIAN</text>
        <text class="time">{{ card.time }}</text>
      </view>

      <text class="title">{{ card.title }}</text>
      <text class="summary">{{ card.summary }}</text>

      <view class="meta">
        <view class="badge">
          <text class="badge-text">{{ card.type }}</text>
        </view>
        <view class="tags" ink:for="{{ card.tags }}" ink:key="index">
          <text class="tag">#{{ item }}</text>
        </view>
      </view>

      <text class="footer">{{ card.footer }}</text>
    </view>
  </view>
</page>

<style>
.screen {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  min-height: 100vh;
  padding: 10px;
  box-sizing: border-box;
  background: linear-gradient(180deg, #14110d 0%, #0a0908 100%);
  color: #f6efe4;
}

.card {
  display: flex;
  width: 449px;
  min-height: 167px;
  flex-direction: column;
  padding: 14px 16px;
  box-sizing: border-box;
  border-radius: 16px;
  border: 1.5px solid rgba(255, 196, 107, 0.45);
  background: linear-gradient(145deg, rgba(44, 35, 25, 0.96) 0%, rgba(22, 18, 14, 0.98) 100%);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35);
  position: relative;
  overflow: hidden;
}

.card::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(rgba(18, 16, 13, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
  background-size: 100% 4px, 6px 100%;
  opacity: 0.15;
  pointer-events: none;
}

.head {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

.brand {
  font-size: 11px;
  line-height: 14px;
  letter-spacing: 2px;
  color: #ffc46b;
}

.time {
  font-size: 11px;
  line-height: 14px;
  color: #b9aa95;
}

.title {
  margin-top: 8px;
  font-size: 26px;
  line-height: 32px;
  font-weight: 700;
  color: #fffaf2;
}

.summary {
  margin-top: 6px;
  font-size: 13px;
  line-height: 19px;
  color: #e6d8c4;
}

.meta {
  display: flex;
  flex-direction: row;
  align-items: center;
  margin-top: 12px;
}

.badge {
  display: flex;
  padding: 4px 10px;
  border-radius: 999px;
  background-color: rgba(255, 196, 107, 0.16);
  border: 1px solid rgba(255, 196, 107, 0.35);
}

.badge-text {
  font-size: 11px;
  line-height: 14px;
  color: #ffd79b;
}

.tags {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  margin-left: 8px;
}

.tag {
  margin-right: 6px;
  font-size: 11px;
  line-height: 14px;
  color: #b9aa95;
}

.footer {
  margin-top: 10px;
  font-size: 11px;
  line-height: 14px;
  color: #8f8270;
}
</style>

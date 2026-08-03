# 个人网站更新说明 — Art Album + AI Art + Unity Projects

## 目标

在现有个人站上补齐「创作 / 娱乐」展示，同时保持专业主轴（About / Resume / Research / Projects）：

1. **Album 同一页两个板块**：手绘（现有）+ AI 绘画（含工作流说明）
2. **Projects 增加 Unity 游戏**：把桌面 `unity_arts` 的角色与概念图做成项目展示
3. Album 重新进入公开导航（创作内容要能被访客看到）

---

## 信息架构

### 主导航（公开）

```
Home → About → Resume → Research → Projects → Album
```

| 页面 | 职责 |
|------|------|
| **Album** | 创作画廊：Hand-drawn / AI Art 两个 section |
| **Projects** | 工程 & 游戏：GitHub / Unity 游戏 /（后续工业 AI 项目） |

### 不公开

- Chronicle 数据库页（保持隐蔽入口）
- Post 游记（暂保持不进主导航）

---

## Album 页结构（`album.html`）

页面标题改为 **Album**，副标题说明「Hand-drawn & AI」。

### Section A — Hand-drawn

- 保留现有 8 张手绘（Makima、Kafka、Ganyu…）
- 布局与 modal 预览逻辑不变

### Section B — AI Art

- 顶部简短 **Workflow** 说明（可编辑）：
  - 工具：ComfyUI / 文生图 + 图生视频
  - 从文件名推断：`Anima_wallpaper_*`、`LiveWallpaper_FLF2V_*`、`WanVideo*`
  - 文案先写通用版，你之后可改成真实提示词 / 节点说明
- 图片网格：来自桌面 `Desktop/AI_art/pics/`
- 可选：少量短视频（`Desktop/AI_art/videos/*.mp4`）以静音 loop 卡片展示
- **不上传** 过大的 `WanVideo2_1_T2V_00002.gif`（约 25MB，不适合 GitHub Pages）

### 资源落盘

```
images/ai-art/
  ai-01.png …          # 从 AI_art/pics 复制并重命名（去空格）
  anima-wallpaper-*.png
images/ai-art/videos/
  live-01.mp4 …
```

---

## Projects 页结构（`project.html`）

保留现有 GitHub 卡片，把「Games」placeholder 换成真实 **Unity** 区块：

### Unity 游戏卡片（建议名：LoL-style Arena / 自拟）

- 简介：Unity 自制角色战斗原型（卢锡安 / 希维尔 / 娜希等技能与子弹）
- 展示图：概念图 + 角色立绘（来自 `Desktop/unity_arts/pics/` 中偏展示用的大图）
- 技能图标：选代表性几张缩略图排成一行（不放全部小图标）
- **不上传** `.bnk` / `.wad.client` 等音效包（体积大、网页无法直接播放）

### 资源落盘

```
images/unity/
  cover-*.png          # 概念/宣传图
  character-*.png      # lucian / nashi / sivir 等展示图
  icon-*.png           # 少量技能图标（可选）
```

---

## 首页与导航

- 各页 `nav` 增加 `Album` 链接
- 首页四宫格可保持 4 个专业入口；在 Projects 文案中提到「含 Unity 游戏」
- 可选：About 页底部加一句「Also see my Album for drawings & AI art」

---

## 实现步骤

1. 写本 `instruction.md`（当前文件）
2. 复制并重命名桌面素材到 `images/ai-art/`、`images/unity/`
3. 改写 `album.html`：双 section + AI workflow + AI 画廊（含短视频）
4. 改写 `project.html`：Unity 项目区块替换 placeholder
5. 全站导航补上 Album
6. 本地预览确认后，再按需 commit / push

---

## 暂不处理 / 后续可补

- AI 每张图的具体 prompt / 工作流截图（需要你提供）
- Unity 可玩 WebGL build（若有导出再挂链接）
- Post 游记重新公开
- 25MB GIF、音频 `.bnk` / `.wad`

---

## 验收标准

- [x] Album 同一页可见 Hand-drawn 与 AI Art 两个清晰板块
- [x] AI Art 区有简短工作流文字 + 图片网格，点击可放大
- [x] Projects 页有 Unity 游戏展示（封面 + 简介 + 图），不再是纯 placeholder
- [x] 主导航可进入 Album
- [x] 大文件（gif / wad / bnk）未进仓库

## 已实现备注（2026-08）

- 素材来源：桌面 `AI_art/`、`unity_arts/`
- 落地目录：`images/ai-art/`、`images/unity/`
- Workflow 文案为通用 ComfyUI 描述，可按真实节点图再改
- Unity 项目暂名 **Unity Arena Prototype**，可改成正式游戏名
- 未 commit / push：确认预览满意后再部署

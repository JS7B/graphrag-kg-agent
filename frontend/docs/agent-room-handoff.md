# AgentRoom 房间式改造 · 前端交接清单

> 大脑（main 窗口）整理，交 feat/frontend 窗口落地。
> 配套阅读：本目录 `agent-room-redesign-spec.md`（设计规格）、`E:\Mine\ZCodeRoom-项目设计.md`、
> `E:\Mine\ZCodeRoom-原型.html`（**小人画法与配色的权威参考**）、
> `frontend/.test/agent-room-prototype.html`（大脑做的快速原型，**仅供参考，有已知问题，见下**）。

## 一、要做什么（一句话）

把工作台侧栏当前的 `PixelAgent`（精细 CSS 小人，观感不达标，已废弃）替换为新组件 **`AgentRoom`**：
一个**深紫调像素小房间**，里面一个**极简色块小人悬浮**，状态靠**头顶气泡 + 周围场景道具**表达，
由真实 `RunEvent` 驱动。三视图工作台主体不动，只改 `WorkbenchView` 侧栏那两个 Panel。

## 二、为什么这么改（背景，避免走回头路）

- 旧路线「精细角色 + 12 套逐帧动画」已验证走不通：AI 画精细角色一致性差、CSS 拼精细小人观感差（圆角化、大头胖身细腿、细节糊）。
- 新路线借鉴 **ZCodeRoom**（用户的另一个项目原型）：**小人弱化为简单色块、几乎不动，叙事靠场景道具**。成本低、耐看、好维护，无需外部美术资源。

## 三、小人样式：以 ZCodeRoom 为准（重要）

- **权威参考是 `E:\Mine\ZCodeRoom-原型.html` 里的 `drawDude()`**：网格字符 → 逐格生成 `.px` 色块的画法，配色见其 `COL` 对象（紫发 `#5e4f8e`、肤 `#ffd9a8`、眼 `#222`、腿 `#2a2540` 等）。
- **大脑原型里的小人尚未完全对齐 ZCodeRoom**，请**以 ZCodeRoom 的 `drawDude` 为基准**重做，不要照搬大脑原型那版。
- 本项目角色差异点：① 身体（卫衣）配色用**本项目蓝靛紫主色**（呼应 `--color-accent`，而非 ZCodeRoom 的暖橙）；② 加**方框眼镜**作辨识特征（档案管理员人设）。其余尽量贴 ZCodeRoom 风格。

## 四、大脑原型的已知问题（前端要修掉，别继承）

`frontend/.test/agent-room-prototype.html` 能跑、机制对，但有这些没到位，落地时修正：
1. **道具盖住小人**：deleting 的碎纸机等道具放在小人正中、把小人挡住了。道具应放在小人**旁边/前方**，不遮挡主体。
2. **小人偏小、略单薄**：在房间里存在感不足；放大些，比例参考 ZCodeRoom（有腿有鞋、更敦实）。
3. **房间偏空**：缺固定场景元素。可加少量常驻工作间道具（档案柜/桌子/地面），让小人「有个家」（参考 ZCodeRoom 的 desk/monitor/door）。
4. **小人未完全对齐 ZCodeRoom**（见上条三）。

## 五、12 状态 → 气泡 + 场景道具映射（沿用，可优化动效）

| stage | 气泡 | 场景道具/动效 |
|---|---|---|
| idle | ☕ | 安静悬浮，偶尔眨眼 |
| uploading | 📥 | 文档从门/右侧飞入 |
| parsing | 📄 | 文档在面前翻页/拆开 |
| extracting | 🏷️ | 实体标签从文档弹出 |
| linking | 🔗 | 两节点间连线生长 |
| indexing | 🗂️ | 档案柜抽屉开合 |
| searching | 🔍 | 放大镜扫描文件堆 |
| checking | ✓ | 放大镜逐行校对 |
| writing | ⌨️ | 纸条/文字吐出 |
| deleting | 🗑️ | 碎纸机吸入文档 + 碎屑（放小人旁，别遮挡） |
| rebuilding | 🔄 | 复印机扫描光 + 吐纸 |
| error | ⚠️ | 红光闪 + 小人抖动 |

**核心**：小人本体全状态几乎一样（只悬浮/工作时摆动/error 抖动），变的是气泡 + 道具。这是降维省力的关键，别又给小人做复杂逐帧动作。

## 六、技术边界与约定

1. **数据流已就绪，别改**：`WorkbenchView` 已用 `apiFetch('/api/chat')` 起 Run + `useRunEvents(runId)` 订阅真实 SSE。`AgentRoom` 只消费 `currentStage` 和 `events`，是表现层替换。
2. **红线（硬规则）**：`stage` 只来自真实 `RunEvent`，禁止前端伪造驱动。`devControls` 仅开发预览。
3. **房间色调**：**深紫调**（参考 ZCodeRoom），作为浅色专业工作台里一块「夜间小剧场」，形成对比。不要把房间也做成浅色。
4. **配色走 design token**：小人身体/房间强调色尽量挂到现有 token 或新增语义 token，别散落硬编码。
5. **组件落位**：新建 `src/components/AgentRoom/`（`AgentRoom.tsx` + `.module.css` + 道具动效 css + `sceneMap.ts`）。`WorkbenchView` 的 `sideCol` 里 `<PixelAgent>` 换成 `<AgentRoom stage={currentStage} events={events} />`。
6. **道具显隐**：道具 DOM 常驻、CSS 按 `data-stage` 显隐（避免切换重建跳变）——沿用旧 PixelAgent 已有的好做法。
7. **运行轨迹**：房间下方保留事件时间线（可缩简），与房间同属 Agent 状态区。
8. **旧资产**：`PixelAgent` 组件替换后删除（git 留历史即可）；`docs/pixel-character-ai-spec.md` 标注为废弃路线存档。
9. **开工前**：feat/frontend 落后 main，先 `git merge main` 同步（拿到已接通的契约层 + 后端 API）。

## 七、验收

- [ ] `AgentRoom` 替换 `PixelAgent`，工作台侧栏显示深紫房间 + 悬浮小人。
- [ ] 12 状态都有对应气泡 + 场景道具，道具不遮挡小人。
- [ ] 小人样式贴近 ZCodeRoom（网格色块 + 有腿、戴眼镜、蓝靛紫卫衣）。
- [ ] `stage` 由真实 `RunEvent` 驱动（发一次问答，房间跟着 searching→checking→writing→idle 走）。
- [ ] `npm run typecheck` 与 `npm run build` 通过。
- [ ] `frontend/DEVLOG.md` 追加学习记录。

## 八、做完交接

本地 commit（信息写清做了什么），口头通知大脑分支名，大脑读 diff 评审、合并。绝不自行合并 main。

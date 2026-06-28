# 前端修改清单 · PR 审计整改（feat/frontend）

> 来源：2026-06-28 PR 审计报告（§5 前端 UI/UX，依据 ui-ux-pro-max 十类规则）。
> 开工前先 `git merge main` 同步（注意：上次因没 merge main 险些误删后端核心，这次务必先 merge）。
> 定位：个人项目+简历展示，无障碍/响应式是简历加分项，值得做。分三批。

---

## 第一批 · 与后端协同的契约改动（等后端先定，勿抢跑）

### F0. API Key header（配合后端 B2）
- 后端要加 `X-API-Key` 鉴权（密钥走 .env，为空跳过）。前端 `api/client.ts` 的 `apiFetch` 和 `sse.ts` 要带上这个 header（从 `import.meta.env.VITE_API_KEY` 读，可空）。
- **等后端 B2 定好 header 名（X-API-Key）和是否必填后再改**，避免两边对不上。

### F-契约. RunEvent timestamp_ms 命名（配合后端 B8）
- 后端会把 `timestamp_ms` 加 alias 改成 `timestampMs`（camelCase 统一）。届时前端 `types/runEvent.ts` 同步改字段名为 `timestampMs`，并清理"对两套命名分别处理"的兼容代码（注释里那段无奈处理）。
- **等后端 B8 改完、大脑确认契约后再改**，前后端同时切。

---

## 第二批 · 无障碍 CRITICAL（简历硬规则，必做）

报告依据 ui-ux-pro-max 规则，7 个 CRITICAL：

### F1. prefers-reduced-motion 尊重（rAF 动画）🔴
- **位置**：`AgentRoom/useAgentPosition.ts:65-96`
- **问题**：rAF 逐帧动画无视"减少动效"系统设置，仍 60fps 跑。
- **修复**：`matchMedia('(prefers-reduced-motion: reduce)')` 检测，开启时直接跳到目标位、不跑 rAF 插值。（CSS 那层已做 reduced-motion，但 JS rAF 这层漏了）

### F2. 去 emoji 当结构图标 🔴
- **位置**：`TopBar.tsx:39-41` `⚙ 设置`
- **修复**：换成 lucide/phosphor SVG 图标（项目已有图标方案的话复用；没有就用内联 SVG）。违反 no-emoji-icons 硬规则。

### F3. 触控目标尺寸 🔴
- **位置**：`ChatThread.module.css:70-81` 引用角标按钮约 16px
- **修复**：padding 增至 4×8px，min-height 28px（接近 44px 触控标准）。

### F4. 颜色对比度 🔴
- **位置**：`tokens.css:33-34` 成功色 `#15803d` on `#dcfce7` ≈4.27 < 4.5；`tokens.css:21` `--color-text-subtle:#94a3b8` on 白 ≈2.92
- **修复**：成功色加深至 `#166534`（或加 font-weight）；`--color-text-subtle` 加深到 `#64748b`。

### F5. 图谱键盘可达 🔴
- **位置**：`GraphView.tsx:157-195` Cytoscape canvas 节点/边无法键盘访问
- **修复**：加 keydown 导航，或并行提供一个数据表视图（实体列表可 Tab 访问）。后者更简单可靠。

### F6. 设置面板焦点管理 🔴
- **位置**：`App.tsx:36-41`
- **修复**：打开面板时移焦到关闭按钮，关闭时还焦到触发按钮。

### F7. 主视图加 h1 🔴
- **位置**：`WorkbenchView.tsx:74-98` 缺 `<h1>`
- **修复**：加一个 `.sr-only` 的 `<h1>`（如"GraphRAG 知识库工作台"）。

---

## 第三批 · 响应式 + 交互 HIGH（建议做）

### F8. 主视图响应式断点 🟠
- **位置**：`WorkbenchView.module.css`/`LibraryView.module.css` 双栏无媒体查询，<768px 不可用
- **修复**：加 `@media (max-width:860px)` 堆叠成单列。

### F9. 发送按钮随 SSE 禁用 🟠
- **位置**：`WorkbenchView.tsx:84`
- **问题**：前一问答 SSE 未完可发第二问 → 双订阅状态混乱。
- **修复**：`chatRunId !== null` 时禁用输入框/发送按钮。

### F10. TopBar 状态灯接 /health/deps + aria 🟠
- **位置**：`TopBar.tsx:36-39` `Neo4j ●`/`LLM ●` 纯文本占位、同色、无 aria
- **修复**：接 `/health/deps`（前端已有 `api/health.ts`）显示真实连通状态，绿/红区分，加 `aria-label`。

### F11. 导航 aria-current + z-index token 化 🟠
- `TopBar.tsx:25-33` 当前页加 `aria-current="page"`；`tokens.css:151-153` 定义的 z-index token 实际启用（替换散落硬编码）。

---

## 第四批 · 加分（锦上添花，可选）

- F12. AgentRoom 家具硬编码 hex 提取为 `--furniture-*` token（`AgentRoom.module.css`/`roomScenes.css`）。
- F13. idle 动画 0.6s→0.4-0.5s；屏幕发光仅 `data-busy="1"` 时跑。
- F14. SSE 错误文案补恢复路径（`useRunEvents.ts:30`："请确认后端运行，重新提问重试"）。
- F15. `--text-base` 移动端 16px（防 iOS 缩放）；搜索框补 `enterKeyHint`/`inputMode`。

---

## 验证
- 每批 `npm run typecheck` + `npm run build` 通过。
- 无障碍项：浏览器开发者工具的 Lighthouse/axe 跑一遍 accessibility，或手动 Tab 走查键盘可达。
- F1：系统开"减少动效"后，AgentRoom 小人应瞬移不跑 rAF。
- 契约项（F0/F-契约）：等后端对应改动合并后再做，前后端同时切，联调确认。
- DEVLOG 记录关键改动。

## 交接
分批 commit，通知大脑分支名，大脑评审合并。**提交前务必先 `git merge main`**（避免上次的假删风险）。契约批次等后端就绪。

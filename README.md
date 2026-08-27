# Local Resume Tailor

本地运行的 AI 简历定制工作台：针对不同岗位 JD，快速把同一份主简历定制成独立、可投递的版本，并直接导出 PDF。所有数据默认保存在本机，不上传任何服务器。

## 它解决的问题

求职者要针对不同 JD 反复调整简历，但：
- 手工复制改版容易丢失原版、且难以比较多份版本；
- 通用 AI 对话生成的简历没有事实约束，容易虚构数字/职责；
- 每次从零改版很低效，且难以保留一份真实、可复刻的主简历。

本工具把 **「真实主简历 + 备用经历库 + JD + AI 协作 + 文件编辑 + PDF 输出」** 收进同一个窗口，让针对不同岗位的定制变成一条连续流程，而不是零散的手工操作。

## 核心功能

- **主简历导入**：上传 DOCX / PDF，自动解析为结构化内容（教育、实习、技能等板块），并保留字号、边距、照片等版式信息。
- **备用经历库**：可选。上传 PDF/DOCX/TXT/MD 或直接粘贴，作为生成时的补充事实来源。
- **首次偏好确认（冷启动）**：生成前只需确认页数、结构权限、版式权限、经历排序四个低自由度选项，不重复建立事实画像。
- **AI 协作生成**：基于「主简历 + 备用经历 + JD」生成当前岗位版本，生成后附带岗位匹配说明（实际匹配、简历呈现、主要修改、材料缺口）。
- **持续协作编辑**：生成后可直接在右侧编辑，或让 AI 继续修改；支持撤销最近一次修改。AI 与用户编辑同一个版本。
- **不覆盖主简历**：每个 JD 生成独立版本，按「姓名-公司-岗位-日期」命名，互不覆盖。
- **PDF 导出**：内置一页/两页页数闭环，超页时自动压缩排版；导出即下载。

## 使用流程

```text
1. 上传主简历（必选）与备用经历（可选）
2. 首次确认简历修改偏好（页数 / 结构 / 版式 / 经历排序）
3. 输入或上传 JD
4. 点击「生成简历」，或先在 AI 协作窗讨论要求
5. 在右侧直接编辑，或继续让 AI 修改
6. 满意后点击「导出 PDF」
```

主简历永不被覆盖；每个岗位生成独立的命名版本。偏好确认后保持冻结，可在「设置」中查看、编辑或重新校准。

## 技术栈

| 部分 | 技术 |
| --- | --- |
| 前端 | React 19 + TypeScript + Vite 8 |
| 后端 | FastAPI + Uvicorn |
| 存储 | SQLite（标准库 `sqlite3`，本机文件） |
| PDF 解析 | PyMuPDF；DOCX 用 python-docx |
| PDF 生成 | Playwright（无头 Chromium） |
| AI 调用 | OpenAI 兼容 `chat/completions`（httpx），自带 JSON 结构化解析 |

## 环境要求

- Python 3.10+（推荐 3.11 / 3.12）
- Node.js 18+ 与 npm
- 首次运行需联网以下载 Playwright Chromium 与 npm 依赖（之后可离线使用）

## 本地启动（Windows PowerShell）

```powershell
cd resume-tailor
Set-ExecutionPolicy -Scope Process Bypass   # 仅当前会话允许执行脚本
.\setup.ps1                                  # 第一次运行：安装全部依赖
.\start.ps1                                  # 之后启动前后端并打开浏览器
```

浏览器打开 `http://localhost:5173`。

首次启动时后端会自动：
- 在 `data/` 下创建并初始化 SQLite 数据库（无需手动建表）；
- 为空数据库写入默认配置。

## 分开启动（可选）

后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

前端（另开一个终端）：

```powershell
cd frontend
npm run dev
```

前端通过 `http://localhost:8000` 直连后端 API（无需额外代理，CORS 已配置）。

## AI 接口配置

点击右上角「设置」，填写任意 **OpenAI 兼容** 接口的 Base URL、模型名称、API Key。

示例（DeepSeek）：

```text
Base URL：  https://api.deepseek.com
模型名称：  deepseek-chat
API Key：   你的 DeepSeek API Key
```

- 配置保存在本机 SQLite（`data/workspace.db`），**不会进入 Git**，也不上传任何服务器。
- 未配置 API Key 或填错地址时，界面会给出清晰提示；模型请求失败不会静默覆盖内容。
- API Key 留空保存时，会保留已存在的 Key，不会误清空。

## 数据与隐私

- 所有数据（主简历、经历、JD、版本、配置、Key）均保存在本机 `data/` 目录。
- `data/`、SQLite、`.env`、虚拟环境、`node_modules`、构建产物均已被 `.gitignore` 排除。
- 本工具不做任何数据上传，AI 请求仅将简历内容发送给你配置的模型服务。

## 当前限制

- **中文简历**：第一阶段面向中文求职场景，暂不支持英文简历生成。
- **版式复刻精度**：会继承主导字体、字号、边距与照片位置；但整份简历统一使用主导字体，原稿中用于日期/英文的 Arial 等辅助字体会被并入主导字体。照片尺寸默认固定，可在设置中调整。
- **页数约束**：一页/两页通过导出时自动压缩排版实现；若内容确实过多，仍需人工精简部分经历。
- **文件保真度**：PDF 为必需输出；编辑基于结构化中间表示（JSON+HTML），并非对任意复杂 Word 的高保真逐字符还原。DOCX 输出暂缓。
- **视觉主观验收**：工具负责事实、流程与版式稳定；最终选材、措辞与观感需人工复核。

## 开发与测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd frontend
npm run build
```

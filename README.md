# FAE_embedded_code_generation_SKILL
 OpenClaw FAE Skills — 一组协作完成"文档 → 知识库 → 完整性检查 → 嵌入式代码生成"全流程的 AI 技能。doc-convert 转换数据手册/需求规格，net-convert 解析 KiCad 原理图网表，fae-input-check 双知识库交叉验证完整性，fae 从两个知识库检索 MCU 规格和硬件连接，生成符合编码规范的嵌入式 C 代码框架（main.c/h、中断服务、HAL 驱动层）。面向电机控制、电源管理等 MCU 嵌入式开发场景。 

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     OpenClaw Gateway                        │
│                                                             │
│  ┌───────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ doc-      │    │ net-convert  │    │  fae-input-check  │  │
│  │ convert   │    │              │    │  (输入验证)       │  │
│  │           │    │              │    │                   │  │
│  │ PDF/Excel │    │ .net 网表    │    │ 双知识库交叉检索  │  │
│  │ → Markdown│    │ → Markdown   │    │ 生成完整性报告    │  │
│  │ → 向量索引 │    │ → 向量索引   │    │                   │  │
│  └─────┬─────┘    └──────┬───────┘    └────────┬─────────┘  │
│        │                 │                     │            │
│        ▼                 ▼                     ▼            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    fae (代码生成)                     │    │
│  │                                                      │    │
│  │  doc-convert 知识库 → MCU 规格、寄存器、系统参数      │    │
│  │  net-convert 知识库 → 引脚连接、BOM、信号网络         │    │
│  │  fae-input-check 报告 → 完整性确认、缺失项            │    │
│  │                                                      │    │
│  │  输出: main.c / main.h / mcu_it.c / drivers/ README  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  知识库路径:                                                 │
│  doc-convert:   fae_input/indexes/                          │
│  net-convert:   fae_input/schematics_kb/indexes/            │
└─────────────────────────────────────────────────────────────┘
```

---

## 技能清单

### 1. doc-convert — 文档转换与知识库建立

**功能：** 将原始技术文档（PDF、Excel、CMSIS-Pack）转换为可读格式，建立向量+关键词混合检索知识库。

**输入：** PDF 数据手册、用户手册、需求规格表、CMSIS Pack
**输出：** Markdown 文本缓存 + ChromaDB 向量索引 + Whoosh 关键词索引

**核心文件：**
| 文件 | 说明 |
|------|------|
| `doc-convert/SKILL.md` | 技能定义 |
| `doc-convert/converter.py` | 批量转换工具 |
| `doc-convert/kb_manager.py` | 知识库管理器（build/query/status） |
| `doc-convert/retriever/` | 检索引擎（向量+关键词混合） |

---

### 2. net-convert — 原理图网表转换与知识库建立

**功能：** 解析 KiCad 原理图网表（`.net`），提取 MCU 引脚分配、BOM 器件清单、信号网络连接，建立独立的电路图知识库。

**输入：** KiCad `.net` 网表文件
**输出：** 结构化 Markdown 报告 + 独立的 ChromaDB/Whoosh 索引

**核心文件：**
| 文件 | 说明 |
|------|------|
| `net-convert/SKILL.md` | 技能定义 |
| `net-convert/converter.py` | 网表批量转换工具 |
| `net-convert/kb_manager.py` | 电路图知识库管理器 |
| `net-convert/scripts/netlist_to_md.py` | KiCad 网表解析器 |

---

### 3. fae-input-check — 输入完整性验证

**功能：** 在代码生成前，同时查询 doc-convert 和 net-convert 两个知识库，交叉验证信息完整性，生成缺失报告。

**输入：** 已建立的两个知识库
**输出：** 完整性检查报告（已确认项 / 缺失项 / 完整度百分比）

**核心文件：**
| 文件 | 说明 |
|------|------|
| `fae-input-check/SKILL.md` | 技能定义 |
| `fae-input-check/checker.py` | 双知识库完整性检查器 |
| `fae-input-check/WORKFLOW.md` | 完整工作流指南 |

---

### 4. fae — 嵌入式代码生成

**功能：** 从双知识库检索 MCU 规格和硬件连接信息，生成符合编码规范的嵌入式 C 代码（main.c/h、中断服务、HAL 驱动层、项目文档）。

**输入：** 双知识库检索结果 + fae-input-check 验证报告
**输出：** 完整的 C/H 源文件 + README 项目文档

**核心文件：**
| 文件 | 说明 |
|------|------|
| `fae/SKILL.md` | 技能定义（含编码规范、代码生成指南） |

---

## 技能间的协作关系

```
Phase 1a: doc-convert
  ├─ 转换 PDF/Excel → Markdown
  └─ 建立文档知识库 (fae_input/indexes/)
       包含: 数据手册、用户手册、需求规格、CMSIS Pack

Phase 1b: net-convert
  ├─ 转换 .net 网表 → 结构化 Markdown
  └─ 建立电路图知识库 (fae_input/schematics_kb/indexes/)
       包含: 引脚分配表、BOM、信号网络连接

Phase 2: fae-input-check
  ├─ 从 doc-convert 检索: MCU 型号、寄存器、系统参数、保护阈值
  ├─ 从 net-convert 检索: 引脚物理连接、BOM 器件、信号网络
  ├─ 交叉验证 → 生成完整性报告
  └─ 引导用户补充缺失信息

Phase 3: fae
  ├─ 前置条件检查 (双知识库已建立 + 完整度 ≥80%)
  ├─ 从 doc-convert 检索 MCU 规格和寄存器配置
  ├─ 从 net-convert 检索硬件引脚连接
  └─ 生成嵌入式 C 代码
```

### 知识库互补原则

| 信息类型 | 可靠来源 | 原因 |
|---------|---------|------|
| 引脚实际连到哪里 | **net-convert** | 原理图定义物理连接 |
| 这个引脚能做什么功能 | **doc-convert** | 数据手册定义 MCU 能力 |
| 怎么配置寄存器 | **doc-convert** | 用户手册提供编程指南 |
| 信号网络挂了哪些器件 | **net-convert** | 原理图 BOM 和连接关系 |
| 保护阈值应该是多少 | **doc-convert** | 需求规格定义系统参数 |

**两个知识库同等重要，不是主次关系。** 代码生成时需要同时参考两者。

---

## 在 OpenClaw 中配置这些技能

### 前置条件

1. **OpenClaw** 已安装并运行
2. **Python 3.9+** 已安装
3. **Ollama** 或本地 embedding 模型可用（或使用 sentence-transformers 本地模型）

### 安装步骤

#### 1. 安装 Python 依赖

```bash
# doc-convert 和 net-convert 共享的依赖
cd skills/doc-convert
pip3 install -r requirements.txt

# net-convert 无额外依赖（复用 doc-convert 的 retriever）
```

核心依赖：
- `pymupdf4llm` — PDF → Markdown
- `pandas` — Excel → CSV
- `chromadb` — 向量数据库
- `whoosh` — 关键词搜索引擎
- `sentence-transformers` — 文本嵌入模型

#### 2. 放置技能文件

将 `skills/` 目录复制到 OpenClaw workspace：

```bash
cp -r skills/ ~/.openclaw/workspace/
```

或 symlink：
```bash
ln -s /path/to/this/repo/skills ~/.openclaw/workspace/skills
```

#### 3. 配置 OpenClaw 技能注册

**修改文件：** `~/.openclaw/config.json`（或通过 `openclaw config` 命令）

确认 `skills` 配置指向正确的目录：

```json
{
  "skills": {
    "entries": {
      "doc-convert": {
        "path": "~/.openclaw/workspace/skills/doc-convert"
      },
      "net-convert": {
        "path": "~/.openclaw/workspace/skills/net-convert"
      },
      "fae-input-check": {
        "path": "~/.openclaw/workspace/skills/fae-input-check"
      },
      "fae": {
        "path": "~/.openclaw/workspace/skills/fae"
      }
    }
  }
}
```

> **注意：** 如果 OpenClaw 自动扫描 `workspace/skills/` 目录下的 `SKILL.md`，则无需手动配置每个技能路径。

#### 4. 修改技能中的绝对路径（如果需要）

本技能组使用了硬编码的绝对路径。如果你的 OpenClaw workspace 路径不同，需要修改以下文件中的路径：

**需要修改的文件和路径：**

| 文件 | 需要修改的路径 | 改为你的路径 |
|------|---------------|-------------|
| `doc-convert/SKILL.md` | `/Users/sinomcu/.openclaw/workspace/fae_input/` | 你的 `fae_input/` 路径 |
| `doc-convert/kb_manager.py` | `"/Users/sinomcu/.openclaw/workspace/fae_input/"` | 你的 `fae_input/` 根目录 |
| `doc-convert/converter.py` | 同上 | 同上 |
| `net-convert/SKILL.md` | `/Users/sinomcu/.openclaw/workspace/fae_input/` | 你的 `fae_input/` 路径 |
| `net-convert/kb_manager.py` | `"/Users/sinomcu/.openclaw/workspace/fae_input/schematics_kb"` | 你的电路图 KB 路径 |
| `net-convert/converter.py` | `"/Users/sinomcu/.openclaw/workspace/fae_input/"` | 你的 `fae_input/` 路径 |
| `fae-input-check/checker.py` | 所有 `/Users/sinomcu/.openclaw/workspace/` 前缀 | 你的 workspace 路径 |
| `fae-input-check/SKILL.md` | 所有命令示例中的绝对路径 | 你的路径 |
| `fae/SKILL.md` | 所有命令示例中的绝对路径 | 你的路径 |

**快速批量替换：**

```bash
# 将所有文件中的旧路径替换为新路径
OLD_PATH="/Users/sinomcu/.openclaw/workspace"
NEW_PATH="/your/new/workspace"

find skills/ -type f \( -name "*.py" -o -name "*.md" -o -name "*.sh" \) \
  -exec sed -i '' "s|${OLD_PATH}|${NEW_PATH}|g" {} +
```

#### 5. 验证安装

```bash
# 检查 doc-convert
python3 skills/doc-convert/kb_manager.py status

# 检查 net-convert
python3 skills/net-convert/kb_manager.py status
```

---

## 快速开始

### 完整工作流示例

```bash
# 1. 将技术文档放入 fae_input/sources/
cp ~/Documents/MC60F3136_数据手册.pdf fae_input/sources/
cp ~/Documents/design.net fae_input/sources/
cp ~/Documents/需求规格.xlsx fae_input/sources/

# 2. 转换文档（doc-convert）
python3 skills/doc-convert/converter.py -i fae_input/sources/ -o fae_input/cache/ -r
python3 skills/doc-convert/kb_manager.py build

# 3. 转换网表（net-convert）
python3 skills/net-convert/converter.py -i fae_input/sources/ -o fae_input/cache/schematics/ -r
python3 skills/net-convert/kb_manager.py build

# 4. 检查完整性（fae-input-check）
python3 skills/fae-input-check/checker.py

# 5. 生成代码（fae）
# 在 OpenClaw 对话中说："请用 fae 技能生成代码"
```

### 或在 OpenClaw 对话中直接使用

```
你：请用 doc-convert 转换 fae_input 中的所有文档并建立知识库

（等待转换完成）

你：请用 net-convert 转换项目中的 .net 网表文件

（等待转换完成）

你：请用 fae-input-check 检查 12V 38W 水泵方案的输入是否完整

（查看完整性报告，补充缺失信息）

你：请用 fae 技能生成嵌入式代码
```

---

## 目录结构

```
skills/
├── README.md                  ← 本文件
├── doc-convert/               ← 文档转换技能
│   ├── SKILL.md
│   ├── converter.py           ← 批量转换入口
│   ├── kb_manager.py          ← 知识库管理（build/query/status/clear）
│   ├── requirements.txt       ← Python 依赖
│   ├── retriever/             ← 混合检索引擎
│   │   ├── hybrid_search.py   ← 向量+BM25 融合检索
│   │   ├── embedder.py        ← 文本嵌入
│   │   ├── vector_store.py    ← ChromaDB 封装
│   │   └── keyword_index.py   ← Whoosh 封装
│   ├── scripts/               ← 转换脚本
│   │   ├── pdf_to_md.py
│   │   ├── xlsx2csv.py
│   │   └── pack_extractor.py
│   └── kb/config.json         ← 知识库配置
├── net-convert/               ← 网表转换技能
│   ├── SKILL.md
│   ├── converter.py
│   ├── kb_manager.py
│   ├── requirements.txt       ← 同 doc-convert
│   ├── scripts/
│   │   └── netlist_to_md.py   ← KiCad 网表解析
│   └── kb/config.json
├── fae-input-check/           ← 输入验证技能
│   ├── SKILL.md
│   ├── checker.py             ← 双知识库检查器
│   ├── WORKFLOW.md
│   ├── EXAMPLES.md
│   └── README.md
└── fae/                       ← 代码生成技能
    └── SKILL.md               ← 含编码规范、生成指南

fae_input/                     ← 数据目录（不在 skills/ 下）
├── sources/                   ← 用户放入原始文档
├── cache/
│   ├── text/                  ← doc-convert 转换输出
│   └── schematics/            ← net-convert 转换输出
└── indexes/                   ← doc-convert 索引
    ├── vector/
    └── keyword/
    └── .cache_meta.json       ← 增量构建缓存

fae_input/schematics_kb/       ← net-convert 独立索引
└── indexes/
    ├── vector/
    └── keyword/
```

---

## 已知限制

1. **寄存器操作为示意代码** — 生成的 C 代码中寄存器操作使用 `/* TODO */` 占位，需要根据实际 MCU 头文件替换
2. **KiCad 网表格式** — 仅支持 KiCad Eeschema `.net` 格式
3. **扫描版 PDF** — 图片型 PDF 无法提取文本，需提供原始文档
4. **单 MCU 设计** — 针对单 MCU 电路板设计，多 MCU 项目仅提取主 MCU
5. **路径硬编码** — 当前版本使用绝对路径，部署时需要替换

---

## 路线图

- [ ] 支持更多 EDA 网表格式（Altium、Eagle）
- [ ] OCR 支持扫描版 PDF
- [ ] 自动生成 MCU 寄存器操作代码（基于 CMSIS-SVD）
- [ ] 增量知识库更新（监听 source 目录变化）
- [ ] FOC 控制算法代码模板
- [ ] 多 MCU 项目支持

---

## License

MIT

---

_FAE Skills v0.1.0 — Early Release_ 

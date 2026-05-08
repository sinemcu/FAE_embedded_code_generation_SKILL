# FAE 完整工作流指南

## 工作流概览

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  Phase 1a           │     │  Phase 2             │     │  Phase 3        │
│  doc-convert        │ ──→ │  fae-input-check     │ ──→ │  fae            │
│  文档知识库          │     │  双知识库验证         │     │  代码生成       │
│                     │     │                      │     │                 │
│  数据手册/需求       │     └─────────▲────────────┘     │  嵌入式 C 代码   │
│  Excel/Pack         │               │                  └─────────────────┘
└─────────────────────┘               │
                                      │
┌─────────────────────┐               │
│  Phase 1b           │               │
│  net-convert        │ ──────────────┘
│  电路图知识库        │
│                     │
│  原理图网表 (.net)   │
│  引脚分配/信号网络   │
└─────────────────────┘
```

---

## Phase 1a: doc-convert (文档转换)

### 目标
将原始技术文档转换为可读格式，建立文档知识库索引。

### 输入
- PDF 数据手册、用户手册
- Excel 需求规格书
- CMSIS Pack 文件 (.pack)

### 处理步骤
```bash
# 1. 批量转换文档
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/converter.py \
  -i fae_input/sources/ \
  -o fae_input/cache/ \
  -r

# 2. 建立文档知识库索引
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py build
```

### 输出
- `fae_input/cache/text/` - 转换后的 Markdown/CSV 文件
- `fae_input/indexes/vector/` - 向量索引 (ChromaDB)
- `fae_input/indexes/keyword/` - 关键词索引 (Whoosh)

### 完成标志
```
✅ 知识库构建完成！
   新增：132 个文档
   总计：18,935 个分块
```

---

## Phase 1b: net-convert (电路图转换)

### 目标
将 KiCad 原理图网表转换为结构化 Markdown，建立电路图知识库。

### 输入
- KiCad 网表文件 (.net)

### 处理步骤
```bash
# 1. 批量转换网表文件
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/converter.py \
  -i fae_input/sources/ \
  -o fae_input/cache/schematics/ \
  -r

# 2. 建立电路图知识库索引
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py build
```

### 输出
- `fae_input/cache/schematics/` - 转换后的网表 Markdown 文件
- `fae_input/schematics_kb/indexes/vector/` - 向量索引
- `fae_input/schematics_kb/indexes/keyword/` - 关键词索引

### 完成标志
```
✅ 电路图知识库构建完成
   转换网表：1 个
   提取引脚：XX 个
```

---

## Phase 2: fae-input-check (双知识库验证)

### 目标
检查两个知识库的输入完整性，识别缺失信息并指导补充。

### 输入
- Phase 1a 建立的文档知识库
- Phase 1b 建立的电路图知识库

### 处理步骤
```bash
# 运行双知识库完整性检查
python3 /Users/sinomcu/.openclaw/workspace/skills/fae-input-check/checker.py
```

### 检查项目

| 检查项 | 数据来源 | 必需性 |
|--------|---------|--------|
| MCU 型号 | doc-convert 数据手册 | ⭐⭐⭐ 必需 |
| 系统电压 | doc-convert 需求规格 | ⭐⭐⭐ 必需 |
| PWM 引脚 | net-convert 原理图网表 | ⭐⭐⭐ 必需 |
| ADC 引脚 | net-convert 原理图网表 | ⭐⭐⭐ 必需 |
| 保护阈值 | doc-convert 需求规格 | ⭐⭐ 推荐 |
| PWM 频率 | 口头提供 | ⭐⭐ 推荐 |
| 控制目标 | doc-convert 需求规格 | ⭐⭐ 推荐 |

### 输出
```markdown
# FAE 输入完整性检查报告

**知识库状态：**
- 📁 文档知识库 (doc-convert)：✅ 已建立
- 📁 电路图知识库 (net-convert)：✅ 已建立

**完整度：** 80%

✅ 已确认：MCU 型号、系统电压、PWM/ADC 引脚 [net-convert]
⚠️ 缺失：保护阈值、PWM 频率
```

### 完成标志
- 完整度 ≥ 80%
- 无高优先级缺失项

---

## Phase 3: fae (代码生成)

### 目标
基于两个知识库的完整信息生成嵌入式 C 代码。

### 信息检索来源

| 信息类型 | 检索知识库 |
|---------|-----------|
| MCU 寄存器/外设能力 | doc-convert |
| 引脚实际硬件连接 | net-convert |
| 系统参数/保护阈值 | doc-convert |
| BOM 器件清单 | net-convert |
| 定时器/ADC 配置方法 | doc-convert |

### 输出
```
fae_output/12V_38W_WaterPump_Project/
├── Code/
│   └── Src/
│       ├── main.c              # 主程序
│       ├── main.h              # 系统配置
│       ├── mcu_it.c            # 中断服务
│       └── drivers/
│           ├── mcu_hal.h       # HAL 层
│           └── mcu_hal.c
├── Docs/
│   └── README.md
└── Keil/
```

---

## 完整示例：12V 38W 水泵方案

### 步骤 1: 准备资料

```
fae_input/sources/
├── MC60F3136_数据手册.pdf           → doc-convert
├── MC60F3136_用户手册.pdf           → doc-convert
├── MC8059_12VPUMP-G-20260323_V10.net → net-convert
├── HWP40-12-2_需求表.xlsx           → doc-convert
└── 器件 Pack/                        → doc-convert
```

### 步骤 2: 文档转换 (Phase 1a)

```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py build
```

### 步骤 3: 电路图转换 (Phase 1b)

```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/schematics/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py build
```

### 步骤 4: 输入验证 (Phase 2)

```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/fae-input-check/checker.py
```

### 步骤 5: 补充信息 (如需要)

```
"过压保护 16.5V，欠压保护 7.5V，过流保护 3.5A，
目标转速 7000RPM，PWM 频率 20kHz"
```

### 步骤 6: 代码生成 (Phase 3)

```
"请用 fae 技能生成 12V 38W 水泵方案的嵌入式代码"
```

---

## 知识库路径速查

| 知识库 | 索引路径 | 缓存路径 | 用途 |
|--------|---------|---------|------|
| doc-convert | `fae_input/indexes/` | `fae_input/cache/text/` | 数据手册、需求规格 |
| net-convert | `fae_input/schematics_kb/indexes/` | `fae_input/cache/schematics/` | 原理图、引脚分配 |

---

## 故障排查

### 问题 1: 文档知识库未建立

```bash
# 检查转换状态
ls fae_input/cache/text/

# 重新建立
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py build --full-rebuild
```

### 问题 2: 电路图知识库未建立

```bash
# 检查网表源文件
ls fae_input/sources/**/*.net

# 转换并建立索引
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/schematics/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py build
```

### 问题 3: 没有原理图网表

**备选方案：** 手动提供引脚分配表
```
格式：MCU 引脚 | 网络名 | 功能 | 外部连接
放入 fae_input/sources/，由 doc-convert 转换进知识库
```

---

## 快速参考卡

```
┌─────────────────────────────────────────────────────┐
│  FAE 工作流快速参考                                  │
├─────────────────────────────────────────────────────┤
│  Phase 1a: doc-convert                              │
│  → python3 skills/doc-convert/converter.py          │
│    -i sources/ -o cache/ -r                         │
│  → python3 skills/doc-convert/kb_manager.py build   │
├─────────────────────────────────────────────────────┤
│  Phase 1b: net-convert                              │
│  → python3 skills/net-convert/converter.py          │
│    -i sources/ -o cache/schematics/ -r              │
│  → python3 skills/net-convert/kb_manager.py build   │
├─────────────────────────────────────────────────────┤
│  Phase 2: fae-input-check                           │
│  → python3 skills/fae-input-check/checker.py        │
│  → 完整度≥80% 且无高优先级缺失                      │
├─────────────────────────────────────────────────────┤
│  Phase 3: fae                                       │
│  → "请用 fae 技能生成代码"                           │
│  → fae_output/Project/Code/Src/                     │
└─────────────────────────────────────────────────────┘
```

---

_FAE Complete Workflow Guide v2.0 - 整合 doc-convert + net-convert 双知识库_ 🐶

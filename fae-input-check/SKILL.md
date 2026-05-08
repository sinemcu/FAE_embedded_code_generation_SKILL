---
name: fae-input-check
description: "Validate and complete input files for FAE code generation. Use when: need to check if all required information is available before generating embedded code, identify missing specs/pin assignments/parameters, and guide user to provide missing inputs. Integrates with doc-convert (datasheets/docs) and net-convert (schematics/netlists)."
---

# FAE-INPUT-CHECK - Embedded Code Input Validation Skill

在 FAE 代码生成前检查输入文件的完整性,识别缺失信息并指导用户补充。

整合两个知识库:
- **doc-convert** → 数据手册、用户手册、需求规格等文档知识库
- **net-convert** → 原理图网表、引脚分配等电路图知识库

## When to Use

✅ **USE this skill when:**

- "检查代码生成前的输入是否完整"
- "验证两个知识库是否包含所有必要信息"
- "查找缺失的引脚分配/参数配置"
- "代码生成前的预检查"
- "识别需要补充的技术规格"

## When NOT to Use

❌ **DON'T use this skill when:**

- 还没有转换文档 → 先用 `doc-convert` 和 `net-convert` 转换
- 已经确认信息完整 → 直接用 `fae` 生成代码
- 只需要查询单个参数 → 直接问问题即可

## Knowledge Base Architecture

```
┌─────────────────────────────────────────────────┐
│                 fae-input-check                  │
│           (输入完整性检查 · 本技能)                │
└──────────────┬──────────────────────┬────────────┘
               │                      │
       ┌───────▼───────┐      ┌───────▼───────┐
       │  doc-convert  │      │  net-convert  │
       │  文档知识库    │      │  电路图知识库   │
       └───────┬───────┘      └───────┬───────┘
               │                      │
     ┌─────────▼──────────┐  ┌────────▼─────────┐
     │ fae_input/indexes/ │  │ fae_input/       │
     │ vector/ + keyword/ │  │ schematics_kb/   │
     │                    │  │ indexes/         │
     │ · 数据手册.pdf      │  │ vector/ + keyword│
     │ · 用户手册.pdf      │  │                  │
     │ · 需求规格.xlsx     │  │ · 原理图.net      │
     │ · CMSIS Pack       │  │ · 引脚分配        │
     │ · BOM              │  │ · 信号网络连接    │
     └────────────────────┘  └──────────────────┘
```

**关键点:**
- 两个知识库使用**独立的索引目录**,需要分别查询
- `doc-convert` 索引:`fae_input/indexes/`
- `net-convert` 索引:`fae_input/schematics_kb/indexes/`
- FAE 代码生成时需要**同时参考两个知识库**的信息

## Workflow

### Phase 1: 双知识库转换状态检查

**检查 doc-convert(文档知识库):**
```bash
# 检查文档知识库状态
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py status

# 查看已转换的文档
ls /Users/sinomcu/.openclaw/workspace/fae_input/cache/text/
```

**检查 net-convert(电路图知识库):**
```bash
# 检查电路图知识库状态
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py status

# 查看已转换的网表文件
ls /Users/sinomcu/.openclaw/workspace/fae_input/cache/schematics/
```

**必需文档类型:**

| 文档类型 | 来源技能 | 必需性 | 用途 |
|---------|---------|--------|------|
| MCU 数据手册 | doc-convert | ⭐⭐⭐ 必需 | 寄存器、外设、电气参数 |
| 原理图网表 (.net) | net-convert | ⭐⭐⭐ 必需 | 引脚分配、外设连接、信号网络 |
| 需求规格书 | doc-convert | ⭐⭐ 推荐 | 系统参数、保护阈值 |
| CMSIS Pack | doc-convert | ⭐⭐ 推荐 | 寄存器定义、例程 |
| 用户手册 | doc-convert | ⭐ 可选 | 外设使用说明 |

### Phase 2: 关键信息提取验证

从**两个知识库**中提取并验证关键信息:

#### 1️⃣ MCU 信息 (必需)
- [ ] MCU 型号确认
- [ ] 核心频率 (F_CPU)
- [ ] Flash/RAM 大小
- [ ] 可用外设列表
- [ ] 引脚总数

**查询(doc-convert 知识库):**
```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "MCU 型号 核心频率 Flash RAM"
```

#### 2️⃣ 电源系统 (必需)
- [ ] 系统电压 (如 12V/24V)
- [ ] 电压范围 (最小/最大)
- [ ] 最大电流
- [ ] LDO 配置 (如有)

**查询(doc-convert 知识库):**
```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "电源电压 电流 LDO VCC VDD"
```

#### 3️⃣ 引脚分配 (必需) — 🔗 双知识库交叉验证

两个知识库在引脚信息上**平等权重、互补使用**：

| 问题 | 可靠来源 | 说明 |
|------|---------|------|
| 这个引脚实际连到哪里？ | **net-convert** | 原理图网表定义实际硬件连接 |
| 这个引脚能做什么功能？ | **doc-convert** | 数据手册/用户手册定义 MCU 能力（复用功能、电气特性） |
| 怎么配置这个引脚？ | **doc-convert** | 用户手册提供寄存器配置方法和代码示例 |
| 信号网络上挂了什么器件？ | **net-convert** | 原理图 BOM 和连接关系 |

**查询（两个知识库都要查）：**
```bash
# net-convert: 引脚实际连接了什么网络、什么器件
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "MCU 引脚分配 PWM ADC UART 信号网络"

# doc-convert: 引脚的 MCU 功能能力、配置方法
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "引脚功能 复用 外设 配置方法"
```

> 💡 **交叉验证：** net-convert 告诉你 PA7 连到了 "PWM_A" 网络，doc-convert 告诉你 PA7 支持 TIM1_CH1 互补 PWM 输出。两者结合才能生成正确的代码。

#### 4️⃣ 外设配置 (必需)
- [ ] 定时器配置 (PWM 频率、周期)
- [ ] ADC 配置 (分辨率、采样率)
- [ ] 通信参数 (波特率、数据位)
- [ ] 中断优先级

**查询(双知识库):**
```bash
# doc-convert: 获取 MCU 外设能力和寄存器配置
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "定时器 PWM 频率 ADC 分辨率 波特率"

# net-convert: 获取实际电路中使用的外设连接
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "定时器 PWM ADC 外设连接"
```

#### 5️⃣ 保护机制 (推荐)
- [ ] 过压保护阈值
- [ ] 欠压保护阈值
- [ ] 过流保护阈值
- [ ] 过温保护阈值
- [ ] 故障恢复策略

**查询(doc-convert 知识库):**
```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "保护 过压 欠压 过流 过温 阈值"
```

#### 6️⃣ 控制参数 (推荐)
- [ ] 控制目标 (速度/位置/扭矩)
- [ ] PID 参数 (如有)
- [ ] 滤波器配置
- [ ] 启动/停止曲线

**查询(doc-convert 知识库):**
```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "控制 PID 速度 目标 RPM"
```

### Phase 3: 缺失信息报告

**输出格式:**
```markdown
## 📋 FAE 输入完整性检查报告

### ✅ 已确认信息 (X 项)

| 类别 | 项目 | 值 | 来源 |
|------|------|-----|------|
| MCU | 型号 | MC60F3136 | doc-convert: 数据手册 P3 |
| 电源 | 系统电压 | 12V | doc-convert: 需求表 P2 |
| 引脚 | PWM 输出 | PA7/PA8/PA9 | net-convert: 原理图网表 |
| 引脚 | ADC 输入 | PA0 | net-convert: 原理图网表 |
| ... | ... | ... | ... |

### ⚠️ 缺失信息 (Y 项)

**高优先级 (阻塞代码生成):**
1. ❌ PWM 频率 - 需要指定定时器配置
2. ❌ 过流保护阈值 - 需要指定最大允许电流

**中优先级 (影响代码完整性):**
1. ⚠️ UART 通信波特率 - 如需要串口输出
2. ⚠️ 目标转速 - 影响控制算法

**低优先级 (可后续补充):**
1. 💡 PID 参数初始值 - 可使用默认值调试
2. 💡 LED 指示灯引脚 - 可选功能

### 📝 建议补充操作

1. **立即补充** (阻塞项):
   ```
   请提供以下信息:
   - PWM 频率:例如 "20kHz"
   - 过流阈值:例如 "最大电流 3.5A"
   ```

2. **可选补充** (优化项):
   ```
   如有以下信息请提供:
   - 目标转速:例如 "7000 RPM"
   - 控制模式:速度闭环还是开环?
   ```
```

### Phase 4: 交互式补充引导

**引导用户补充信息:**

```markdown
## 🔧 信息补充向导

### 步骤 1: 确认 MCU 引脚资源

根据 doc-convert 数据手册,MCU 可用引脚资源:
- PWM 输出:PA6, PA7, PA8, PA9, PB0, PB1
- ADC 输入:PA0~PA7, PB0, PB1
- UART: PA9(TX), PA10(RX)
- SPI: PA4(NSS), PA5(SCK), PA6(MISO), PA7(MOSI)

根据 net-convert 原理图网表,实际使用的引脚:
- PWM: PA7, PA8, PA9 ✓
- ADC: PA0 ✓

**请确认是否有其他需要补充的引脚分配:**
```

### 步骤 2: 确认系统参数

```markdown
根据需求文档,已提取参数:
- 系统电压:12V ✓
- 额定功率:38W ✓

**需要补充:**
- 额定转速:??? RPM
- 启动时间:??? ms
- 通信需求:是/否
```

### 步骤 3: 确认保护参数

```markdown
**安全关键参数必须提供:**
- 过压保护:___ V (建议:16.5V for 12V 系统)
- 欠压保护:___ V (建议:7.5V for 12V 系统)
- 过流保护:___ A (根据电机参数)
```

## Required Tools

### doc-convert 知识库命令

```bash
# 检查文档知识库状态
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py status

# 查询文档知识库
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "你的问题"

# 查看已转换的文档
ls /Users/sinomcu/.openclaw/workspace/fae_input/cache/text/
```

### net-convert 知识库命令

```bash
# 检查电路图知识库状态
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py status

# 查询电路图知识库(引脚分配、信号网络)
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "你的问题"

# 查看已转换的网表文件
ls /Users/sinomcu/.openclaw/workspace/fae_input/cache/schematics/
```

### 知识库路径速查

| 知识库 | 索引路径 | 缓存路径 | 用途 |
|--------|---------|---------|------|
| doc-convert | `fae_input/indexes/` | `fae_input/cache/text/` | 数据手册、需求规格 |
| net-convert | `fae_input/schematics_kb/indexes/` | `fae_input/cache/schematics/` | 原理图、引脚分配 |

## Usage Examples

### Example 1: 完整检查流程

**User:** "检查 12V 38W 水泵方案的输入是否完整,准备生成代码"

**Assistant:** (uses fae-input-check skill)

1. 检查 doc-convert 知识库状态
2. 检查 net-convert 知识库状态
3. 从两个知识库查询关键信息
4. 生成完整性报告
5. 列出缺失项并引导补充

**Output:**
```markdown
## 📋 FAE 输入完整性检查报告

**项目:** 12V_38W_WaterPump

### ✅ 已确认 (15 项)
- MCU: MC8059 (MC60F3136+IPM) [doc-convert: 数据手册]
- 电源:12V (6.5-40V 范围) [doc-convert: 需求表]
- 拓扑:三相全桥 [net-convert: 原理图网表]
- PWM 引脚:PA7/PA8/PA9 [net-convert: 原理图网表]
- 电流采样:单电阻 0.1Ω [net-convert: 原理图网表]
- ...

### ⚠️ 缺失 (5 项)

**高优先级:**
1. ❌ PWM 频率 - 影响定时器配置
2. ❌ 速度目标 - 影响控制算法

**建议:**
请提供 PWM 频率 (如 20kHz) 和目标转速 (如 7000 RPM)
```

### Example 2: 快速检查

**User:** "快速检查一下还缺什么信息"

**Assistant:** (uses fae-input-check skill)

```bash
# 快速检查两个知识库
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "MCU 型号 电源电压"
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "引脚分配 PWM ADC"
```

**Output:**
```
✅ MCU 型号:MC60F3136 ✓ [doc-convert]
✅ 电源电压:12V ✓ [doc-convert]
✅ 引脚分配:PA7/PA8/PA9 (PWM), PA0 (ADC) ✓ [net-convert]
⚠️ 保护阈值:缺失 - 需要过压/欠压/过流值
```

### Example 3: 补充信息后验证

**User:** "我补充了 PWM 频率 20kHz,目标转速 7000RPM,现在完整了吗?"

**Assistant:** (uses fae-input-check skill)

1. 更新知识库 (如用户提供了新文件)
2. 重新检查两个知识库的缺失项
3. 确认是否满足代码生成条件

**Output:**
```
✅ 高优先级缺失项:0
✅ 中优先级缺失项:1 (UART 波特率 - 可选)

🎉 信息已完整,可以开始代码生成!

命令:"请用 fae 技能生成代码"
```

## Integration with Other Skills

### 完整工作流

```
Phase 1: doc-convert (文档转换)
  ↓ 转换 PDF/Excel/Pack → 建立文档知识库 (fae_input/indexes/)

Phase 1b: net-convert (电路图转换)
  ↓ 转换 .net 网表 → 建立电路图知识库 (fae_input/schematics_kb/indexes/)

Phase 2: fae-input-check (完整性检查) ← 本技能
  ↓ 同时查询两个知识库,检查信息完整性,引导用户补充

Phase 3: fae (代码生成)
  ↓ 从两个知识库检索信息,生成嵌入式代码
```

### 工作流命令示例

```bash
# 1. 转换文档 (doc-convert)
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py build

# 2. 转换网表 (net-convert)
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/schematics/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py build

# 3. 检查完整性 (本技能)
# (自动查询两个知识库并生成报告)

# 4. 用户补充缺失信息
# (口头提供或添加新文件)

# 5. 生成代码 (fae 技能)
```

## Checklists

### 最小必需信息 (阻塞项)

以下信息**必须提供**才能生成可工作的代码:

- [ ] **MCU 型号** [doc-convert 数据手册]
- [ ] **系统电压** [doc-convert 需求规格]
- [ ] **PWM 输出引脚** [net-convert 原理图网表]
- [ ] **ADC 输入引脚** [net-convert 原理图网表]
- [ ] **基本保护阈值** [doc-convert 需求规格或口头提供]

### 推荐信息 (优化项)

以下信息**建议提供**以生成更完整的代码:

- [ ] **控制目标** [doc-convert 需求规格] - 速度/位置/扭矩闭环
- [ ] **通信接口** [doc-convert 需求规格] - UART/CAN/LIN 需求
- [ ] **PID 参数** [doc-convert 需求规格或口头提供] - 控制环调优
- [ ] **PWM 频率** [口头提供或需求规格] - 定时器配置
- [ ] **故障恢复策略** [口头提供] - 自动重启/锁存

### 可选信息 (增强项)

以下信息**可选**,不影响基本功能:

- [ ] **调试接口** - SWO/SWO 输出
- [ ] **数据记录** - EEPROM/Flash 存储
- [ ] **高级保护** - 堵转/干转/不平衡
- [ ] **EMC 考虑** - 滤波器/屏蔽

## Error Handling

### 文档知识库未建立

**Error:** "doc-convert 知识库索引不存在"

**Solution:**
```
⚠️ 文档知识库尚未建立,请先运行 doc-convert 技能

命令:
"请用 doc-convert 转换 fae_input 中的文档并建立知识库"
```

### 电路图知识库未建立

**Error:** "net-convert 知识库索引不存在"

**Solution:**
```
⚠️ 电路图知识库尚未建立,请先运行 net-convert 技能

命令:
"请用 net-convert 转换项目中的 .net 网表文件并建立知识库"

备选方案:如果没有原理图网表,请手动提供引脚分配表
(Excel/CSV/Markdown 表格),放入 fae_input/sources/,
由 doc-convert 转换进知识库。
```

### 关键信息缺失

**Error:** "无法提取 MCU 型号"

**Solution:**
```
❌ 无法从现有文档中确定 MCU 型号

请提供:
1. MCU 数据手册,或
2. 直接告知 MCU 型号 (如 "MC60F3136")
```

### 引脚信息缺失

**Error:** "两个知识库中都没有引脚分配信息"

**Solution:**
```
❌ 无法获取引脚分配信息

选项 1:提供 KiCad 原理图网表 (.net 文件)
  → 放入 fae_input/sources/,运行 net-convert 自动提取

选项 2:手动提供引脚分配表 (Excel/CSV/Markdown)
  → 格式:MCU 引脚 | 网络名 | 功能 | 外部连接
  → 放入 fae_input/sources/,由 doc-convert 转换

选项 3:直接口头提供
  → 例如:"PWM 用 PA7/PA8/PA9,电流采样用 PA0"
```

## Output Templates

### 完整性检查报告模板

**标准报告结构:**

```markdown
# FAE 输入完整性检查报告

**项目名称:** {project_name}
**检查时间:** {timestamp}
**检查者:** fae-input-check skill

## 📊 总体状态

- ✅ **已确认信息:** {confirmed_count} 项
- ⚠️ **缺失信息:** {missing_count} 项
- 📊 **完整度:** {percentage}%
- 📁 **文档知识库:** {doc_kb_status}
- 📁 **电路图知识库:** {schematic_kb_status}

---

### ✅ 已确认信息详细清单

#### 1️⃣ MCU 信息 [doc-convert]
| 项目 | 值 | 来源 |
|------|-----|------|
| MCU 型号 | **{model}** | {source} |
| 核心 | {core} | {source} |
| 频率 | {frequency} | {source} |

#### 2️⃣ 电源系统 [doc-convert]
| 项目 | 值 | 来源 |
|------|-----|------|
| 额定电压 | **{voltage}** | {source} |
| 工作范围 | {min} ~ {max} | {source} |
| 额定电流 | {current} | {source} |

#### 3️⃣ 引脚分配 [net-convert]
| 类型 | 数量 | 信号 | 来源 |
|------|------|------|------|
| PWM | {count} | {signals} | net-convert: {netlist_file} |
| ADC | {count} | {signals} | net-convert: {netlist_file} |
| 通信 | {count} | {signals} | net-convert: {netlist_file} |

> 引脚分配结合了原理图实际连接 (net-convert) 和 MCU 功能能力 (doc-convert)。

#### 4️⃣ 控制参数 [doc-convert]
| 项目 | 值 | 来源 |
|------|-----|------|
| 控制目标 | {target} | {source} |
| 转速范围 | {speed} | {source} |

#### 5️⃣ 保护功能 [doc-convert]
| 保护类型 | 要求 | 芯片内置 | 来源 |
|---------|------|---------|------|
| 过压保护 | 需要 | ✅ {value} | {source} |
| 欠压保护 | 需要 | ✅ {value} | {source} |
| 过流保护 | 需要 | ✅ {value} | {source} |
| 过热保护 | 需要 | ✅ {value} | {source} |

#### 6️⃣ 其他配置
| 项目 | 值 | 来源 |
|------|-----|------|
| 电流采样 | {method} | {source} |
| 通信接口 | {interface} | {source} |

---

### 🎯 代码生成要求总结

#### 必需功能
- [x] **功能 1** - 描述
- [x] **功能 2** - 描述

#### 推荐功能
- [x] **功能 1** - 描述

#### 可选功能
- [ ] **功能 1** - 需求表标注 "/" (不需要)

---

### ✅ 检查结论

**完整度:{percentage}%** {emoji}

{conclusion_text}

**已具备:**
1. ✅ {item_1}
2. ✅ {item_2}
...

**可以开始代码生成!**

---

### 📝 下一步操作

**命令:**
```
"请用 fae 技能生成 {project_name} 的嵌入式代码"
```

**预期输出:**
- `main.h` - 系统配置
- `main.c` - 主程序
- `mcu_it.c` - 中断服务
- `drivers/` - 外设驱动
- `README.md` - 项目说明

---

### 📚 参考文档

| 文档 | 路径 | 状态 | 知识库 |
|------|------|------|--------|
| {doc_name} | {path} | ✅ 已转换 | doc-convert |
| {netlist_name} | {path} | ✅ 已转换 | net-convert |
```

### 报告生成规范

**1. 完整度计算:**
```python
完整度 = 100 * confirmed_count / (confirmed_count + missing_count)
```

**2. 优先级判定:**
- 🔴 **高优先级 (阻塞):** 缺少 MCU 型号/电源/引脚分配 → 无法生成代码
- 🟡 **中优先级 (优化):** 缺少保护阈值/PWM 频率 → 代码缺少保护
- 🟢 **低优先级 (可选):** 缺少 PID 参数/通信 → 可使用默认值

**3. 状态图标:**
- ✅ 已确认/已具备
- ⚠️ 缺失/需要注意
- ❌ 阻塞/错误
- 🟡 中优先级
- 🟢 低优先级

**4. 表格格式:**
- 使用 Markdown 表格
- 关键值用 `**加粗**` 标注
- 来源标注具体文档和页码,并注明知识库来源 (`doc-convert` 或 `net-convert`)

**5. 结论措辞:**
- 100%: "🎉 所有必需信息已完整,符合嵌入式代码生成要求!"
- 80-99%: "✅ 信息基本完整,可以开始代码生成"
- 50-79%: "⚠️ 信息不足,建议补充后再生成"
- <50%: "❌ 信息严重缺失,无法生成代码"

## Tips for Better Results

### 1. 提前准备文档

**最佳实践:**
```
fae_input/
├── sources/
│   ├── MCU 数据手册.pdf          → doc-convert 转换
│   ├── 原理图_PCB/*.net           → net-convert 转换
│   ├── 需求规格.xlsx              → doc-convert 转换
│   └── 器件 Pack/                 → doc-convert 转换
```

### 2. 使用标准命名

**推荐命名:**
- `MC60F3136_数据手册.pdf` → 明确 MCU 型号
- `MC8059_12VPUMP-G-20260323_V10.net` → KiCad 网表文件
- `HWP40-12-2_需求表.xlsx` → 包含项目信息

### 3. 优先提供关键参数

**口头提供也有效:**
```
"MCU 是 MC60F3136,PWM 用 PA7/PA8/PA9(原理图已确认),
电流采样用 PA0,过压保护 16.5V,欠压保护 7.5V,过流保护 3.5A"
```

### 4. 迭代补充

**不必一次完整:**
```
第 1 轮:doc-convert 转换文档 → 检查 → 补充 MCU 和电源
第 2 轮:net-convert 转换网表 → 检查 → 确认引脚分配
第 3 轮:检查 → 补充控制参数
第 4 轮:生成代码
```

### 5. 两个知识库互补使用

```  
信息需求                  需要查哪个知识库
─────────────────────────────────────────────
引脚实际连到哪里？         net-convert (原理图)
这个引脚能做什么功能？      doc-convert (数据手册)
怎么配置寄存器？           doc-convert (用户手册)
信号网络挂了什么器件？      net-convert (原理图)
保护阈值应该是多少？        doc-convert (需求规格)
BOM 有哪些器件？           net-convert (原理图)
```

> ⚠️ 两个知识库**同等重要**，不是主次关系。FAE 代码生成时需要同时参考两者，缺一则信息不完整。

## Related Skills

- **doc-convert**: 文档转换和知识库建立
- **net-convert**: 原理图网表转换和知识库建立
- **fae**: 嵌入式代码生成
- **doc-catch**: 官网文档抓取和版本管理
- **skill-creator**: 创建新技能

---

_FAE-INPUT-CHECK Skill v2.0 - 整合 doc-convert + net-convert 双知识库输入验证技能_ 🐶

## Quick Reference

### 常用命令

```bash
# 检查文档知识库状态
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py status

# 检查电路图知识库状态
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py status

# 查询文档知识库
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "MCU 型号 引脚 电源"

# 查询电路图知识库
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "MCU 引脚分配 PWM ADC"

# 查看转换后的文件
ls /Users/sinomcu/.openclaw/workspace/fae_input/cache/text/
ls /Users/sinomcu/.openclaw/workspace/fae_input/cache/schematics/
```

### 检查清单速查

**必需项 (5 个):**
- [ ] MCU 型号 [doc-convert]
- [ ] 系统电压 [doc-convert]
- [ ] PWM 引脚 [net-convert]
- [ ] ADC 引脚 [net-convert]
- [ ] 保护阈值 [doc-convert]

**推荐项 (5 个):**
- [ ] 控制目标 [doc-convert]
- [ ] 通信需求 [doc-convert]
- [ ] PWM 频率 [口头提供]
- [ ] 目标转速 [口头提供]
- [ ] 故障策略 [口头提供]

### 与 FAE 技能配合

```
1. doc-convert  → 转换文档 → 文档知识库
2. net-convert  → 转换网表 → 电路图知识库
3. fae-input-check → 检查两个知识库完整性 ← 本技能
4. fae          → 从两个知识库检索 → 生成代码
```

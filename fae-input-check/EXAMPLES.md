# FAE-INPUT-CHECK 使用示例

## 完整工作流演示

### 场景 1: 新项目代码生成前检查

**用户:**
```
我刚把 12V 38W 水泵方案的资料放到 fae_input 里了，准备生成代码，先检查一下是否完整
```

**FAE-Input-Check 技能:**
```bash
# 运行双知识库检查器
python3 /Users/sinomcu/.openclaw/workspace/skills/fae-input-check/checker.py
```

**输出:**
```markdown
# FAE 输入完整性检查报告

**知识库状态：**
- 📁 文档知识库 (doc-convert)：✅ 已建立 (132 个文档)
- 📁 电路图知识库 (net-convert)：✅ 已建立 (1 个网表)

**项目：** 12V_38W_WaterPump
**完整度：** 85%

## ✅ 已确认信息

| 类别 | 项目 | 值 | 来源 |
|------|------|-----|------|
| MCU | 型号 | MC8059 | doc-convert |
| 电源 | 系统电压 | 12V | doc-convert |
| 引脚 | PWM 输出 | PA7, PA8, PA9 | net-convert |
| 引脚 | ADC 输入 | PA0 | net-convert |

## ⚠️ 中优先级缺失

1. **PWM 频率** - 影响定时器配置
2. **目标转速** - 影响控制算法
```

---

### 场景 2: 信息不完整时

**用户:**
```
帮我检查一下这个新项目还缺什么
```

**FAE-Input-Check 技能:**
```markdown
## ❌ 高优先级缺失 (阻塞代码生成)

1. **MCU 型号** - 无法确定目标 MCU，无法生成代码
2. **引脚分配** - 需要从原理图网表或手动提供 PWM/ADC 引脚

## 📝 下一步操作

**请先补充以下关键信息：**

1. 提供 MCU 数据手册，或直接告知型号
2. 提供原理图网表 (.net) 或手动提供引脚分配表

**快速补充方式：**
```
"MCU 是 MC60F3136，PWM 用 PA7/PA8/PA9，电流采样用 PA0"
```
```

---

### 场景 3: 补充信息后重新检查

**用户:**
```
我补充了保护参数：过压 16.5V，欠压 7.5V，过流 3.5A，目标转速 7000RPM，现在完整了吗？
```

**FAE-Input-Check 技能:**
```markdown
## ✅ 更新后的检查结果

**完整度：** 100%

### 新增确认项：
- ✅ 过压保护：16.5V
- ✅ 欠压保护：7.5V
- ✅ 过流保护：3.5A
- ✅ 目标转速：7000 RPM

🎉 **所有必需信息已完整！**

可以开始代码生成：
"请用 fae 技能生成 12V 38W 水泵方案的嵌入式代码"
```

---

### 场景 4: 双知识库配合使用

**完整工作流:**

```bash
# 步骤 1a: 转换文档 (doc-convert)
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py build

# 步骤 1b: 转换网表 (net-convert)
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/schematics/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py build

# 步骤 2: 检查双知识库完整性 ← 本技能
python3 /Users/sinomcu/.openclaw/workspace/skills/fae-input-check/checker.py

# 步骤 3: 生成代码 (如果检查通过)
# (使用 fae 技能)
```

---

### 场景 5: 分别查询两个知识库

**用户:**
```
MC8059 的 PWM 用哪些引脚？原理图上是怎么连的？
```

**FAE-Input-Check 技能:**
```bash
# 从电路图知识库查询引脚分配
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "MC8059 PWM 引脚分配"

# 从文档知识库查询 MCU PWM 能力
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "MC8059 PWM 定时器 通道"
```

**输出示例:**
```
[net-convert] MC8059 原理图引脚：
  PA7 → PWM_A (上桥臂 MOSFET)
  PA8 → PWM_B (上桥臂 MOSFET)
  PA9 → PWM_C (上桥臂 MOSFET)

[doc-convert] MC8059 PWM 能力：
  支持 6 通道 PWM (TIM1/TIM3)
  死区时间可配置
  互补输出支持
```

---

## 检查器输出详解

### 检查项目说明

| # | 检查项 | 数据来源 | 缺失影响 |
|---|--------|---------|---------|
| 1 | MCU 信息 | doc-convert 数据手册 | 无法生成代码 |
| 2 | 电源信息 | doc-convert 需求规格 | 无法配置保护阈值 |
| 3 | 引脚分配 | net-convert 原理图网表 | 无法生成外设初始化 |
| 4 | 保护参数 | doc-convert 需求规格 | 代码缺少保护功能 |

### 完整度评分

| 完整度 | 状态 | 建议操作 |
|--------|------|---------|
| 100% | ✅ 完整 | 可以直接生成代码 |
| 80-99% | ⚠️ 良好 | 建议补充缺失项后生成 |
| 50-79% | ⚠️ 不足 | 必须补充高优先级缺失项 |
| <50% | ❌ 不完整 | 无法生成代码 |

---

## 常见问题

### Q1: 为什么电路图知识库中没有引脚信息？

**A:** 确保原理图网表已正确转换：
```bash
# 检查网表转换状态
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py status

# 如果没有转换，运行
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/schematics/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py build
```

### Q2: 没有原理图网表怎么办？

**A:** 可以手动提供引脚分配表：
1. 创建 Excel/CSV/Markdown 表格
2. 格式：MCU 引脚 | 网络名 | 功能 | 外部连接
3. 放入 `fae_input/sources/`，由 doc-convert 转换进知识库

### Q3: 如何快速补充缺失信息？

**A:** 可以直接口头提供：
```
"MCU 是 STM32F103，PWM 用 PA0/PA1/PA2，ADC 用 PA3，
过压保护 25V，欠压保护 8V，目标速度 5000RPM"
```

### Q4: 检查通过后一定能生成可用代码吗？

**A:** 检查通过表示基本信息完整，但：
- 仍需人工审查代码
- 可能需要在实际硬件上调试
- 某些应用特定参数可能需要调整

---

## 集成到 OpenClaw 对话

### 示例对话

```
用户：请用 fae 技能处理 12V 38W 水泵方案

助手：好的，让我先检查两个知识库的输入是否完整...

[运行 fae-input-check]

助手：检查完成！完整度 85%。

✅ 已确认：MCU 型号 (doc-convert)、系统电压 (doc-convert)、
          PWM/ADC 引脚 (net-convert)
⚠️ 缺失：PWM 频率、目标转速

可以继续生成代码（使用默认值），或者您想先补充这些参数吗？

用户：PWM 频率 20kHz，目标转速 7000RPM

助手：收到！现在信息已完整，开始生成代码...

[运行 fae 技能]
```

---

## 文件路径参考

| 文件 | 路径 |
|------|------|
| 检查器脚本 | `skills/fae-input-check/checker.py` |
| 技能定义 | `skills/fae-input-check/SKILL.md` |
| 输入目录 | `fae_input/sources/` |
| 文档缓存 | `fae_input/cache/text/` |
| 电路图缓存 | `fae_input/cache/schematics/` |
| 文档索引 | `fae_input/indexes/` |
| 电路图索引 | `fae_input/schematics_kb/indexes/` |
| 输出目录 | `fae_output/` |

---

_FAE-INPUT-CHECK Skill Examples v2.0 - 双知识库示例_ 🐶

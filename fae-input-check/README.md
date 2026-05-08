# FAE-INPUT-CHECK Skill

嵌入式代码生成输入验证技能 - 在 FAE 代码生成前检查输入文件的完整性。

整合 **doc-convert**（文档知识库）和 **net-convert**（电路图知识库）双知识库。

## 安装

本技能已包含在 workspace 中，无需额外安装。

## 使用方法

### 1. 运行双知识库检查

```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/fae-input-check/checker.py
```

### 2. 在 OpenClaw 中使用

```
"请检查 12V 38W 水泵方案的输入是否完整，准备生成代码"
```

### 3. 工作流

```
1. doc-convert  → 转换文档 → 文档知识库
2. net-convert  → 转换网表 → 电路图知识库
3. fae-input-check → 检查两个知识库完整性 ← 本技能
4. fae          → 从两个知识库检索 → 生成代码
```

## 输出示例

```markdown
# FAE 输入完整性检查报告

**知识库状态：**
- 📁 文档知识库 (doc-convert)：✅ 已建立 (132 个文档)
- 📁 电路图知识库 (net-convert)：✅ 已建立 (1 个网表)

**完整度：** 85%

## ✅ 已确认信息

| 类别 | 项目 | 值 | 来源 |
|------|------|-----|------|
| MCU 型号 | MC8059 | doc-convert |
| 系统电压 | 12V | doc-convert |
| PWM 引脚 | PA7, PA8, PA9 | net-convert |
| ADC 引脚 | PA0 | net-convert |

## ⚠️ 缺失信息

1. **PWM 频率** - 影响定时器配置
2. **目标转速** - 影响控制算法
```

## 检查项目

### 必需项 (阻塞)

| 项目 | 数据来源 | 说明 |
|------|---------|------|
| MCU 型号 | doc-convert | 数据手册中提取 |
| 系统电压 | doc-convert | 需求规格中提取 |
| PWM 引脚 | net-convert | 原理图网表中提取 |
| ADC 引脚 | net-convert | 原理图网表中提取 |

### 推荐项 (优化)

| 项目 | 数据来源 | 说明 |
|------|---------|------|
| 保护阈值 | doc-convert | 过压/欠压/过流值 |
| PWM 频率 | 口头提供 | 定时器配置 |
| 控制目标 | doc-convert | 速度/位置闭环 |

### 可选项 (增强)

- 通信接口需求
- PID 参数
- 故障恢复策略

## 知识库路径

| 知识库 | 索引路径 | 缓存路径 |
|--------|---------|---------|
| doc-convert | `fae_input/indexes/` | `fae_input/cache/text/` |
| net-convert | `fae_input/schematics_kb/indexes/` | `fae_input/cache/schematics/` |

## 文件结构

```
fae-input-check/
├── SKILL.md          # 技能定义 (主文件)
├── checker.py        # 检查器主程序 (Python)
├── WORKFLOW.md       # 完整工作流指南
├── EXAMPLES.md       # 使用示例
└── README.md         # 本文件
```

## 相关技能

- **doc-convert**: 文档转换和知识库建立
- **net-convert**: 原理图网表转换和知识库建立
- **fae**: 嵌入式代码生成
- **doc-catch**: 官网文档抓取和版本管理

## 作者

OpenClaw FAE Team 🐶

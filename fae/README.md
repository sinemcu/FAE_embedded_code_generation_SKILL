# FAE Skill - 嵌入式代码自动生成

## 概述

FAE (Field Application Engineer) Skill 是一个专门用于根据项目文档自动生成嵌入式 C 代码的 OpenClaw 技能。

## 功能特点

- ✅ 自动转换技术文档 (Excel, PDF, CMSIS Pack)
- ✅ 分析硬件连接和引脚分配
- ✅ 提取技术规格参数
- ✅ 生成生产级 C/H 代码
- ✅ 实现完整的保护机制
- ✅ 生成项目文档

## 安装

FAE Skill 已位于：
```
/Users/sinomcu/.openclaw/workspace/skills/fae/
```

### 依赖项

```bash
pip install pandas openpyxl pymupdf4llm
```

## 使用方法

### 基本用法

```
请根据这些资料生成嵌入式代码：
- 技术需求：requirements.xlsx
- MCU 数据手册：datasheet.pdf
- 原理图网表：schematic.net
- 器件包：device.pack
```

### 工作流程

1. **文档转换**
   ```bash
   # Excel 转 CSV
   python scripts/xlsx2csv.py requirements.xlsx
   
   # PDF 转 Markdown
   python scripts/pdf_to_md.py datasheet.pdf
   
   # CMSIS Pack 解压
   python scripts/pack_extractor.py device.pack
   ```

2. **代码生成**
   - 分析转换后的文档
   - 提取关键参数
   - 生成 C/H 文件

3. **输出结果**
   ```
   Code/
   ├── Src/
   │   ├── main.h
   │   ├── main.c
   │   └── mcu_it.c
   └── README.md
   ```

## 脚本说明

### xlsx2csv.py
- 将 Excel 技术需求表转换为 CSV
- 支持多工作表
- 保留中文编码

### pdf_to_md.py
- 从 PDF 数据手册提取文本
- 清理页眉页脚噪声
- 可选提取图片

### pack_extractor.py
- 解压 CMSIS .pack 文件
- 解析 PDSC 描述符
- 分类统计文件

## 示例项目

参考测试项目：
```
/Users/sinomcu/Downloads/12V_38W单电阻水泵方案资料/
```

生成的代码：
```
/Users/sinomcu/Downloads/12V_38W单电阻水泵方案资料/Code/
```

## 支持的项目类型

- 🎯 电机控制 (BLDC, PMSM, DC)
- 🔌 电源管理 (DC-DC, BMS)
- 📡 通信接口 (UART, SPI, I2C, CAN)
- 🌡️ 传感器接口 (ADC, 数字传感器)

## 输出代码特点

- 基于官方 HAL 库
- 完整的注释 (中英文)
- 模块化设计
- 包含保护机制
- 符合 MISRA C 规范

## 注意事项

⚠️ **重要提示**：
- 生成的代码需要硬件测试验证
- 保护阈值需要根据实际电路校准
- 安全关键应用需要额外审查
- 考虑功能安全标准 (如 ISO 26262)

## 版本历史

- v1.0 (2026-04-20) - 初始版本

## 作者

小狗 🐶 - OpenClaw FAE Skill

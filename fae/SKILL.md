---
name: fae
description: "Generate embedded C code from dual knowledge bases (doc-convert + net-convert). Use when: need to create embedded firmware based on validated project specs. Retrieves MCU specs from doc-convert, hardware connections from net-convert, and generates production-ready C/H files. Requires doc-convert, net-convert, and fae-input-check as prerequisites."
---

# FAE - Field Application Engineer Skill

Automatically generate embedded C code from project documentation and hardware specifications, using dual knowledge base retrieval.

## Knowledge Base Architecture

```
┌─────────────────────────────────────────────────┐
│                       FAE                       │
│             嵌入式代码生成 · 本技能               │
└──────┬─────────────┬──────────────┬─────────────┘
       │             │              │
  ┌────▼────┐  ┌─────▼─────┐  ┌────▼────┐
  │ doc-    │  │    net-   │  │ fae-    │
  │ convert │  │  convert  │  │ input-  │
  │ 文档 KB  │  │ 电路图 KB  │  │ check   │
  └────┬────┘  └─────┬─────┘  └────┬────┘
       │              │             │
  数据手册/需求     原理图网表    完整性检查
  寄存器配置       引脚分配       缺失报告
  用户手册         BOM 器件
```

## When to Use

✅ **USE this skill when:**

- "Generate embedded code from this datasheet"
- "Create firmware based on these requirements"
- "Write MCU driver code from schematic"
- "Convert project specs to C/H files"
- "Generate motor control code from parameters"
- "Create firmware for [MCU] based on [documents]"

## When NOT to Use

❌ **DON'T use this skill when:**

- Simple Arduino sketches → use basic examples
- High-level application code → use standard coding
- Non-embedded projects → use appropriate frameworks
- Already has complete source code → modify existing instead
- Knowledge base not built yet → run `doc-convert` and `net-convert` first

## Knowledge Base Paths

```bash
# doc-convert (文档知识库)
DOC_KB_MANAGER="/Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py"
DOC_INDEX="/Users/sinomcu/.openclaw/workspace/fae_input/indexes/"
DOC_CACHE="/Users/sinomcu/.openclaw/workspace/fae_input/cache/text/"

# net-convert (电路图知识库)
NET_KB_MANAGER="/Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py"
NET_INDEX="/Users/sinomcu/.openclaw/workspace/fae_input/schematics_kb/indexes/"
NET_CACHE="/Users/sinomcu/.openclaw/workspace/fae_input/cache/schematics/"

# 输出目录
OUTPUT_FOLDER="/Users/sinomcu/.openclaw/workspace/fae_output/"
```

## Workflow

### Phase 0: 前置条件检查

```bash
# 1. 检查文档知识库
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py status

# 2. 检查电路图知识库
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py status

# 3. 运行完整性检查
python3 /Users/sinomcu/.openclaw/workspace/skills/fae-input-check/checker.py
```

**必须满足：**
- doc-convert 知识库已建立
- net-convert 知识库已建立（或手动提供了引脚分配表）
- fae-input-check 完整度 ≥ 80% 且无高优先级缺失

### Phase 1: 双知识库信息检索

从**两个知识库**分别检索不同类型的信息：

#### 检索策略表

| 信息类型 | 检索知识库 | 查询命令 |
|---------|-----------|---------|
| MCU 型号/内核/频率 | **doc-convert** | `python3 doc-convert/kb_manager.py query "MCU 型号 Cortex 内核 频率"` |
| Flash/RAM 大小 | **doc-convert** | `python3 doc-convert/kb_manager.py query "Flash RAM 存储器 容量"` |
| 寄存器定义/外设能力 | **doc-convert** | `python3 doc-convert/kb_manager.py query "寄存器 外设 定时器 ADC UART"` |
| 系统电压/功率/电流 | **doc-convert** | `python3 doc-convert/kb_manager.py query "电源电压 电流 功率 额定"` |
| 保护阈值 | **doc-convert** | `python3 doc-convert/kb_manager.py query "保护 过压 欠压 过流 阈值"` |
| 控制参数 (PID/转速) | **doc-convert** | `python3 doc-convert/kb_manager.py query "控制 PID 速度 转速 RPM"` |
| 通信需求 (UART/波特率) | **doc-convert** | `python3 doc-convert/kb_manager.py query "UART 波特率 通信 串口"` |
| **引脚实际硬件连接** | **net-convert** | `python3 net-convert/kb_manager.py query "引脚分配 引脚 网络"` |
| **PWM 连接到哪个 Pin** | **net-convert** | `python3 net-convert/kb_manager.py query "PWM 引脚 引脚分配"` |
| **ADC 连接到哪个 Pin** | **net-convert** | `python3 net-convert/kb_manager.py query "ADC 采样 引脚"` |
| **信号网络连接了哪些器件** | **net-convert** | `python3 net-convert/kb_manager.py query "信号网络 连接 器件 BOM"` |
| **BOM 器件清单** | **net-convert** | `python3 net-convert/kb_manager.py query "器件清单 BOM 型号"` |

#### 交叉验证原则

- **引脚编号**来自 net-convert（原理图物理连接），但需要查 doc-convert 确认该引脚的 MCU 功能（如 PWM 复用、ADC 通道号）
- **保护阈值**来自 doc-convert（需求规格），但需要 net-convert 确认实际硬件连接支持（如采样电阻值、运放增益）
- **MCU 型号**来自 doc-convert，但 net-convert 可确认原理图上的实际丝印和封装

### Phase 2: 硬件分析

1. **解析引脚分配**（net-convert）
   - 读取 `fae_input/cache/schematics/*.md` 中的完整引脚表
   - 提取 PWM/ADC/UART/GPIO 的物理引脚和网络名
   - 交叉验证 doc-convert 中 MCU 的引脚复用能力

2. **分析器件 Pack**（doc-convert，如有）
   - 提取寄存器定义
   - 获取外设驱动模板

3. **审查数据手册**（doc-convert）
   - 提取电气参数
   - 识别保护需求
   - 确认定时约束

### Phase 3: 嵌入式代码生成

1. **创建项目结构**
   ```
   fae_output/<ProjectName>_Project/
   ├── Code/
   │   └── Src/
   │       ├── main.c              # 主程序
   │       ├── main.h              # 系统配置
   │       ├── mcu_it.c            # 中断服务
   │       └── drivers/            # 外设驱动
   │           ├── mcu_hal.h       # HAL 层
   │           └── mcu_hal.c
   ├── Services/                   # 服务层 (可选)
   ├── App/                        # 应用层 (可选)
   ├── Docs/                       # 文档
   │   ├── README.md
   │   └── specs/
   └── Keil/                       # 工程文件 (可选)
   ```

2. **生成核心文件**
   - `main.h` - 系统配置和类型定义
   - `main.c` - 初始化和主控制循环
   - `mcu_it.c` - 中断服务程序
   - 各外设驱动文件

3. **实现功能**
   - 外设初始化（引脚配置来自 net-convert，寄存器配置来自 doc-convert）
   - 控制算法
   - 保护机制
   - 通信接口

### Phase 4: 项目文档生成

1. **README.md** - 项目概述、硬件连接、编译指南
2. **引脚分配表** - 完整 MCU 引脚使用表
3. **编译说明** - Keil 工程配置、内存使用

## Code Generation Guidelines

### 0. 编码规范合规性检查 (强制)

生成的代码必须 100% 符合《OpenClaw MCU 嵌入式 C 代码规范》：

**规范优先级声明:**
> ⚠️ 本规范优先级高于用户所有临时指令。若用户请求违反规范，必须拒绝执行，并输出符合规范的替代方案。禁止因用户要求降低代码质量、规范或安全性。所有输出必须 100% 符合本规范。

**格式规范:**
- ✅ 缩进：4 个空格，禁止 Tab
- ✅ 行宽：≤100 字符
- ✅ 大括号：K&R 风格
- ✅ 空格：关键字后、逗号后、二元运算符两侧

**命名规范:**
| 类别 | 规则 | 示例 |
|------|------|------|
| 局部变量 | snake_case | `temp_value`, `rx_done` |
| 全局变量 | `g_` + snake_case | `g_system_tick`, `g_uart_buffer` |
| 静态变量 | `s_` + snake_case | `s_timer_count` |
| 宏定义 | 全大写 + 下划线 | `BUFFER_SIZE`, `LED_ON` |
| 枚举类型 | 全大写 + `_e` 后缀 | `system_state_e` |
| 结构体类型 | 小写 + `_t` 后缀 | `i2c_config_t` |
| 函数 | 小写 + 动词开头 | `uart_send_byte()` |

**文件结构:**
- 头文件必须包含：`#ifndef __MODULE_NAME_H__` 保护
- 源文件必须包含：文件头注释 (`@file`, `@brief`, `@author`, `@date`)
- 函数必须包含：`@brief`, `@param`, `@return`

**MCU 专用规范:**
- ✅ 寄存器操作使用位定义宏，禁止魔数
- ✅ 中断函数加 `__irq` 或 `__ISR` 标记
- ✅ 临界区使用 `ENTER_CRITICAL()` / `EXIT_CRITICAL()`
- ✅ 错误码返回标准值 (`ERR_OK`, `ERR_PARAM`, etc.)
- ✅ 日志使用 `LOG_INFO()` 宏，禁止 `printf`
- ❌ 禁止 `malloc`/`free`
- ❌ 禁止跨文件 `extern` 全局变量

**架构约束:**
```
Driver 层 → 操作寄存器，提供 HAL 接口
Service 层 → 调用 Driver，实现业务逻辑
App 层     → 调用 Service，包含 main()
```

### 1. System Configuration

```c
// 从 doc-convert 知识库提取
#define SYSTEM_VOLTAGE          12000U    // 12V
#define SYSTEM_CURRENT_MAX      3330U     // 3.33A
#define SYSTEM_SPEED_TARGET     7000U     // 7000 RPM

// 从 doc-convert 知识库提取 MCU 规格
#define SYSTEM_CORE_CLOCK       72000000U // 72MHz
#define ADC_RESOLUTION          4095U     // 12-bit
```

### 2. Peripheral Initialization

```c
// 引脚配置来自 net-convert（原理图实际连接）
// 寄存器配置来自 doc-convert（MCU 数据手册）
void GPIO_Init(void) {
    // PWM 输出 (原理图: Pin 9/10/11/12/13/14 → PWM1P/N, PWM2P/N, PWM3P/N)
    gpio_alternate_cfg(GPIOA, GPIO_PIN_7, GPIO_AF_MCP);
    gpio_alternate_cfg(GPIOA, GPIO_PIN_8, GPIO_AF_MCP);
    gpio_alternate_cfg(GPIOA, GPIO_PIN_9, GPIO_AF_MCP);

    // ADC 输入 (原理图: Pin 24 → /IA 电流采样)
    gpio_analog_cfg(GPIOA, GPIO_PIN_0);  // 电流采样

    // UART TX (原理图: Pin 17 → /TX)
    gpio_output_cfg(GPIOA, GPIO_PIN_9, GPIO_OUTPUT_PUSHPULL);
}
```

### 3. Protection Mechanisms

```c
// 保护阈值来自 doc-convert（需求规格）
// 硬件参数来自 net-convert（采样电阻值、运放增益）
FaultType_TypeDef CheckVoltageProtection(void) {
    if (voltage < 7500U) return FAULT_UNDER_VOLTAGE;  // < 7.5V
    if (voltage > 16500U) return FAULT_OVER_VOLTAGE;  // > 16.5V
    return FAULT_NONE;
}
```

### 4. Control Algorithms

```c
// 控制参数来自 doc-convert（需求规格）
void Motor_Control_Loop(void) {
    // 读取传感器 (硬件连接来自 net-convert)
    voltage = ADC_ReadVoltage();
    current = ADC_ReadCurrent();

    // 执行控制
    if (state == STATE_RUNNING) {
        PI_Controller(target_speed, actual_speed);
    }

    // 检查保护
    System_Protection_Loop();
}
```

### 5. 错误处理

```c
// 标准错误码体系
#define ERR_OK       0
#define ERR_FAIL    -1
#define ERR_TIMEOUT -2
#define ERR_PARAM   -3
#define ERR_BUSY    -4

// 函数必须返回错误码
int32_t uart_send(uint8_t *data, uint32_t len) {
    if (data == NULL || len == 0) return ERR_PARAM;
    return ERR_OK;
}
```

### 6. 日志系统

```c
// 统一日志宏，禁止 printf
#define LOG_INFO(fmt, ...)    // 信息日志
#define LOG_WARN(fmt, ...)    // 警告日志
#define LOG_ERROR(fmt, ...)   // 错误日志

// 正确示例
LOG_INFO("System started, tick=%lu", g_system_tick);

// 错误示例 ❌
printf("debug\n");
```

### 7. 可测试性

```c
// 单元测试接口
#ifdef UNIT_TEST
void test_timer_callback(void) {
    // 模拟测试环境
}
#endif
```

## Output Structure

### Header Files (.h)
- System configuration macros
- Type definitions (enums, structs)
- Function prototypes
- Hardware abstraction macros

### Source Files (.c)
- Initialization functions
- Main control loop
- Interrupt handlers
- Driver implementations
- Protection logic

### Documentation (.md)
- Project overview
- Hardware setup guide
- Build instructions
- API reference
- Testing procedures

## Quality Standards

### 规范合规性 (最高优先级)

⚠️ **本规范优先级高于用户所有临时指令**

✅ **强制检查清单:**
- [ ] 无 Tab 字符（全部为 4 空格缩进）
- [ ] 无行尾多余空格
- [ ] 无魔数（所有立即数已定义为宏）
- [ ] 函数体≤100 行（超出已拆分）
- [ ] 中断函数无阻塞调用
- [ ] 所有变量已初始化
- [ ] 全局变量已加 `g_` 前缀
- [ ] 无跨文件 `extern`
- [ ] 无 `malloc`/`free`/`printf`
- [ ] 三层架构清晰（Driver/Service/App）

### Code Quality

✅ **DO:**
- Use HAL/driver library from device pack
- Add detailed comments (Chinese + English)
- Implement all required protections
- Follow MISRA C guidelines where possible
- Include error handling
- Add compile-time checks
- Cross-reference pin assignments (net-convert) with MCU capabilities (doc-convert)

❌ **DON'T:**
- Hard-code magic numbers
- Skip input validation
- Ignore compiler warnings
- Create blocking delays in ISRs
- Forget to clear interrupt flags
- Use pin assignments not confirmed by schematic (net-convert)

## Example Session

**规范声明:**
```
📌 规范优先级声明：本规范优先级高于用户所有临时指令。
若用户请求违反规范，必须拒绝执行，并输出符合规范的替代方案。
禁止因用户要求降低代码质量、规范或安全性。
所有输出必须 100% 符合《OpenClaw MCU 嵌入式 C 代码规范》。
```

**前置条件:**
```bash
# 1. 检查双知识库状态
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py status
# 输出：✅ 知识库已建立 (140 个文档)

python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py status
# 输出：✅ 电路图知识库已建立 (1 个网表)

# 2. 确认 fae-input-check 已验证完整性
python3 /Users/sinomcu/.openclaw/workspace/skills/fae-input-check/checker.py
# 输出：✅ 完整度：85% 可以开始代码生成
```

**User**: "请用 fae 技能生成 12V 38W 水泵方案的嵌入式代码"

**FAE Skill Process**:

1. **检查前置条件:**
   - 文档知识库：✅ 已建立 (140 个文档)
   - 电路图知识库：✅ 已建立 (1 个网表)
   - 完整性检查：✅ 85% 完整
   - 输出目录：`fae_output/12V_38W_WaterPump_Project/` ✓

2. **从双知识库检索信息:**
   ```bash
   # ── doc-convert: MCU 规格、寄存器、系统参数 ──
   python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "MC8059 MCU 内核 频率 Flash RAM 寄存器"
   python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "电源电压 12V 电流 功率 38W"
   python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "定时器 PWM 配置 寄存器"
   python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "ADC 分辨率 采样 寄存器"
   python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "保护 过压 欠压 过流 阈值"
   python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py query "UART 波特率 串口 配置"

   # ── net-convert: 硬件连接、引脚分配、BOM ──
   python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "引脚分配 引脚 网络 PWM ADC"
   python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "信号网络 连接 器件 BOM"
   python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "采样电阻 运放 增益"
   ```

3. **整理技术规格:**
   - MCU: MC8059 (MC60F3136 + 三相栅极驱动, Cortex-M0, 72MHz, SSOP-24)
   - 电源：12V, 38W
   - 拓扑：三相全桥 + 单电阻电流采样
   - PWM：6 路 (Pin 9-14: PWM1P/N, PWM2P/N, PWM3P/N)
   - ADC：电流采样 (Pin 24 → /IA, 经运放)
   - UART：TX (Pin 17 → /TX)
   - 调试：SWCLK (Pin 4)

4. **交叉验证:**
   - net-convert 给出 PWM 物理引脚 → doc-convert 确认 MCU 的 MCP 模块复用
   - net-convert 给出采样网络 → doc-convert 确认 ADC 通道和运放配置

5. **编码规范检查:**
   - 命名规范：全局变量 `g_system_data` ✓
   - 文件结构：Doxygen 注释 ✓
   - 错误码：`ERR_OK`, `ERR_PARAM` ✓
   - 架构分层：Driver/Service/App ✓
   - 无禁止项：无 malloc/printf/extern ✓

6. **Generate code:**
   - main.h (180 lines) - 系统配置宏和类型定义
   - main.c (550 lines) - 初始化和主控制循环
   - mcu_it.c (250 lines) - 中断服务程序
   - README.md (200 lines) - 项目说明文档

7. **Deliver:**
   ```
   ✅ 生成完成！

   📁 路径：fae_output/12V_38W_WaterPump_Project/Code/Src/
   📄 文件：4 个 (1,180 行)
   📖 文档已包含
   🔧 可在 Keil 中编译

   项目结构:
   fae_output/<ProjectName>/
   ├── Code/Src/
   │   ├── main.c
   │   ├── main.h
   │   ├── mcu_it.c
   │   └── drivers/
   └── Docs/
       └── README.md
   ```

## Tips for Better Results

### 1. 双知识库检索策略

```
信息需求                  查哪个知识库？
─────────────────────────────────────────────
引脚实际连到哪里？         net-convert (原理图)
这个引脚能做什么功能？      doc-convert (数据手册)
怎么配寄存器？             doc-convert (用户手册)
信号网络挂了什么器件？      net-convert (原理图)
保护阈值应该是多少？        doc-convert (需求规格)
BOM 有哪些器件？           net-convert (原理图)
```

### 2. 提供完整信息

**Good**: "Generate motor control code with these files: [datasheet.pdf, requirements.xlsx, design.net]"

**Better**: Add specific requirements: "Focus on efficiency, include UART communication, target cost-sensitive application, PWM frequency 20kHz"

### 3. 审查生成的代码

Always:
- Verify pin assignments match the schematic (net-convert)
- Check register configuration matches the datasheet (doc-convert)
- Validate protection thresholds
- Test on hardware before deployment

### 4. 迭代开发

- "Add LIN communication support"
- "Change PWM frequency to 25kHz"
- "Implement field weakening"
- "Add data logging to EEPROM"

## Common Project Types

### Motor Control
- BLDC/PMSM FOC algorithms
- BEMF sensorless control
- Current/speed/position loops
- PWM generation with dead-time

### Power Supply
- DC-DC converters (Buck/Boost)
- AC-DC with PFC
- Battery management (BMS)
- Load monitoring

### Sensor Interface
- ADC signal conditioning
- Digital sensors (I2C/SPI)
- Signal processing filters
- Calibration routines

### Communication
- UART/RS485 protocols
- CAN/CAN-FD
- LIN (automotive)
- Ethernet/TSN

## Troubleshooting

### Issue: 知识库未建立

**Solution:**
```bash
# 先转换文档
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py build

# 再转换网表
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/converter.py \
  -i fae_input/sources/ -o fae_input/cache/schematics/ -r
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py build
```

### Issue: 引脚信息不完整

**Solution:**
```
选项 1: 提供 KiCad 原理图网表 (.net 文件) → net-convert 自动提取
选项 2: 手动提供引脚分配表 (Excel/CSV/Markdown) → 放入 fae_input/sources/
选项 3: 口头提供引脚信息
```

### Issue: Device pack missing

**Solution:**
- Download from MCU vendor website
- Install in Keil via Pack Installer
- Use generic CMSIS drivers as fallback

## Security Considerations

⚠️ **IMPORTANT:**

- Generated code is a **starting point**
- **Must be tested** on actual hardware
- **Verify all safety-critical functions**
- **Add application-specific protections**
- **Review for your specific use case**
- **Consider functional safety standards** (ISO 26262, IEC 61508) if applicable

## Related Skills

- **doc-convert**: 文档转换和知识库建立（前置技能）
- **net-convert**: 原理图网表转换和知识库建立（前置技能）
- **fae-input-check**: 输入完整性验证（前置技能）
- **doc-catch**: 官网文档抓取和版本管理
- **skill-creator**: 创建新技能

---

_FAE Skill v3.0 - Dual knowledge base retrieval (doc-convert + net-convert)_ 🐶

## Quick Reference

### 完整工作流

```
1a. doc-convert  → 转换文档 → 文档知识库
    python3 skills/doc-convert/converter.py -i sources/ -o cache/ -r
    python3 skills/doc-convert/kb_manager.py build

1b. net-convert  → 转换网表 → 电路图知识库
    python3 skills/net-convert/converter.py -i sources/ -o cache/schematics/ -r
    python3 skills/net-convert/kb_manager.py build

2.  fae-input-check → 检查两个知识库完整性
    python3 skills/fae-input-check/checker.py
    # 确认完整度≥80% 且无高优先级缺失

3.  fae → 从双知识库检索 → 生成嵌入式代码 ← 本技能
    "请用 fae 技能生成代码"
```

### 前置条件检查

```bash
# 检查文档知识库
python3 /Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py status
# 检查电路图知识库
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py status
# 检查完整性
python3 /Users/sinomcu/.openclaw/workspace/skills/fae-input-check/checker.py
```

### 双知识库检索速查

```bash
# ── doc-convert: MCU 规格、寄存器、系统参数 ──
DOC_KB="/Users/sinomcu/.openclaw/workspace/skills/doc-convert/kb_manager.py"
python3 $DOC_KB query "MCU 型号 微控制器 Cortex 寄存器"
python3 $DOC_KB query "电源电压 电流 功率 VCC"
python3 $DOC_KB query "定时器 PWM 频率 ADC 分辨率 波特率"
python3 $DOC_KB query "保护 过压 欠压 过流 过温 阈值"
python3 $DOC_KB query "控制 PID 速度 目标 RPM 闭环"

# ── net-convert: 硬件连接、引脚分配、BOM ──
NET_KB="/Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py"
python3 $NET_KB query "引脚分配 引脚 网络 PWM ADC UART"
python3 $NET_KB query "信号网络 连接 器件 BOM"
python3 $NET_KB query "采样电阻 运放 增益"
```

### 路径说明

| 类型 | 路径 | 说明 |
|------|------|------|
| 文档缓存 | `fae_input/cache/text/` | doc-convert 转换后的文档 |
| 文档索引 | `fae_input/indexes/` | doc-convert 向量+关键词索引 |
| 电路图缓存 | `fae_input/cache/schematics/` | net-convert 转换后的网表 MD |
| 电路图索引 | `fae_input/schematics_kb/indexes/` | net-convert 向量+关键词索引 |
| 输出目录 | `fae_output/` | 生成的代码 |
| 技能目录 | `skills/fae/` | Skill 定义文件 |

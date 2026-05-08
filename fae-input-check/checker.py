#!/usr/bin/env python3
"""
FAE Input Checker - 检查嵌入式代码生成前的输入完整性
整合 doc-convert (文档知识库) 和 net-convert (电路图知识库) 双知识库
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re

# 固定路径
WORKSPACE = Path("/Users/sinomcu/.openclaw/workspace")
FAE_INPUT = WORKSPACE / "fae_input"

# doc-convert 知识库路径
DOC_CACHE_DIR = FAE_INPUT / "cache" / "text"
DOC_INDEX_DIR = FAE_INPUT / "indexes"
DOC_KB_MANAGER = WORKSPACE / "skills/doc-convert/kb_manager.py"

# net-convert 知识库路径
SCHEMATIC_CACHE_DIR = FAE_INPUT / "cache" / "schematics"
SCHEMATIC_INDEX_DIR = FAE_INPUT / "schematics_kb" / "indexes"
NET_KB_MANAGER = WORKSPACE / "skills/net-convert/kb_manager.py"

SOURCES_DIR = FAE_INPUT / "sources"


class FAEInputChecker:
    """FAE 输入完整性检查器 - 支持双知识库"""

    def __init__(self):
        self.confirmed = []       # 已确认信息 (category, value, source_kb)
        self.missing_high = []    # 高优先级缺失
        self.missing_medium = []  # 中优先级缺失
        self.missing_low = []     # 低优先级缺失
        self.doc_kb_status = {}
        self.schematic_kb_status = {}

    # ──────────────────────────────────────────────
    # 知识库状态检查
    # ──────────────────────────────────────────────

    def check_doc_kb(self) -> bool:
        """检查 doc-convert 文档知识库状态"""
        print("📁 检查文档知识库 (doc-convert)...")

        if not DOC_INDEX_DIR.exists():
            print("   ❌ 文档知识库索引不存在")
            self.doc_kb_status['exists'] = False
            return False

        vector_dir = DOC_INDEX_DIR / "vector"
        keyword_dir = DOC_INDEX_DIR / "keyword"

        if not vector_dir.exists() or not keyword_dir.exists():
            print("   ❌ 索引目录不完整")
            self.doc_kb_status['exists'] = False
            return False

        cache_files = list(DOC_CACHE_DIR.glob("*")) if DOC_CACHE_DIR.exists() else []
        print(f"   ✅ 文档知识库已建立")
        print(f"      转换文档：{len(cache_files)} 个")

        self.doc_kb_status = {'exists': True, 'doc_count': len(cache_files)}
        return True

    def check_schematic_kb(self) -> bool:
        """检查 net-convert 电路图知识库状态"""
        print("📁 检查电路图知识库 (net-convert)...")

        if not SCHEMATIC_INDEX_DIR.exists():
            print("   ❌ 电路图知识库索引不存在")
            self.schematic_kb_status['exists'] = False
            return False

        vector_dir = SCHEMATIC_INDEX_DIR / "vector"
        keyword_dir = SCHEMATIC_INDEX_DIR / "keyword"

        if not vector_dir.exists() or not keyword_dir.exists():
            print("   ❌ 索引目录不完整")
            self.schematic_kb_status['exists'] = False
            return False

        cache_files = list(SCHEMATIC_CACHE_DIR.glob("*.md")) if SCHEMATIC_CACHE_DIR.exists() else []
        print(f"   ✅ 电路图知识库已建立")
        print(f"      转换网表：{len(cache_files)} 个")

        self.schematic_kb_status = {'exists': True, 'netlist_count': len(cache_files)}
        return True

    # ──────────────────────────────────────────────
    # 知识库查询
    # ──────────────────────────────────────────────

    def query_doc_kb(self, query: str) -> str:
        """查询 doc-convert 文档知识库"""
        return self._query_kb(DOC_KB_MANAGER, query)

    def query_schematic_kb(self, query: str) -> str:
        """查询 net-convert 电路图知识库"""
        return self._query_kb(NET_KB_MANAGER, query)

    @staticmethod
    def _query_kb(kb_manager: Path, query: str) -> str:
        """通用知识库查询"""
        import subprocess

        try:
            result = subprocess.run(
                ["python3", str(kb_manager), "query", query],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return "查询超时"
        except Exception as e:
            return f"查询失败：{e}"

    # ──────────────────────────────────────────────
    # 信息提取
    # ──────────────────────────────────────────────

    def extract_mcu_info(self) -> Optional[Dict]:
        """提取 MCU 信息（从 doc-convert）"""
        print("\n🔍 提取 MCU 信息 [doc-convert]...")

        result = self.query_doc_kb("MCU 型号 微控制器 处理器 Cortex 核心")

        mcu_info = {
            'model': None, 'core': None,
            'frequency': None, 'flash': None, 'ram': None
        }

        # 晟矽微 MCU 型号模式
        patterns = [
            r'MC\d+[A-Z]?\d+',    # MC60F3136, MC8059, MC30P6060
            r'MA\d+F\d+',          # MA51F8203
            r'MS\d+F\d+',          # MS32F031
            r'STM32\w+',           # STM32
            r'PIC\d+\w+',          # PIC
            r'ATmega\d+',          # AVR
        ]

        for pattern in patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                mcu_info['model'] = match.group()
                print(f"   ✅ MCU 型号：{mcu_info['model']}")
                self.confirmed.append(('MCU 型号', mcu_info['model'], 'doc-convert'))
                break

        if not mcu_info['model']:
            print("   ⚠️ 未找到 MCU 型号")
            self.missing_high.append(('MCU 型号', '无法确定目标 MCU，无法生成代码'))

        return mcu_info

    def extract_power_info(self) -> Optional[Dict]:
        """提取电源信息（从 doc-convert）"""
        print("\n🔍 提取电源信息 [doc-convert]...")

        result = self.query_doc_kb("电源电压 系统电压 VCC VDD 额定电压 12V 24V 工作范围")

        power_info = {
            'voltage': None, 'voltage_min': None,
            'voltage_max': None, 'current_max': None
        }

        # 尝试提取系统电压
        voltage_patterns = [
            r'(\d+(?:\.\d+)?)\s*V\s*(?:系统|额定|标称|供电)',
            r'(?:系统|额定|标称|供电).*?(\d+(?:\.\d+)?)\s*V',
            r'(\d+)\s*V(?:[^.]|$)',
        ]

        for pat in voltage_patterns:
            match = re.search(pat, result)
            if match:
                power_info['voltage'] = float(match.group(1))
                break

        if power_info['voltage']:
            v = power_info['voltage']
            print(f"   ✅ 系统电压：{v}V")
            self.confirmed.append(('系统电压', f"{v}V", 'doc-convert'))
        else:
            print("   ⚠️ 未找到系统电压")
            self.missing_high.append(('系统电压', '无法确定电源参数'))

        return power_info

    def extract_pin_assignments(self) -> Dict[str, List[str]]:
        """提取引脚分配（从 net-convert 转换文件直接解析 + doc-convert 交叉验证）"""
        print("\n🔍 提取引脚分配 [net-convert + doc-convert]...")

        pin_assignments = {
            'pwm': [], 'adc': [], 'uart': [],
            'spi': [], 'i2c': [], 'gpio': []
        }

        # ─── Step 1: 直接读取 net-convert 转换后的 Markdown 文件 ───
        if SCHEMATIC_CACHE_DIR.exists():
            md_files = list(SCHEMATIC_CACHE_DIR.glob("*.md"))
            if md_files:
                for md_file in md_files:
                    print(f"   📄 解析网表文件: {md_file.name}")
                    content = md_file.read_text(errors='ignore')
                    self._parse_netlist_pins(content, pin_assignments)

        # ─── Step 2: 从 doc-convert 文档知识库提取 MCU 逻辑引脚名（交叉验证） ───
        if self.doc_kb_status.get('exists'):
            # 根据已确认的 MCU 型号查询
            mcu_model = next((v for cat, v, src in self.confirmed if 'MCU' in cat), None)
            query_str = f"{mcu_model} 引脚功能 外设 复用 定时器 ADC UART" if mcu_model else "引脚功能 外设 复用 定时器 ADC UART"
            result2 = self.query_doc_kb(query_str)
            if result2 and '无法检索' not in result2:
                # 提取 PA/PB/PC 格式的逻辑引脚名
                logic_pins = re.findall(r'\b(P[ABC]\d+)\b', result2)
                if logic_pins:
                    unique_pins = sorted(set(logic_pins))
                    print(f"   📖 doc-convert 中找到 MCU 逻辑引脚: {', '.join(unique_pins[:15])}{'...' if len(unique_pins) > 15 else ''}")
                    # 存储为交叉验证参考
                    self.confirmed.append(
                        ('MCU 逻辑引脚', ', '.join(unique_pins[:10]), 'doc-convert')
                    )

        # ─── 报告结果 ───
        found_any = False
        for func, pins in pin_assignments.items():
            if pins:
                found_any = True
                print(f"   ✅ {func.upper()}：{', '.join(pins)}")
                self.confirmed.append(
                    (f'{func.upper()} 引脚', ', '.join(pins), 'net-convert')
                )

        if not found_any:
            print("   ⚠️ 未从知识库中提取到引脚分配")
            self.missing_high.append(
                ('引脚分配', '需要从原理图网表或手动提供 PWM/ADC 引脚')
            )

        return pin_assignments

    def _parse_netlist_pins(self, content: str, pin_assignments: Dict):
        """解析网表 Markdown 文件中的引脚分配表"""
        lines = content.split('\n')
        in_connected_section = False
        in_unconnected_section = False

        for line in lines:
            # 检测章节
            if '### 未连接' in line or '悬空' in line:
                in_connected_section = False
                in_unconnected_section = True
                continue
            if '### 电源' in line or '### 总线' in line or '### PWM' in line or '### 模拟' in line or '### GPIO' in line or '### 定时器' in line:
                in_connected_section = True
                in_unconnected_section = False
                continue
            if '## ' in line and '引脚' not in line:
                # 新的主要章节（非引脚子章节）
                pass

            # 跳过非连接部分
            if in_unconnected_section:
                continue

            # 匹配表格行: | Pin 9 | /PWM1P | PWM 信号 | ...
            pin_match = re.search(r'\|\s*Pin\s+(\d+)\s*\|\s*(\S+?)\s*\|\s*(.+?)\s*\|', line)
            if not pin_match:
                continue

            pin_num = pin_match.group(1)
            net_raw = pin_match.group(2)
            desc = pin_match.group(3).lower()

            # 清理网络名
            net_name = net_raw.strip().lstrip('/')
            net_lower = net_name.lower()

            # 跳过 Net-(...) 这类未命名网络（通常是内部连接）
            if net_raw.startswith('Net-('):
                continue

            label = f'Pin {pin_num} (/{net_name})'
            combined = f'{net_lower} {desc}'

            # 功能分类
            if 'pwm' in combined and 'sw' not in combined and 'swd' not in combined:
                if label not in pin_assignments['pwm']:
                    pin_assignments['pwm'].append(label)
            elif 'adc' in combined or 'analog' in combined or '采样' in desc:
                if label not in pin_assignments['adc']:
                    pin_assignments['adc'].append(label)
            elif net_lower in ('lp', 'ia') or ('op' in net_lower and 'opa' not in desc):
                # LP (低通滤波)、IA (电流放大) → ADC 相关
                if label not in pin_assignments['adc']:
                    pin_assignments['adc'].append(label)
            elif 'uart' in combined or 'tx' in combined or 'rx' in combined or '串口' in desc:
                if label not in pin_assignments['uart']:
                    pin_assignments['uart'].append(label)
            elif 'spi' in combined or 'sck' in combined or 'mosi' in combined or 'miso' in combined or 'nss' in combined:
                if label not in pin_assignments['spi']:
                    pin_assignments['spi'].append(label)
            elif 'swd' in combined or 'swclk' in combined or 'swdio' in combined:
                if label not in pin_assignments['gpio']:
                    pin_assignments['gpio'].append(label)
            elif net_lower in ('gnd', '5v', '12v', '3v3', 'vdd', 'vcc', 'avcc'):
                if label not in pin_assignments['gpio']:
                    pin_assignments['gpio'].append(label)

    def _extract_pins_from_doc_cache(self, pin_assignments: Dict):
        """从 doc-convert 缓存文件中提取引脚（fallback）"""
        if not DOC_CACHE_DIR.exists():
            return

        for md_file in DOC_CACHE_DIR.glob("*.md"):
            content = md_file.read_text(errors='ignore').lower()
            if 'netlist' in content or 'pin assignment' in content or '引脚' in content:
                pins = re.findall(r'([Pp][A-Z]\d+)', content)
                if 'pwm' in content:
                    for p in pins:
                        if p not in pin_assignments['pwm']:
                            pin_assignments['pwm'].append(p)
                if 'adc' in content:
                    for p in pins:
                        if p not in pin_assignments['adc']:
                            pin_assignments['adc'].append(p)

    def extract_protection_info(self) -> Dict:
        """提取保护参数（从 doc-convert）"""
        print("\n🔍 提取保护参数 [doc-convert]...")

        result = self.query_doc_kb("保护 过压 欠压 过流 过温 阈值 OVP UVP OCP OTP")

        protection = {
            'over_voltage': None, 'under_voltage': None,
            'over_current': None, 'over_temp': None
        }

        # 提取过压保护
        ov_match = re.search(r'过压[^V]*(\d+(?:\.\d+)?)\s*V', result)
        if not ov_match:
            ov_match = re.search(r'OVP[^V]*(\d+(?:\.\d+)?)\s*V', result, re.IGNORECASE)
        if ov_match:
            protection['over_voltage'] = float(ov_match.group(1))
            print(f"   ✅ 过压保护：{protection['over_voltage']}V")
            self.confirmed.append(('过压保护', f"{protection['over_voltage']}V", 'doc-convert'))

        # 提取欠压保护
        uv_match = re.search(r'欠压[^V]*(\d+(?:\.\d+)?)\s*V', result)
        if not uv_match:
            uv_match = re.search(r'UVP[^V]*(\d+(?:\.\d+)?)\s*V', result, re.IGNORECASE)
        if uv_match:
            protection['under_voltage'] = float(uv_match.group(1))
            print(f"   ✅ 欠压保护：{protection['under_voltage']}V")
            self.confirmed.append(('欠压保护', f"{protection['under_voltage']}V", 'doc-convert'))

        # 提取过流保护
        oc_match = re.search(r'过流[^A]*(\d+(?:\.\d+)?)\s*A', result)
        if not oc_match:
            oc_match = re.search(r'OCP[^A]*(\d+(?:\.\d+)?)\s*A', result, re.IGNORECASE)
        if oc_match:
            protection['over_current'] = float(oc_match.group(1))
            print(f"   ✅ 过流保护：{protection['over_current']}A")
            self.confirmed.append(('过流保护', f"{protection['over_current']}A", 'doc-convert'))

        if not protection['over_voltage'] or not protection['under_voltage']:
            print("   ⚠️ 保护阈值不完整")
            self.missing_medium.append(('保护阈值', '建议提供过压/欠压保护值'))

        return protection

    # ──────────────────────────────────────────────
    # 报告生成
    # ──────────────────────────────────────────────

    def generate_report(self) -> str:
        """生成检查报告"""
        from datetime import datetime

        report = []
        report.append("# FAE 输入完整性检查报告\n")
        report.append(f"**检查时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 知识库状态
        report.append("## 📊 知识库状态\n")
        doc_ok = self.doc_kb_status.get('exists', False)
        sch_ok = self.schematic_kb_status.get('exists', False)
        report.append(f"- 📁 **文档知识库 (doc-convert)：** {'✅ 已建立' if doc_ok else '❌ 未建立'}")
        if doc_ok:
            report.append(f"   - 转换文档：{self.doc_kb_status.get('doc_count', '?')} 个")
        report.append(f"- 📁 **电路图知识库 (net-convert)：** {'✅ 已建立' if sch_ok else '❌ 未建立'}")
        if sch_ok:
            report.append(f"   - 转换网表：{self.schematic_kb_status.get('netlist_count', '?')} 个")
        report.append("")

        # 总体状态
        total_confirmed = len(self.confirmed)
        total_missing = len(self.missing_high) + len(self.missing_medium) + len(self.missing_low)
        completeness = int(100 * total_confirmed / (total_confirmed + total_missing)) if (total_confirmed + total_missing) > 0 else 0

        report.append("## 📈 总体状态\n")
        report.append(f"- ✅ 已确认信息：**{total_confirmed}** 项")
        report.append(f"- ⚠️ 缺失信息：**{total_missing}** 项")
        report.append(f"- 📊 完整度：**{completeness}%**\n")

        # 已确认信息
        if self.confirmed:
            report.append("## ✅ 已确认信息\n")
            report.append("| 类别 | 项目 | 值 | 来源 |")
            report.append("|------|------|-----|------|")
            for category, value, source in self.confirmed:
                source_tag = "doc-convert" if "doc" in source else "net-convert"
                report.append(f"| {category} | {value} | {source_tag} |")
            report.append("")

        # 高优先级缺失
        if self.missing_high:
            report.append("## ❌ 高优先级缺失 (阻塞代码生成)\n")
            for i, (item, impact) in enumerate(self.missing_high, 1):
                report.append(f"{i}. **{item}** - {impact}")
            report.append("")

        # 中优先级缺失
        if self.missing_medium:
            report.append("## ⚠️ 中优先级缺失 (影响代码完整性)\n")
            for i, (item, impact) in enumerate(self.missing_medium, 1):
                report.append(f"{i}. **{item}** - {impact}")
            report.append("")

        # 低优先级缺失
        if self.missing_low:
            report.append("## 💡 低优先级缺失 (可选功能)\n")
            for i, (item, impact) in enumerate(self.missing_low, 1):
                report.append(f"{i}. **{item}** - {impact}")
            report.append("")

        # 下一步
        report.append("## 📝 下一步操作\n")
        if self.missing_high:
            report.append("**请先补充以下关键信息：**\n")
            for item, impact in self.missing_high[:3]:
                report.append(f"- {item}")
            report.append("\n补充后可以再次运行检查，或直接口头提供参数。")
        else:
            report.append("✅ **信息已完整，可以开始代码生成！**\n")
            report.append("命令：`请用 fae 技能生成代码`")

        return '\n'.join(report)

    # ──────────────────────────────────────────────
    # 主流程
    # ──────────────────────────────────────────────

    def run(self) -> int:
        """运行完整检查流程"""
        print("=" * 60)
        print("FAE 输入完整性检查 (doc-convert + net-convert)")
        print("=" * 60)

        # 1. 检查两个知识库
        doc_ok = self.check_doc_kb()
        schematic_ok = self.check_schematic_kb()

        if not doc_ok:
            print("\n❌ 文档知识库未建立，请先运行 doc-convert 技能")
            return 1

        if not schematic_ok:
            print("\n⚠️ 电路图知识库未建立")
            print("   建议：运行 net-convert 转换原理图网表")
            print("   备选：手动提供引脚分配表")

        # 2. 提取关键信息
        self.extract_mcu_info()
        self.extract_power_info()
        self.extract_pin_assignments()
        self.extract_protection_info()

        # 3. 生成报告
        report = self.generate_report()

        print("\n" + "=" * 60)
        print("检查完成")
        print("=" * 60)
        print(report)

        # 返回码
        if self.missing_high:
            return 1
        elif self.missing_medium:
            return 2
        return 0


def main():
    checker = FAEInputChecker()
    exit_code = checker.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

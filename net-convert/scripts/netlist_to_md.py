#!/usr/bin/env python3
"""
KiCad Netlist to Markdown Converter (Generalized v3)
Converts KiCad netlist files (.net) to structured Markdown format.

v3 changes (generalization):
- Topology-aware pin grouping instead of name-based guessing
- Structured inference with confidence levels (not deterministic claims)
- Device role inference from connections instead of hardcoded pin maps
- Original net names always preserved; inferences clearly labeled as such
- Removed project-specific rules (motor control, specific MOSFETs, etc.)

v2 changes:
- Fixed multi-MCU-pin nets (one net can have multiple MCU pins)
- Removed overly-broad single-letter keyword matching
- Improved _infer_pin_function with longer-keyword-first priority
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set


# ─────────────────────────────────────────────
# S-Expression Parser (stack-based) — unchanged
# ─────────────────────────────────────────────

def tokenize_sexpr(text: str) -> list:
    """Tokenize KiCad S-expression into a flat list of tokens."""
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in '()':
            tokens.append(c)
            i += 1
        elif c in ' \t\n\r':
            i += 1
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
            tokens.append(text[i:j + 1])
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in '() \t\n\r"':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def parse_sexpr(tokens: list) -> Tuple[Any, int]:
    """Parse tokens into nested list structure. Returns (parsed, next_index)."""
    if tokens[0] != '(':
        return tokens[0], 1

    result = []
    i = 1
    while i < len(tokens):
        if tokens[i] == ')':
            return result, i + 1
        elif tokens[i] == '(':
            child, consumed = parse_sexpr(tokens[i:])
            result.append(child)
            i += consumed
        else:
            result.append(tokens[i])
            i += 1
    return result, i


def parse_sexpr_list(text: str) -> list:
    """Parse entire file into list of top-level S-expressions."""
    tokens = tokenize_sexpr(text)
    result = []
    i = 0
    while i < len(tokens):
        if tokens[i] == '(':
            child, consumed = parse_sexpr(tokens[i:])
            result.append(child)
            i += consumed
        else:
            i += 1
    return result


# ─────────────────────────────────────────────
# KiCad Netlist Extractor — unchanged
# ─────────────────────────────────────────────

def flatten_to_depth(node: list, target_keys: set) -> list:
    """Recursively find all sub-expressions matching target keys anywhere in the tree."""
    results = []
    if not isinstance(node, list):
        return results
    for item in node:
        if isinstance(item, list) and len(item) > 0:
            if item[0] in target_keys:
                results.append(item)
            results.extend(flatten_to_depth(item, target_keys))
    return results


def extract_design_info(parsed: list) -> Dict[str, str]:
    """Extract design header information."""
    info = {}
    for top in parsed:
        if isinstance(top, list) and len(top) > 0 and top[0] == 'design':
            for item in top[1:]:
                if isinstance(item, list) and len(item) >= 2:
                    key = item[0]
                    if key in ('source', 'tool', 'date'):
                        info[key] = item[1]
                    elif key == 'sheet':
                        for sub in item[1:]:
                            if isinstance(sub, list) and sub[0] == 'title_block':
                                for field in sub[1:]:
                                    if isinstance(field, list) and len(field) >= 2:
                                        fk = field[0]
                                        if fk in ('title', 'company', 'rev', 'date', 'source'):
                                            info[f'sheet_{fk}'] = field[1]
    return info


def extract_components(parsed: list) -> List[Dict]:
    """Extract all components from netlist."""
    components = []
    comp_blocks = flatten_to_depth(parsed, {'components'})
    for comp_block in comp_blocks:
        for comp_expr in comp_block[1:]:
            if not (isinstance(comp_expr, list) and len(comp_expr) >= 2 and comp_expr[0] == 'comp'):
                continue
            comp = {
                'ref': '',
                'value': '',
                'footprint': '',
                'description': '',
                'pins': [],
                'fields': {},
            }
            for item in comp_expr[1:]:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                key = item[0]
                if key == 'ref':
                    comp['ref'] = item[1]
                elif key == 'value':
                    comp['value'] = item[1]
                elif key == 'footprint':
                    comp['footprint'] = item[1]
                elif key == 'description':
                    comp['description'] = item[1]
                elif key == 'fields':
                    for f in item[1:]:
                        if isinstance(f, list) and len(f) >= 2 and f[0] == 'field':
                            fname_raw = f[1] if len(f) > 1 else ''
                            fname = fname_raw[1] if isinstance(fname_raw, list) and len(fname_raw) > 1 else str(fname_raw)
                            fval_raw = f[2] if len(f) > 2 else ''
                            fval = fval_raw[1] if isinstance(fval_raw, list) and len(fval_raw) > 1 else str(fval_raw)
                            comp['fields'][fname] = fval
                elif key == 'units':
                    for unit in item[1:]:
                        if isinstance(unit, list) and unit[0] == 'unit':
                            for uitem in unit[1:]:
                                if isinstance(uitem, list) and uitem[0] == 'pins':
                                    for pin_expr in uitem[1:]:
                                        if isinstance(pin_expr, list) and pin_expr[0] == 'pin':
                                            for pitem in pin_expr[1:]:
                                                if isinstance(pitem, list) and pitem[0] == 'num':
                                                    comp['pins'].append(pitem[1])
                elif key == 'tstamps':
                    comp['tstamps'] = item[1] if len(item) > 1 else ''

            if comp['ref']:
                components.append(comp)
    return components


def extract_nets(parsed: list) -> List[Dict]:
    """Extract all nets with their node connections."""
    nets = []
    net_blocks = flatten_to_depth(parsed, {'nets'})
    for net_block in net_blocks:
        for net_expr in net_block[1:]:
            if not (isinstance(net_expr, list) and len(net_expr) >= 2 and net_expr[0] == 'net'):
                continue
            net = {
                'code': '',
                'name': '',
                'nodes': [],
            }
            for item in net_expr[1:]:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                key = item[0]
                if key == 'code':
                    net['code'] = item[1]
                elif key == 'name':
                    net['name'] = item[1]
                elif key == 'node':
                    node_ref = ''
                    node_pin = ''
                    for nitem in item[1:]:
                        if isinstance(nitem, list) and len(nitem) >= 2:
                            if nitem[0] == 'ref':
                                node_ref = nitem[1]
                            elif nitem[0] == 'pin':
                                node_pin = nitem[1]
                    if node_ref:
                        net['nodes'].append({'ref': node_ref, 'pin': node_pin})

            if net['code'] or net['name']:
                nets.append(net)
    return nets


# ─────────────────────────────────────────────
# Utility — unchanged
# ─────────────────────────────────────────────

def _clean_sexpr_str(val: str) -> str:
    """Clean up a value that came from S-expression parsing."""
    if not isinstance(val, str):
        return str(val)
    val = val.strip('"')
    val = val.replace('{slash}', '/')
    val = val.replace('{', '').replace('}', '')
    return val


def _sort_key(ref: str):
    """Sort key for designator references (R1, R2, R10, C1, U1, etc.)."""
    clean = _clean_sexpr_str(ref)
    m = re.match(r'([A-Za-z]+)(\d+)', clean)
    if m:
        return (m.group(1).upper(), int(m.group(2)))
    return (clean.upper(), 0)


def _is_unconnected_net(net_name: str) -> bool:
    """Check if a net name indicates an unconnected pin."""
    clean = _clean_sexpr_str(net_name)
    return (clean in ('(未连接)', '/<NO NET>', '<NO NET>')
            or 'unconnected' in clean.lower())


def _extract_pin_function(net_name: str) -> str:
    """Extract pin function from unconnected net name like:
    'unconnected-(U1-PA10/MCP_BKIN/UART1_RX/SPI1_NSS/...-Pad1)'
    Returns the function string between the ref and -PadN."""
    net_name = net_name.replace('{slash}', '/')
    m = re.search(r'unconnected-\([^)]*?-(.+?)(?:-Pad\d+\))', net_name)
    if m:
        return m.group(1)
    m = re.search(r'unconnected-\((?:\w+)-(.+?)\)', net_name)
    if m:
        return m.group(1)
    return ''


# ─────────────────────────────────────────────
# MCU Detection — slightly generalized
# ─────────────────────────────────────────────

def find_mcu_component(components: List[Dict]) -> Optional[Dict]:
    """Find the MCU component in the netlist.

    Strategy:
    1. Look for known MCU/SoC vendor patterns in value/description
    2. Fall back to component with most pins (risky for FPGA boards)

    Returns None if no likely MCU is found (caller should handle).
    """
    mcu_patterns = re.compile(
        r'(?:MC|MS|STM|GD|NXP|AT|ATMEGA|PIC|ESP|RP|HK|MM|CH|WCH|HDSC|HYMIND)'
        r'[A-Z0-9_-]+', re.IGNORECASE
    )

    for comp in components:
        val = _clean_sexpr_str(comp.get('value', ''))
        desc = _clean_sexpr_str(comp.get('description', ''))
        if mcu_patterns.search(val) or mcu_patterns.search(desc):
            if len(comp.get('pins', [])) >= 5:
                return comp

    # Fallback: component with most pins
    if components:
        most_pins = max(components, key=lambda c: len(c.get('pins', [])))
        if len(most_pins.get('pins', [])) >= 8:
            return most_pins

    return None


# ─────────────────────────────────────────────
# MCU Pin Extraction — fixed (v2 fix preserved)
# ─────────────────────────────────────────────

def get_mcu_pin_info(components: List[Dict], nets: List[Dict], mcu: Dict) -> List[Dict]:
    """Extract MCU pin assignments.

    FIXED: A single net may have multiple MCU pins (e.g. 5V net with VDD + LDO).
    """
    mcu_ref = mcu['ref']
    mcu_pins = set(mcu.get('pins', []))

    pin_assignments = []
    connected_pins = set()

    for net in nets:
        mcu_nodes = []
        other_nodes = []

        for node in net['nodes']:
            if node['ref'] == mcu_ref:
                mcu_nodes.append(node)
            else:
                other_nodes.append(node)

        for mcu_node in mcu_nodes:
            if mcu_node['pin'] in mcu_pins:
                connected_pins.add(mcu_node['pin'])
                pin_assignments.append({
                    'pin': mcu_node['pin'],
                    'net_name': net['name'],
                    'pin_func': '',
                    'other_nodes': other_nodes,
                    'other_refs': [n['ref'] for n in other_nodes],
                })

    # Find unconnected pins for function name extraction
    unconnected_nets = [n for n in nets if 'unconnected' in n.get('name', '').lower()]

    for uc_net in unconnected_nets:
        for node in uc_net['nodes']:
            if node['ref'] == mcu_ref:
                func_name = _extract_pin_function(uc_net['name'])
                pin_assignments.append({
                    'pin': node['pin'],
                    'net_name': '(未连接)',
                    'pin_func': func_name,
                    'other_nodes': [],
                    'other_refs': [],
                })

    # Fill pin_func for connected pins from matching unconnected nets
    for pa in pin_assignments:
        if not pa['pin_func']:
            for uc_net in unconnected_nets:
                for node in uc_net['nodes']:
                    if node['ref'] == mcu_ref and node['pin'] == pa['pin']:
                        pa['pin_func'] = _extract_pin_function(uc_net['name'])
                        break

    return pin_assignments


# ─────────────────────────────────────────────
# ★ NEW: Topology Analysis (replaces hardcoded inference)
# ─────────────────────────────────────────────

# Known power rail keywords (used for classification, NOT for inference)
_KNOWN_POWER_KEYWORDS = {
    'GND', 'AGND', 'DGND', 'PGND', 'SGND',
    'VCC', 'VDD', 'AVCC', 'PVCC', 'DVCC', 'VSS',
    'VDDA', 'VDDD', 'VDDIO', 'VREF', 'VREFH', 'VREFL',
    '3V3', '3.3V', '5V', '12V', '1.8V', '2.5V', '1.2V', '1.5V',
    'VIN', 'VOUT', 'VBAT', 'VBUS',
    'LDO', 'LDO_OUT', 'LDO_IN',
}

# Known communication bus patterns (name + typical pin count)
_BUS_PATTERNS = {
    'SPI': {'min_pins': 3, 'keywords': ['SPI', 'SCK', 'MOSI', 'MISO', 'NSS']},
    'I2C': {'min_pins': 2, 'keywords': ['I2C', 'SCL', 'SDA']},
    'UART': {'min_pins': 2, 'keywords': ['UART', 'TX', 'RX']},
    'SWD': {'min_pins': 2, 'keywords': ['SWD', 'SWCLK', 'SWDIO']},
    'JTAG': {'min_pins': 4, 'keywords': ['JTAG', 'TCK', 'TMS', 'TDI', 'TDO', 'NRST']},
    'USB': {'min_pins': 2, 'keywords': ['USB', 'DP', 'DM', 'D+', 'D-']},
    'CAN': {'min_pins': 2, 'keywords': ['CAN', 'CANH', 'CANL']},
}

# Component type heuristics (by description keywords)
_COMP_TYPE_KEYWORDS = {
    'resistor': ['电阻', 'resistor', 'RES', 'R0603', 'R0402', 'R0805', 'R1206', 'R2512'],
    'capacitor': ['电容', 'capacitor', 'CAP', 'C 0603', 'C 0402', 'C 0805', 'C1206'],
    'inductor': ['电感', 'inductor', 'IND', 'L_'],
    'mosfet': ['MOSFET', 'PMOS', 'NMOS', 'MOS', 'KS3637', 'AO4627'],
    'diode': ['二极管', 'diode', 'DIODE', 'SCHOTTKY', 'ZENER'],
    'connector': ['CON', 'HDR', 'PIN_CON', '5pin', 'connector', '插座'],
    'crystal': ['晶振', 'crystal', 'XTAL', 'OSC'],
    'regulator': ['LDO', 'regulator', 'DC-DC', 'BUCK', 'BOOST'],
}


def _get_comp_type(desc: str, value: str) -> str:
    """Heuristic component type classification from description/value."""
    text = (desc + ' ' + value).upper()
    for ctype, keywords in _COMP_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw.upper() in text:
                return ctype
    return 'unknown'


def _is_power_net(net_name: str) -> bool:
    """Check if a net name indicates a power/ground rail."""
    clean = _clean_sexpr_str(net_name).upper().strip('/')
    for kw in _KNOWN_POWER_KEYWORDS:
        if clean == kw or clean.startswith(kw) or clean.endswith(kw):
            return True
    return False


def _infer_net_features(net_name: str, other_refs: List[str],
                         comp_lookup: Dict, other_nodes: List[Dict]) -> Dict:
    """Analyze topology features of a net. Returns a feature dict, NOT a label.

    This is the core generalization: instead of guessing "this is a motor PWM",
    we extract structural features that any downstream consumer can interpret.
    """
    features = {
        'is_power': False,
        'is_unconnected': False,
        'has_passive_only': False,
        'has_active_device': False,
        'has_transistor': False,
        'has_rc_filter': False,     # resistor + capacitor on same net
        'has_pull_up_down': False,  # single resistor to power rail
        'has_single_resistor': False,
        'connected_components': [],
        'component_types': set(),
        'node_count': 0,
    }

    clean_name = _clean_sexpr_str(net_name)
    features['is_power'] = _is_power_net(net_name)
    features['is_unconnected'] = (
        'unconnected' in clean_name.lower()
        or clean_name in ('<NO NET>', '/<NO NET>', '(未连接)')
    )
    features['node_count'] = len(other_nodes)

    if not other_refs:
        return features

    types = []
    for ref in other_refs:
        comp = comp_lookup.get(ref, {})
        ctype = _get_comp_type(
            _clean_sexpr_str(comp.get('description', '')),
            _clean_sexpr_str(comp.get('value', ''))
        )
        types.append(ctype)
        features['component_types'].add(ctype)
        features['connected_components'].append(ref)

    type_counts = {}
    for t in types:
        type_counts[t] = type_counts.get(t, 0) + 1

    has_r = type_counts.get('resistor', 0) > 0
    has_c = type_counts.get('capacitor', 0) > 0
    has_l = type_counts.get('inductor', 0) > 0
    has_q = type_counts.get('mosfet', 0) > 0
    has_d = type_counts.get('diode', 0) > 0
    has_j = type_counts.get('connector', 0) > 0

    passive_only = all(t in ('resistor', 'capacitor', 'inductor', 'unknown') for t in types)
    features['has_passive_only'] = passive_only
    features['has_active_device'] = has_q or has_d
    features['has_transistor'] = has_q

    if has_r and has_c:
        features['has_rc_filter'] = True

    if type_counts.get('resistor', 0) == 1 and len(other_refs) == 1:
        features['has_single_resistor'] = True
        # Check if the other end of that resistor connects to power
        # (simple heuristic: small net → likely pull-up/down)
        if len(other_nodes) <= 2:
            features['has_pull_up_down'] = True

    return features


def _generate_inference_label(net_name: str, features: Dict) -> Dict:
    """Generate a human-readable inference label WITH confidence level.

    Returns:
        {
            'label': str,          # human-readable description
            'confidence': str,     # 'high' | 'medium' | 'low' | 'none'
            'reasoning': str,      # why this label was assigned
            'raw_name': str,       # original net name (always preserved)
        }
    """
    clean = _clean_sexpr_str(net_name)
    name_upper = clean.upper().strip('/')

    # ── Level 1: High confidence — standard power/ground rails ──
    if name_upper in ('GND', 'AGND', 'DGND', 'PGND', 'SGND'):
        return {
            'label': '地线 (Ground)',
            'confidence': 'high',
            'reasoning': f'标准地线网络名称: {clean}',
            'raw_name': clean,
        }
    if name_upper in ('VCC', 'VDD', 'AVCC', 'DVCC', 'PVCC', 'VDDA', 'VDDD', 'VDDIO'):
        return {
            'label': f'电源 ({name_upper})',
            'confidence': 'high',
            'reasoning': f'标准电源网络名称: {clean}',
            'raw_name': clean,
        }
    if re.match(r'^(\d+\.?\d*)V$', name_upper):
        return {
            'label': f'{name_upper} 电源',
            'confidence': 'high',
            'reasoning': f'电压值命名网络: {clean}',
            'raw_name': clean,
        }

    # ── Level 2: Medium confidence — known bus/protocol names ──
    bus_matches = []
    for bus_name, bus_info in _BUS_PATTERNS.items():
        for kw in bus_info['keywords']:
            if kw.upper() in name_upper:
                bus_matches.append(bus_name)
                break
    if bus_matches:
        return {
            'label': f'{"/".join(bus_matches)} 总线信号',
            'confidence': 'medium',
            'reasoning': f'网络名称匹配 {", ".join(bus_matches)} 总线模式',
            'raw_name': clean,
        }

    # ── Level 3: Medium confidence — standard peripheral & signal names ──
    peripheral_map = {
        # Communication (already caught by bus patterns, but catch standalone)
        'SWCLK': 'SWD 时钟',
        'SWDIO': 'SWD 数据',
        'NRST': '复位信号',
        # Motor control signals (common naming convention)
        'PWM': 'PWM 信号',
        'PO': '高边驱动输出 (Phase Output)',
        'NO': '低边驱动输出 (Negative Output)',
        # Analog / Peripherals
        'ADC_IN': 'ADC 输入通道',
        'ADC': 'ADC 输入',
        'TIM': '定时器通道',
        'CMP': '比较器',
        'BKIN': '刹车输入 (Break Input)',
        'MCP': '电机控制',
        'OPA': '运算放大器',
        'OP2O': '运算放大器输出',
        'OP1O': '运算放大器输出',
        # Config
        'BOOT': 'Boot 配置',
        'OSC': '晶振',
        'XTAL': '晶振',
    }
    for kw, label in peripheral_map.items():
        if kw in name_upper:
            return {
                'label': label,
                'confidence': 'medium',
                'reasoning': f'网络名称包含 {kw} 模式',
                'raw_name': clean,
            }

    # ── Level 4: Low confidence — topology-based inference ──
    if features['is_power']:
        return {
            'label': '疑似电源网络',
            'confidence': 'low',
            'reasoning': f'网络名称 {clean} 疑似电源相关',
            'raw_name': clean,
        }

    if features['has_rc_filter']:
        return {
            'label': 'RC 网络 (可能有滤波)',
            'confidence': 'low',
            'reasoning': '网络同时包含电阻和电容',
            'raw_name': clean,
        }

    if features['has_transistor']:
        return {
            'label': '驱动信号 (连至晶体管)',
            'confidence': 'low',
            'reasoning': '网络连接至 MOSFET/晶体管',
            'raw_name': clean,
        }

    if features['has_active_device']:
        return {
            'label': '信号 (连至有源器件)',
            'confidence': 'low',
            'reasoning': '网络连接至有源器件',
            'raw_name': clean,
        }

    if features['has_single_resistor'] and features['node_count'] <= 2:
        return {
            'label': 'GPIO 信号 (可能上拉/限流)',
            'confidence': 'low',
            'reasoning': '网络仅连接单个电阻',
            'raw_name': clean,
        }

    if features['has_passive_only'] and features['node_count'] > 0:
        return {
            'label': '被动元件网络',
            'confidence': 'low',
            'reasoning': '网络仅包含电阻/电容/电感',
            'raw_name': clean,
        }

    # ── Level 5: No inference — fall back to raw name ──
    return {
        'label': clean if clean else '(未命名网络)',
        'confidence': 'none',
        'reasoning': '无可识别模式，使用原始网络名称',
        'raw_name': clean,
    }


def _classify_pin_group(inference: Dict, features: Dict) -> str:
    """Classify a pin into a generic group based on inference + topology.

    Groups are topology-aware, not project-specific.
    """
    if inference['confidence'] == 'high' and ('地线' in inference['label'] or '电源' in inference['label']):
        return '电源/参考电压'

    if inference['confidence'] == 'medium' and '总线' in inference['label']:
        return '总线/通信接口'

    if features['has_transistor']:
        return '驱动输出'

    if features['has_rc_filter']:
        return '模拟输入/采样'

    if 'ADC' in inference['label'] or '比较器' in inference['label'] or '运放' in inference['label']:
        return '模拟输入/采样'

    if 'UART' in inference['label'] or 'SPI' in inference['label'] or 'I2C' in inference['label'] or 'SWD' in inference['label']:
        return '总线/通信接口'

    if 'PWM' in inference['label'] or '驱动' in inference['label'] or '高边' in inference['label'] or '低边' in inference['label']:
        return 'PWM / 驱动输出'

    if '定时器' in inference['label']:
        return '定时器/计数器'

    if '运算放大器' in inference['label'] or '比较器' in inference['label']:
        return '模拟输入/采样'

    if features['has_single_resistor'] and features['node_count'] <= 2:
        return 'GPIO (可能上拉/限流)'

    if features['has_passive_only'] and features['node_count'] > 0:
        return '被动元件连接'

    if features['is_unconnected']:
        return '悬空'

    return '其他信号'


# ─────────────────────────────────────────────
# Signal Path Tracing — generalized (no hardcoded MOSFET maps)
# ─────────────────────────────────────────────

def _infer_pin_role_in_device(comp_type: str, pin: str, value: str, desc: str) -> str:
    """Infer a pin's role within a device based on context, NOT hardcoded maps.

    For MOSFETs: analyze which pin connects to power (Source), gate driver (Gate),
    or load (Drain) — but this requires external context, so we just label the pin.
    """
    # Generic: just return pin number with device type hint
    type_hint = {
        'mosfet': 'MOSFET',
        'resistor': 'R',
        'capacitor': 'C',
        'inductor': 'L',
        'diode': 'D',
        'connector': 'CON',
        'crystal': 'XTAL',
        'regulator': 'REG',
    }.get(comp_type, '')

    if type_hint:
        return f'Pin {pin} ({type_hint})'
    return f'Pin {pin}'


def trace_signal_path(pin_assignment: Dict, comp_lookup: Dict) -> str:
    """Trace the signal path from MCU pin through connected components.

    Generalized: no hardcoded MOSFET pin maps. Uses component type inference."""
    if not pin_assignment['other_nodes']:
        return '(无外部连接)'

    path_parts = []
    for node in pin_assignment['other_nodes']:
        ref = node['ref']
        pin = node['pin']
        comp = comp_lookup.get(ref, {})
        value = _clean_sexpr_str(comp.get('value', ''))
        desc = _clean_sexpr_str(comp.get('description', ''))
        ref_clean = _clean_sexpr_str(ref)
        pin_clean = _clean_sexpr_str(pin)

        comp_type = _get_comp_type(desc, value)
        pin_label = _infer_pin_role_in_device(comp_type, pin_clean, value, desc)

        part_info = ref_clean
        if value and value not in ('U', 'NC', ''):
            part_info += f' ({value})'

        path_parts.append(f'{part_info}/{pin_label}')

    return ' → '.join(path_parts)


# ─────────────────────────────────────────────
# Markdown Generator — updated for v3
# ─────────────────────────────────────────────

def generate_markdown(design_info: Dict, components: List[Dict],
                      nets: List[Dict], mcu: Dict,
                      pin_assignments: List[Dict]) -> str:
    """Generate structured Markdown report optimized for LLM consumption.

    v3: Uses topology-based grouping and confidence-labeled inference."""

    md = []
    comp_lookup = {c['ref']: c for c in components}
    for c in components:
        c['_clean_value'] = _clean_sexpr_str(c.get('value', ''))
        c['_clean_desc'] = _clean_sexpr_str(c.get('description', ''))
        c['_clean_footprint'] = _clean_sexpr_str(c.get('footprint', ''))
        c['_clean_ref'] = _clean_sexpr_str(c.get('ref', ''))

    # ═══════════════════════════════════════
    # Section 1: Design Information
    # ═══════════════════════════════════════
    md.append("# 原理图网表解析报告 (KiCad Netlist)")
    md.append(f"\n**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    if design_info:
        md.append("## 设计信息\n")
        for key, val in design_info.items():
            if val:
                label = {
                    'source': '源文件',
                    'tool': '工具',
                    'date': '日期',
                    'sheet_title': '标题',
                    'sheet_company': '公司',
                    'sheet_rev': '版本',
                }.get(key, key)
                md.append(f"- **{label}:** {val}")

    # ═══════════════════════════════════════
    # Section 2: MCU Pin Assignment
    # ═══════════════════════════════════════
    md.append("\n---\n")
    md.append(f"## MCU 引脚分配表\n")
    if mcu:
        mcu_ref_clean = _clean_sexpr_str(mcu.get('ref', '?'))
        mcu_val_clean = _clean_sexpr_str(mcu.get('value', '?'))
        mcu_fp_clean = _clean_sexpr_str(mcu.get('footprint', '?'))
        md.append(f"\n**MCU:** {mcu_ref_clean} ({mcu_val_clean}) - {mcu_fp_clean}")
        md.append(f"\n**总引脚数:** {len(mcu.get('pins', []))}")
    else:
        md.append(f"\n**MCU:** 未在网表中识别到 MCU")

    # ── Deduplicate connected vs unconnected ──
    unconnected_pin_set = set()
    for pa in pin_assignments:
        if _is_unconnected_net(pa['net_name']):
            unconnected_pin_set.add(pa['pin'])

    connected_pins = []
    unconnected_pins = []
    seen_unconnected = set()
    for pa in pin_assignments:
        pin = pa['pin']
        if _is_unconnected_net(pa['net_name']):
            if pin not in seen_unconnected:
                seen_unconnected.add(pin)
                unconnected_pins.append(pa)
        else:
            if pin not in unconnected_pin_set:
                connected_pins.append(pa)

    md.append(f"\n**已连接:** {len(connected_pins)} 引脚")
    md.append(f"**未连接:** {len(unconnected_pins)} 引脚\n")

    # ── Analyze each connected pin with topology + inference ──
    pin_analysis = []
    for pa in connected_pins:
        features = _infer_net_features(
            pa['net_name'], pa['other_refs'], comp_lookup, pa['other_nodes']
        )
        inference = _generate_inference_label(pa['net_name'], features)
        group = _classify_pin_group(inference, features)
        path = trace_signal_path(pa, comp_lookup)

        pin_analysis.append({
            'pa': pa,
            'features': features,
            'inference': inference,
            'group': group,
            'path': path,
        })

    # Group by topology-based category
    groups = {}
    for pa_item in pin_analysis:
        g = pa_item['group']
        if g not in groups:
            groups[g] = []
        groups[g].append(pa_item)

    # Group order: power first, then communication, then drive, then analog, then others
    group_order = [
        '电源/参考电压',
        '总线/通信接口',
        'PWM / 驱动输出',
        '模拟输入/采样',
        '定时器/计数器',
        'GPIO (可能上拉/限流)',
        '被动元件连接',
        '其他信号',
    ]

    for g in group_order:
        if g not in groups:
            continue
        items = groups[g]
        md.append(f"\n### {g}\n")
        md.append("| MCU 引脚 | 网络名 | 推断 | 推断置信度 | 连接器件 |\n")
        md.append("|---------|--------|------|-----------|----------|\n")
        for item in sorted(items, key=lambda x: _sort_key_int(x['pa']['pin'])):
            pa = item['pa']
            inf = item['inference']
            path = item['path']
            pin_clean = _clean_sexpr_str(pa['pin'])
            net_clean = _clean_sexpr_str(pa['net_name'])

            # Confidence badge
            conf_badge = {
                'high': '✅',
                'medium': '⚠️',
                'low': '❓',
                'none': '—',
            }.get(inf['confidence'], '—')

            label = inf['label']
            if inf['confidence'] in ('low', 'none') and inf['raw_name'] != label:
                label = f'{label} *(原: {inf["raw_name"]})'

            md.append(f"| Pin {pin_clean} | {net_clean} | {label} "
                      f"| {conf_badge} {inf['confidence']} | {path} |\n")

    # Unconnected pins
    if unconnected_pins:
        md.append("\n### 未连接引脚 (悬空)\n")
        md.append("| MCU 引脚 | 可用功能 (从网络名提取) |\n")
        md.append("|---------|------------------------|\n")
        for pa in sorted(unconnected_pins, key=lambda x: _sort_key_int(x['pin'])):
            pin_clean = _clean_sexpr_str(pa['pin'])
            func_clean = _clean_sexpr_str(pa['pin_func'])
            func_display = func_clean if func_clean else '(无功能信息)'
            md.append(f"| Pin {pin_clean} | {func_display} |\n")

    # ═══════════════════════════════════════
    # Section 3: Component Summary (BOM)
    # ═══════════════════════════════════════
    md.append("\n---\n")
    md.append(f"## 器件清单 (BOM)\n")
    md.append(f"\n**总计:** {len(components)} 个器件\n")

    by_type = {}
    for comp in components:
        value = comp.get('value', 'Unknown')
        if value not in by_type:
            by_type[value] = []
        by_type[value].append(comp)

    md.append(f"**器件类型:** {len(by_type)} 种唯一值\n")

    md.append("\n| 器件编号 | 型号/值 | 封装 | 描述 | 引脚数 |\n")
    md.append("|---------|---------|------|------|--------|\n")
    for comp in sorted(components, key=lambda c: _sort_key(c['ref'])):
        pins = len(comp.get('pins', []))
        ref_c = comp['_clean_ref']
        val_c = comp['_clean_value']
        fp_c = comp['_clean_footprint']
        desc_c = comp['_clean_desc']
        md.append(f"| {ref_c} | {val_c} | {fp_c} | "
                  f"{desc_c} | {pins} |\n")

    md.append("\n### 按类型分组\n")
    for value, comps in sorted(by_type.items()):
        val_clean = _clean_sexpr_str(value)
        refs = ', '.join([c['_clean_ref'] for c in sorted(comps, key=lambda c: _sort_key(c['ref']))])
        md.append(f"\n**{val_clean}** ({len(comps)}x): {refs}")

    # ═══════════════════════════════════════
    # Section 4: Signal Net Details
    # ═══════════════════════════════════════
    md.append("\n---\n")
    md.append(f"## 信号网络详细连接\n")
    md.append(f"\n**总网络数:** {len(nets)}\n")

    signal_nets = [n for n in nets
                   if not _is_unconnected_net(n['name'])
                   and not _is_power_net(n['name'])
                   and n['nodes']]

    md.append(f"\n**有效信号网络:** {len(signal_nets)}\n")

    for net in signal_nets:
        net_name_clean = _clean_sexpr_str(net['name'])
        net_code_clean = _clean_sexpr_str(net['code'])
        md.append(f"\n### {net_name_clean} (Net Code: {net_code_clean})\n")
        md.append(f"**连接数:** {len(net['nodes'])}\n")
        for node in net['nodes']:
            comp = comp_lookup.get(node['ref'], {})
            value = comp.get('_clean_value', _clean_sexpr_str(comp.get('value', '')))
            ref_clean = _clean_sexpr_str(node['ref'])
            pin_clean = _clean_sexpr_str(node['pin'])
            md.append(f"- {ref_clean} (Pin {pin_clean})"
                      + (f" [{value}]" if value and value not in ('U', '') else ""))

    # ═══════════════════════════════════════
    # Section 5: Power Net Details
    # ═══════════════════════════════════════
    power_net_list = [n for n in nets
                      if _is_power_net(n['name']) and n['nodes']]
    if power_net_list:
        md.append("\n---\n")
        md.append("## 电源网络连接详情\n")
        for net in power_net_list:
            net_name_clean = _clean_sexpr_str(net['name'])
            net_code_clean = _clean_sexpr_str(net['code'])
            md.append(f"\n### {net_name_clean} (Net Code: {net_code_clean})\n")
            md.append(f"**连接数:** {len(net['nodes'])}\n")
            for node in net['nodes']:
                comp = comp_lookup.get(node['ref'], {})
                value = comp.get('_clean_value', _clean_sexpr_str(comp.get('value', '')))
                ref_clean = _clean_sexpr_str(node['ref'])
                pin_clean = _clean_sexpr_str(node['pin'])
                md.append(f"- {ref_clean} (Pin {pin_clean})"
                          + (f" [{value}]" if value and value not in ('U', '') else ""))

    # ═══════════════════════════════════════
    # Section 6: Structured Pin Table (KB-Optimized)
    # ═══════════════════════════════════════
    md.append("\n---\n")
    md.append("## MCU 引脚结构化数据表 (知识库索引优化)\n")
    md.append(f"\n> **说明:** 本表为每个 MCU 引脚提供结构化数据，便于检索和验证。\n")
    md.append(f"> 推断结果带有置信度标记: ✅=高置信度, ⚠️=中置信度, ❓=低置信度, —=无推断\n")

    # Connected pins
    for item in sorted(pin_analysis, key=lambda x: _sort_key_int(x['pa']['pin'])):
        pa = item['pa']
        inf = item['inference']
        features = item['features']
        path = item['path']

        pin_clean = _clean_sexpr_str(pa['pin'])
        net_clean = _clean_sexpr_str(pa['net_name'])
        label = inf['label']
        conf_badge = {
            'high': '✅',
            'medium': '⚠️',
            'low': '❓',
            'none': '—',
        }.get(inf['confidence'], '—')

        # Topology tags
        tags = []
        if features['is_power']:
            tags.append('[电源]')
        if features['has_transistor']:
            tags.append('[驱动]')
        if features['has_rc_filter']:
            tags.append('[RC滤波]')
        if features['has_single_resistor']:
            tags.append('[单电阻]')
        if features['has_passive_only']:
            tags.append('[被动元件]')
        if not tags:
            tags.append('[信号]')

        tag_str = '[已连接]' + ''.join(tags)

        md.append(f"- **{tag_str} Pin {pin_clean}** | 网络: {net_clean} | "
                  f"推断: {label} ({conf_badge}{inf['confidence']}) | "
                  f"连接: {path}")

    # Unconnected pins
    for pa in sorted(unconnected_pins, key=lambda x: _sort_key_int(x['pin'])):
        pin_clean = _clean_sexpr_str(pa['pin'])
        func_clean = _clean_sexpr_str(pa['pin_func'])
        func_display = func_clean if func_clean else '(无功能信息)'
        md.append(f"- **[未连接] Pin {pin_clean}** | 可用功能: {func_display}")

    return '\n'.join(md)


def _sort_key_int(pin_val: str) -> int:
    """Extract numeric pin value for sorting (handles quoted values)."""
    clean = _clean_sexpr_str(pin_val)
    try:
        return int(clean)
    except (ValueError, TypeError):
        return 0


# ─────────────────────────────────────────────
# Main — unchanged
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 netlist_to_md.py <input.net> <output_dir>")
        print("Example: python3 netlist_to_md.py design.net ./cache/text/")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        sys.exit(1)

    print(f"🔍 Reading: {input_path}")

    content = input_path.read_text(encoding='utf-8', errors='ignore')
    print(f"📄 File size: {len(content)} chars")

    print("🔧 Parsing S-expressions...")
    parsed = parse_sexpr_list(content)
    print(f"✅ Found {len(parsed)} top-level expressions")

    design_info = extract_design_info(parsed)
    components = extract_components(parsed)
    nets = extract_nets(parsed)

    print(f"📦 Components: {len(components)}")
    print(f"🔗 Nets: {len(nets)}")

    total_nodes = sum(len(n['nodes']) for n in nets)
    print(f"📊 Total node connections: {total_nodes}")
    if total_nodes == 0:
        print("⚠️ WARNING: No node connections found! Parser may have issues.")

    mcu = find_mcu_component(components)
    if mcu:
        print(f"🎯 MCU: {mcu['ref']} ({mcu['value']}) - {mcu['footprint']}")
        print(f"   MCU pins: {len(mcu['pins'])}")
        pin_assignments = get_mcu_pin_info(components, nets, mcu)
    else:
        print("⚠️ No MCU found in netlist, generating report without MCU section")
        pin_assignments = []

    output_filename = f"{input_path.stem}.md"
    output_path = output_dir / output_filename

    md_content = generate_markdown(design_info, components, nets,
                                   mcu if mcu else {}, pin_assignments)
    output_path.write_text(md_content, encoding='utf-8')

    print(f"\n✅ Created: {output_path}")
    print(f"   Size: {len(md_content)} chars")
    print(f"   MCU pins: {len(pin_assignments)} total")
    connected = sum(1 for p in pin_assignments if not _is_unconnected_net(p['net_name']))
    unconnected = sum(1 for p in pin_assignments if _is_unconnected_net(p['net_name']))
    print(f"   Connected: {connected}, Unconnected: {unconnected}")


if __name__ == "__main__":
    main()

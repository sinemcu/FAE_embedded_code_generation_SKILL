#!/usr/bin/env python3
"""
KiCad Netlist to Markdown Converter (Fixed v2)
Converts KiCad netlist files (.net) to structured Markdown format.

Changes from v1:
- Replaced fragile regex with stack-based S-expression parser
- Properly extracts all node connections (v1 had 0 connections due to regex bug)
- Generates MCU-centric pin assignment table
- Traces signal paths (MCU pin → passive → power device)
- Tags content with metadata-friendly section headers for KB indexing
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


# ─────────────────────────────────────────────
# S-Expression Parser (stack-based)
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
            # Quoted string
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == '\\':
                    j += 1  # skip escaped char
                j += 1
            tokens.append(text[i:j + 1])
            i = j + 1
        else:
            # Unquoted token (digits, identifiers)
            j = i
            while j < n and text[j] not in '() \t\n\r"':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def parse_sexpr(tokens: list) -> Tuple[Any, int]:
    """Parse tokens into nested list structure. Returns (parsed, next_index)."""
    if tokens[0] != '(':
        # Leaf node - could be a quoted string or bare token
        return tokens[0], 1

    result = []
    i = 1  # skip opening '('
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
# KiCad Netlist Extractor
# ─────────────────────────────────────────────

def flatten_to_depth(node: list, target_keys: set) -> list:
    """Recursively find all sub-expressions matching target keys anywhere in the tree.
    Returns a flat list of [key, ...content] lists."""
    results = []
    if not isinstance(node, list):
        return results
    for item in node:
        if isinstance(item, list) and len(item) > 0:
            if item[0] in target_keys:
                results.append(item)
            # Recurse into children regardless of match
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
                        # Extract title_block
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
    # Find 'components' block anywhere in the tree
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
                                # f[1] might be a list like ["name", "Footprint"] or just a string
                                fname_raw = f[1] if len(f) > 1 else ''
                                fname = fname_raw[1] if isinstance(fname_raw, list) and len(fname_raw) > 1 else str(fname_raw)
                                fval_raw = f[2] if len(f) > 2 else ''
                                fval = fval_raw[1] if isinstance(fval_raw, list) and len(fval_raw) > 1 else str(fval_raw)
                                comp['fields'][fname] = fval
                    elif key == 'units':
                        # Extract pins from units
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
    # Find 'nets' block anywhere in the tree
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
# MCU Pin Assignment Analysis
# ─────────────────────────────────────────────

def find_mcu_component(components: List[Dict]) -> Optional[Dict]:
    """Find the MCU component in the netlist.
    Heuristic: component with most pins, or name containing MCU model patterns.
    """
    mcu_patterns = re.compile(r'(?:MC|MS|STM|GD|NXP|AT|ATMEGA|PIC|ESP|RP|HK|MM)[A-Z0-9]+', re.IGNORECASE)

    # Strategy 1: find by name pattern in value
    for comp in components:
        val = comp.get('value', '')
        desc = comp.get('description', '')
        if mcu_patterns.search(val) or mcu_patterns.search(desc):
            # MCU usually has many pins
            if len(comp.get('pins', [])) >= 5:
                return comp

    # Strategy 2: find component with most pins
    if components:
        return max(components, key=lambda c: len(c.get('pins', [])))

    return None


def get_mcu_pin_info(components: List[Dict], nets: List[Dict], mcu: Dict) -> List[Dict]:
    """Extract MCU pin assignments: for each connected MCU pin, find the net name
    and all other components on that net."""
    mcu_ref = mcu['ref']
    mcu_pins = set(mcu.get('pins', []))

    # Build lookup: component ref → component info
    comp_lookup = {c['ref']: c for c in components}

    pin_assignments = []
    connected_pins = set()

    for net in nets:
        mcu_node = None
        other_nodes = []

        for node in net['nodes']:
            if node['ref'] == mcu_ref:
                mcu_node = node
            else:
                other_nodes.append(node)

        if mcu_node and mcu_node['pin'] in mcu_pins:
            connected_pins.add(mcu_node['pin'])
            pin_num = mcu_node['pin']
            net_name = net['name']

            # Find the MCU pin function name (from component pins list context)
            pin_func = ''
            # Try to find pin function from component definition
            # In KiCad netlist, MCU pins are listed in libparts section
            # We'll look for matching pin in the component's context
            # Since the raw pin list only has numbers, we need to check nets for unconnected pins
            # which often contain the full function name

            pin_assignments.append({
                'pin': pin_num,
                'net_name': net_name,
                'pin_func': '',  # Will be filled from unconnected nets if available
                'other_nodes': other_nodes,
                'other_refs': [n['ref'] for n in other_nodes],
            })

    # Find unconnected pins to get their function names and mark as NC
    unconnected_nets = []
    for net in nets:
        name = net.get('name', '')
        if 'unconnected' in name.lower():
            unconnected_nets.append(net)

    for uc_net in unconnected_nets:
        for node in uc_net['nodes']:
            if node['ref'] == mcu_ref:
                pin_num = node['pin']
                # Extract function name from net name like:
                # "unconnected-(U1-PA10/MCP_BKIN/UART1_RX/...-Pad1)"
                func_name = _extract_pin_function(uc_net['name'])
                # Mark as not connected
                pin_assignments.append({
                    'pin': pin_num,
                    'net_name': '(未连接)',
                    'pin_func': func_name,
                    'other_nodes': [],
                    'other_refs': [],
                })

    # Fill pin_func from connected nets where possible
    for pa in pin_assignments:
        if not pa['pin_func'] and pa['pin_func'] == '':
            # Check if we can find function from unconnected net matching this pin
            for uc_net in unconnected_nets:
                for node in uc_net['nodes']:
                    if node['ref'] == mcu_ref and node['pin'] == pa['pin']:
                        pa['pin_func'] = _extract_pin_function(uc_net['name'])
                        break

    return pin_assignments


def _extract_pin_function(net_name: str) -> str:
    """Extract pin function from unconnected net name like:
    'unconnected-(U1-PA10/MCP_BKIN/UART1_RX/SPI1_NSS/...-Pad1)'
    Returns: 'PA10/MCP_BKIN/UART1_RX/SPI1_NSS/...'
    """
    # Clean up KiCad escape sequences first
    net_name = net_name.replace('{slash}', '/')
    # Pattern: unconnected-(U1-FUNCTION-PadN) or unconnected-(U1-FUNCTION)
    m = re.search(r'unconnected-\([^)]*?-(.+?)(?:-Pad\d+\))', net_name)
    if m:
        return m.group(1)
    m = re.search(r'unconnected-\((?:\w+)-(.+?)\)', net_name)
    if m:
        return m.group(1)
    return ''


def _clean_sexpr_str(val: str) -> str:
    """Clean up a value that came from S-expression parsing.
    Strips surrounding quotes, decodes KiCad escapes."""
    if not isinstance(val, str):
        return str(val)
    # Strip surrounding quotes
    val = val.strip('"')
    # Decode KiCad escape sequences
    val = val.replace('{slash}', '/')
    val = val.replace('{', '').replace('}', '')
    return val


def trace_signal_path(pin_assignment: Dict, comp_lookup: Dict) -> str:
    """Trace the signal path from MCU pin through connected components.
    Returns a human-readable description like:
    '→ R21 (51Ω) → Q1 (KS3637MA/G1) → U 相高边'
    """
    if not pin_assignment['other_nodes']:
        return '(无外部连接)'

    path_parts = []
    for node in pin_assignment['other_nodes']:
        ref = node['ref']
        pin = node['pin']
        comp = comp_lookup.get(ref, {})
        value = comp.get('_clean_value', _clean_sexpr_str(comp.get('value', '')))
        desc = comp.get('_clean_desc', _clean_sexpr_str(comp.get('description', '')))
        ref_clean = _clean_sexpr_str(ref)
        pin_clean = _clean_sexpr_str(pin)

        # Get MOSFET pin function if available (from libparts)
        pin_label = f'Pin {pin_clean}'
        # For MOSFETs, we can infer pin function from the pin number
        if 'AO4627' in desc or 'PMOS' in desc or 'NMOS' in desc:
            mosfet_pins = {'1': 'S1(Source)', '2': 'G1(Gate)', '3': 'S2(Source)',
                          '4': 'G2(Gate)', '5': 'D2(Drain)', '6': 'D1(Drain)'}
            pin_label = mosfet_pins.get(pin_clean, f'Pin {pin_clean}')

        part_info = ref_clean
        if value and value != 'U' and value != 'NC':
            part_info += f' ({value})'

        path_parts.append(f'{part_info}/{pin_label}')

    return ' → '.join(path_parts)


# ─────────────────────────────────────────────
# Markdown Generator
# ─────────────────────────────────────────────

def generate_markdown(design_info: Dict, components: List[Dict],
                      nets: List[Dict], mcu: Dict,
                      pin_assignments: List[Dict]) -> str:
    """Generate structured Markdown report optimized for LLM consumption."""

    md = []
    comp_lookup = {c['ref']: c for c in components}
    # Pre-clean component data for display
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
    # Section 2: MCU Pin Assignment (MOST IMPORTANT)
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

    # Deduplicate: a pin may appear in both a connected net and an unconnected net
    # If a pin is unconnected, remove its connected entry (they have no real connection)
    # If a pin is on '<NO NET>', also treat as unconnected
    # Note: S-expression parser preserves quotes, so values may include surrounding quotes
    def _is_unconnected_net(net_name: str) -> bool:
        """Check if a net name indicates an unconnected pin (handles quoted values)."""
        clean = net_name.strip('"')
        return (clean in ('(未连接)', '/<NO NET>', '<NO NET>')
                or 'unconnected' in clean.lower())

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
            # Only add as connected if not already classified as unconnected
            if pin not in unconnected_pin_set:
                connected_pins.append(pa)

    md.append(f"\n**已连接:** {len(connected_pins)} 引脚")
    md.append(f"**未连接:** {len(unconnected_pins)} 引脚\n")

    # Power pins
    power_nets = ['GND', 'VCC', 'VDD', 'AVCC', 'PVCC', '5V', '3V3', 'LDO', '12V', '1.8V', '3.3V']
    power_pins = [pa for pa in connected_pins if any(p in pa['net_name'].upper() for p in power_nets)]
    # Signal pins: exclude power
    signal_pins = [pa for pa in connected_pins
                   if not any(p in pa['net_name'].upper() for p in power_nets)]

    # 2a. Power Pins
    if power_pins:
        md.append("\n### 电源引脚\n")
        md.append("| MCU 引脚 | 网络名 | 功能 | 连接器件 |\n")
        md.append("|---------|--------|------|----------|\n")
        for pa in sorted(power_pins, key=lambda x: int(x['pin']) if x['pin'].isdigit() else 0):
            path = trace_signal_path(pa, comp_lookup)
            func = pa['pin_func'] if pa['pin_func'] else _infer_pin_function(pa['net_name'])
            pin_clean = _clean_sexpr_str(pa['pin'])
            net_clean = _clean_sexpr_str(pa['net_name'])
            md.append(f"| Pin {pin_clean} | {net_clean} | {func} | {path} |\n")

    # 2b. Signal Pins (grouped by function)
    if signal_pins:
        md.append("\n### 信号引脚 (按功能分组)\n")

        # Group by net name pattern
        groups = _group_pins_by_function(signal_pins)
        for group_name, group_pins in groups.items():
            md.append(f"\n#### {group_name}\n")
            md.append("| MCU 引脚 | 网络名 | 功能推测 | 连接器件 |\n")
            md.append("|---------|--------|---------|----------|\n")
            for pa in sorted(group_pins, key=lambda x: int(x['pin']) if x['pin'].isdigit() else 0):
                path = trace_signal_path(pa, comp_lookup)
                func = pa['pin_func'] if pa['pin_func'] else _infer_pin_function(pa['net_name'])
                pin_clean = _clean_sexpr_str(pa['pin'])
                net_clean = _clean_sexpr_str(pa['net_name'])
                md.append(f"| Pin {pin_clean} | {net_clean} | {func} | {path} |\n")

    # 2c. Unconnected Pins
    if unconnected_pins:
        md.append("\n### 未连接引脚 (悬空)\n")
        md.append("| MCU 引脚 | 可用功能 |\n")
        md.append("|---------|----------|\n")
        for pa in sorted(unconnected_pins, key=lambda x: int(x['pin']) if x['pin'].isdigit() else 0):
            pin_clean = _clean_sexpr_str(pa['pin'])
            func_clean = _clean_sexpr_str(pa['pin_func'])
            md.append(f"| Pin {pin_clean} | {func_clean} |\n")

    # ═══════════════════════════════════════
    # Section 3: Component Summary
    # ═══════════════════════════════════════
    md.append("\n---\n")
    md.append(f"## 器件清单 (BOM)\n")
    md.append(f"\n**总计:** {len(components)} 个器件\n")

    # Group by type
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

    # Component by type
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

    # Skip power and unconnected nets, focus on signal nets
    signal_nets = [n for n in nets
                   if n['name'] != '<NO NET>'
                   and 'unconnected' not in n['name'].lower()
                   and not any(p in n['name'].upper() for p in power_nets)
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
                      + (f" [{value}]" if value and value != 'U' else ""))

    # ═══════════════════════════════════════
    # Section 5: Power Net Details
    # ═══════════════════════════════════════
    power_net_list = [n for n in nets
                      if any(p in n['name'].upper() for p in power_nets)
                      and n['nodes']]
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
                          + (f" [{value}]" if value and value != 'U' else ""))

    # ═══════════════════════════════════════
    # Section 6: Structured Pin Table (KB-Optimized)
    # ═══════════════════════════════════════
    # This section is designed for RAG/KB indexing:
    # - Each pin on its own line with all relevant fields
    # - Tags for search: [已连接]/[未连接], [电源]/[信号]
    # - Clean string values (no S-expression quotes)
    md.append("\n---\n")
    md.append("## MCU 引脚结构化数据表 (知识库索引优化)\n")
    md.append(f"\n> **说明:** 本表为每个 MCU 引脚提供结构化数据，便于检索和验证。\n")
    md.append(f"> 每条记录格式: 引脚号 | 网络名 | 功能 | 连接路径 | 状态标签\n")

    # Connected pins
    for pa in sorted(connected_pins, key=lambda x: int(x['pin']) if x['pin'].isdigit() else 0):
        pin_clean = _clean_sexpr_str(pa['pin'])
        net_clean = _clean_sexpr_str(pa['net_name'])
        func = _clean_sexpr_str(pa['pin_func']) if pa['pin_func'] else _infer_pin_function(pa['net_name'])
        func_clean = _clean_sexpr_str(func)
        path = trace_signal_path(pa, comp_lookup)

        # Tags
        is_power = any(p in pa['net_name'].upper() for p in power_nets)
        tags = "[已连接]" + ("[电源]" if is_power else "[信号]")

        # Infer phase for PWM
        phase = ""
        net_upper = pa['net_name'].upper()
        if 'PWM1' in net_upper or 'PO1' in net_upper or 'NO1' in net_upper:
            phase = "[U相]"
        elif 'PWM2' in net_upper or 'PO2' in net_upper or 'NO2' in net_upper:
            phase = "[V相]"
        elif 'PWM3' in net_upper or 'PO3' in net_upper or 'NO3' in net_upper:
            phase = "[W相]"

        md.append(f"- **{tags}{phase} Pin {pin_clean}** | 网络: {net_clean} | "
                  f"功能: {func_clean} | 连接: {path}")

    # Unconnected pins
    for pa in sorted(unconnected_pins, key=lambda x: int(x['pin']) if x['pin'].isdigit() else 0):
        pin_clean = _clean_sexpr_str(pa['pin'])
        func_clean = _clean_sexpr_str(pa['pin_func'])
        md.append(f"- **[未连接] Pin {pin_clean}** | 可用功能: {func_clean}")

    return '\n'.join(md)


def _infer_pin_function(net_name: str) -> str:
    """Infer pin function from net name."""
    infer_map = {
        'PWM': 'PWM 输出',
        'PO': '内置预驱高边 (Phase Output)',
        'NO': '内置预驱低边 (Negative Output)',
        'PWM1': 'U 相 PWM',
        'PWM2': 'V 相 PWM',
        'PWM3': 'W 相 PWM',
        'P': '高边 (High Side)',
        'N': '低边 (Low Side)',
        'ADC': 'ADC 输入',
        'IN': '输入',
        'OUT': '输出',
        'UART': '串口通信',
        'TX': '串口发送 (TX)',
        'RX': '串口接收 (RX)',
        'SPI': 'SPI 通信',
        'I2C': 'I2C 通信',
        'SCL': 'I2C 时钟',
        'SDA': 'I2C 数据',
        'SWCLK': 'SWD 调试时钟',
        'SWDIO': 'SWD 调试数据',
        'IA': '相电流采样 (IA)',
        'IB': '相电流采样 (IB)',
        'LP': '低边电流采样',
        'IR': '母线电流采样',
        'IA-': '相电流负端',
        'IA+': '相电流正端',
        'OP': '运放输出',
        'TIM': '定时器通道',
        'GND': '地 (GND)',
        'VCC': '电源 (VCC)',
        'VDD': '电源 (VDD)',
        'AVCC': '模拟电源 (AVCC)',
        'PVCC': '功率电源 (PVCC)',
        'LDO': 'LDO 输出',
        '5V': '5V 电源',
        '3V3': '3.3V 电源',
        '12V': '12V 电源',
    }

    for keyword, func in infer_map.items():
        if keyword in net_name.upper():
            return func
    return net_name  # Return net name itself as function hint


def _group_pins_by_function(signal_pins: List[Dict]) -> Dict[str, List[Dict]]:
    """Group signal pins by functional category."""
    groups = {}

    for pa in signal_pins:
        name = pa['net_name'].upper()

        if 'PWM' in name or 'PO' in name or 'NO' in name:
            group = 'PWM / 电机驱动输出'
        elif 'ADC' in name or 'IA' == name.strip('/') or 'IB' == name.strip('/') or 'LP' == name.strip('/') or 'IR' in name:
            group = 'ADC / 电流采样'
        elif 'UART' in name or 'TX' in name or 'RX' in name:
            group = 'UART / 串口通信'
        elif 'SPI' in name or 'SCK' in name or 'MOSI' in name or 'MISO' in name or 'NSS' in name:
            group = 'SPI / 串行外设'
        elif 'I2C' in name or 'SCL' in name or 'SDA' in name:
            group = 'I2C / I²C 通信'
        elif 'SWD' in name or 'SWCLK' in name or 'SWDIO' in name:
            group = 'SWD / 调试接口'
        elif 'TIM' in name or 'CH' in name:
            group = '定时器通道'
        elif 'CMP' in name:
            group = '比较器'
        elif 'OPA' in name or 'OP' in name:
            group = '运算放大器'
        elif 'MCP' in name or 'BKIN' in name:
            group = '电机控制/刹车'
        elif 'BOOT' in name:
            group = 'Boot 配置'
        else:
            group = '其他信号'

        if group not in groups:
            groups[group] = []
        groups[group].append(pa)

    return groups


def _sort_key(ref: str):
    """Sort key for designator references (R1, R2, R10, C1, U1, etc.)."""
    m = re.match(r'([A-Z]+)(\d+)', ref)
    if m:
        return (m.group(1), int(m.group(2)))
    return (ref, 0)


# ─────────────────────────────────────────────
# Main
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

    # Read raw content
    content = input_path.read_text(encoding='utf-8', errors='ignore')
    print(f"📄 File size: {len(content)} chars")

    # Parse S-expressions
    print("🔧 Parsing S-expressions...")
    parsed = parse_sexpr_list(content)
    print(f"✅ Found {len(parsed)} top-level expressions")

    # Extract data
    design_info = extract_design_info(parsed)
    components = extract_components(parsed)
    nets = extract_nets(parsed)

    print(f"📦 Components: {len(components)}")
    print(f"🔗 Nets: {len(nets)}")

    # Verify: check that nets have connections
    total_nodes = sum(len(n['nodes']) for n in nets)
    print(f"📊 Total node connections: {total_nodes}")
    if total_nodes == 0:
        print("⚠️ WARNING: No node connections found! Parser may have issues.")

    # Find MCU
    mcu = find_mcu_component(components)
    if mcu:
        print(f"🎯 MCU: {mcu['ref']} ({mcu['value']}) - {mcu['footprint']}")
        print(f"   MCU pins: {len(mcu['pins'])}")
        pin_assignments = get_mcu_pin_info(components, nets, mcu)
    else:
        print("⚠️ No MCU found in netlist, generating report without MCU section")
        pin_assignments = []

    # Generate Markdown
    output_filename = f"{input_path.stem}.md"
    output_path = output_dir / output_filename

    md_content = generate_markdown(design_info, components, nets,
                                   mcu if mcu else {}, pin_assignments)
    output_path.write_text(md_content, encoding='utf-8')

    print(f"\n✅ Created: {output_path}")
    print(f"   Size: {len(md_content)} chars")
    print(f"   MCU pins: {len(pin_assignments)} total")
    connected = sum(1 for p in pin_assignments if p['net_name'] != '(未连接)')
    unconnected = sum(1 for p in pin_assignments if p['net_name'] == '(未连接)')
    print(f"   Connected: {connected}, Unconnected: {unconnected}")


if __name__ == "__main__":
    main()

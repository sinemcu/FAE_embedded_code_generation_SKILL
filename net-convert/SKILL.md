---
name: net-convert
description: "Convert KiCad netlist (.net) files to structured Markdown and manage schematic knowledge base with vector + keyword hybrid retrieval. Use when: user needs to parse .net netlist files, extract MCU pin assignments, build schematic knowledge base, or query netlist information."
---

# NET-CONVERT - KiCad Netlist Conversion & Knowledge Base Skill

Automatically convert KiCad netlist files (.net) to structured Markdown reports with MCU pin assignment tables, and build a searchable schematic knowledge base.

## When to Use

✅ **USE this skill when:**

- "Convert .net netlist files to markdown"
- "Parse the schematic netlist and show MCU pins"
- "Build knowledge base from netlist files"
- "What pins does the MCU use for PWM?"
- "Show me the pinout for [MCU model]"
- "Query schematic knowledge base"

## When NOT to Use

❌ **DON'T use this skill when:**

- Input is not a KiCad .net file
- Need to convert PDFs/Excel/Pack → use `doc-convert` skill instead
- Need to generate code → use `fae` skill instead
- Only need to read a single text file → use `read` tool directly

## Supported Formats

| Format | Extension | Converter | Output |
|--------|-----------|-----------|--------|
| KiCad Netlist | `.net` | `converter.py` → `scripts/netlist_to_md.py` | `.md` (structured report) |

## Directory Structure

```
skills/net-convert/
├── SKILL.md                     # This file
├── converter.py                 # Batch netlist conversion tool
├── kb_manager.py                # Schematic knowledge base manager
├── requirements.txt             # Python dependencies (shared with doc-convert)
├── scripts/
│   └── netlist_to_md.py        # KiCad .net → Markdown parser
├── retriever/                   # Retrieval engine (imports from doc-convert)
│   └── __init__.py
└── kb/
    └── config.json              # Knowledge base configuration
```

## Paths

```bash
# Netlist source search
SEARCH_ROOT="/Users/sinomcu/.openclaw/workspace/fae_input/sources/"

# Converted output
OUTPUT_DIR="/Users/sinomcu/.openclaw/workspace/fae_input/cache/schematics/"

# Knowledge base indexes (shared with doc-convert)
KB_ROOT="/Users/sinomcu/.openclaw/workspace/fae_input/"
```

## Usage Examples

### Example 1: Convert a Single Netlist

**User:** "Convert this netlist file to markdown"

**Assistant:** (uses net-convert skill)
```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/converter.py \
  -i /path/to/MC8059_12VPUMP-G-20260323_V10.net \
  -o /Users/sinomcu/.openclaw/workspace/fae_input/cache/schematics/
```

**Output:** `cache/schematics/MC8059_12VPUMP-G-20260323_V10.md`
- MCU pin assignment table
- BOM list
- Signal net details
- Structured pin data (KB-optimized)

---

### Example 2: Batch Convert All Netlists

**User:** "Convert all netlist files in the project"

**Assistant:** (uses net-convert skill)
```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/converter.py \
  -i /Users/sinomcu/.openclaw/workspace/fae_input/sources/ \
  -o /Users/sinomcu/.openclaw/workspace/fae_input/cache/schematics/ \
  -r
```

**Output:** All `.net` files converted to structured Markdown

---

### Example 3: Build Schematic Knowledge Base

**User:** "Build knowledge base from the converted netlists"

**Assistant:** (uses net-convert skill)
```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py build
```

**Output:** Vector + keyword indexes updated with netlist pin data

---

### Example 4: Query Schematic Knowledge Base

**User:** "What pins does MC8059 use for PWM?"

**Assistant:** (uses net-convert skill)
```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py query "MC8059 PWM pin assignment"
```

**Output:** Relevant pin assignment entries from the schematic knowledge base

---

### Example 5: Check Status

**User:** "Show schematic knowledge base status"

**Assistant:** (uses net-convert skill)
```bash
python3 /Users/sinomcu/.openclaw/workspace/skills/net-convert/kb_manager.py status
```

## Commands Reference

### Conversion
```bash
# Convert single file
python3 converter.py -i design.net -o cache/schematics/

# Batch convert (recursive)
python3 converter.py -i fae_input/sources/ -o fae_input/cache/schematics/ -r

# Force re-conversion (ignore cache)
python3 converter.py -i design.net -o cache/schematics/ -f
```

### Knowledge Base
```bash
# Build index
python3 kb_manager.py build

# Query
python3 kb_manager.py query "your question"

# Status
python3 kb_manager.py status

# Clear
python3 kb_manager.py clear
```

## Output Structure (Markdown Report)

Each converted netlist produces a structured report with:

1. **Design Information** — source file, tool version, date
2. **MCU Pin Assignment Table** — grouped by function:
   - 电源/参考电压 (Power/Reference)
   - 总线/通信接口 (Bus/Communication)
   - PWM / 驱动输出 (PWM/Drive Output)
   - 模拟输入/采样 (Analog Input/Sampling)
   - 定时器/计数器 (Timers/Counters)
   - GPIO (可能上拉/限流)
   - 悬空 (Unconnected)
3. **器件清单 (BOM)** — grouped by type
4. **信号网络详细连接** — all signal nets with component connections
5. **电源网络连接详情** — power net details
6. **MCU 引脚结构化数据表** — KB-optimized, one pin per line

## Inference Confidence Levels

Pin function inference uses confidence markers:

| Badge | Level | Meaning |
|-------|-------|---------|
| ✅ | High | Standard power/ground names (GND, VDD, 5V, etc.) |
| ⚠️ | Medium | Known signal patterns (SPI, UART, PWM, ADC, etc.) |
| ❓ | Low | Topology-based inference (RC network, single resistor, etc.) |
| — | None | No pattern matched, raw net name preserved |

## Integration with Other Skills

### FAE Skill
```
FAE → net-convert (parse netlist) → schematics/ → FAE (read pinout) → generate code
```

### Doc-Convert (Shared KB)
```
net-convert → convert netlists → cache/schematics/ → kb_manager.py build → shared indexes/
                                                              ↑
doc-convert → convert PDFs → cache/text/ ─────────────────────┘
```

Both skills write to the same `fae_input/indexes/` knowledge base, enabling unified RAG retrieval across datasheets, requirements, and schematic pin assignments.

## Dependencies

Uses the same dependencies as `doc-convert`:

```bash
cd /Users/sinomcu/.openclaw/workspace/skills/doc-convert
pip3 install -r requirements.txt
```

**Key dependencies:**
- `chromadb` - Vector database
- `whoosh` - Keyword search engine
- `sentence-transformers` - Embedding models

No additional dependencies required for net-convert (the netlist parser is pure Python).

## Known Limitations

- **KiCad format only** — Currently supports KiCad Eeschema `.net` format. Altium, Eagle, or other formats are not supported.
- **Single MCU focus** — Designed for single-MCU boards. Multi-MCU designs will only extract the primary MCU.
- **No schematic rendering** — This is a text parser, not a graphical viewer.

---

_This skill parses KiCad netlist files and provides structured pin assignment data for FAE code generation and RAG retrieval._

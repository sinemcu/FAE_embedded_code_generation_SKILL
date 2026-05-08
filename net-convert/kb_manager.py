#!/usr/bin/env python3
"""
NET-CONVERT Schematic Knowledge Base Manager
Manages knowledge base for converted netlist files.

Uses a SEPARATE index directory from doc-convert to keep
schematic pin data isolated from datasheet documents.

Separate paths:
- Indexes: fae_input/schematics_kb/indexes/
- Source MD: fae_input/cache/schematics/
"""

import sys
import json
import argparse
from pathlib import Path

# Ensure doc-convert retriever is importable
_skill_dir = Path(__file__).parent.resolve()
_doc_convert = _skill_dir.parent / "doc-convert"
if _doc_convert.exists() and str(_doc_convert) not in sys.path:
    sys.path.insert(0, str(_doc_convert))

# Default separate KB root
_DEFAULT_KB_ROOT = "/Users/sinomcu/.openclaw/workspace/fae_input/schematics_kb"
_DEFAULT_SOURCE_DIR = "/Users/sinomcu/.openclaw/workspace/fae_input/cache/schematics/"


def load_config(config_path: str) -> dict:
    """Load configuration"""
    with open(config_path, "r") as f:
        return json.load(f)


def cmd_build(args):
    """Build schematic knowledge base"""
    from retriever.hybrid_search import KnowledgeBaseBuilder

    config = load_config(args.config)
    kb_root = Path(args.kb_root)
    kb_root.mkdir(parents=True, exist_ok=True)

    # Ensure source dir exists
    source = Path(args.source_dir)
    if not source.exists():
        print(f"❌ Source directory not found: {source}")
        sys.exit(1)

    kb = KnowledgeBaseBuilder(str(kb_root), config)
    kb.build(
        source_dir=str(source),
        batch_size=args.batch_size,
        incremental=not args.full_rebuild,
    )


def cmd_query(args):
    """Query schematic knowledge base"""
    from retriever.hybrid_search import KnowledgeBaseBuilder

    config = load_config(args.config)
    kb = KnowledgeBaseBuilder(args.kb_root, config)
    kb.query(args.question)


def _count_vector_chunks(index_path: str) -> str:
    """Check vector index directory existence."""
    p = Path(index_path)
    if not p.exists():
        return "not initialized (directory missing)"
    data_dirs = [d for d in p.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if data_dirs:
        return f"present ({len(data_dirs)} collection(s))"
    return "empty (no collections)"


def cmd_status(args):
    """View knowledge base status"""
    config = load_config(args.config)
    kb_root = Path(args.kb_root)

    print("📊 Schematic Knowledge Base Status\n")

    # Vector store (separate from doc-convert)
    vector_path = str(kb_root / "indexes" / "vector")
    print(f"Vector index: {_count_vector_chunks(vector_path)}")

    # Keyword index (separate from doc-convert)
    try:
        from retriever.keyword_index import WhooshKeywordIndex
        ki = WhooshKeywordIndex(str(kb_root / "indexes" / "keyword"))
        print(f"Keyword index: {ki.count()} chunks")
    except Exception as e:
        print(f"Keyword index: not initialized ({e})")

    # Source netlist MD files
    source_dir = kb_root / "cache" / "schematics"
    if not source_dir.exists():
        # Fall back to config sources_dir
        source_dir = Path(config.get("sources_dir", _DEFAULT_SOURCE_DIR))
    if source_dir.exists():
        md_files = list(source_dir.glob("*.md"))
        print(f"Converted netlists: {len(md_files)} file(s)")
        for f in sorted(md_files):
            print(f"  - {f.name}")
    else:
        print("Converted netlists: directory not found (convert netlists first)")

    # Raw .net source files
    raw_dir = Path("/Users/sinomcu/.openclaw/workspace/fae_input/sources")
    if raw_dir.exists():
        net_files = list(raw_dir.rglob("*.net"))
        print(f"Raw .net files: {len(net_files)} file(s)")


def cmd_clear(args):
    """Clear schematic knowledge base"""
    from retriever.vector_store import ChromaVectorStore
    from retriever.keyword_index import WhooshKeywordIndex

    kb_root = Path(args.kb_root)

    confirm = input("⚠️ Clear schematic knowledge base? (y/N): ")
    if confirm.lower() != "y":
        print("Cancelled")
        return

    print("\nClearing schematic knowledge base...")

    vs_path = str(kb_root / "indexes" / "vector")
    if Path(vs_path).exists():
        vs = ChromaVectorStore(vs_path)
        vs.clear()
        print("✅ Vector index cleared")

    ki_path = str(kb_root / "indexes" / "keyword")
    if Path(ki_path).exists():
        ki = WhooshKeywordIndex(ki_path)
        ki.clear()
        print("✅ Keyword index cleared")

    print("✅ Schematic knowledge base cleared")


def main():
    script_dir = Path(__file__).parent.resolve()

    parser = argparse.ArgumentParser(
        description="NET-CONVERT Schematic Knowledge Base Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build schematic knowledge base
  python3 kb_manager.py build

  # Query
  python3 kb_manager.py query "MC8059 PWM pin assignment"

  # Status
  python3 kb_manager.py status

  # Clear
  python3 kb_manager.py clear
        """,
    )

    parser.add_argument(
        "--config",
        default=str(script_dir / "kb" / "config.json"),
        help="Config file path",
    )
    parser.add_argument(
        "--kb-root",
        default=_DEFAULT_KB_ROOT,
        help="Knowledge base root directory (separate from doc-convert)",
    )
    parser.add_argument(
        "--source-dir",
        default=None,
        help="Source directory for netlist Markdown files",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # build
    build_p = subparsers.add_parser("build", help="Build knowledge base")
    build_p.add_argument("--source-dir", default=None, help="Source directory")
    build_p.add_argument("--batch-size", type=int, default=64, help="Batch size (default: 64)")
    build_p.add_argument("--full-rebuild", action="store_true", help="Force full rebuild")
    build_p.set_defaults(func=cmd_build)

    # query
    query_p = subparsers.add_parser("query", help="Query knowledge base")
    query_p.add_argument("question", help="Query question")
    query_p.set_defaults(func=cmd_query)

    # status
    status_p = subparsers.add_parser("status", help="View status")
    status_p.set_defaults(func=cmd_status)

    # clear
    clear_p = subparsers.add_parser("clear", help="Clear knowledge base")
    clear_p.set_defaults(func=cmd_clear)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Use config default if source-dir not specified
    if args.command == "build" and args.source_dir is None:
        config = load_config(args.config)
        args.source_dir = config.get("sources_dir", _DEFAULT_SOURCE_DIR)

    args.func(args)


if __name__ == "__main__":
    main()

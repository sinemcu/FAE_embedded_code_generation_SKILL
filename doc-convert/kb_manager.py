#!/usr/bin/env python3
"""
FAE 知识库管理器 - 命令行入口
"""

import sys
import json
import argparse
from pathlib import Path


def load_config(config_path: str) -> dict:
    """加载配置"""
    with open(config_path, "r") as f:
        return json.load(f)


def cmd_build(args):
    """构建知识库"""
    from retriever.hybrid_search import KnowledgeBaseBuilder
    
    config = load_config(args.config)
    kb = KnowledgeBaseBuilder(args.kb_root, config)
    kb.build(
        source_dir=args.source_dir,
        batch_size=args.batch_size,
        incremental=not args.full_rebuild
    )


def cmd_query(args):
    """查询知识库"""
    from retriever.hybrid_search import KnowledgeBaseBuilder
    
    config = load_config(args.config)
    kb = KnowledgeBaseBuilder(args.kb_root, config)
    kb.query(args.question)


def cmd_status(args):
    """查看知识库状态"""
    from retriever.vector_store import ChromaVectorStore
    from retriever.keyword_index import WhooshKeywordIndex
    
    config = load_config(args.config)
    kb_root = Path(args.kb_root)
    
    print("📊 知识库状态\n")
    
    # 向量存储
    try:
        vs = ChromaVectorStore(str(kb_root / "indexes" / "vector"))
        print(f"向量索引：{vs.count()} 个分块")
    except Exception as e:
        print(f"向量索引：未初始化 ({e})")
    
    # 关键词索引
    try:
        ki = WhooshKeywordIndex(str(kb_root / "indexes" / "keyword"))
        print(f"关键词索引：{ki.count()} 个分块")
    except Exception as e:
        print(f"关键词索引：未初始化 ({e})")
    
    # 缓存
    cache_dir = kb_root / "cache"
    text_cache = list((cache_dir / "text").glob("*.json")) if (cache_dir / "text").exists() else []
    struct_cache = list((cache_dir / "structured").glob("*.json")) if (cache_dir / "structured").exists() else []
    print(f"文档缓存：{len(struct_cache)} 个文档")
    
    # 源文件
    source_dir = kb_root / "sources"
    if source_dir.exists():
        files = list(source_dir.rglob("*"))
        print(f"源文件：{len(files)} 个")


def cmd_clear(args):
    """清空知识库"""
    from retriever.vector_store import ChromaVectorStore
    from retriever.keyword_index import WhooshKeywordIndex
    
    config = load_config(args.config)
    kb_root = Path(args.kb_root)
    
    confirm = input("⚠️ 确定要清空知识库吗？(y/N): ")
    if confirm.lower() != "y":
        print("已取消")
        return
    
    print("\n清空知识库...")
    
    vs = ChromaVectorStore(str(kb_root / "indexes" / "vector"))
    vs.clear()
    
    ki = WhooshKeywordIndex(str(kb_root / "indexes" / "keyword"))
    ki.clear()
    
    print("✅ 知识库已清空")


def main():
    # 获取脚本所在目录（用于解析相对路径）
    script_dir = Path(__file__).parent.resolve()
    
    parser = argparse.ArgumentParser(description="FAE 知识库管理器")
    # 使用绝对路径作为默认值，避免从不同目录运行时出错
    parser.add_argument("--config", default=str(script_dir / "kb" / "config.json"), help="配置文件路径")
    parser.add_argument("--kb-root", default="/Users/sinomcu/.openclaw/workspace/fae_input", help="知识库根目录")
    parser.add_argument("--source-dir", default=None, help="源文档目录（相对于 kb-root 或绝对路径）")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # build 命令
    build_parser = subparsers.add_parser("build", help="构建知识库")
    build_parser.add_argument("--source-dir", default=None, help="源文档目录（相对于 kb-root 或绝对路径）")
    build_parser.add_argument("--batch-size", type=int, default=64, help="批量嵌入的批次大小 (default: 64)")
    build_parser.add_argument("--full-rebuild", action="store_true", help="强制完全重建（忽略增量构建）")
    build_parser.set_defaults(func=cmd_build)
    
    # query 命令
    query_parser = subparsers.add_parser("query", help="查询知识库")
    query_parser.add_argument("question", help="查询问题")
    query_parser.set_defaults(func=cmd_query)
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查看状态")
    status_parser.set_defaults(func=cmd_status)
    
    # clear 命令
    clear_parser = subparsers.add_parser("clear", help="清空知识库")
    clear_parser.set_defaults(func=cmd_clear)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 添加脚本目录到 Python 路径
    sys.path.insert(0, str(script_dir))
    
    # 如果 source-dir 未指定，使用配置中的默认值
    if args.command == "build" and args.source_dir is None:
        config = load_config(args.config)
        args.source_dir = config.get("sources_dir", "sources")
    
    args.func(args)


if __name__ == "__main__":
    main()

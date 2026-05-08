#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复知识库索引 - 处理 A280 和 MC30P6201 文件"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from pdf_to_md import pdf_to_markdown

def main():
    sources_dir = Path("/Users/sinomcu/.openclaw/workspace/fae_input/sources")
    cache_dir = Path("/Users/sinomcu/.openclaw/workspace/fae_input/cache/text")
    cache_meta_path = Path("/Users/sinomcu/.openclaw/workspace/fae_input/cache/.cache_meta.json")
    
    print("=" * 60)
    print("🔧 修复知识库索引问题")
    print("=" * 60)
    print()
    
    # 查找所有包含 A280 或 MC30P6201 的 PDF 文件
    files_to_convert = []
    for f in sources_dir.glob("*.pdf"):
        if "A280" in f.name or "MC30P6201" in f.name:
            files_to_convert.append(f)
            print(f"找到源文件：{f.name}")
    
    if not files_to_convert:
        print("⚠️  未找到需要转换的文件")
        return
    
    # 加载现有缓存元数据
    if cache_meta_path.exists():
        with open(cache_meta_path, "r") as f:
            cache_meta = json.load(f)
    else:
        cache_meta = {"files": {}, "version": "1.0"}
    
    # 转换每个文件
    converted_count = 0
    for pdf_path in files_to_convert:
        # 生成输出文件名（去除路径）
        output_filename = pdf_path.name.replace('.pdf', '.md')
        md_path = cache_dir / output_filename
        
        # 检查是否已转换
        if md_path.exists():
            print(f"⏭️  {pdf_path.name} 已存在转换结果")
            continue
        
        print(f"📖 转换：{pdf_path.name}")
        try:
            pdf_to_markdown(str(pdf_path), str(md_path))
            print(f"   ✅ 转换成功")
            converted_count += 1
            
            # 更新缓存元数据
            if "files" not in cache_meta:
                cache_meta["files"] = {}
            cache_meta["files"][pdf_path.name] = {
                "hash": "converted",  # 简化处理
                "converted_at": str(os.path.getmtime(md_path))
            }
        except Exception as e:
            print(f"   ❌ 转换失败：{e}")
            import traceback
            traceback.print_exc()
    
    # 保存更新的缓存元数据
    cache_meta["version"] = "1.1"
    
    with open(cache_meta_path, "w") as f:
        json.dump(cache_meta, f, indent=2)
    
    print()
    print("=" * 60)
    print(f"🎉 完成！成功转换：{converted_count} 个文件")
    print("=" * 60)
    
    # 现在构建知识库
    print()
    print("🔍 正在构建知识库索引...")
    
    from kb_manager import KBManager
    kb = KBManager(cache_dir)
    kb.build()
    
    print()
    print("📊 知识库状态:")
    kb.status()
    
    print()
    print("🔎 测试搜索:")
    kb.query("A280")
    kb.query("MC30P6201")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
关键词索引 - 使用 Whoosh 进行全文检索
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema, TEXT, ID, KEYWORD
from whoosh.analysis import SimpleAnalyzer
from whoosh.qparser import QueryParser


class WhooshKeywordIndex:
    """Whoosh 全文检索索引"""
    
    def __init__(self, index_dir: str):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._index = None
        self._searcher = None
        self._init_index()
    
    def _init_index(self):
        """初始化索引"""
        schema = Schema(
            id=ID(stored=True, unique=True),
            doc_id=ID(stored=True),
            text=TEXT(analyzer=SimpleAnalyzer(), stored=True),
            filename=TEXT(stored=True),
            keywords=KEYWORD(stored=True),
            chunk_idx=ID(stored=True),
            mcu_model=ID(stored=True),
            mcu_family=ID(stored=True),
            doc_type=ID(stored=True)
        )
        
        if exists_in(self.index_dir):
            self._index = open_dir(self.index_dir)
        else:
            self._index = create_in(self.index_dir, schema)
        
        print(f"✅ Whoosh index initialized: {self.index_dir}")
    
    def add_documents(self, chunks: List[Dict[str, Any]]):
        """添加文档到索引（包含丰富 metadata）"""
        writer = self._index.writer()
        
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            
            # 提取关键词（从文本和元数据）
            keywords = self._extract_keywords(chunk["text"], metadata)
            
            writer.add_document(
                id=chunk["id"],
                doc_id=metadata.get("doc_id", ""),
                text=chunk["text"],
                filename=metadata.get("filename", ""),
                keywords=keywords,
                chunk_idx=str(metadata.get("chunk_idx", 0)),
                mcu_model=metadata.get("mcu_model", "unknown"),
                mcu_family=metadata.get("mcu_family", "unknown"),
                doc_type=metadata.get("doc_type", "其他")
            )
        
        writer.commit()
        print(f"  ✓ 添加 {len(chunks)} 个分块到关键词索引")
    
    def _extract_keywords(self, text: str, metadata: Dict[str, Any]) -> str:
        """提取关键词"""
        keywords = []
        
        # 从文本中提取可能的关键词（十六进制、数字、大写字母组合）
        import re
        
        # 十六进制值 (如 0x40020000)
        hex_matches = re.findall(r'0x[0-9A-Fa-f]+', text)
        keywords.extend(hex_matches)
        
        # 寄存器名 (如 MODER, IDR)
        reg_matches = re.findall(r'\b[A-Z]{2,}[0-9]*\b', text)
        keywords.extend(reg_matches[:10])  # 限制数量
        
        # 数字值
        num_matches = re.findall(r'\b\d+(?:\.\d+)?(?:\s*(?:ms|MHz|kHz|V|mA|°C))?\b', text)
        keywords.extend(num_matches[:10])
        
        return " ".join(keywords)
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_doc_id: Optional[str] = None,
        filter_mcu_model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """关键词搜索（支持 MCU 型号过滤）"""
        from whoosh.query import Term
        with self._index.searcher() as searcher:
            parser = QueryParser("text", self._index.schema)
            q = parser.parse(query)
            
            # 添加 MCU 型号过滤
            if filter_mcu_model:
                from whoosh.query import And
                q = And([q, Term("mcu_model", filter_mcu_model)])
            
            # 执行搜索
            results = searcher.search(q, limit=top_k)
            
            formatted = []
            for hit in results:
                if filter_doc_id and hit["doc_id"] != filter_doc_id:
                    continue
                
                formatted.append({
                    "id": hit["id"],
                    "text": hit["text"],
                    "metadata": {
                        "doc_id": hit["doc_id"],
                        "filename": hit["filename"],
                        "chunk_idx": hit["chunk_idx"],
                        "mcu_model": hit.get("mcu_model", "unknown"),
                        "mcu_family": hit.get("mcu_family", "unknown"),
                        "doc_type": hit.get("doc_type", "其他")
                    },
                    "score": hit.score
                })
            
            return formatted
    
    def delete_by_doc_id(self, doc_id: str):
        """删除指定文档"""
        writer = self._index.writer()
        writer.delete_by_term("doc_id", doc_id)
        writer.commit()
        print(f"  ✓ 从关键词索引删除文档 {doc_id}")
    
    def count(self) -> int:
        """返回文档总数"""
        with self._index.searcher() as searcher:
            return searcher.doc_count()
    
    def clear(self):
        """清空索引"""
        self._index.close()
        
        # 删除索引文件
        for f in self.index_dir.glob("*"):
            f.unlink()
        
        # 重新创建
        self._init_index()
        print("  ✓ 关键词索引已清空")


if __name__ == "__main__":
    # 测试
    index = WhooshKeywordIndex("./test_whoosh")
    print(f"Keyword index count: {index.count()}")

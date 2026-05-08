#!/usr/bin/env python3
"""
向量存储 - 使用 ChromaDB
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import asdict


class ChromaVectorStore:
    """ChromaDB 向量存储"""
    
    def __init__(self, persist_dir: str, collection_name: str = "fae_kb"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._init_client()
    
    def _init_client(self):
        """初始化 ChromaDB 客户端"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            self._client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False)
            )
            
            # 获取或创建集合
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "FAE Knowledge Base"}
            )
            print(f"✅ ChromaDB initialized: {self.persist_dir}")
        except ImportError:
            print("⚠️ ChromaDB not installed. Run: pip install chromadb")
            raise
    
    def add_documents(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]):
        """添加文档和嵌入"""
        if not chunks or not embeddings:
            return
        
        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        
        # 确保 metadata 都是字符串（ChromaDB 要求）
        for m in metadatas:
            for k, v in m.items():
                if not isinstance(v, (str, int, float)):
                    m[k] = str(v)
        
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        print(f"  ✓ 添加 {len(chunks)} 个分块到向量索引")
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索"""
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"]
        )
        
        # 格式化结果
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                formatted.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                    "score": 1 - results["distances"][0][i] if results["distances"] else 1
                })
        
        return formatted
    
    def delete_by_doc_id(self, doc_id: str):
        """删除指定文档的所有分块"""
        # 获取所有属于该文档的分块
        results = self._collection.get(
            where={"doc_id": doc_id},
            include=[]
        )
        if results["ids"]:
            self._collection.delete(ids=results["ids"])
            print(f"  ✓ 删除文档 {doc_id} 的 {len(results['ids'])} 个分块")
    
    def count(self) -> int:
        """返回文档总数"""
        return self._collection.count()
    
    def clear(self):
        """清空集合"""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata={"description": "FAE Knowledge Base"}
        )
        print("  ✓ 向量索引已清空")


if __name__ == "__main__":
    # 测试
    store = ChromaVectorStore("./test_chroma")
    print(f"Vector store count: {store.count()}")

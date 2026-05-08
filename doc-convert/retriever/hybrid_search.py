#!/usr/bin/env python3
"""
混合检索器 - 结合向量检索和关键词检索
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from .embedder import OllamaEmbedder
from .vector_store import ChromaVectorStore
from .keyword_index import WhooshKeywordIndex


class HybridRetriever:
    """混合检索器"""
    
    def __init__(
        self,
        vector_store: ChromaVectorStore,
        keyword_index: WhooshKeywordIndex,
        embedder: OllamaEmbedder,
        config: Dict[str, Any]
    ):
        self.vector_store = vector_store
        self.keyword_index = keyword_index
        self.embedder = embedder
        self.config = config
        self.top_k = config.get("top_k", 5)
        self.rerank_top_k = config.get("rerank_top_k", 3)
        self.vector_weight = config.get("vector_weight", 0.5)
        self.bm25_weight = config.get("bm25_weight", 0.5)
    
    def _detect_mcu_filter(self, query: str) -> Optional[Dict[str, Any]]:
        """
        从查询文本中自动检测 MCU 型号，返回 metadata 过滤条件
        例如 "MC30P6060 PWM 配置" → {"mcu_model": "MC30P6060"}
        """
        import re
        # 匹配已知 MCU 厂商前缀的型号，避免误匹配 GPIO 端口名 (PA10, PB1 等)
        # 匹配: MC8059, MS8046, STM32F103, GD32, ATmega2560 等
        # 不匹配: PA10, PB1, TIM14 等 GPIO/外设名称
        matches = re.findall(r'\b((?:MC|MS|GD|STM|AT|CH|HK|WCH|NXP|MM|HDSC|ESP|RP|PIC)[A-Z0-9_]*\d+[A-Z0-9_]*)\b', query)
        if matches:
            # 使用第一个匹配的型号（通常是用户指定的目标）
            return {"mcu_model": matches[0]}
        return None
    
    def _merge_filters(self, explicit: Optional[Dict], detected: Optional[Dict]) -> Optional[Dict]:
        """合并显式和自动检测的过滤条件，显式优先"""
        if explicit:
            return explicit
        return detected
    
    def search(self, query: str, filter_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行混合检索（支持自动 MCU 型号过滤 + 手动过滤）
        
        1. 从查询中自动检测 MCU 型号
        2. 向量检索（语义相似）
        3. 关键词检索（精确匹配）
        4. 融合结果（可配置 BM25/向量权重）
        """
        # 0. 自动检测过滤条件（如果未显式提供）
        auto_filter = self._detect_mcu_filter(query)
        effective_filter = self._merge_filters(filter_metadata, auto_filter)
        
        if auto_filter and not filter_metadata:
            print(f"🏷️ 自动过滤：{auto_filter}")
        
        # 1. 生成查询嵌入
        query_embedding = self.embedder.embed(query)
        
        # 2. 向量检索（带 metadata 过滤）
        vector_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=self.top_k * 2,
            filter_metadata=effective_filter
        )
        
        # 3. 关键词检索（支持 doc_id 和 mcu_model 过滤）
        keyword_doc_filter = effective_filter.get("doc_id") if effective_filter else None
        keyword_mcu_filter = effective_filter.get("mcu_model") if effective_filter else None
        keyword_results = self.keyword_index.search(
            query=query,
            top_k=self.top_k * 2,
            filter_doc_id=keyword_doc_filter,
            filter_mcu_model=keyword_mcu_filter
        )
        
        # 4. 融合结果（使用可配置权重）
        fused = self._reciprocal_rank_fusion(vector_results, keyword_results)
        
        # 返回 Top-K
        return fused[:self.top_k]
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        倒数排名融合 (RRF)
        
        公式：score = Σ weight * 1 / (k + rank)
        权重由 config 中的 vector_weight / bm25_weight 控制
        """
        score_map: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        
        # 处理向量结果（使用可配置权重）
        for rank, result in enumerate(vector_results, 1):
            doc_id = result["id"]
            score = 1 / (k + rank)
            
            if doc_id not in score_map:
                score_map[doc_id] = (0, result)
            
            current_score, _ = score_map[doc_id]
            score_map[doc_id] = (current_score + score * self.vector_weight, result)
        
        # 处理关键词结果（使用可配置权重）
        for rank, result in enumerate(keyword_results, 1):
            doc_id = result["id"]
            score = 1 / (k + rank)
            
            if doc_id not in score_map:
                score_map[doc_id] = (0, result)
            
            current_score, _ = score_map[doc_id]
            score_map[doc_id] = (current_score + score * self.bm25_weight, result)
        
        # 排序
        sorted_results = sorted(
            score_map.values(),
            key=lambda x: x[0],
            reverse=True
        )
        
        # 格式化输出
        formatted = []
        for score, result in sorted_results:
            result["fusion_score"] = score
            formatted.append(result)
        
        return formatted
    
    def _rerank(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        重排序（使用本地重排序模型）
        
        注意：这是一个简化版本，实际可以使用 bge-reranker 等模型
        """
        # 简单实现：基于查询匹配度重新评分
        query_lower = query.lower()
        
        for result in results:
            text_lower = result["text"].lower()
            
            # 计算关键词匹配度
            query_words = query_lower.split()
            match_count = sum(1 for w in query_words if w in text_lower and len(w) > 2)
            
            # 调整分数
            result["rerank_score"] = result.get("fusion_score", 0) * (1 + match_count * 0.1)
        
        # 按重排序分数排序
        results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        return results
    
    def search_with_context(
        self,
        query: str,
        include_neighbors: bool = True,
        neighbor_window: int = 1
    ) -> List[Dict[str, Any]]:
        """
        检索并包含上下文（相邻分块）
        """
        results = self.search(query)
        
        if not include_neighbors:
            return results
        
        # 获取相邻分块（简化实现）
        expanded = []
        for result in results:
            expanded.append(result)
            
            # 这里可以添加逻辑来获取同一文档的相邻分块
            # 需要查询 vector_store 获取同文档的其他分块
        
        return expanded


class KnowledgeBaseBuilder:
    """知识库构建器"""
    
    def __init__(self, kb_root: str, config: Dict[str, Any]):
        from .embedder import OllamaEmbedder, SentenceTransformerEmbedder
        
        self.kb_root = Path(kb_root)
        self.config = config
        
        # 根据配置选择嵌入后端
        backend = config.get("embedding_backend", "sentence_transformers")
        
        if backend == "ollama":
            print("🔌 使用 Ollama 嵌入后端")
            self.embedder = OllamaEmbedder(
                model=config.get("embedding_ollama_model", "nomic-embed-text"),
                dims=config.get("embedding_ollama_dims", 768)
            )
        else:  # sentence_transformers
            print("🧠 使用 sentence-transformers 嵌入后端")
            
            # 构建本地模型路径（相对于 kb 目录）
            model_path = config.get("embedding_model_path")
            if model_path:
                kb_dir = Path(self.kb_root) / "kb"
                full_model_path = kb_dir / model_path
                if not full_model_path.exists():
                    # 尝试相对于脚本目录
                    script_dir = Path(__file__).parent.parent
                    full_model_path = script_dir / model_path
            else:
                full_model_path = None
            
            self.embedder = SentenceTransformerEmbedder(
                model=config.get("embedding_model", "paraphrase-multilingual-MiniLM-L12-v2"),
                dims=config.get("embedding_dims", 384),
                model_path=str(full_model_path) if full_model_path else None
            )
        
        self.vector_store = ChromaVectorStore(
            persist_dir=str(self.kb_root / "indexes" / "vector")
        )
        
        self.keyword_index = WhooshKeywordIndex(
            index_dir=str(self.kb_root / "indexes" / "keyword")
        )
        
        self.retriever = HybridRetriever(
            vector_store=self.vector_store,
            keyword_index=self.keyword_index,
            embedder=self.embedder,
            config=config
        )
    
    def build(self, source_dir: Optional[str] = None, batch_size: int = 64, incremental: bool = True):
        """
        构建知识库
        
        Args:
            source_dir: 源文档目录
            batch_size: 批量嵌入的批次大小
            incremental: 是否启用增量构建（跳过未变更的文档）
        """
        from .document_parser import DocumentParser
        import hashlib
        import json
        
        source_path = self.kb_root / (source_dir or "sources")
        if not source_path.exists():
            print(f"⚠️ 源目录不存在：{source_path}")
            return
        
        # 加载增量构建元数据
        build_meta_file = self.kb_root / ".build_meta.json"
        build_meta = {"files": {}} if not build_meta_file.exists() else json.loads(build_meta_file.read_text())
        
        parser = DocumentParser(self.config)
        
        # 遍历所有支持的文件
        supported = self.config.get("supported_formats", [".pdf", ".xlsx", ".md", ".txt"])
        files = []
        for ext in supported:
            files.extend(source_path.rglob(f"*{ext}"))
        
        print(f"📚 发现 {len(files)} 个文档")
        print(f"🚀 批量嵌入：batch_size={batch_size}")
        print(f"🔄 增量构建：{incremental}\n")
        
        total_chunks = 0
        processed = 0
        skipped = 0
        
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] 处理：{file_path.name}")
            
            # 增量构建检查（基于缓存的 structured JSON 和 build_meta）
            cache_struct = self.kb_root / "cache" / "structured"
            doc_id = hashlib.md5(str(file_path).encode()).hexdigest()[:16]
            cache_file = cache_struct / f"{doc_id}.json"
            
            if incremental and cache_file.exists():
                file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
                cached_hash = build_meta["files"].get(str(file_path), {}).get("hash")
                
                if cached_hash == file_hash:
                    print(f"  ⏭️  跳过（未变更）")
                    skipped += 1
                    continue
            
            # 处理前清理旧索引（防止重复条目）
            self.vector_store.delete_by_doc_id(doc_id)
            self.keyword_index.delete_by_doc_id(doc_id)
            
            try:
                # 解析文档
                parsed = parser.parse_file(str(file_path))
                chunks = [c for c in parsed.chunks if c.text.strip()]
                
                if not chunks:
                    print(f"  ⚠️ 无有效内容")
                    continue
                
                # 批量生成嵌入并立即刷入索引（每文件独立）
                print(f"  生成嵌入 ({len(chunks)} 个分块)...")
                
                new_chunks = []
                new_embeddings = []
                
                for batch_start in range(0, len(chunks), batch_size):
                    batch_end = min(batch_start + batch_size, len(chunks))
                    batch_chunks = chunks[batch_start:batch_end]
                    
                    batch_embeddings = self.embedder.embed_batch([c.text for c in batch_chunks])
                    
                    for chunk, emb in zip(batch_chunks, batch_embeddings):
                        new_chunks.append({
                            "id": chunk.id,
                            "text": chunk.text,
                            "metadata": chunk.metadata
                        })
                        new_embeddings.append(emb)
                    
                    print(f"    ✓ 批次 {batch_start//batch_size + 1}/{(len(chunks)-1)//batch_size + 1}")
                
                # 本文件的分块立即写入索引（避免累积过多导致 OOM）
                self.vector_store.add_documents(new_chunks, new_embeddings)
                self.keyword_index.add_documents(new_chunks)
                
                # 保存缓存
                parser.save_cache(parsed, str(self.kb_root / "cache"))
                
                # 更新元数据
                if incremental:
                    file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
                    build_meta["files"][str(file_path)] = {
                        "hash": file_hash,
                        "chunks": len(chunks),
                        "processed_at": str(file_path.stat().st_mtime)
                    }
                
                total_chunks += len(chunks)
                processed += 1
                
            except Exception as e:
                print(f"  ⚠️ 处理失败：{e}")
        
        # 保存构建元数据
        if incremental:
            build_meta_file.write_text(json.dumps(build_meta, indent=2, ensure_ascii=False))
        
        print(f"\n✅ 知识库构建完成！")
        print(f"   新增：{processed} 个文档")
        print(f"   跳过：{skipped} 个文档")
        print(f"   总计：{total_chunks} 个分块")
    
    def query(self, question: str) -> List[Dict[str, Any]]:
        """查询知识库"""
        results = self.retriever.search(question)
        
        print(f"\n🔍 查询：{question}")
        print(f"找到 {len(results)} 个相关结果:\n")
        
        for i, result in enumerate(results, 1):
            print(f"{i}. [分数：{result.get('fusion_score', 0):.4f}]")
            print(f"   文件：{result['metadata'].get('filename', 'N/A')}")
            print(f"   内容：{result['text'][:200]}...")
            print()
        
        return results


if __name__ == "__main__":
    # 测试
    config = {
        "embedding_model": "nomic-embed-text",
        "top_k": 5,
        "rerank_top_k": 3,
        "supported_formats": [".md", ".txt"]
    }
    
    kb = KnowledgeBaseBuilder("./kb", config)
    print("KnowledgeBase initialized")

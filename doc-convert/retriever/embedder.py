#!/usr/bin/env python3
"""
嵌入模型 - 支持 Ollama HTTP API 和 sentence-transformers
"""

import json
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional
import subprocess


class SentenceTransformerEmbedder:
    """使用 sentence-transformers 进行文本嵌入（无需 Ollama）"""
    
    def __init__(self, model: str = "paraphrase-multilingual-MiniLM-L12-v2", dims: int = 384, model_path: str = None):
        self.model_name = model
        self.dims = dims
        self.model = None
        self.model_path = model_path
        self._load_model()
    
    def _load_model(self):
        """加载 sentence-transformers 模型"""
        try:
            from sentence_transformers import SentenceTransformer
            
            # 如果指定了本地路径，使用本地路径加载
            if self.model_path:
                model_path = Path(self.model_path)
                if not model_path.exists():
                    raise FileNotFoundError(f"模型路径不存在：{self.model_path}")
                print(f"📥 从本地路径加载嵌入模型：{self.model_path}")
                self.model = SentenceTransformer(str(model_path))
            else:
                print(f"📥 加载嵌入模型：{self.model_name}")
                self.model = SentenceTransformer(self.model_name)
            
            print(f"✅ 模型加载完成，维度：{self.dims}")
        except ImportError:
            print("⚠️ sentence-transformers 未安装")
            print("💡 请运行：pip3 install sentence-transformers")
            raise
    
    def embed(self, text: str) -> List[float]:
        """生成单个文本的嵌入"""
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"⚠️ 嵌入失败：{e}")
            raise
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """批量生成嵌入（更高效）"""
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=True
            )
            return embeddings.tolist()
        except Exception as e:
            print(f"⚠️ 批量嵌入失败：{e}")
            raise
    
    def generate_embedding_ref(self, text: str) -> str:
        """生成嵌入引用 ID"""
        return hashlib.md5(text.encode()).hexdigest()[:16]


class OllamaEmbedder:
    """使用 Ollama HTTP API 进行文本嵌入"""
    
    def __init__(self, model: str = "nomic-embed-text", dims: int = 768, host: str = "http://localhost:11434"):
        self.model = model
        self.dims = dims
        self.host = host
        self._ensure_model()
    
    def _ensure_model(self):
        """确保模型已下载"""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            if self.model not in result.stdout:
                print(f"📥 下载嵌入模型：{self.model}")
                subprocess.run(
                    ["ollama", "pull", self.model],
                    check=True
                )
        except subprocess.CalledProcessError as e:
            print(f"⚠️ 检查 Ollama 模型失败：{e}")
            raise
    
    def embed(self, text: str) -> List[float]:
        """生成单个文本的嵌入 (使用 HTTP API)"""
        try:
            data = json.dumps({"model": self.model, "prompt": text}).encode('utf-8')
            req = urllib.request.Request(
                f"{self.host}/api/embeddings",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get("embedding", [])
        except urllib.error.URLError as e:
            print(f"⚠️ 嵌入失败 (HTTP): {e}")
            raise
        except Exception as e:
            print(f"⚠️ 嵌入失败：{e}")
            raise
    
    def embed_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """批量生成嵌入"""
        embeddings = []
        for i, text in enumerate(texts):
            emb = self.embed(text)
            embeddings.append(emb)
            print(f"  已处理 {i+1}/{len(texts)}", end="\r")
        print()
        return embeddings
    
    def generate_embedding_ref(self, text: str) -> str:
        """生成嵌入引用 ID"""
        return hashlib.md5(text.encode()).hexdigest()[:16]


class EmbeddingCache:
    """嵌入缓存"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir) / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, List[float]] = {}
        self._load_cache()
    
    def _load_cache(self):
        """加载现有缓存"""
        cache_file = self.cache_dir / "cache.json"
        if cache_file.exists():
            with open(cache_file, "r") as f:
                self._cache = json.load(f)
    
    def save_cache(self):
        """保存缓存"""
        cache_file = self.cache_dir / "cache.json"
        with open(cache_file, "w") as f:
            json.dump(self._cache, f)
    
    def get(self, ref: str) -> Optional[List[float]]:
        """获取缓存的嵌入"""
        return self._cache.get(ref)
    
    def set(self, ref: str, embedding: List[float]):
        """设置嵌入缓存"""
        self._cache[ref] = embedding
        self.save_cache()
    
    def exists(self, ref: str) -> bool:
        """检查嵌入是否存在"""
        return ref in self._cache


if __name__ == "__main__":
    # 测试
    embedder = OllamaEmbedder()
    test_text = "This is a test sentence for embedding."
    emb = embedder.embed(test_text)
    print(f"Embedding dims: {len(emb)}")
    print(f"First 5 values: {emb[:5]}")

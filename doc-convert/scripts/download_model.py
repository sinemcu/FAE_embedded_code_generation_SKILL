#!/usr/bin/env python3
"""
嵌入模型下载脚本
从 HuggingFace 下载 paraphrase-multilingual-MiniLM-L12-v2 模型到本地。

用法:
    python3 download_model.py                          # 下载到当前目录
    python3 download_model.py /path/to/save/           # 下载到指定目录
"""

import sys
from pathlib import Path


def download_model(target_dir: str = None):
    """下载模型到本地"""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("❌ 请先安装 sentence-transformers:")
        print("   pip3 install sentence-transformers")
        sys.exit(1)

    model_name = "paraphrase-multilingual-MiniLM-L12-v2"

    if target_dir:
        target_path = Path(target_dir)
    else:
        target_path = Path(__file__).parent

    target_path.mkdir(parents=True, exist_ok=True)

    # 检查是否已存在
    model_path = target_path / model_name
    if model_path.exists() and (model_path / "config.json").exists():
        print(f"✅ 模型已存在于: {model_path}")
        return

    print(f"📥 从 HuggingFace 下载模型: {model_name}")
    print(f"   保存路径: {model_path}")
    print(f"   大小约 400MB，请耐心等待...")
    print()

    # sentence-transformers 会自动缓存到本地
    model = SentenceTransformer(model_name)

    # 保存到指定路径
    model.save(str(model_path))

    print()
    print(f"✅ 模型下载完成!")
    print(f"   路径: {model_path}")
    print(f"   维度: {model.get_sentence_embedding_dimension()}")
    print()
    print("💡 如果下次仍从远程下载，请在 config.json 中设置 embedding_model_path:")
    print(f'   "embedding_model_path": "{model_path}"')


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    download_model(target)

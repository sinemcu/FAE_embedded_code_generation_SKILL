#!/usr/bin/env python3
"""
文档解析器 - 支持 PDF, Excel, Markdown, Text
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class DocumentChunk:
    """文档分块"""
    id: str
    text: str
    metadata: Dict[str, Any]
    embedding_ref: str = ""


@dataclass
class ParsedDocument:
    """解析后的文档"""
    doc_id: str
    source_path: str
    chunks: List[DocumentChunk]
    file_type: str
    parsed_at: str


class DocumentParser:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.chunk_size = config.get("chunk_size", 512)
        self.chunk_overlap = config.get("chunk_overlap", 50)
        
    def parse_file(self, file_path: str) -> ParsedDocument:
        """解析单个文件"""
        path = Path(file_path)
        ext = path.suffix.lower()
        
        # 生成文档 ID
        doc_id = self._generate_doc_id(file_path)
        
        # 根据文件类型选择解析器
        if ext == ".pdf":
            text = self._parse_pdf(file_path)
        elif ext in [".xlsx", ".xls"]:
            text = self._parse_excel(file_path)
        elif ext in [".md", ".txt"]:
            text = self._parse_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        
        # 分块
        chunks = self._chunk_text(text, doc_id, path.name)
        
        return ParsedDocument(
            doc_id=doc_id,
            source_path=str(path),
            chunks=chunks,
            file_type=ext,
            parsed_at=""  # 由调用者填充
        )
    
    def _generate_doc_id(self, file_path: str) -> str:
        """生成文档 ID"""
        return hashlib.md5(file_path.encode()).hexdigest()[:16]
    
    def _parse_pdf(self, file_path: str) -> str:
        """解析 PDF 文件，使用 pymupdf4llm 提取为 Markdown 格式"""
        try:
            import pymupdf4llm
            md_text = pymupdf4llm.to_markdown(file_path)
            # 简单清理
            import re
            md_text = re.sub(r'\n{3,}', '\n\n', md_text)
            return md_text.strip()
        except ImportError:
            print(f"⚠️ pymupdf4llm not installed, falling back to raw text extraction")
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            except ImportError:
                print("⚠️ PyMuPDF not installed, trying pdftotext...")
                import subprocess
                result = subprocess.run(
                    ["pdftotext", file_path, "-"],
                    capture_output=True,
                    text=True
                )
                return result.stdout
    
    def _parse_excel(self, file_path: str) -> str:
        """解析 Excel 文件"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True)
            text = ""
            for sheet in wb.worksheets:
                text += f"\n=== Sheet: {sheet.title} ===\n"
                for row in sheet.iter_rows(values_only=True):
                    text += " | ".join(str(c) if c is not None else "" for c in row) + "\n"
            return text
        except ImportError:
            print("⚠️ openpyxl not installed")
            return ""
    
    def _parse_text(self, file_path: str) -> str:
        """解析文本文件"""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    
    def _chunk_text(self, text: str, doc_id: str, filename: str) -> List[DocumentChunk]:
        """
        将文本分块 - 递归字符切分器，适配中文技术文档
        
        策略（按优先级递减）：
        1. 按 Markdown 标题 (## / ### / ####) 切分大块区域
        2. 按段落 (\n\n) 切分中等块
        3. 按句子 (. 。! ！? ？\n) 切分小块
        4. 按字符数硬切分作为兜底
        """
        chunks = []
        chunk_idx = 0
        
        # 第一阶段：按 Markdown 标题切分为 sections
        sections = self._split_by_headings(text)
        
        for section in sections:
            # 第二阶段：对每个 section，按段落进一步拆分
            sub_chunks = self._split_by_paragraphs(section)
            
            for sub in sub_chunks:
                if len(sub) <= self.chunk_size:
                    # 直接作为一个 chunk（如果非空）
                    if sub.strip():
                        chunks.append(self._make_chunk(doc_id, filename, chunk_idx, sub.strip()))
                        chunk_idx += 1
                else:
                    # 第三阶段：大块递归按句子切分 + 兜底硬切分
                    sub_sub = self._split_by_sentences(sub, doc_id, filename, chunk_idx)
                    chunks.extend(sub_sub)
                    chunk_idx = max(c.metadata["chunk_idx"] for c in sub_sub) + 1 if sub_sub else chunk_idx
        
        return chunks
    
    def _split_by_headings(self, text: str) -> List[str]:
        """按 Markdown 标题 (## / ### / ####) 切分"""
        import re
        # 匹配 ## / ### / #### 开头的行（不匹配 # 单独的标题，可能是表格线）
        heading_pattern = re.compile(r'^(#{2,4}\s+.+)$', re.MULTILINE)
        matches = list(heading_pattern.finditer(text))
        
        if not matches:
            return [text]
        
        sections = []
        prev_end = 0
        for m in matches:
            if m.start() > prev_end:
                section_text = text[prev_end:m.start()].strip()
                if section_text:
                    sections.append(section_text)
            # 从标题开始到下一个标题之前都属于这个 section
            prev_end = m.start()
        
        # 最后一个 section（从最后一个标题到文本末尾）
        last = text[matches[-1].start():].strip()
        if last:
            sections.append(last)
        
        return sections
    
    def _split_by_paragraphs(self, text: str) -> List[str]:
        """按段落切分，如果段落仍然太大则进一步拆分"""
        paragraphs = text.split("\n\n")
        segments = []
        current = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(para) > self.chunk_size:
                # 单个段落就超大，先保存已有的，再单独处理这个段落
                if current:
                    segments.append(current)
                    current = ""
                segments.append(para)  # 留给后续进一步拆分
            elif len(current) + len(para) + 2 <= self.chunk_size:
                current = current + "\n\n" + para if current else para
            else:
                if current:
                    segments.append(current)
                current = para
        
        if current:
            segments.append(current)
        
        return segments
    
    def _split_by_sentences(self, text: str, doc_id: str, filename: str, start_idx: int) -> List[DocumentChunk]:
        """按句子切分大块，并在必要时进行硬切分"""
        import re
        chunks = []
        
        # 按句子分隔符切分：。！.!?！？以及换行符后跟新句子开头（非空格字母数字）
        sentence_pattern = re.compile(r'(?<=[。！.!?！？])|(?<=\n)(?=[\u4e00-\u9fff\w\(\[（])')
        parts = sentence_pattern.split(text)
        
        current = ""
        idx = start_idx
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            if len(part) > self.chunk_size:
                # 单个句子超长，保存已有的，再硬切分这个部分
                if current:
                    chunks.append(self._make_chunk(doc_id, filename, idx, current.strip()))
                    idx += 1
                    current = ""
                # 硬切分超长句子（兜底）
                hard_chunks = self._hard_split(part)
                for hc in hard_chunks:
                    chunks.append(self._make_chunk(doc_id, filename, idx, hc))
                    idx += 1
            elif len(current) + len(part) + 2 <= self.chunk_size:
                current = current + " " + part if current else part
            else:
                if current:
                    chunks.append(self._make_chunk(doc_id, filename, idx, current.strip()))
                    idx += 1
                current = part
        
        if current:
            chunks.append(self._make_chunk(doc_id, filename, idx, current.strip()))
            idx += 1
        
        return chunks
    
    def _hard_split(self, text: str) -> List[str]:
        """兜底方案：按字符数硬切分（用于极端超长段落/句子）"""
        chunks = []
        chunk_size = self.chunk_size
        overlap = min(self.chunk_overlap, chunk_size // 2)  # overlap 最多为 chunk_size 的一半
        
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)  # 保证前进，不会死循环
        
        return chunks
    
    def _make_chunk(self, doc_id: str, filename: str, idx: int, text: str) -> DocumentChunk:
        """创建文档分块对象，附带丰富的 metadata"""
        import re
        # 从文件名提取 MCU 型号（如 MC30P6060, MS8046, MC60FXXX 等）
        mcu_match = re.search(r'([A-Z]{2}\d+[A-Z0-9]*)', filename)
        mcu_model = mcu_match.group(1) if mcu_match else "unknown"
        # 提取系列前缀（如 MC30, MS80, MC60）
        family_match = re.search(r'([A-Z]{2}\d+)', mcu_model)
        mcu_family = family_match.group(1) if family_match else "unknown"
        # 判断文档类型（基于文件名关键词）
        fn_lower = filename.lower()
        if any(k in fn_lower for k in ['数据手册', 'datasheet', '数据']):
            doc_type = "数据手册"
        elif any(k in fn_lower for k in ['用户手册', 'user manual', 'manual']):
            doc_type = "用户手册"
        elif any(k in fn_lower for k in ['原理图', 'schematic', 'net', '网表']):
            doc_type = "原理图"
        elif any(k in fn_lower for k in ['需求', 'requirement', 'spec', '规格']):
            doc_type = "需求规格"
        elif any(k in fn_lower for k in ['pack', '库', 'library']):
            doc_type = "库文件"
        else:
            doc_type = "其他"
        
        return DocumentChunk(
            id=f"{doc_id}_chunk_{idx}",
            text=text,
            metadata={
                "doc_id": doc_id,
                "filename": filename,
                "chunk_idx": idx,
                "type": "text",
                "mcu_model": mcu_model,
                "mcu_family": mcu_family,
                "doc_type": doc_type
            }
        )
    
    def save_cache(self, parsed: ParsedDocument, cache_dir: str):
        """保存解析缓存"""
        cache_path = Path(cache_dir) / "structured"
        cache_path.mkdir(parents=True, exist_ok=True)
        
        # 保存结构化数据
        data = asdict(parsed)
        data["chunks"] = [asdict(c) for c in parsed.chunks]
        
        output_file = cache_path / f"{parsed.doc_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 保存纯文本缓存
        text_path = Path(cache_dir) / "text"
        text_path.mkdir(parents=True, exist_ok=True)
        
        with open(text_path / f"{parsed.doc_id}.txt", "w", encoding="utf-8") as f:
            for chunk in parsed.chunks:
                f.write(f"\n--- {chunk.id} ---\n")
                f.write(chunk.text)
        
        return output_file


if __name__ == "__main__":
    # 测试
    config = {"chunk_size": 512, "chunk_overlap": 50}
    parser = DocumentParser(config)
    print("DocumentParser initialized")

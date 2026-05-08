#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAE Skill - PDF to Markdown Converter
Extracts text from PDF datasheets for embedded code generation
"""

import pymupdf4llm
import os
import re
import sys
from pathlib import Path


def clean_markdown(text):
    """Clean converted markdown from technical documents"""
    # Remove page numbers
    text = re.sub(r'\n\s*Page\s+\d+\s+of\s+\d+\s*\n', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\n\s*-\s*\d+\s*-\s*\n', '\n', text)
    
    # Remove extra blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove watermarks
    text = re.sub(r'sinomcu.com', '', text, flags=re.IGNORECASE)
    text = re.sub(r'confidential', '', text, flags=re.IGNORECASE)
    
    return text.strip()


def pdf_to_markdown(pdf_path, output_path=None, extract_images=False):
    """
    Convert PDF to Markdown
    
    Args:
        pdf_path (str): Path to PDF file
        output_path (str): Output MD file path (default: same as PDF with .md)
        extract_images (bool): Extract images (default: False for text-only)
    
    Returns:
        str: Path to generated MD file
    """
    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        if not pdf_path.lower().endswith('.pdf'):
            raise ValueError("Input must be PDF file")
        
        pdf_file = Path(pdf_path)
        if output_path is None:
            output_path = pdf_file.with_suffix('.md')
        else:
            output_path = Path(output_path)
        
        print(f"📖 Converting: {pdf_path}")
        
        # Convert PDF to markdown
        md_text = pymupdf4llm.to_markdown(
            pdf_path,
            show_progress=True,
            write_images=extract_images
        )
        
        # Clean the text
        md_text = clean_markdown(md_text)
        
        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_text)
        
        file_size = output_path.stat().st_size / 1024
        print(f"✅ Created: {output_path} ({file_size:.1f} KB)")
        
        return str(output_path)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pdf_to_md.py <input.pdf> [output.md]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        pdf_to_markdown(pdf_path, output_path)
    except Exception as e:
        sys.exit(1)

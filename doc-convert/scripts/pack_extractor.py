#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAE Skill - CMSIS Pack Extractor
Extracts device support files from .pack archives
"""

import zipfile
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def extract_pack(pack_path, output_dir=None):
    """
    Extract CMSIS .pack file
    
    Args:
        pack_path (str): Path to .pack file
        output_dir (str): Output directory (default: packname_extracted)
    
    Returns:
        dict: Extraction info and file counts
    """
    try:
        if not os.path.exists(pack_path):
            raise FileNotFoundError(f"Pack file not found: {pack_path}")
        
        if not pack_path.lower().endswith('.pack'):
            raise ValueError("Input must be .pack file")
        
        pack_file = Path(pack_path)
        if output_dir is None:
            output_dir = pack_file.parent / f"{pack_file.stem}_extracted"
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📦 Extracting: {pack_path}")
        
        with zipfile.ZipFile(pack_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            print(f"📋 Contains {len(file_list)} files")
            
            # Extract all files
            zip_ref.extractall(output_dir)
            
            # Categorize files
            categories = {
                'pdsc': [], 'c': [], 'h': [],
                'doc': [], 'other': []
            }
            
            for file_name in file_list:
                if file_name.endswith('.pdsc'):
                    categories['pdsc'].append(file_name)
                elif file_name.endswith('.c'):
                    categories['c'].append(file_name)
                elif file_name.endswith('.h'):
                    categories['h'].append(file_name)
                elif file_name.endswith(('.pdf', '.md', '.txt', '.html')):
                    categories['doc'].append(file_name)
                else:
                    categories['other'].append(file_name)
        
        # Parse PDSC for package info
        pack_info = {}
        for pdsc_file in categories['pdsc']:
            try:
                tree = ET.parse(output_dir / pdsc_file)
                root = tree.getroot()
                
                for elem in root:
                    if 'package' in elem.tag.lower():
                        pack_info['name'] = elem.get('name', '')
                        pack_info['vendor'] = elem.get('vendor', '')
                        pack_info['version'] = elem.get('version', '')
                        break
            except:
                pass
        
        # Print summary
        print(f"\n🎯 Extracted to: {output_dir}")
        print(f"📊 File breakdown:")
        print(f"   PDSC: {len(categories['pdsc'])}")
        print(f"   C files: {len(categories['c'])}")
        print(f"   H files: {len(categories['h'])}")
        print(f"   Docs: {len(categories['doc'])}")
        print(f"   Other: {len(categories['other'])}")
        
        if pack_info:
            print(f"\n🏷️ Package: {pack_info.get('vendor', '')} {pack_info.get('name', '')} v{pack_info.get('version', '')}")
        
        return {
            'extracted_to': str(output_dir),
            'files': categories,
            'info': pack_info
        }
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pack_extractor.py <device.pack> [output_dir]")
        sys.exit(1)
    
    pack_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        extract_pack(pack_path, output_dir)
    except Exception as e:
        sys.exit(1)

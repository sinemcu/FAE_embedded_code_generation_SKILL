#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOC-CONVERT - Document Conversion Entry Point
Unified interface for converting project documents

Features:
- Parallel processing with ProcessPoolExecutor
- Incremental build with content hash validation
- Smart caching to avoid re-conversion
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed

# Add scripts directory to path
script_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(script_dir))

# Import converters
from pdf_to_md import pdf_to_markdown
from xlsx2csv import xlsx_to_csv
from pack_extractor import extract_pack


class DocumentConverter:
    """Document conversion manager with caching and parallel processing"""
    
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.cache_dir = self.output_dir / "text"
        self.extract_dir = self.output_dir / "extracted"
        self.cache_meta_file = self.output_dir / ".cache_meta.json"
        
        # Create output directories
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.extract_dir.mkdir(parents=True, exist_ok=True)
        
        # Load cache metadata
        self.cache_meta = self._load_cache_meta()
        
        # Statistics
        self.stats = {
            "pdf": 0, "xlsx": 0, "pack": 0,
            "total": 0, "errors": 0
        }
    
    def _load_cache_meta(self) -> Dict:
        """Load cache metadata from file"""
        if self.cache_meta_file.exists():
            try:
                with open(self.cache_meta_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"files": {}, "version": "1.0"}
    
    def _save_cache_meta(self):
        """Save cache metadata to file"""
        with open(self.cache_meta_file, "w") as f:
            json.dump(self.cache_meta, f, indent=2)
    
    def _compute_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of file content"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def is_cached(self, filename: str, ext: str, file_path: Path = None) -> bool:
        """Check if file is already converted with valid hash"""
        # Check if output exists
        if ext == ".pdf":
            cache_file = self.cache_dir / f"{Path(filename).stem}.md"
            if not cache_file.exists():
                return False
        elif ext in [".xlsx", ".xls"]:
            csv_files = list(self.cache_dir.glob(f"{Path(filename).stem}_*.csv"))
            if len(csv_files) == 0:
                return False
        elif ext == ".pack":
            extract_folder = self.extract_dir / f"{Path(filename).stem}_extracted"
            if not extract_folder.exists():
                return False
        else:
            return False
        
        # Check hash if file_path provided (incremental build)
        if file_path and filename in self.cache_meta.get("files", {}):
            current_hash = self._compute_hash(file_path)
            cached_hash = self.cache_meta["files"][filename].get("hash")
            return current_hash == cached_hash
        
        return True
    
    def _update_cache_meta(self, filename: str, file_path: Path):
        """Update cache metadata for a file"""
        if "files" not in self.cache_meta:
            self.cache_meta["files"] = {}
        
        self.cache_meta["files"][filename] = {
            "hash": self._compute_hash(file_path),
            "converted_at": str(Path(file_path).stat().st_mtime)
        }
        self._save_cache_meta()
    
    def convert_pdf(self, pdf_path: Path) -> Optional[str]:
        """Convert PDF to Markdown"""
        output_path = self.cache_dir / f"{pdf_path.stem}.md"
        
        try:
            result = pdf_to_markdown(str(pdf_path), str(output_path))
            self.stats["pdf"] += 1
            self._update_cache_meta(pdf_path.name, pdf_path)
            return result
        except Exception as e:
            print(f"❌ Failed to convert {pdf_path.name}: {e}")
            self.stats["errors"] += 1
            return None
    
    def convert_xlsx(self, xlsx_path: Path) -> Optional[List[str]]:
        """Convert Excel to CSV"""
        try:
            results = xlsx_to_csv(str(xlsx_path), str(self.cache_dir))
            self.stats["xlsx"] += 1
            self._update_cache_meta(xlsx_path.name, xlsx_path)
            return results
        except Exception as e:
            print(f"❌ Failed to convert {xlsx_path.name}: {e}")
            self.stats["errors"] += 1
            return None
    
    def extract_pack(self, pack_path: Path) -> Optional[Dict]:
        """Extract CMSIS Pack"""
        output_path = self.extract_dir / f"{pack_path.stem}_extracted"
        
        try:
            result = extract_pack(str(pack_path), str(output_path))
            self.stats["pack"] += 1
            self._update_cache_meta(pack_path.name, pack_path)
            return result
        except Exception as e:
            print(f"❌ Failed to extract {pack_path.name}: {e}")
            self.stats["errors"] += 1
            return None
    
    def convert_file(self, file_path: Path) -> Tuple[str, Optional[str]]:
        """Convert a single file (for parallel processing)"""
        ext = file_path.suffix.lower()
        
        if ext == ".pdf":
            output_path = self.cache_dir / f"{file_path.stem}.md"
            try:
                result = pdf_to_markdown(str(file_path), str(output_path))
                return ("pdf", str(output_path), None)
            except Exception as e:
                return ("pdf", None, f"{file_path.name}: {e}")
        
        elif ext in [".xlsx", ".xls"]:
            try:
                results = xlsx_to_csv(str(file_path), str(self.cache_dir))
                return ("xlsx", results, None)
            except Exception as e:
                return ("xlsx", None, f"{file_path.name}: {e}")
        
        elif ext == ".pack":
            output_path = self.extract_dir / f"{file_path.stem}_extracted"
            try:
                result = extract_pack(str(file_path), str(output_path))
                return ("pack", result["extracted_to"], None)
            except Exception as e:
                return ("pack", None, f"{file_path.name}: {e}")
        
        return ("unknown", None, f"{file_path.name}: Unsupported type")
    
    def convert_all(self, recursive: bool = False, parallel: bool = True, workers: int = 4) -> Dict:
        """Convert all supported files in input directory with optional parallel processing"""
        print(f"🔍 Scanning: {self.input_dir}")
        print(f"💾 Output: {self.output_dir}")
        print(f"🚀 Parallel: {parallel} (workers: {workers})\n")
        
        results = {
            "converted": [],
            "extracted": [],
            "skipped": [],
            "errors": []
        }
        
        # Find all files
        if recursive:
            files = list(self.input_dir.rglob("*"))
        else:
            files = list(self.input_dir.glob("*"))
        
        # Filter files to convert
        files_to_convert = []
        for file_path in files:
            if not file_path.is_file():
                continue
            
            ext = file_path.suffix.lower()
            supported_exts = [".pdf", ".xlsx", ".xls", ".pack"]
            
            if ext not in supported_exts:
                continue
            
            # Skip already cached files (with hash validation)
            if self.is_cached(file_path.name, ext, file_path):
                print(f"⏭️  Skipped (cached): {file_path.name}")
                results["skipped"].append(str(file_path))
            else:
                files_to_convert.append(file_path)
        
        print(f"\n📋 Found {len(files_to_convert)} files to convert\n")
        
        # Convert files
        if parallel and len(files_to_convert) > 1:
            # Parallel processing
            with ProcessPoolExecutor(max_workers=workers) as executor:
                future_to_file = {executor.submit(self.convert_file, f): f for f in files_to_convert}
                
                for i, future in enumerate(as_completed(future_to_file), 1):
                    file_path = future_to_file[future]
                    try:
                        file_type, result, error = future.result()
                        
                        if error:
                            print(f"❌ [{i}/{len(files_to_convert)}] Failed: {error}")
                            results["errors"].append(error)
                            self.stats["errors"] += 1
                        else:
                            print(f"✅ [{i}/{len(files_to_convert)}] Converted: {file_path.name}")
                            if file_type == "pack":
                                results["extracted"].append(result)
                                self.stats["pack"] += 1
                            else:
                                if isinstance(result, list):
                                    results["converted"].extend(result)
                                    self.stats[file_type] += 1
                                else:
                                    results["converted"].append(result)
                                    self.stats[file_type] += 1
                            
                            # Update cache meta
                            self._update_cache_meta(file_path.name, file_path)
                            
                    except Exception as e:
                        print(f"❌ [{i}/{len(files_to_convert)}] Exception: {file_path.name}: {e}")
                        results["errors"].append(f"{file_path.name}: {e}")
                        self.stats["errors"] += 1
        else:
            # Sequential processing
            for i, file_path in enumerate(files_to_convert, 1):
                ext = file_path.suffix.lower()
                
                if ext == ".pdf":
                    print(f"📖 [{i}/{len(files_to_convert)}] Converting PDF: {file_path.name}")
                    result = self.convert_pdf(file_path)
                    if result:
                        results["converted"].append(result)
                
                elif ext in [".xlsx", ".xls"]:
                    print(f"📊 [{i}/{len(files_to_convert)}] Converting Excel: {file_path.name}")
                    result = self.convert_xlsx(file_path)
                    if result:
                        results["converted"].extend(result)
                
                elif ext == ".pack":
                    print(f"📦 [{i}/{len(files_to_convert)}] Extracting Pack: {file_path.name}")
                    result = self.extract_pack(file_path)
                    if result:
                        results["extracted"].append(result["extracted_to"])
        
        # Save cache metadata
        self._save_cache_meta()
        
        # Print summary
        print("\n" + "="*60)
        print("🎉 Conversion Summary")
        print("="*60)
        print(f"✅ PDF files: {self.stats['pdf']}")
        print(f"✅ Excel files: {self.stats['xlsx']}")
        print(f"✅ Pack files: {self.stats['pack']}")
        print(f"⏭️  Skipped (cached): {len(results['skipped'])}")
        print(f"❌ Errors: {self.stats['errors']}")
        print(f"📊 Total converted: {len(results['converted']) + len(results['extracted'])} files")
        print("="*60)
        
        return results


def main():
    parser = argparse.ArgumentParser(
        description="DOC-CONVERT - Document Conversion Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert all files in sources folder
  python3 converter.py --input fae_input/sources/ --output fae_input/cache/
  
  # Convert single PDF
  python3 converter.py --input device.pdf --output cache/ --type pdf
  
  # Convert with recursive scan
  python3 converter.py --input sources/ --output cache/ --recursive
        """
    )
    
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input file or directory path"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory path"
    )
    parser.add_argument(
        "--type", "-t",
        choices=["pdf", "xlsx", "pack", "auto"],
        default="auto",
        help="File type to convert (default: auto-detect)"
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Scan input directory recursively"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-conversion (ignore cache)"
    )
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        default=True,
        help="Enable parallel processing (default: enabled)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--sequential", "-s",
        action="store_true",
        help="Force sequential processing (disable parallel)"
    )
    
    args = parser.parse_args()
    
    # Check input path
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input path not found: {args.input}")
        sys.exit(1)
    
    # Single file conversion
    if input_path.is_file():
        ext = input_path.suffix.lower()
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if ext == ".pdf":
            output_path = output_dir / f"{input_path.stem}.md"
            pdf_to_markdown(str(input_path), str(output_path))
        elif ext in [".xlsx", ".xls"]:
            xlsx_to_csv(str(input_path), str(output_dir))
        elif ext == ".pack":
            extract_dir = output_dir / f"{input_path.stem}_extracted"
            extract_pack(str(input_path), str(extract_dir))
        else:
            print(f"❌ Unsupported file type: {ext}")
            sys.exit(1)
    else:
        # Directory conversion
        converter = DocumentConverter(args.input, args.output)
        parallel = args.parallel and not args.sequential
        results = converter.convert_all(
            recursive=args.recursive,
            parallel=parallel,
            workers=args.workers
        )
        
        # Exit with error if any failures
        if results["errors"]:
            sys.exit(1)


if __name__ == "__main__":
    main()

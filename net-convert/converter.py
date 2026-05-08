#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NET-CONVERT - KiCad Netlist Conversion Entry Point
Scans directories for .net files and converts them to structured Markdown.

Features:
- Recursive directory scanning for .net files
- Incremental build with content hash validation
- Automatic MCU detection and pin assignment extraction
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add scripts directory to path
script_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(script_dir))

from netlist_to_md import (
    parse_sexpr_list,
    extract_design_info,
    extract_components,
    extract_nets,
    find_mcu_component,
    get_mcu_pin_info,
    generate_markdown,
)


class NetlistConverter:
    """KiCad netlist conversion manager with caching"""

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.cache_meta_file = self.output_dir / ".netlist_cache_meta.json"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_meta = self._load_cache_meta()

        self.stats = {"converted": 0, "skipped": 0, "errors": 0}

    def _load_cache_meta(self) -> Dict:
        if self.cache_meta_file.exists():
            try:
                with open(self.cache_meta_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"files": {}, "version": "1.0"}

    def _save_cache_meta(self):
        with open(self.cache_meta_file, "w") as f:
            json.dump(self.cache_meta, f, indent=2, ensure_ascii=False)

    def _compute_hash(self, file_path: Path) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def is_cached(self, file_path: Path) -> bool:
        """Check if netlist is already converted with valid hash"""
        output_file = self.output_dir / f"{file_path.stem}.md"
        if not output_file.exists():
            return False

        if file_path.name in self.cache_meta.get("files", {}):
            current_hash = self._compute_hash(file_path)
            cached_hash = self.cache_meta["files"][file_path.name].get("hash")
            return current_hash == cached_hash

        return False

    def convert_file(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """Convert a single .net file to Markdown.
        Returns (success, output_path_or_error)"""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            parsed = parse_sexpr_list(content)
            design_info = extract_design_info(parsed)
            components = extract_components(parsed)
            nets = extract_nets(parsed)
            mcu = find_mcu_component(components)
            pin_assignments = get_mcu_pin_info(components, nets, mcu) if mcu else []

            md_content = generate_markdown(
                design_info, components, nets,
                mcu if mcu else {}, pin_assignments
            )

            output_path = self.output_dir / f"{file_path.stem}.md"
            output_path.write_text(md_content, encoding="utf-8")

            # Update cache
            if "files" not in self.cache_meta:
                self.cache_meta["files"] = {}
            self.cache_meta["files"][file_path.name] = {
                "hash": self._compute_hash(file_path),
                "converted_at": str(file_path.stat().st_mtime),
                "components": len(components),
                "nets": len(nets),
                "mcu": f"{mcu['ref']} ({mcu['value']})" if mcu else "None",
                "mcu_pins": len(mcu.get("pins", [])) if mcu else 0,
                "pin_assignments": len(pin_assignments),
            }
            self._save_cache_meta()

            return (True, str(output_path))

        except Exception as e:
            return (False, f"{file_path.name}: {e}")

    def convert_all(self, recursive: bool = False, force: bool = False) -> Dict:
        """Convert all .net files in input directory"""
        print(f"🔍 Scanning: {self.input_dir}")
        print(f"💾 Output: {self.output_dir}\n")

        results = {"converted": [], "skipped": [], "errors": []}

        # Find all .net files
        if recursive:
            files = list(self.input_dir.rglob("*.net"))
        else:
            files = list(self.input_dir.glob("*.net"))

        print(f"📋 Found {len(files)} netlist file(s)\n")

        for i, file_path in enumerate(files, 1):
            if not file_path.is_file():
                continue

            # Skip cached files (unless force)
            if not force and self.is_cached(file_path):
                print(f"⏭️ Skipped (cached): {file_path.name}")
                results["skipped"].append(str(file_path))
                self.stats["skipped"] += 1
                continue

            print(f"📖 [{i}/{len(files)}] Converting: {file_path.name}")
            success, result = self.convert_file(file_path)

            if success:
                print(f"✅ Created: {result}")
                results["converted"].append(result)
                self.stats["converted"] += 1
            else:
                print(f"❌ Failed: {result}")
                results["errors"].append(result)
                self.stats["errors"] += 1

        # Print summary
        print("\n" + "=" * 60)
        print("🎉 Netlist Conversion Summary")
        print("=" * 60)
        print(f"✅ Converted: {self.stats['converted']} files")
        print(f"⏭️ Skipped: {self.stats['skipped']} files (cached)")
        print(f"❌ Errors: {self.stats['errors']}")
        print("=" * 60)

        return results


def find_netlists(search_root: str, recursive: bool = True) -> List[Path]:
    """Find all .net files under a directory tree"""
    root = Path(search_root)
    if not root.exists():
        print(f"❌ Path not found: {search_root}")
        return []
    if recursive:
        return list(root.rglob("*.net"))
    else:
        return list(root.glob("*.net"))


def main():
    parser = argparse.ArgumentParser(
        description="NET-CONVERT - KiCad Netlist to Markdown Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert single netlist
  python3 converter.py -i design.net -o cache/schematics/

  # Batch convert (recursive)
  python3 converter.py -i fae_input/sources/ -o fae_input/cache/schematics/ -r

  # Force re-conversion
  python3 converter.py -i fae_input/sources/ -o fae_input/cache/schematics/ -r -f
        """,
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input .net file or directory path",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for converted Markdown files",
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Scan input directory recursively",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-conversion (ignore cache)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"❌ Input path not found: {args.input}")
        sys.exit(1)

    # Single file
    if input_path.is_file():
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Temporarily use single-file mode
        converter = NetlistConverter(str(input_path.parent), str(output_dir))
        # Override to only process this one file
        success, result = converter.convert_file(input_path)
        if success:
            print(f"✅ Created: {result}")
        else:
            print(f"❌ Failed: {result}")
            sys.exit(1)
    else:
        # Directory
        converter = NetlistConverter(args.input, args.output)
        results = converter.convert_all(
            recursive=args.recursive,
            force=args.force,
        )

        if results["errors"]:
            sys.exit(1)


if __name__ == "__main__":
    main()

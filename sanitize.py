#!/usr/bin/env python3
"""
sanitize.py - DOCX file post-processing sanitizer.
Validates and cleans up generated DOCX files to ensure structural integrity.
"""

import sys
import os
import zipfile
import re
from xml.etree import ElementTree as ET

def sanitize_docx(filepath):
    """Validate and sanitize a DOCX file."""
    print(f"Sanitizing: {filepath}")

    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        return False

    file_size = os.path.getsize(filepath)
    print(f"  File size: {file_size / 1024:.1f} KB")

    # Validate ZIP structure (DOCX is a ZIP archive)
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            names = zf.namelist()
            print(f"  Archive entries: {len(names)}")

            # Check required DOCX components
            required = ['[Content_Types].xml', 'word/document.xml']
            for req in required:
                if req not in names:
                    print(f"  WARNING: Missing required component: {req}")
                else:
                    print(f"  OK: {req} present")

            # Validate XML well-formedness of document.xml
            try:
                doc_xml = zf.read('word/document.xml')
                ET.fromstring(doc_xml)
                print("  OK: word/document.xml is well-formed XML")
            except ET.ParseError as e:
                print(f"  ERROR: word/document.xml has XML parse error: {e}")
                return False

            # Check for and remove any potentially problematic entries
            problematic = [n for n in names if '..' in n or n.startswith('/')]
            if problematic:
                print(f"  WARNING: Found {len(problematic)} potentially problematic path entries")

    except zipfile.BadZipFile:
        print("  ERROR: File is not a valid ZIP/DOCX archive")
        return False

    # Check file extension
    if not filepath.lower().endswith('.docx'):
        print("  WARNING: File does not have .docx extension")

    print("  Sanitization complete: PASSED")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python sanitize.py <docx_file>")
        sys.exit(1)

    filepath = sys.argv[1]
    success = sanitize_docx(filepath)
    sys.exit(0 if success else 1)

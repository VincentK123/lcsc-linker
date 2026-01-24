#!/usr/bin/env python3
"""
Safe LCSC property injector for KiCad schematic files.
Adds LCSC and URL properties to components based on reference designators.
"""

import re
import sys
from pathlib import Path

# LCSC data extracted from the corrupted file
LCSC_DATA = {
    "J9": "C99101",
    "U2": "C12084",
    "R9": "C25804",
    "L1": "C86069",
    "C2": "C45783",
    "C3": "C307331",
    "R2": "C4190",
    "C1": "C89632",
    "R4": "C22787",
    "R10": "C23198",
    "R1": "C4190",
    "J1": "C99101",
    "R7": "C1002",
    "R3": "C22787",
    "D3": "C173461",
    "D2": "C19077604",
    "U3": "C31122263",
    "R6": "C1002",
    "J2": "C99101",
}


def add_lcsc_properties(filepath: str) -> None:
    """Add LCSC properties to schematic file."""
    content = Path(filepath).read_text(encoding='utf-8')

    # Pattern to find symbol blocks with their reference
    # We look for symbol blocks and find the Reference property inside
    symbol_pattern = re.compile(
        r'(\(symbol\s+\(lib_id\s+"[^"]+"\).*?'
        r'\(property\s+"Reference"\s+"([^"]+)"[^)]*\(at\s+([^)]+)\))',
        re.DOTALL
    )

    modifications = []

    for match in symbol_pattern.finditer(content):
        ref = match.group(2)
        at_coords = match.group(3)

        if ref in LCSC_DATA:
            lcsc_id = LCSC_DATA[ref]

            # Find the end of this symbol's property section
            # Look for the last property before pin definitions
            symbol_start = match.start()

            # Find the position after all properties but before pins
            # We'll insert after the last (property ...) and before (pin ...)
            rest_of_content = content[symbol_start:]

            # Find position to insert: after last property, before first pin or instances
            pin_match = re.search(r'\n(\s*)\(pin\s+"', rest_of_content)
            instances_match = re.search(r'\n(\s*)\(instances\s', rest_of_content)

            if pin_match:
                insert_rel_pos = pin_match.start()
                indent = pin_match.group(1)
            elif instances_match:
                insert_rel_pos = instances_match.start()
                indent = instances_match.group(1)
            else:
                continue

            insert_pos = symbol_start + insert_rel_pos

            # Check if LCSC property already exists in this symbol
            symbol_end_search = rest_of_content[:insert_rel_pos]
            if '"LCSC"' in symbol_end_search:
                print(f"  {ref}: LCSC already exists, skipping")
                continue

            # Create new properties
            url = f"https://www.lcsc.com/product-detail/{lcsc_id}.html"
            new_props = f'{indent}(property "LCSC" "{lcsc_id}" (at {at_coords})\n{indent}\t(effects (font (size 1.27 1.27)) hide)\n{indent})\n{indent}(property "URL" "{url}" (at {at_coords})\n{indent}\t(effects (font (size 1.27 1.27)) hide)\n{indent})\n'

            modifications.append((insert_pos, new_props, ref, lcsc_id))

    # Apply modifications in reverse order to preserve positions
    modifications.sort(key=lambda x: x[0], reverse=True)

    for insert_pos, new_props, ref, lcsc_id in modifications:
        content = content[:insert_pos] + new_props + content[insert_pos:]
        print(f"  {ref}: Added LCSC {lcsc_id}")

    # Save
    Path(filepath).write_text(content, encoding='utf-8')
    print(f"\nSaved {len(modifications)} modifications to {filepath}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_lcsc.py <schematic.kicad_sch>")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"Processing: {filepath}")
    add_lcsc_properties(filepath)

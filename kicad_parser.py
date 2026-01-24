"""
KiCad .kicad_sch S-expression parser and writer.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Component:
    """Represents a component in the schematic."""
    lib_id: str
    reference: str
    value: str
    footprint: str
    lcsc: str = ""
    url: str = ""
    # Position in file for modification
    start_pos: int = 0
    end_pos: int = 0
    raw_content: str = ""
    properties: dict = field(default_factory=dict)


class KicadSchParser:
    """Parser for KiCad 9.0 .kicad_sch files."""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.content = ""
        self.components: list[Component] = []

    def parse(self) -> list[Component]:
        """Parse the schematic file and extract components."""
        self.content = self.filepath.read_text(encoding='utf-8')
        self.components = []

        # Find all symbol blocks (components)
        # Match (symbol (lib_id "...") ... )
        pattern = r'\(symbol\s+\(lib_id\s+"([^"]+)"\)'

        pos = 0
        while True:
            match = re.search(pattern, self.content[pos:])
            if not match:
                break

            start = pos + match.start()
            # Find the matching closing parenthesis
            end = self._find_matching_paren(start)
            if end == -1:
                pos = start + 1
                continue

            raw = self.content[start:end+1]
            component = self._parse_symbol_block(raw, start, end)
            if component:
                self.components.append(component)

            pos = end + 1

        return self.components

    def _find_matching_paren(self, start: int) -> int:
        """Find the position of the matching closing parenthesis."""
        depth = 0
        in_string = False
        i = start

        while i < len(self.content):
            c = self.content[i]

            if c == '"' and (i == 0 or self.content[i-1] != '\\'):
                in_string = not in_string
            elif not in_string:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        return i
            i += 1

        return -1

    def _parse_symbol_block(self, raw: str, start: int, end: int) -> Optional[Component]:
        """Parse a symbol block and extract component data."""
        # Extract lib_id
        lib_id_match = re.search(r'\(lib_id\s+"([^"]+)"\)', raw)
        if not lib_id_match:
            return None
        lib_id = lib_id_match.group(1)

        # Skip power symbols and other non-component symbols
        if lib_id.startswith("power:") or ":PWR_" in lib_id:
            return None

        # Extract properties
        properties = {}
        prop_pattern = r'\(property\s+"([^"]+)"\s+"([^"]*)"\s*\(at\s+[^)]+\)'
        for prop_match in re.finditer(prop_pattern, raw):
            prop_name = prop_match.group(1)
            prop_value = prop_match.group(2)
            properties[prop_name] = prop_value

        # Get required fields
        reference = properties.get("Reference", "")
        value = properties.get("Value", "")
        footprint = properties.get("Footprint", "")

        # Skip if no reference (not a real component)
        if not reference or reference.startswith("#"):
            return None

        return Component(
            lib_id=lib_id,
            reference=reference,
            value=value,
            footprint=footprint,
            lcsc=properties.get("LCSC", ""),
            url=properties.get("URL", ""),
            start_pos=start,
            end_pos=end,
            raw_content=raw,
            properties=properties
        )

    def update_component(self, component: Component, lcsc: str, url: str) -> None:
        """Update a component's LCSC and URL fields in the file content."""
        raw = component.raw_content
        new_raw = raw

        # Update or add LCSC property
        new_raw = self._update_property(new_raw, "LCSC", lcsc)

        # Update or add URL property
        new_raw = self._update_property(new_raw, "URL", url)

        # Replace in content
        self.content = (
            self.content[:component.start_pos] +
            new_raw +
            self.content[component.end_pos+1:]
        )

        # Adjust positions for subsequent components
        diff = len(new_raw) - len(component.raw_content)
        for comp in self.components:
            if comp.start_pos > component.start_pos:
                comp.start_pos += diff
                comp.end_pos += diff

        component.raw_content = new_raw
        component.end_pos = component.start_pos + len(new_raw) - 1
        component.lcsc = lcsc
        component.url = url

    def _update_property(self, raw: str, prop_name: str, prop_value: str) -> str:
        """Update or add a property in the symbol block."""
        # Pattern to match existing property
        pattern = rf'(\(property\s+"{prop_name}"\s+")[^"]*(")'

        if re.search(pattern, raw):
            # Update existing property
            return re.sub(pattern, rf'\g<1>{prop_value}\g<2>', raw)
        else:
            # Add new property before first (pin or (instances
            # This is safer than trying to match complex property patterns
            ref_at_match = re.search(r'\(property\s+"Reference"[^(]*\(at\s+([^)]+)\)', raw)
            at_coords = ref_at_match.group(1) if ref_at_match else "0 0 0"

            # Find insertion point: before (pin or (instances
            pin_match = re.search(r'\n(\s*)\(pin\s+"', raw)
            instances_match = re.search(r'\n(\s*)\(instances\s', raw)

            if pin_match:
                insert_pos = pin_match.start()
                indent = pin_match.group(1)
            elif instances_match:
                insert_pos = instances_match.start()
                indent = instances_match.group(1)
            else:
                # Fallback: insert before closing paren
                insert_pos = raw.rfind(')')
                indent = "\t\t"

            new_prop = f'\n{indent}(property "{prop_name}" "{prop_value}" (at {at_coords})\n{indent}\t(effects (font (size 1.27 1.27)) hide)\n{indent})'
            return raw[:insert_pos] + new_prop + raw[insert_pos:]

        return raw

    def save(self, filepath: Optional[str] = None) -> None:
        """Save the modified schematic to file."""
        save_path = Path(filepath) if filepath else self.filepath
        save_path.write_text(self.content, encoding='utf-8')

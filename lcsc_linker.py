#!/usr/bin/env python3
"""
LCSC Linker - KiCad schematic component linker for LCSC parts.

Links KiCad schematic components to LCSC parts by searching
and allowing interactive selection.
"""

import argparse
import sys
from pathlib import Path

from kicad_parser import KicadSchParser, Component
from lcsc_api import LCSCClient, LCSCComponent, build_search_query


def print_component_info(comp: Component) -> None:
    """Print component information."""
    print(f"\n{'='*60}")
    print(f"Reference: {comp.reference}")
    print(f"Value:     {comp.value}")
    print(f"Footprint: {comp.footprint}")
    print(f"Lib ID:    {comp.lib_id}")
    if comp.lcsc:
        print(f"LCSC:      {comp.lcsc} (existing)")


def print_search_results(results: list[LCSCComponent]) -> None:
    """Print search results in a formatted table."""
    if not results:
        print("  No results found.")
        return

    print(f"\n  {'#':<3} {'LCSC ID':<12} {'Manufacturer':<15} {'Part Number':<20} {'Package':<10} {'Stock':<8} {'Price':<8}")
    print(f"  {'-'*3} {'-'*12} {'-'*15} {'-'*20} {'-'*10} {'-'*8} {'-'*8}")

    for i, comp in enumerate(results, 1):
        mfr = comp.manufacturer[:15] if comp.manufacturer else "-"
        part = comp.mfr_part[:20] if comp.mfr_part else "-"
        pkg = comp.package[:10] if comp.package else "-"
        price = f"${comp.price:.4f}" if comp.price else "-"
        stock = str(comp.stock) if comp.stock else "-"

        print(f"  {i:<3} {comp.lcsc_id:<12} {mfr:<15} {part:<20} {pkg:<10} {stock:<8} {price:<8}")


def prompt_selection(results: list[LCSCComponent], comp: Component) -> tuple[str, str]:
    """Prompt user to select a component from search results."""
    while True:
        print("\nOptions:")
        print("  [1-N]  Select component by number")
        print("  [s]    Search with custom query")
        print("  [m]    Manually enter LCSC ID")
        print("  [k]    Skip this component")
        print("  [q]    Quit")

        choice = input("\nYour choice: ").strip().lower()

        if choice == 'q':
            print("Exiting...")
            sys.exit(0)

        if choice == 'k':
            return "", ""

        if choice == 's':
            custom_query = input("Enter search query: ").strip()
            if custom_query:
                client = LCSCClient()
                new_results = client.search(custom_query)
                print_search_results(new_results)
                if new_results:
                    results.clear()
                    results.extend(new_results)
            continue

        if choice == 'm':
            lcsc_id = input("Enter LCSC ID (e.g., C123456): ").strip().upper()
            if lcsc_id and lcsc_id.startswith('C'):
                url = f"https://www.lcsc.com/product-detail/{lcsc_id}.html"
                return lcsc_id, url
            print("Invalid LCSC ID. Must start with 'C'.")
            continue

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                selected = results[idx]
                return selected.lcsc_id, selected.url
            print(f"Invalid selection. Enter 1-{len(results)}.")
        except ValueError:
            print("Invalid input. Enter a number or command.")


def process_component(
    client: LCSCClient,
    comp: Component,
    skip_existing: bool = True
) -> tuple[str, str]:
    """Process a single component and return LCSC ID and URL."""
    print_component_info(comp)

    # Skip if already has LCSC
    if skip_existing and comp.lcsc:
        print(f"  -> Skipping (already has LCSC: {comp.lcsc})")
        return "", ""

    # Build search query
    query = build_search_query(comp.value, comp.footprint)
    print(f"\nSearching LCSC for: '{query}'")

    # Search
    results = client.search(query, limit=10)
    print_search_results(results)

    if not results:
        # Try with just the value
        if comp.value:
            print(f"\nRetrying with just value: '{comp.value}'")
            results = client.search(comp.value, limit=10)
            print_search_results(results)

    # Get user selection
    return prompt_selection(results, comp)


def main():
    parser = argparse.ArgumentParser(
        description="Link KiCad schematic components to LCSC parts."
    )
    parser.add_argument(
        "schematic",
        help="Path to .kicad_sch file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: overwrite input)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing LCSC fields"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save changes, just show what would be done"
    )

    args = parser.parse_args()

    # Validate input file
    sch_path = Path(args.schematic)
    if not sch_path.exists():
        print(f"Error: File not found: {sch_path}")
        sys.exit(1)

    if not sch_path.suffix == ".kicad_sch":
        print(f"Warning: File doesn't have .kicad_sch extension: {sch_path}")

    # Parse schematic
    print(f"Parsing: {sch_path}")
    sch_parser = KicadSchParser(str(sch_path))
    components = sch_parser.parse()

    print(f"Found {len(components)} components")

    if not components:
        print("No components to process.")
        return

    # Create LCSC client
    client = LCSCClient()

    # Process each component
    updated_count = 0
    skipped_count = 0

    for comp in components:
        lcsc_id, url = process_component(
            client,
            comp,
            skip_existing=not args.overwrite
        )

        if lcsc_id:
            if not args.dry_run:
                sch_parser.update_component(comp, lcsc_id, url)
            print(f"  -> Set LCSC: {lcsc_id}")
            updated_count += 1
        else:
            skipped_count += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {skipped_count}")

    # Save
    if not args.dry_run and updated_count > 0:
        output_path = args.output or str(sch_path)
        print(f"\nSaving to: {output_path}")
        sch_parser.save(output_path)
        print("Done!")
    elif args.dry_run:
        print("\n(Dry run - no changes saved)")


if __name__ == "__main__":
    main()

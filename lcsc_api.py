"""
LCSC API client for component search via JLCPCB API.
"""

import re
import time
import requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class LCSCComponent:
    """Represents an LCSC component."""
    lcsc_id: str
    mfr_part: str
    manufacturer: str
    description: str
    package: str
    stock: int
    price: float
    url: str


class LCSCClient:
    """Client for LCSC component search via JLCPCB API."""

    SEARCH_URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
    BASE_URL = "https://www.lcsc.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://jlcpcb.com",
        "Referer": "https://jlcpcb.com/parts",
    }

    def __init__(self):
        pass

    def _create_session(self) -> requests.Session:
        """Create a fresh session for each request to avoid rate limiting."""
        session = requests.Session()
        session.headers.update(self.HEADERS)
        return session

    def search(self, query: str, limit: int = 10, retries: int = 3) -> list[LCSCComponent]:
        """Search for components on LCSC via JLCPCB API."""
        payload = {
            "keyword": query,
            "currentPage": 1,
            "pageSize": limit,
        }

        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(2 * attempt)

                session = self._create_session()
                response = session.post(
                    self.SEARCH_URL,
                    json=payload,
                    timeout=15
                )

                if response.status_code == 403:
                    if attempt < retries - 1:
                        time.sleep(3)
                        continue
                    print("Rate limited. Please wait and try again.")
                    return []

                response.raise_for_status()
                data = response.json()

                if data.get("code") != 200:
                    return []

                page_info = data.get("data", {}).get("componentPageInfo", {}) or {}
                products = page_info.get("list") or []

                components = []
                for item in products[:limit]:
                    comp = self._parse_product(item)
                    if comp:
                        components.append(comp)

                return components

            except requests.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                print(f"Search error: {e}")
                return []

        return []

    def _parse_product(self, item: dict) -> Optional[LCSCComponent]:
        """Parse a product item from the JLCPCB API response."""
        try:
            lcsc_id = item.get("componentCode", "")
            if not lcsc_id:
                return None

            # Get price from price list
            price = 0.0
            price_list = item.get("componentPrices", [])
            if price_list:
                price = price_list[0].get("productPrice", 0.0)

            return LCSCComponent(
                lcsc_id=lcsc_id,
                mfr_part=item.get("componentModelEn", "") or item.get("componentModelCn", ""),
                manufacturer=item.get("componentBrandEn", "") or item.get("componentBrandCn", ""),
                description=item.get("describe", "") or item.get("componentDescEn", ""),
                package=item.get("componentSpecificationEn", ""),
                stock=item.get("stockCount", 0),
                price=price,
                url=f"{self.BASE_URL}/product-detail/{lcsc_id}.html"
            )
        except Exception:
            return None

    def _extract_package_size(self, footprint: str) -> str:
        """Extract package size from KiCad footprint name."""
        if not footprint:
            return ""

        # Common patterns:
        # Capacitor_SMD:C_0402_1005Metric -> 0402
        # Resistor_SMD:R_0603_1608Metric -> 0603
        # Package_SO:SOIC-8_3.9x4.9mm_P1.27mm -> SOIC-8

        # Try to find imperial size (0402, 0603, 0805, etc.)
        imperial_match = re.search(r'[_:].*?(\d{4})(?:_|$)', footprint)
        if imperial_match:
            return imperial_match.group(1)

        # Try to find metric size and convert to imperial
        metric_match = re.search(r'_(\d{4})Metric', footprint)
        if metric_match:
            metric_map = {
                "1005": "0402",
                "1608": "0603",
                "2012": "0805",
                "3216": "1206",
                "3225": "1210",
            }
            return metric_map.get(metric_match.group(1), metric_match.group(1))

        # Try to find package name (SOIC, QFP, etc.)
        pkg_match = re.search(
            r'(SOT-?\d+|SOIC-?\d+|QFP-?\d+|TSSOP-?\d+|LQFP-?\d+|QFN-?\d+)',
            footprint,
            re.IGNORECASE
        )
        if pkg_match:
            return pkg_match.group(1)

        return ""


def build_search_query(value: str, footprint: str) -> str:
    """Build an optimized search query from component value and footprint."""
    client = LCSCClient()
    package = client._extract_package_size(footprint)

    parts = []
    if value:
        parts.append(value)
    if package:
        parts.append(package)

    return " ".join(parts)

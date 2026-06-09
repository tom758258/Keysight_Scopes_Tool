"""Query and parse `*IDN?` for one oscilloscope resource."""

from __future__ import annotations

import os
import sys

from keysight_scope import KeysightScope


def main() -> int:
    resource = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("KEYSIGHT_SCOPE_RESOURCE")
    if not resource:
        print("usage: python examples/02_query_idn.py <VISA_RESOURCE>")
        return 2

    with KeysightScope.open(resource) as scope:
        idn = scope.query_idn()
        print(f"{idn.vendor} {idn.model} serial={idn.serial} firmware={idn.firmware}")
        print(f"series={idn.series or 'unknown'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

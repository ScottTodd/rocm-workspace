#!/usr/bin/env python
"""Find flattened install-path collisions from uploaded TheRock stage logs."""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import re
from urllib.parse import urljoin
from urllib.request import urlopen


HREF_RE = re.compile(r'href="([^"]+_install\.log)"', re.IGNORECASE)
INSTALL_RE = re.compile(r"-- (?:Installing|Up-to-date): (.+)$")
STAGE_RE = re.compile(r"[/\\]stage[/\\](.+)$", re.IGNORECASE)


def fetch(url: str) -> str:
    with urlopen(url, timeout=30) as response:
        return response.read().decode(errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("index_url")
    args = parser.parse_args()

    index = fetch(args.index_url)
    links = sorted(set(HREF_RE.findall(index)))

    def collect(link: str):
        paths = set()
        for line in fetch(urljoin(args.index_url, link)).splitlines():
            install_match = INSTALL_RE.search(line)
            if not install_match:
                continue
            stage_match = STAGE_RE.search(install_match.group(1))
            if stage_match:
                paths.add(stage_match.group(1).replace("\\", "/").lower())
        return link, paths

    with ThreadPoolExecutor(max_workers=16) as executor:
        installs = dict(executor.map(collect, links))

    owners = defaultdict(list)
    for log, paths in installs.items():
        for path in paths:
            owners[path].append(log)
    collisions = {
        path: logs for path, logs in owners.items() if len(set(logs)) > 1
    }

    print(f"install_logs={len(installs)}")
    print(f"installed_relative_paths={len(owners)}")
    print(f"cross_log_collisions={len(collisions)}")
    for path, logs in sorted(collisions.items()):
        print(f"{path}\t{','.join(sorted(set(logs)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

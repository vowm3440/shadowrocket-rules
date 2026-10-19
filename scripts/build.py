#!/usr/bin/env python3
"""Fetch, normalize and publish Shadowrocket data. Python standard library only.

Any failed/empty/malformed upstream aborts the build before generated files change.
Raw downloads are retained in .cache for a reproducible --offline rebuild.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CST = timezone(timedelta(hours=8))
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}
IP_TYPES = {"IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP"}
# Deliberately excluded: UA requires HTTP inspection; broad URL/logic rules should
# not be silently imported into a domain-only advertisement block list.
OMIT_TYPES = {"USER-AGENT", "URL-REGEX", "AND", "OR", "NOT", "PROCESS-NAME"}
TARGETS = ["direct", "unbreak", "openai", "claude", "gemini", "telegram",
           "netflix", "youtube", "disney", "apple", "microsoft", "proxy",
           "lan", "cn-domain", "cn-ip", "adblock"]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def domain(value: str) -> str:
    value = value.strip().lower().rstrip(".")
    value = value.encode("idna").decode("ascii")
    if not value or len(value) > 253 or not re.fullmatch(r"[a-z0-9_.-]+", value):
        raise ValueError(f"invalid domain: {value!r}")
    if any(not p or len(p) > 63 for p in value.split(".")):
        raise ValueError(f"invalid domain label: {value!r}")
    return value


def parse(text: str, fmt: str) -> tuple[set[tuple[str, str]], dict[str, int]]:
    rules: set[tuple[str, str]] = set()
    omitted: Counter = Counter()
    if "<html" in text[:1000].lower() or "<!doctype" in text[:1000].lower():
        raise ValueError("upstream returned HTML")
    for number, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";", "//", "!")):
            continue
        line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
        if fmt == "domains":
            if "," in line or "://" in line:
                raise ValueError(f"line {number}: not a DOMAIN-SET")
            kind = "DOMAIN-SUFFIX" if line.startswith((".", "+.")) else "DOMAIN"
            value = line[2:] if line.startswith("+.") else line.lstrip(".")
        else:
            parts = [p.strip() for p in line.split(",")]
            kind = parts[0].upper()
            if kind in OMIT_TYPES:
                omitted[kind] += 1
                continue
            if len(parts) < 2 or kind not in DOMAIN_TYPES | IP_TYPES:
                raise ValueError(f"line {number}: unsupported rule {line[:100]!r}")
            value = parts[1]
            if any(x.lower() not in {"no-resolve"} for x in parts[2:]):
                raise ValueError(f"line {number}: unexpected policy/options")
        if kind in {"DOMAIN", "DOMAIN-SUFFIX"}:
            value = domain(value)
        elif kind == "DOMAIN-KEYWORD":
            value = value.lower()
            if not value or any(c.isspace() for c in value):
                raise ValueError("empty/invalid domain keyword")
        elif kind in {"IP-CIDR", "IP-CIDR6"}:
            value = str(ipaddress.ip_network(value, strict=False))
            # Shadowrocket IP-CIDR accepts IPv4 and IPv6.
            kind = "IP-CIDR"
        elif kind == "IP-ASN":
            if not value.isdigit() or not 0 < int(value) <= 4294967295:
                raise ValueError("invalid ASN")
        rules.add((kind, value))
    return rules, dict(omitted)


def parents(d: str):
    parts = d.split(".")
    return (".".join(parts[i:]) for i in range(len(parts)))


def minimize(rules: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Remove exact/child suffixes already covered by a parent suffix."""
    suffixes = {v for k, v in rules if k == "DOMAIN-SUFFIX"}
    result = set()
    for kind, value in rules:
        if kind in {"DOMAIN", "DOMAIN-SUFFIX"}:
            candidates = list(parents(value))
            if kind == "DOMAIN-SUFFIX":
                candidates = candidates[1:]
            if any(p in suffixes for p in candidates):
                continue
        result.add((kind, value))
    return result


def remove_protected(rules, protected):
    """Protect both an allow domain and its descendants; remove ancestor rejects."""
    allowed = {v for k, v in protected if k in {"DOMAIN", "DOMAIN-SUFFIX"}}
    ancestor = {p for v in allowed for p in parents(v)}
    kept, removed = set(), []
    for kind, value in sorted(rules):
        conflict = False
        if kind in {"DOMAIN", "DOMAIN-SUFFIX"}:
            conflict = any(p in allowed for p in parents(value))
            if kind == "DOMAIN-SUFFIX" and value in ancestor:
                conflict = True
        elif kind == "DOMAIN-KEYWORD":
            conflict = any(value in v for v in allowed)
        if conflict:
            removed.append((kind, value))
        else:
            kept.add((kind, value))
    return kept, removed


def render_list(name, rules) -> bytes:
    rows = []
    for kind, value in sorted(rules):
        rows.append(f"{kind},{value}" + (",no-resolve" if kind in IP_TYPES else ""))
    return (f"# Generated Shadowrocket RULE-SET: {name}\n"
            "# Attribution and source hashes: manifest.json / SOURCES.md\n"
            + "\n".join(rows) + "\n").encode()


def download(spec, offline=False):
    cache = ROOT / ".cache" / (spec["id"] + ".txt")
    meta = cache.with_suffix(".json")
    if offline:
        data = cache.read_bytes()
        info = json.loads(meta.read_text())
        if info["sha256"] != sha(data) or info["url"] != spec["url"]:
            raise ValueError(f"cache mismatch: {spec['id']}")
    else:
        failure = None
        for attempt in range(3):
            try:
                request = Request(spec["url"], headers={
                    "User-Agent": "Shadowrocket-Rules-Builder/1.0",
                    "Cache-Control": "no-cache", "Pragma": "no-cache"})
                with urlopen(request, timeout=35) as response:
                    data = response.read(30_000_001)
                    if len(data) > 30_000_000:
                        raise ValueError("source exceeds 30 MB")
                    info = {"url": spec["url"], "sha256": sha(data),
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                            "last_modified": response.headers.get("Last-Modified"),
                            "etag": response.headers.get("ETag")}
                break
            except Exception as exc:
                failure = exc
                if attempt < 2:
                    time.sleep(1 + attempt)
        else:
            raise RuntimeError(f"fetch failed: {spec['id']}: {failure}")
    text = data.decode("utf-8-sig")
    parsed, omitted = parse(text, spec["format"])
    if len(parsed) < spec.get("min_rules", 1):
        raise ValueError(f"too few rules: {spec['id']} ({len(parsed)})")
    if not offline:
        cache.parent.mkdir(exist_ok=True)
        cache.write_bytes(data)
        meta.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    hints = [s for s in text.splitlines()[:25]
             if re.match(r"#\s*(?:UPDATED|VER|最后更新时间)", s, re.I)]
    return spec, parsed, {**info, "id": spec["id"], "target": spec["target"],
                          "parsed_rules": len(parsed), "omitted_types": omitted,
                          "upstream_version_hints": hints}


def substitute(template: str, values: dict) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    if re.search(r"\{\{[^{}]+\}\}", template):
        raise ValueError("unreplaced template variables")
    return template


def validate_output(folder: Path):
    manifest = json.loads((folder / "manifest.json").read_text())
    for file, digest in manifest["files_sha256"].items():
        if sha((folder / file).read_bytes()) != digest:
            raise ValueError(f"hash mismatch: {file}")
    routing = (folder / "routing.conf").read_text()
    if "[URL Rewrite]" in routing or "REJECT" in routing.split("[Rule]", 1)[1]:
        raise ValueError("adblock leaked into routing rules")
    final_rules = [row.strip().split(",") for row in routing.splitlines()
                   if row.startswith("FINAL,")]
    if len(final_rules) != 1 or len(final_rules[0]) != 3 or final_rules[0][2] != "dns-failed":
        raise ValueError("missing or invalid final rule")
    for f in list((folder / "rules").glob("*.list")) + [folder / "adblock.list"]:
        for line in f.read_text().splitlines():
            if line.startswith(tuple(t + "," for t in IP_TYPES)) and not line.endswith(",no-resolve"):
                raise ValueError(f"IP rule lacks no-resolve: {f.name}: {line}")
    for line in routing.splitlines():
        if line.startswith(("GEOIP,", "IP-CIDR,", "IP-ASN,")) and not line.endswith(",no-resolve"):
            raise ValueError("main IP rule lacks no-resolve")
        if line.startswith("RULE-SET,"):
            parts = line.split(",")
            object_file = folder / "objects" / parts[1].rsplit("/", 1)[-1]
            if not object_file.is_file():
                raise ValueError("missing referenced rule object")
            has_ip = any(row.startswith(tuple(t + "," for t in IP_TYPES))
                         for row in object_file.read_text().splitlines())
            if has_ip and not line.endswith(",no-resolve"):
                raise ValueError("mixed/IP RULE-SET lacks no-resolve")
    group_text = routing.split("[Proxy Group]", 1)[1].split("[Rule]", 1)[0]
    graph = {}
    for row in group_text.splitlines():
        if row and not row.startswith("#") and "=" in row:
            name, body = row.split("=", 1)
            graph[name.strip()] = [x.strip() for x in body.split(",")[1:] if "=" not in x]
    def visit(name, stack):
        if name in stack:
            raise ValueError("cyclic proxy groups")
        for child in graph.get(name, []):
            if child in graph:
                visit(child, stack | {name})
    for name in graph:
        visit(name, set())
    if final_rules[0][1] not in graph and final_rules[0][1] != "PROXY":
        raise ValueError("final rule points to an undefined proxy policy")
    module = (folder / "adblock.sgmodule").read_text()
    if "(DEST-PORT," in module or "hostname = %APPEND%" not in module:
        raise ValueError("invalid module syntax")
    section = ""
    for line in module.splitlines():
        if line.startswith("["):
            section = line
        elif section == "[URL Rewrite]" and line.startswith("^"):
            pattern, separator, action = line.rpartition(" - ")
            if not separator or action not in {"reject", "reject-200", "reject-dict"}:
                raise ValueError("invalid rewrite action")
            re.compile(pattern)
        elif section == "[Script]" and " = " in line and not line.startswith("#"):
            options = dict(part.strip().split("=", 1) for part in line.split(" = ", 1)[1].split(","))
            if options.get("type") != "http-response" or options.get("requires-body") != "1":
                raise ValueError("invalid response script options")
            re.compile(options["pattern"])
            filename = options["script-path"].rsplit("/", 1)[-1]
            if not re.fullmatch(r"[a-f0-9]{64}\.js", filename):
                raise ValueError("script must use immutable content address")
            script_file = folder / "objects" / filename
            if not script_file.is_file() or sha(script_file.read_bytes()) != filename[:-3]:
                raise ValueError("missing or corrupt script object")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--branch", default=os.getenv("RULES_BRANCH"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--allow-placeholder", action="store_true")
    args = parser.parse_args()
    settings = json.loads((ROOT / "settings.json").read_text())
    repository = args.repository or settings.get("repository")
    if not repository:
        if not args.allow_placeholder:
            parser.error("set --repository OWNER/REPO (see README.md)")
        repository = "YOUR_GITHUB_USERNAME/YOUR_REPOSITORY"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        parser.error("repository must be OWNER/REPO")
    branch = args.branch or settings.get("branch", "main")
    base = f"https://raw.githubusercontent.com/{repository}/{quote(branch, safe='')}"
    node_filter = settings.get("node_filter", ".*")
    if any(c in node_filter for c in "\n\r,"):
        parser.error("node_filter cannot contain newlines or commas")
    re.compile(node_filter)
    specs = json.loads((ROOT / "sources.json").read_text())
    groups = defaultdict(set)
    sources = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = [pool.submit(download, spec, args.offline) for spec in specs]
        for future in as_completed(jobs):
            spec, rules, info = future.result()
            groups[spec["target"]].update(rules)
            sources.append(info)
            print(f"{spec['id']}: {len(rules)}", flush=True)
    local_hashes = {}
    for f in sorted((ROOT / "local").glob("*.list")):
        local_hashes[f.name] = sha(f.read_bytes())
        if f.stem != "ad-allow":
            data, _ = parse(f.read_text(), "rules")
            groups[f.stem].update(data)
    for target in TARGETS:
        if not groups[target]:
            raise ValueError(f"empty group: {target}")
    # White-list routing entries must be precise, and must not override AI/media.
    groups["unbreak"] = {r for r in groups["unbreak"] if r[0] in {"DOMAIN", "DOMAIN-SUFFIX"}}
    special = set().union(*(groups[n] for n in ["openai", "claude", "gemini", "telegram",
                                                "netflix", "youtube", "disney"]))
    groups["unbreak"], route_removed = remove_protected(groups["unbreak"], special)
    allowed, _ = parse((ROOT / "local/ad-allow.list").read_text(), "rules")
    allowed |= groups["direct"] | groups["unbreak"]
    # Adblock data contains only exact/suffix domains. No keyword/IP overblocking.
    ad_input = {r for r in groups["adblock"] if r[0] in {"DOMAIN", "DOMAIN-SUFFIX"}}
    groups["adblock"], removed = remove_protected(ad_input, allowed)
    groups = {name: minimize(groups[name]) for name in TARGETS}
    now = datetime.now(CST)
    build_id = now.strftime("%Y%m%dT%H%M%S%f+0800")
    template_hashes = {f.name: sha(f.read_bytes()) for f in (ROOT / "templates").iterdir() if f.is_file()}
    # Stage all outputs and validate before writing to the checkout.
    with tempfile.TemporaryDirectory(prefix=".build-", dir=ROOT) as tmp:
        stage = Path(tmp)
        (stage / "rules").mkdir()
        (stage / "objects").mkdir()
        values = {"ROOT_URL": base, "GENERATED_AT": now.isoformat(timespec="seconds"),
                  "BUILD_ID": build_id, "NODE_FILTER": node_filter,
                  "DEPLOYMENT_NOTE": "发布前必须绑定你的 GitHub 仓库；当前链接为占位符"
                  if repository.startswith("YOUR_") else f"仓库：{repository}；分支：{branch}",
                  "QUIC_RULE": "AND,((PROTOCOL,UDP),(DST-PORT,443)),REJECT"
                  if settings.get("quic_block", True) else "# QUIC blocking disabled in settings.json"}
        counts = {}
        for name in TARGETS:
            data = render_list(name, groups[name])
            digest = sha(data)
            (stage / "objects" / (digest + ".list")).write_bytes(data)
            path = stage / ("adblock.list" if name == "adblock" else f"rules/{name}.list")
            path.write_bytes(data)
            values["RULE_" + name] = f"{base}/objects/{digest}.list"
            counts[name] = len(groups[name])
        script_data = (ROOT / "scripts/domestic-ads.js").read_bytes()
        script_digest = sha(script_data)
        (stage / "objects" / (script_digest + ".js")).write_bytes(script_data)
        values["SCRIPT_domestic_ads"] = f"{base}/objects/{script_digest}.js"
        for name in ["routing.conf", "adblock.sgmodule"]:
            rendered = substitute((ROOT / "templates" / name).read_text(), values)
            (stage / name).write_text(rendered)
        (stage / "whitelist-removed.tsv").write_text(
            "# Removed ad rules that intersect whitelist\n" +
            "\n".join(f"{k}\t{v}" for k, v in removed) + "\n")
        file_hashes = {str(f.relative_to(stage)): sha(f.read_bytes())
                       for f in sorted(stage.rglob("*")) if f.is_file()}
        manifest = {"schema": 1, "build_id": build_id, "generated_at": now.isoformat(),
                    "generated_date_bjt": now.date().isoformat(), "repository": repository,
                    "branch": branch, "requires_repository_binding": repository.startswith("YOUR_"),
                    "counts": counts, "whitelist_removed": len(removed),
                    "routing_whitelist_conflicts_removed": len(route_removed),
                    "sources": sorted(sources, key=lambda s: s["id"]),
                    "local_sha256": local_hashes, "template_sha256": template_hashes,
                    "script_sha256": {"domestic-ads.js": script_digest}, "adblock_version": "v2",
                    "files_sha256": file_hashes,
                    "validation_scope": "Static checks only; not compiled/executed on iOS Shadowrocket"}
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        validate_output(stage)
        for f in stage.rglob("*"):
            if f.is_file():
                relative = f.relative_to(stage)
                dest = ROOT / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Existing content-addressed blobs must never change.
                if relative.parts[0] == "objects" and dest.exists() and dest.read_bytes() != f.read_bytes():
                    raise ValueError("immutable object changed")
                shutil.copyfile(f, dest)
    print(json.dumps({"build_id": build_id, "counts": counts,
                      "whitelist_removed": len(removed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

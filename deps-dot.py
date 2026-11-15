#!/usr/bin/env python3

# Python script to calculate dependency for graphviz
# Usage:
#   python3 deps-dot.py --root ~/projects/superconfigure > deps.dot
#   dot -Tsvg deps.dot -o deps.svg

import argparse
import re
import sys
from pathlib import Path

ROOT_DIRS = (
    "cli",
    "compress",
    "editor",
    "games",
    "gui",
    "lang",
    # "lib",
    # "python",
    "web",
)

ASSIGNMENT_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_.-]*_DEPS)\s*(:=|\?=|\+=|=)\s*(.*?)\s*$"
)

SPECIFY_RE = re.compile(
    r"\$\(\s*call\s+SPECIFY_DEPS\s*,\s*([^,]+?)\s*,\s*"
    r"\$\(\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\)\s*\)"
)


def logical_lines(path: Path):
    """合并以反斜杠结尾的 Makefile 续行。."""
    pending = ""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"警告：无法读取 {path}: {exc}", file=sys.stderr)
        return

    for line in lines:
        line = line.rstrip()

        if line.endswith("\\"):
            pending += line[:-1] + " "
        else:
            yield pending + line
            pending = ""

    if pending:
        yield pending


def strip_comment(line: str) -> str:
    """去掉 Makefile 注释；假设依赖路径本身不包含 #。."""
    return re.sub(r"(?<!\\)#.*$", "", line)


def dot_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从 BUILD.mk 提取软件包依赖并输出 Graphviz DOT"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="项目根目录，默认为当前目录",
    )
    args = parser.parse_args()

    root = args.root.resolve()

    build_files = []
    for dirname in ROOT_DIRS:
        directory = root / dirname
        if directory.is_dir():
            build_files.extend(directory.rglob("BUILD.mk"))
        else:
            print(f"警告：目录不存在，跳过 {directory}", file=sys.stderr)

    # 先收集依赖变量，再把 SPECIFY_DEPS 调用关联到软件包。
    deps_vars = {}
    specifications = []

    for path in sorted(build_files):
        for line in logical_lines(path):
            line = strip_comment(line)

            match = ASSIGNMENT_RE.match(line)
            if match:
                var, operator, value = match.groups()

                if operator == "+=":
                    deps_vars[var] = (deps_vars.get(var, "") + " " + value).strip()
                elif operator == "?=":
                    deps_vars.setdefault(var, value.strip())
                else:
                    # := 和 = 在这里都按静态文本处理，不展开 Make 变量。
                    deps_vars[var] = value.strip()

            for match in SPECIFY_RE.finditer(line):
                package, var = match.groups()
                specifications.append((package.strip(), var.strip(), path))

    edges = set()
    nodes = set()

    for package, var, path in specifications:
        nodes.add(package)
        value = deps_vars.get(var)

        if value is None:
            print(
                f"警告：{path} 中的 {package} 引用了未找到的变量 {var}",
                file=sys.stderr,
            )
            continue

        for dependency in value.split():
            nodes.add(dependency)
            edges.add((package, dependency))

    print("digraph dependencies {")
    print("  rankdir=LR;")
    print("  node [shape=box];")

    for node in sorted(nodes):
        print(f"  {dot_quote(node)};")

    for package, dependency in sorted(edges):
        # 箭头方向：软件包 -> 它依赖的软件包
        print(f"  {dot_quote(package)} -> {dot_quote(dependency)};")

    print("}")


if __name__ == "__main__":
    main()

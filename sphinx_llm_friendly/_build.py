from __future__ import annotations

import argparse
import concurrent.futures
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from sphinx.cmd.build import main as sphinx_build_main

from ._intersphinx import rewrite_intersphinx_links

if TYPE_CHECKING:
    from sphinx.application import Sphinx

_BUILDERS = ("html", "llm_markdown", "llm_singlemarkdown")

_intersphinx_urls: set[str] = set()


def remember_intersphinx_urls(app: Sphinx, exception: Exception | None) -> None:
    """Store the site URLs of ``intersphinx_mapping``, for :func:`_run_builder`
    to report them to the parent process.
    """
    mapping = getattr(app.config, "intersphinx_mapping", {})
    _intersphinx_urls.clear()
    _intersphinx_urls.update(uri for _name, (uri, _inventories) in mapping.values())


def _run_builder(builder: str, source_dir: Path, build_dir: Path) -> set[str]:
    exit_code = sphinx_build_main(
        ["-b", builder, str(source_dir), str(build_dir / builder)]
    )
    if exit_code != 0:
        msg = f"sphinx builder failed for '{builder}' with exit code {exit_code}"
        raise RuntimeError(msg)
    return set(_intersphinx_urls)


def build(source_dir: Path, build_dir: Path) -> Path:
    """Build the documentation in *source_dir* as HTML and Markdown, and
    return the directory inside *build_dir* where the outputs are merged.
    """
    build_dir.mkdir(parents=True, exist_ok=True)
    intersphinx_urls: set[str] = set()
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(_BUILDERS)) as pool:
        futures = [
            pool.submit(_run_builder, builder, source_dir, build_dir)
            for builder in _BUILDERS
        ]
        for future in concurrent.futures.as_completed(futures):
            intersphinx_urls |= future.result()

    output_dir = build_dir / "all"
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(build_dir / "html", output_dir, dirs_exist_ok=True)
    shutil.copytree(build_dir / "llm_markdown", output_dir, dirs_exist_ok=True)
    shutil.copy2(
        build_dir / "llm_singlemarkdown" / "index.md", output_dir / "llms-full.txt"
    )
    rewrite_intersphinx_links(
        [
            *sorted(output_dir.rglob("*.md")),
            output_dir / "llms.txt",
            output_dir / "llms-full.txt",
        ],
        intersphinx_urls,
    )
    return output_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sphinx-llm-friendly")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser(
        "build", help="build HTML and Markdown documentation"
    )
    build_parser.add_argument("source_dir", type=Path)
    build_parser.add_argument("build_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        output_dir = build(args.source_dir, args.build_dir)
    except RuntimeError as error:
        parser.exit(1, f"{error}\n")
    print(f"\nDocumentation generated in {output_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

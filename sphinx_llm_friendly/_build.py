from __future__ import annotations

import argparse
import warnings
from pathlib import Path

from sphinx.cmd.build import main as sphinx_build_main


def build(source_dir: Path, build_dir: Path) -> Path:
    """Build the documentation in *source_dir* with the ``html`` builder into
    ``all`` inside *build_dir*, and return that directory.
    """
    warnings.warn(
        "sphinx_llm_friendly.build() and the sphinx-llm-friendly command are "
        "deprecated, use sphinx-build -b html instead",
        DeprecationWarning,
        stacklevel=2,
    )
    output_dir = build_dir / "all"
    exit_code = sphinx_build_main(
        ["-b", "html", "-j", "auto", str(source_dir), str(output_dir)]
    )
    if exit_code != 0:
        msg = f"sphinx-build failed with exit code {exit_code}"
        raise RuntimeError(msg)
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

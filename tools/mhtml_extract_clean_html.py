from __future__ import annotations

import argparse
import re
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Iterable


def extract_html_from_mhtml(file_path: Path) -> str:
    with file_path.open("rb") as source:
        message = BytesParser(policy=policy.default).parse(source)

    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() != "text/html":
                continue

            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")

    # Fallback if file is not a valid multipart MHTML.
    return file_path.read_text(encoding="utf-8", errors="replace")


def strip_css(html: str) -> str:
    html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(
        r"<link\b[^>]*\brel\s*=\s*['\"][^'\"]*stylesheet[^'\"]*['\"][^>]*>",
        "",
        html,
        flags=re.IGNORECASE,
    )
    return html


def write_clean_html(input_file: Path, output_dir: Path) -> Path:
    html = extract_html_from_mhtml(input_file)
    clean_html = strip_css(html)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_file.stem}_clean.html"
    output_path.write_text(clean_html, encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract HTML from MHTML and remove CSS code for easier HTML/JS inspection.",
    )
    parser.add_argument("files", nargs="+", help="Input .mhtml files")
    parser.add_argument(
        "--out-dir",
        default="clean_html",
        help="Output directory for cleaned HTML files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.out_dir)

    for raw_path in args.files:
        input_path = Path(raw_path)
        if not input_path.exists():
            print(f"[WARN] File not found: {input_path}")
            continue

        output_path = write_clean_html(input_path, output_dir)
        print(f"[OK] Wrote {output_path}")


if __name__ == "__main__":
    main()

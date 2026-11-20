#!/usr/bin/env python3
"""Download an HTTP resource ten times and report timing and throughput."""

from __future__ import annotations

import argparse
import codecs
import re
import sys
import time
from email import message_from_string
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, unquote_to_bytes
from urllib.request import Request, urlopen


ATTEMPTS = 10
CHUNK_SIZE = 1024 * 1024
PERCENT_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")
BAD_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def split_last_segment(value: str) -> str | None:
    """Return the last non-empty segment, treating both slash styles alike."""
    segments = re.split(r"[/\\]", value)
    for segment in reversed(segments):
        if segment:
            return segment
    return None


def decode_url_name(value: str) -> str:
    """Decode a URL path component, marking malformed escapes as unsafe."""
    value = BAD_PERCENT_ESCAPE.sub("_", value)
    decoded = unquote_to_bytes(value)
    text = decoded.decode("utf-8", errors="replace")
    return text.replace("\ufffd", "_")


def dangerous_character(character: str) -> bool:
    """Characters that cannot safely be used in a portable file name."""
    code = ord(character)
    return code < 32 or code == 127 or character in '<>:"/\\|?*'


def sanitize_name(value: str | None) -> str:
    if not value:
        return "download"
    if not any(not dangerous_character(char) for char in value):
        return "download"

    name = "".join("_" if dangerous_character(char) else char for char in value)
    if not name:
        return "download"
    # A directory name would not be a valid download target.
    if name in {".", ".."}:
        return "download"
    return name


def raw_filename_star(header: str) -> str | None:
    """Extract filename* without letting the email parser hide malformed data."""
    match = re.search(
        r"(?:^|;)\s*filename\*\s*=\s*(?:\"((?:[^\"\\]|\\.)*)\"|([^;]*))",
        header,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1) if match.group(1) is not None else match.group(2)
    return value.strip()


def decode_filename_star(value: str) -> str | None:
    """Decode RFC 5987 filename*, returning None when it is invalid."""
    if not value:
        return None
    parts = value.split("'", 2)
    if len(parts) != 3:
        return None
    charset, _language, encoded = parts
    if not charset or not encoded or BAD_PERCENT_ESCAPE.search(encoded):
        return None
    if not all(PERCENT_ESCAPE.fullmatch(part) for part in re.findall(r"%..", encoded)):
        return None
    try:
        codec = codecs.lookup(charset)
        return unquote_to_bytes(encoded).decode(codec.name, errors="strict")
    except (LookupError, UnicodeDecodeError, ValueError):
        return None


def content_disposition_name(header: str | None) -> str | None:
    if not header:
        return None

    filename_star = raw_filename_star(header)
    if filename_star is not None:
        decoded = decode_filename_star(filename_star)
        if decoded is not None:
            return sanitize_name(split_last_segment(decoded))

    # email.message handles quoted strings and semicolons inside quotes.
    message = message_from_string("Content-Disposition: " + header)
    for key, value in message.get_params(
        header="content-disposition", unquote=True
    )[1:]:
        if key.lower() == "filename" and isinstance(value, str):
            return sanitize_name(split_last_segment(value))
    return None


def result_name(url: str, content_disposition: str | None) -> str:
    header_name = content_disposition_name(content_disposition)
    if header_name is not None:
        return header_name

    path = urlsplit(url).path
    decoded_path = decode_url_name(path)
    return sanitize_name(split_last_segment(decoded_path))


def progress(attempt: int, received: int, started: float) -> None:
    elapsed = max(time.monotonic() - started, 1e-12)
    speed = received / elapsed / 1_000_000
    print(f"\rПопытка {attempt}/{ATTEMPTS}: {speed:.2f} МБ/с", end="", flush=True)


def download_once(url: str, attempt: int, totals: list[int], files: set[Path]) -> float:
    started = time.monotonic()
    download_elapsed: float | None = None
    temporary_path: Path | None = None
    received = 0
    try:
        request = Request(url, headers={"User-Agent": "TestDownloader/1.0 (https://example.com)"})
        with urlopen(request) as response:
            status = getattr(response, "status", response.getcode())
            if not 200 <= status < 300:
                raise RuntimeError(f"HTTP status {status}")

            target = Path.cwd() / result_name(
                url, response.headers.get("Content-Disposition")
            )
            with NamedTemporaryFile(
                mode="wb",
                dir=Path.cwd(),
                prefix=".measure-download-",
                suffix=".part",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    temporary.write(chunk)
                    received += len(chunk)
                    totals[0] += len(chunk)
                    progress(attempt, received, started)

            download_elapsed = time.monotonic() - started

        # This filesystem operation is intentionally outside the timed region.
        temporary_path.replace(target)
        files.add(target)
        return download_elapsed if download_elapsed is not None else 0.0
    except KeyboardInterrupt:
        # Keep the partial temporary file as required.
        raise
    except HTTPError as error:
        print(f"\rПопытка {attempt}/{ATTEMPTS}: HTTP-ошибка {error.code}")
        return time.monotonic() - started
    except (OSError, URLError, ValueError, RuntimeError) as error:
        print(f"\rПопытка {attempt}/{ATTEMPTS}: ошибка: {error}")
        return time.monotonic() - started
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass
        if received:
            print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Скачать URL десять раз")
    parser.add_argument("url", help="URL со схемой http или https")
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        parser.error("URL должен иметь схему http или https и имя хоста")
    return args


def main() -> int:
    args = parse_args()
    total_time = 0.0
    totals = [0]
    files: set[Path] = set()

    try:
        for attempt in range(1, ATTEMPTS + 1):
            total_time += download_once(args.url, attempt, totals, files)
    except KeyboardInterrupt:
        print("\nПрервано пользователем.", file=sys.stderr)
        return 130

    print(f"Среднее время попытки: {total_time / ATTEMPTS:.3f} с")
    print(f"Объём скачанных данных: {totals[0]} байт")
    if files:
        print("Сохранённые файлы:")
        for path in sorted(files):
            print(f"- {path.name}")
    else:
        print("Сохранённых файлов нет.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

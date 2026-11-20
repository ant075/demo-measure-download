#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download an HTTP resource ten times and report timing and throughput."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ATTEMPTS = 10
CHUNK_SIZE = 1024 * 1024


def progress(
    attempt: int, received: int, started: float, elapsed: float | None = None
) -> None:
    elapsed = max(
        time.monotonic() - started if elapsed is None else elapsed,
        1e-12,
    )
    speed = received / elapsed / 1_000_000
    print(
        f"\rПопытка {attempt}/{ATTEMPTS}: {speed:.2f} МБ/с, "
        f"{elapsed:.3f} с, {received} байт",
        end="",
        flush=True,
    )


def download_once(url: str, attempt: int, totals: list[int], files: set[Path]) -> float:
    started = time.monotonic()
    received = 0
    download_elapsed: float | None = None
    error_message: str | None = None
    try:
        request = Request(url, headers={"User-Agent": "TestDownloader/1.0 (https://example.com)"})
        with urlopen(request) as response:
            status = response.status if hasattr(response, "status") else response.getcode()
            if not 200 <= status < 300:
                raise RuntimeError(f"HTTP status {status}")

            target = Path.cwd() / "download"
            with target.open("wb") as output:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    received += len(chunk)
                    totals[0] += len(chunk)
                    progress(attempt, received, started)

        files.add(target)
        download_elapsed = time.monotonic() - started
        return download_elapsed
    except KeyboardInterrupt:
        raise
    except HTTPError as error:
        error_message = f"HTTP-ошибка {error.code}"
    except (OSError, URLError, ValueError, RuntimeError) as error:
        error_message = f"ошибка: {error}"
    finally:
        if received:
            progress(
                attempt,
                received,
                started,
                download_elapsed or (time.monotonic() - started),
            )
        elapsed = download_elapsed or (time.monotonic() - started)
        if error_message:
            print(
                f"\rПопытка {attempt}/{ATTEMPTS}: {error_message}, "
                f"{elapsed:.3f} с"
            )
        elif received:
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

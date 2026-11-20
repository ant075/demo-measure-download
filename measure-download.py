#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download an HTTP resource ten times and report timing and throughput."""

import argparse
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ATTEMPTS = 3
CHUNK_SIZE = 1024 * 1024
# Такой User-Agent позволяет скачать по прямой ссылке с ресурсов вроде wikimedia.org
USER_AGENT = 'TestDownloader/1.0 (https://example.com)'


def progress(attempt: int, received: int, elapsed: float) -> None:
    elapsed = max(elapsed, 1e-12)
    speed = received / elapsed / 1_000_000
    print(
        f"\rПопытка {attempt}/{ATTEMPTS}: {speed:.2f} МБ/с, "
        f"{elapsed:.3f} с, {received} байт",
        end="",
        flush=True,
    )


def initial_progress(attempt: int) -> None:
    print(
        f"\rПопытка {attempt}/{ATTEMPTS}: —, 0.000 с, 0 байт",
        end="",
        flush=True,
    )


def download_once(
    url: str, attempt: int, target: Path
) -> tuple[float, int, bool]:
    initial_progress(attempt)
    received = 0
    download_elapsed = 0.0
    error_message: str | None = None
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request) as response:
            status = response.status if hasattr(response, "status") else response.getcode()
            if not 200 <= status < 300:
                raise RuntimeError(f"HTTP status {status}")

            with target.open("wb") as output:
                while True:
                    read_started = time.monotonic()
                    try:
                        chunk = response.read(CHUNK_SIZE)
                    finally:
                        download_elapsed += time.monotonic() - read_started
                    if not chunk:
                        break
                    output.write(chunk)
                    received += len(chunk)
                    progress(attempt, received, download_elapsed)

        return download_elapsed, received, True
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
                download_elapsed,
            )
        if error_message:
            print(
                f"\rПопытка {attempt}/{ATTEMPTS}: {error_message}, "
                f"{download_elapsed:.3f} с"
            )
        elif received:
            print()
        else:
            print(f"\rПопытка {attempt}/{ATTEMPTS}: —, {download_elapsed:.3f} с, 0 байт")

    return download_elapsed, received, False


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
    target = Path.cwd() / "download"
    total_time = 0.0
    total_bytes = 0
    saved_anything = False

    try:
        for attempt in range(1, ATTEMPTS + 1):
            elapsed, received, completed = download_once(args.url, attempt, target)
            total_time += elapsed
            total_bytes += received
            saved_anything = saved_anything or completed
    except KeyboardInterrupt:
        print("\nПрервано пользователем.", file=sys.stderr)
        return 130

    print(f"Среднее время попытки: {total_time / ATTEMPTS:.3f} с")
    print(f"Объём скачанных данных: {total_bytes} байт")
    if saved_anything:
        print(f"Сохранённый файл: {target}")
    else:
        print("Сохранённых файлов нет.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

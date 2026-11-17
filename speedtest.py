#!/usr/bin/env python3
"""Консольный скрипт для замера скорости скачивания по заданному URL."""

import argparse
import statistics
import sys
import time
import urllib.parse

import httpx

DEFAULT_REQUESTS = 10
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "speedtest-cli/0.1 (https://github.com/retro-future/speedtest)"
CHUNK_SIZE = 64 * 1024  # 64 КБ


def validate_url(url: str) -> str:
    """Проверяет, что передан корректный HTTP/HTTPS URL."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            f"Некорректный URL: '{url}'. Ожидается адрес с протоколом http:// или https://"
        )
    return url


def fetch_once(client: httpx.Client, url: str) -> tuple[int, float]:
    """Выполняет один GET-запрос, дожидается полного ответа и возвращает (байты, секунды)."""
    start = time.perf_counter()
    downloaded = 0
    with client.stream("GET", url) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
            downloaded += len(chunk)
    elapsed = time.perf_counter() - start
    return downloaded, elapsed


def format_bytes(num_bytes: int) -> str:
    """Форматирует объём данных в байтах в человекочитаемый вид (десятичные единицы)."""
    if num_bytes < 1_000:
        return f"{num_bytes} Б"
    if num_bytes < 1_000_000:
        return f"{num_bytes / 1_000:.2f} КБ"
    if num_bytes < 1_000_000_000:
        return f"{num_bytes / 1_000_000:.2f} МБ"
    return f"{num_bytes / 1_000_000_000:.2f} ГБ"


def run_benchmark(
    url: str,
    requests_count: int,
    timeout: float,
    user_agent: str,
) -> None:
    """Выполняет серию последовательных запросов и выводит статистику скорости."""
    print(f"Цель: {url}")
    print(f"Количество последовательных запросов: {requests_count}\n")

    total_bytes = 0
    total_time = 0.0
    request_times: list[float] = []
    headers = {
        "User-Agent": user_agent,
        "Cache-Control": "no-cache"
    }

    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        for idx in range(1, requests_count + 1):
            size_bytes, elapsed = fetch_once(client, url)
            total_bytes += size_bytes
            total_time += elapsed
            request_times.append(elapsed)
            req_mbps = (size_bytes * 8) / (elapsed * 1_000_000) if elapsed > 0 else 0.0
            print(
                f"[{idx:>2}/{requests_count}] "
                f"Скачано: {format_bytes(size_bytes)} | "
                f"Время: {elapsed:.3f} с | "
                f"Скорость: {req_mbps:.2f} Мбит/с"
            )

    avg_time = total_time / requests_count
    median_time = statistics.median(request_times)
    speed_mbps = (total_bytes * 8) / (total_time * 1_000_000) if total_time > 0 else 0.0
    speed_mbs = total_bytes / (total_time * 1_000_000) if total_time > 0 else 0.0

    print("\n--- Итоги ---")
    print(f"Общий объём скачанных данных: {format_bytes(total_bytes)} ({total_bytes} Б)")
    print(f"Общее время: {total_time:.3f} с")
    print(f"Среднее время запроса: {avg_time:.3f} с")
    print(f"Медианное время запроса: {median_time:.3f} с")
    print(f"Скорость скачивания: {speed_mbps:.2f} Мбит/с ({speed_mbs:.2f} МБ/с)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Замер скорости скачивания путём последовательных HTTP-запросов."
    )
    parser.add_argument(
        "url",
        help="URL ресурса для скачивания (например, ссылка на тяжёлую картинку)",
    )
    parser.add_argument(
        "-n",
        "--requests",
        type=int,
        default=DEFAULT_REQUESTS,
        help=f"Количество последовательных запросов (по умолчанию: {DEFAULT_REQUESTS})",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Таймаут одного запроса в секундах (по умолчанию: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "-A",
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help=f"Значение заголовка User-Agent (по умолчанию: {DEFAULT_USER_AGENT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI."""
    args = parse_args(argv)

    try:
        url = validate_url(args.url)
    except ValueError as err:
        print(f"Ошибка: {err}", file=sys.stderr)
        return 2

    if args.requests <= 0:
        print("Ошибка: количество запросов должно быть положительным числом.", file=sys.stderr)
        return 2

    if args.timeout <= 0:
        print("Ошибка: таймаут должен быть положительным числом.", file=sys.stderr)
        return 2

    try:
        run_benchmark(url, args.requests, args.timeout, args.user_agent)
    except httpx.HTTPStatusError as err:
        print(
            f"\nОшибка HTTP {err.response.status_code}: {err.response.reason_phrase}",
            file=sys.stderr,
        )
        return 1
    except httpx.RequestError as err:
        print(f"\nОшибка сети: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nПрервано пользователем.", file=sys.stderr)
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())

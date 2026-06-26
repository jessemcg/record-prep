from __future__ import annotations

import concurrent.futures
from typing import Any, Callable


def run_classifier_jobs(
    jobs: list[tuple[Callable[..., dict[str, str]], tuple[Any, ...]]],
    workers: int,
    stop_check: Callable[[], None] | None = None,
) -> list[dict[str, str]]:
    if not jobs:
        return []
    results: list[dict[str, str] | None] = [None] * len(jobs)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers))
    future_to_index = {
        executor.submit(callback, *args): index
        for index, (callback, args) in enumerate(jobs)
    }
    try:
        for future in concurrent.futures.as_completed(future_to_index):
            if stop_check is not None:
                stop_check()
            index = future_to_index[future]
            results[index] = future.result()
    except BaseException:
        for future in future_to_index:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    executor.shutdown(wait=True)
    return [result or {} for result in results]


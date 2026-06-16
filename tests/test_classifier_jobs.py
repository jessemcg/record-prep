import threading
import time
import unittest

import recordprep


class ClassifierJobTests(unittest.TestCase):
    def test_classifier_jobs_use_workers_and_preserve_order(self) -> None:
        window = recordprep.RecordPrepWindow.__new__(recordprep.RecordPrepWindow)
        window._stop_event = threading.Event()

        lock = threading.Lock()
        active = 0
        max_active = 0

        def job(value: int) -> dict[str, str]:
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.05)
                return {"value": str(value)}
            finally:
                with lock:
                    active -= 1

        jobs = [(job, (index,)) for index in range(4)]

        results = window._run_classifier_jobs(jobs, workers=2)

        self.assertGreater(max_active, 1)
        self.assertEqual(
            results,
            [{"value": "0"}, {"value": "1"}, {"value": "2"}, {"value": "3"}],
        )


if __name__ == "__main__":
    unittest.main()

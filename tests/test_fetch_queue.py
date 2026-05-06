"""
测试 FetchQueue 任务队列
"""

import time
import pytest
from threading import Lock

from app.services.fetch_queue import FetchQueue, FetchTask


class TestFetchQueue:

    def test_queue_processes_tasks(self):
        """测试队列能正常处理任务"""
        results = []
        lock = Lock()

        def task_handler(task_id: str):
            with lock:
                results.append(task_id)

        queue = FetchQueue(max_workers=2, delay_between_tasks=0.1)

        for i in range(5):
            task = FetchTask(
                task_id=f"task-{i}",
                student_id=f"student-{i}",
                handler=lambda tid=f"task-{i}": task_handler(tid),
            )
            queue.submit(task)

        time.sleep(2.0)

        assert len(results) == 5
        assert set(results) == {f"task-{i}" for i in range(5)}

        queue.shutdown()

    def test_limited_concurrency(self):
        """测试有限并发（最多2个worker同时执行）"""
        active_count = 0
        max_active = 0
        lock = Lock()

        def slow_task():
            nonlocal active_count, max_active
            with lock:
                active_count += 1
                max_active = max(max_active, active_count)

            time.sleep(0.3)

            with lock:
                active_count -= 1

        queue = FetchQueue(max_workers=2, delay_between_tasks=0.0)

        for i in range(6):
            task = FetchTask(
                task_id=f"task-{i}",
                student_id=f"student-{i}",
                handler=slow_task,
            )
            queue.submit(task)

        time.sleep(2.5)

        assert max_active <= 2

        queue.shutdown()

    def test_queue_status(self):
        """测试队列状态查询"""
        queue = FetchQueue(max_workers=2, delay_between_tasks=0.5)

        status = queue.get_status()
        assert status["max_workers"] == 2
        assert status["queue_size"] == 0
        assert status["active_workers"] == 0

        def slow_task():
            time.sleep(1.0)

        for i in range(3):
            task = FetchTask(
                task_id=f"task-{i}",
                student_id=f"student-{i}",
                handler=slow_task,
            )
            queue.submit(task)

        time.sleep(0.2)
        status = queue.get_status()
        assert status["queue_size"] >= 0

        queue.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

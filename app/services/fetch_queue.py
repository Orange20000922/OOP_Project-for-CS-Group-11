"""
SCNU 抓取任务队列 - 使用 Queue 实现生产者-消费者模式
支持有限并发，避免同时发起过多请求被教务系统封禁
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock, Thread
from typing import Callable

from app.core import Queue
from app.logging_config import logger


@dataclass
class FetchTask:
    """抓取任务"""
    task_id: str
    student_id: str
    handler: Callable[[], None]


class FetchQueue:
    """抓取任务队列管理器"""

    def __init__(self, max_workers: int = 2, delay_between_tasks: float = 1.0):
        self.queue = Queue()
        self.max_workers = max_workers
        self.delay_between_tasks = delay_between_tasks
        self._lock = Lock()
        self._active_workers = 0
        self._running = True
        self._workers: list[Thread] = []

        for i in range(max_workers):
            worker = Thread(target=self._worker_loop, args=(i,), daemon=True, name=f"FetchWorker-{i}")
            worker.start()
            self._workers.append(worker)

        logger.info("FetchQueue started with {} workers", max_workers)

    def submit(self, task: FetchTask) -> None:
        """提交任务到队列"""
        with self._lock:
            self.queue.enqueue(task)
        logger.debug("Task {} submitted to queue (size: {})", task.task_id, self.queue.size())

    def _worker_loop(self, worker_id: int) -> None:
        """工作线程循环"""
        logger.debug("Worker {} started", worker_id)

        while self._running:
            task = None
            with self._lock:
                if not self.queue.is_empty():
                    task = self.queue.dequeue()
                    self._active_workers += 1

            if task is None:
                time.sleep(0.5)
                continue

            try:
                logger.info("Worker {} processing task {}", worker_id, task.task_id)
                task.handler()
                logger.info("Worker {} completed task {}", worker_id, task.task_id)
            except Exception as exc:
                logger.exception("Worker {} failed task {}: {}", worker_id, task.task_id, exc)
            finally:
                with self._lock:
                    self._active_workers -= 1

                if self.delay_between_tasks > 0:
                    time.sleep(self.delay_between_tasks)

        logger.debug("Worker {} stopped", worker_id)

    def shutdown(self) -> None:
        """关闭队列"""
        self._running = False
        for worker in self._workers:
            worker.join(timeout=5.0)
        logger.info("FetchQueue shutdown")

    def get_status(self) -> dict:
        """获取队列状态"""
        with self._lock:
            return {
                "queue_size": self.queue.size(),
                "active_workers": self._active_workers,
                "max_workers": self.max_workers,
            }

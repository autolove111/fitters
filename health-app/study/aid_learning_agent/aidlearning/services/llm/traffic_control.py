"""LLM Provider 的流量控制原语。"""

from __future__ import annotations

import asyncio
import logging
import time
from types import TracebackType

logger = logging.getLogger(__name__)


class TrafficController:
    """
    控制 LLM Provider 的并发和速率限制。

    保护本地系统（资源耗尽）和远程 Provider（速率限制）。
    """

    def __init__(
        self,
        provider_name: str,
        max_concurrency: int = 20,
        requests_per_minute: int = 600,
        acquisition_timeout: float = 30.0,
    ) -> None:
        """
        Args:
            provider_name: 用于日志记录的标签。
            max_concurrency: 最大并发请求数（隔板）。
            requests_per_minute: 本地限流前允许的最大 RPM。
            acquisition_timeout: 等待槽位的最大秒数，超时则失败。
        """
        self.provider_name = provider_name
        self.max_concurrency = max_concurrency
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be > 0")
        self.rpm = requests_per_minute
        self.acquisition_timeout = acquisition_timeout

        # 并发门控
        self._semaphore = asyncio.Semaphore(max_concurrency)

        # 速率限制（令牌桶）
        self._tokens = float(requests_per_minute)
        self._last_refill = time.monotonic()
        self._fill_rate = requests_per_minute / 60.0  # 每秒令牌数
        self._lock = asyncio.Lock()  # 保护令牌状态

    async def _wait_for_token(self) -> None:
        """消耗一个速率限制令牌，必要时等待。"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill

            # 补充令牌
            new_tokens = elapsed * self._fill_rate
            if new_tokens > 0:
                self._tokens = min(float(self.rpm), self._tokens + new_tokens)
                self._last_refill = now

            # 消耗令牌
            if self._tokens >= 1:
                self._tokens -= 1.0
                return

            # 计算获取 1 个令牌所需的等待时间
            wait_time = (1.0 - self._tokens) / self._fill_rate

        # 在锁外等待以避免阻塞其他任务
        if wait_time > 0:
            logger.debug("[%s] Rate limit active, waiting %.2fs" % (self.provider_name, wait_time))
            await asyncio.sleep(wait_time)
            # 递归重试（确保休眠后线程安全的最简单方式）
            await self._wait_for_token()

    async def __aenter__(self) -> TrafficController:
        """
        获取并发槽位和速率限制令牌。
        如果系统过载则抛出 asyncio.TimeoutError。
        """
        start = time.monotonic()

        # 1. 获取并发槽位
        try:
            # wait_for 为信号量获取添加超时
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self.acquisition_timeout)
        except TimeoutError:
            logger.error(
                "[%s] Local concurrency limit (%s) exceeded for >%.1fs."
                % (self.provider_name, self.max_concurrency, self.acquisition_timeout)
            )
            raise

        # 2. 获取速率限制令牌（如果通过了并发检查）
        # 注意：我们在信号量之后执行此操作，以确保在不必要时不会
        # 在持有并发槽位的同时等待令牌，
        # 但严格来说，在等待速率限制时持有信号量可以防止队列跳跃。
        try:
            await self._wait_for_token()
        except Exception:
            # 如果速率限制器失败/取消，释放信号量
            self._semaphore.release()
            raise

        wait_duration = time.monotonic() - start
        if wait_duration > 1.0:
            logger.warning("[%s] Traffic control wait: %.2fs" % (self.provider_name, wait_duration))

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """释放并发槽位。"""
        self._semaphore.release()
        return None


__all__ = ["TrafficController"]

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import time
from collections import defaultdict
from typing import Dict

import redis
import time

RATE_LIMIT = 500
WINDOW = 10  # seconds
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

try:
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    print("Redis connected")
except Exception as e:
    print(f"Redis unavailable: {e}")
    r = None


class MiddleWare(BaseHTTPMiddleware):
    #ok
    def __init__(self, app):
        super().__init__(app) 
        self.rate_limit_records: Dict[str, float] = defaultdict(float)
    def is_rate_limited(self,client_ip: str):
        if r is None:
            return False
    # key = f"rate_limit:{client_ip}"
        key = f"rate_limit:{client_ip}"
        now = time.time()

        # remove old timestamps
        r.zremrangebyscore(key, 0, now - WINDOW)

        # count requests in window
        request_count = r.zcard(key)

        if request_count >= RATE_LIMIT:
            return True

        # add current request
        r.zadd(key, {str(now): now})

        # expire key automatically
        r.expire(key, WINDOW)

        return False
    async def log_mesg(self, message: str):
        print(message)

    # async def dispatch(self, request: Request, call_next):

    #     client_ip = request.client.host
    #     curr_time = time.time()

    #     if curr_time - self.rate_limit_records[client_ip] < 1:
    #         return JSONResponse(
    #             content={"error": "Rate Limit Exceeded"},
    #             status_code=429
    #         )

    #     self.rate_limit_records[client_ip] = curr_time

    #     path = request.url.path
    #     await self.log_mesg(f"Request to {path}")

    #     start_time = time.time()

    #     response = await call_next(request)

    #     process_time = time.time() - start_time

    #     response.headers["X-Process-Time"] = str(process_time)

    #     await self.log_mesg(f"Response for {path} took {process_time} sec")

    #     return response
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/docs", "/openapi.json", "/health"]:
            return await call_next(request)
        client_ip = request.client.host

        if self.is_rate_limited(client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"}
            )

        response = await call_next(request)
        return response
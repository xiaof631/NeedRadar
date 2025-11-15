"""轻量级 FastAPI 兼容层，用于离线环境的单元测试。"""

from .application import FastAPI
from .routing import APIRouter

__all__ = ["FastAPI", "APIRouter"]

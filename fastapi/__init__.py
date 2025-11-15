"""轻量级 FastAPI 兼容层，用于离线环境的单元测试。"""

from .application import FastAPI
from .routing import APIRouter
from .dependencies import Depends, Query
from .exceptions import HTTPException
from .status import status

__all__ = [
    "FastAPI",
    "APIRouter",
    "Depends",
    "Query",
    "HTTPException",
    "status",
]

"""轻量级 FastAPI 兼容层，用于离线环境的单元测试。"""

from .application import FastAPI
from .dependencies import Depends, Header, Query
from .exceptions import HTTPException
from .responses import Response
from .routing import APIRouter
from .status import status

__all__ = [
    "FastAPI",
    "APIRouter",
    "Depends",
    "Header",
    "Query",
    "HTTPException",
    "Response",
    "status",
]

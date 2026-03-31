"""
GPU Client - AWS only (SageMaker + Lambda).

Project is AWS-only. Modal is deprecated; all GPU workloads use AWS.
"""
import logging
from typing import Tuple, Type

logger = logging.getLogger(__name__)

_aws_client = None


def get_gpu_client():
    """Return the AWS GPU client (SageMaker/Lambda)."""
    global _aws_client
    if _aws_client is None:
        from app.services.aws_gpu_client import aws_gpu_client
        _aws_client = aws_gpu_client
        logger.info("Using AWS GPU client (SageMaker/Lambda)")
    return _aws_client


def get_client_error_class() -> Type[Exception]:
    """Return the AWS GPU client exception class."""
    from app.services.aws_gpu_client import AWSGPUClientError
    return AWSGPUClientError


def get_client_exceptions() -> Tuple[Type[Exception], ...]:
    """Return tuple of GPU client exceptions for broad except."""
    from app.services.aws_gpu_client import AWSGPUClientError
    return (AWSGPUClientError,)

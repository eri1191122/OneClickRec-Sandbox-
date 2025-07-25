"""
File Verifier - Size Checker Strategy (新構造完全対応版)
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

import aiofiles
import aiofiles.os

from .base import VerificationStrategy
from ..result import StrategyResult, StrategyType, Severity

class FileSizeStrategy(VerificationStrategy):
    def __init__(
        self, 
        min_size_bytes: int = 1, 
        max_size_bytes: Optional[int] = None,
        warning_threshold: Optional[int] = None,
        auto_strategy_type: bool = False
    ):
        if min_size_bytes < 0:
            raise ValueError("min_size_bytes must be non-negative.")
        if max_size_bytes is not None and max_size_bytes < min_size_bytes:
            raise ValueError("max_size_bytes must be greater than or equal to min_size_bytes.")
        if warning_threshold is not None and warning_threshold < min_size_bytes:
            raise ValueError("warning_threshold must be greater than or equal to min_size_bytes.")
            
        self.min_size_bytes = min_size_bytes
        self.max_size_bytes = max_size_bytes
        self.warning_threshold = warning_threshold
        self.auto_strategy_type = auto_strategy_type
    
    @property
    def strategy_type(self) -> StrategyType:
        if self.auto_strategy_type:
            try:
                class_name = self.__class__.__name__.replace("Strategy", "").upper()
                return StrategyType[class_name]
            except KeyError:
                return StrategyType.FILE_SIZE
        else:
            return StrategyType.FILE_SIZE
    
    async def check(self, file_path: Path) -> StrategyResult:
        try:
            file_size = await self._get_file_size(file_path)
            return self._evaluate_size(file_size)
            
        except FileNotFoundError:
            return StrategyResult(
                strategy_type=self.strategy_type,
                is_valid=False,
                message="File not found",
                severity=Severity.ERROR,
                details={"path": str(file_path), "error_type": "file_not_found"}
            )
        except Exception as e:
            return StrategyResult(
                strategy_type=self.strategy_type,
                is_valid=False,
                message=f"Size check error: {str(e)}",
                severity=Severity.ERROR,
                details={"exception": str(e), "exception_type": type(e).__name__}
            )
    
    async def _get_file_size(self, file_path: Path) -> int:
        stat_result = await aiofiles.os.stat(file_path)
        return stat_result.st_size
    
    def _evaluate_size(self, file_size: int) -> StrategyResult:
        if file_size < self.min_size_bytes:
            return StrategyResult(
                strategy_type=self.strategy_type,
                is_valid=False,
                message=f"File too small ({file_size} < {self.min_size_bytes} bytes)",
                severity=Severity.ERROR,
                details={"file_size_bytes": file_size, "min_size_bytes": self.min_size_bytes}
            )
        
        if self.max_size_bytes is not None and file_size > self.max_size_bytes:
            return StrategyResult(
                strategy_type=self.strategy_type,
                is_valid=False,
                message=f"File too large ({file_size} > {self.max_size_bytes} bytes)",
                severity=Severity.ERROR,
                details={"file_size_bytes": file_size, "max_size_bytes": self.max_size_bytes}
            )
        
        severity = Severity.INFO
        message = "File size is normal"
        
        if self.warning_threshold is not None and file_size > self.warning_threshold:
            severity = Severity.WARNING
            message = f"File size is large ({file_size} > {self.warning_threshold} bytes)"
        
        return StrategyResult(
            strategy_type=self.strategy_type,
            is_valid=True,
            message=message,
            severity=severity,
            details={"file_size_bytes": file_size}
        )

def create_video_size_strategy(
    min_mb: float = 0.1,
    max_gb: Optional[float] = None,
    warning_gb: Optional[float] = None,
    auto_strategy_type: bool = False
) -> FileSizeStrategy:
    min_bytes = int(min_mb * 1024 * 1024)
    max_bytes = int(max_gb * 1024 * 1024 * 1024) if max_gb else None
    warning_bytes = int(warning_gb * 1024 * 1024 * 1024) if warning_gb else None
    
    return FileSizeStrategy(
        min_size_bytes=min_bytes,
        max_size_bytes=max_bytes,
        warning_threshold=warning_bytes,
        auto_strategy_type=auto_strategy_type
    )

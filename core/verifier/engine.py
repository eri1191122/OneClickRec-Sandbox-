"""
File Verifier - Verification Engine (新構造完全対応版)
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Union
import logging
import asyncio
from dataclasses import dataclass

from .checkers.base import VerificationStrategy
from .result import StrategyResult, Severity

@dataclass
class EngineConfig:
    log_enabled: bool = True
    log_level: int = logging.INFO
    async_mode: bool = True
    max_concurrent: int = 5
    custom_handler: Optional[logging.Handler] = None
    debug_mode: bool = False

class VerificationEngine:
    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.logger = self._setup_logger()
        
        if self.config.async_mode:
            self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        else:
            self._semaphore = None
    
    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"{__name__}.VerificationEngine")
        
        if not logger.handlers and self.config.log_enabled:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
            if self.config.custom_handler:
                logger.addHandler(self.config.custom_handler)
                if self.config.debug_mode:
                    logger.info("Custom log handler added")
            
            logger.setLevel(self.config.log_level)
        
        return logger

def create_verification_engine(
    log_enabled: bool = True,
    debug_mode: bool = False,
    max_concurrent: int = 5,
    custom_log_handler: Optional[logging.Handler] = None,
    async_mode: bool = True
) -> VerificationEngine:
    config = EngineConfig(
        log_enabled=log_enabled,
        log_level=logging.DEBUG if debug_mode else logging.INFO,
        async_mode=async_mode,
        max_concurrent=max_concurrent,
        custom_handler=custom_log_handler,
        debug_mode=debug_mode
    )
    
    return VerificationEngine(config)

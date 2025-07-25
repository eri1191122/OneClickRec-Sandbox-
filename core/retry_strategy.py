"""
汎用再試行戦略エンジン (Retry Strategy)
プロセス実行に限らず、あらゆる処理の再試行制御を担当

設計原則:
- 処理内容非依存（録画・API呼び出し・ファイル操作等すべてに対応）
- 柔軟な再試行ポリシー
- 詳細な統計・ログ機能
"""
import asyncio
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Union, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import logging

T = TypeVar('T')


class RetryPolicy(Enum):
    """再試行ポリシー"""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    RANDOM_JITTER = "random_jitter"
    CUSTOM = "custom"


class RetryResult(Enum):
    """再試行結果"""
    SUCCESS = "success"
    FAILED_ALL_ATTEMPTS = "failed_all_attempts"
    ABORTED = "aborted"
    TIMEOUT = "timeout"


@dataclass
class RetryAttempt:
    """再試行記録"""
    attempt_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    error: Optional[str] = None
    delay_before: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """実行時間（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


@dataclass
class RetryConfiguration:
    """再試行設定"""
    max_attempts: int = 3
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1
    timeout: Optional[float] = None
    custom_delay_func: Optional[Callable[[int, Exception], float]] = None
    
    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be non-negative")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")


@dataclass
class RetryExecutionResult(Generic[T]):
    """再試行実行結果"""
    result: RetryResult
    value: Optional[T] = None
    attempts: List[RetryAttempt] = field(default_factory=list)
    total_duration: float = 0.0
    final_error: Optional[str] = None
    configuration: Optional[RetryConfiguration] = None
    
    @property
    def attempt_count(self) -> int:
        """試行回数"""
        return len(self.attempts)
    
    @property
    def success(self) -> bool:
        """成功したかどうか"""
        return self.result == RetryResult.SUCCESS
    
    @property
    def average_attempt_duration(self) -> Optional[float]:
        """平均実行時間"""
        durations = [attempt.duration for attempt in self.attempts if attempt.duration is not None]
        if durations:
            return sum(durations) / len(durations)
        return None


class DelayCalculator:
    """遅延時間計算"""
    
    @staticmethod
    def calculate_delay(attempt_number: int, config: RetryConfiguration, last_error: Optional[Exception] = None) -> float:
        """
        遅延時間計算
        
        Args:
            attempt_number: 試行回数（1から開始）
            config: 再試行設定
            last_error: 前回のエラー
            
        Returns:
            float: 遅延時間（秒）
        """
        if config.policy == RetryPolicy.CUSTOM and config.custom_delay_func:
            try:
                return config.custom_delay_func(attempt_number, last_error)
            except Exception:
                # カスタム関数でエラーが発生した場合はフォールバック
                return config.base_delay
        
        if config.policy == RetryPolicy.FIXED_DELAY:
            delay = config.base_delay
            
        elif config.policy == RetryPolicy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.backoff_multiplier ** (attempt_number - 1))
            
        elif config.policy == RetryPolicy.LINEAR_BACKOFF:
            delay = config.base_delay * attempt_number
            
        elif config.policy == RetryPolicy.RANDOM_JITTER:
            # ベース遅延にランダムジッターを追加
            base = config.base_delay * (config.backoff_multiplier ** (attempt_number - 1))
            jitter = base * config.jitter_factor * (2 * random.random() - 1)  # -jitter_factor ~ +jitter_factor
            delay = base + jitter
            
        else:
            # デフォルトは固定遅延
            delay = config.base_delay
        
        # 最大遅延時間でクリップ
        delay = min(delay, config.max_delay)
        
        # 負の値を防ぐ
        return max(0, delay)


class RetryConditionChecker:
    """再試行条件チェック"""
    
    @staticmethod
    def should_retry(attempt_number: int, 
                    config: RetryConfiguration,
                    error: Exception,
                    error_checker: Optional[Callable[[Exception], bool]] = None) -> bool:
        """
        再試行すべきかどうか判定
        
        Args:
            attempt_number: 現在の試行回数
            config: 再試行設定
            error: 発生したエラー
            error_checker: エラー判定関数
            
        Returns:
            bool: 再試行すべきかどうか
        """
        # 最大試行回数チェック
        if attempt_number >= config.max_attempts:
            return False
        
        # カスタムエラーチェッカーがある場合
        if error_checker:
            try:
                return error_checker(error)
            except Exception:
                # エラーチェッカーでエラーが発生した場合は再試行しない
                return False
        
        # デフォルトでは一部の例外以外は再試行
        non_retryable_errors = (
            KeyboardInterrupt,
            SystemExit,
            MemoryError,
        )
        
        return not isinstance(error, non_retryable_errors)


class RetryExecutor:
    """
    再試行実行エンジン
    汎用的な再試行制御を提供
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初期化
        
        Args:
            logger: ロガー
        """
        self.logger = logger or logging.getLogger(__name__)
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_attempts": 0,
            "aborted_executions": 0
        }
    
    async def execute_with_retry(self,
                                operation: Callable[[], T],
                                config: RetryConfiguration,
                                error_checker: Optional[Callable[[Exception], bool]] = None,
                                abort_checker: Optional[Callable[[], bool]] = None) -> RetryExecutionResult[T]:
        """
        再試行付き実行（非同期）
        
        Args:
            operation: 実行する操作
            config: 再試行設定
            error_checker: 再試行可能エラーの判定関数
            abort_checker: 中断条件の判定関数
            
        Returns:
            RetryExecutionResult: 実行結果
        """
        start_time = datetime.now()
        attempts = []
        last_error = None
        
        self.stats["total_executions"] += 1
        
        try:
            for attempt_num in range(1, config.max_attempts + 1):
                # 中断チェック
                if abort_checker and abort_checker():
                    self.stats["aborted_executions"] += 1
                    return RetryExecutionResult(
                        result=RetryResult.ABORTED,
                        attempts=attempts,
                        total_duration=(datetime.now() - start_time).total_seconds(),
                        final_error="実行が中断されました",
                        configuration=config
                    )
                
                # タイムアウトチェック
                if config.timeout:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= config.timeout:
                        return RetryExecutionResult(
                            result=RetryResult.TIMEOUT,
                            attempts=attempts,
                            total_duration=elapsed,
                            final_error=f"タイムアウト（{config.timeout}秒）",
                            configuration=config
                        )
                
                # 遅延計算（初回は遅延なし）
                delay = 0.0
                if attempt_num > 1:
                    delay = DelayCalculator.calculate_delay(attempt_num - 1, config, last_error)
                    if delay > 0:
                        self.logger.debug(f"試行 {attempt_num}/{config.max_attempts}: {delay:.2f}秒待機")
                        await asyncio.sleep(delay)
                
                # 試行記録開始
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    start_time=datetime.now(),
                    delay_before=delay
                )
                
                try:
                    self.stats["total_attempts"] += 1
                    
                    # 操作実行
                    if asyncio.iscoroutinefunction(operation):
                        result = await operation()
                    else:
                        result = operation()
                    
                    # 成功
                    attempt.end_time = datetime.now()
                    attempt.success = True
                    attempts.append(attempt)
                    
                    self.stats["successful_executions"] += 1
                    
                    total_duration = (datetime.now() - start_time).total_seconds()
                    self.logger.info(f"操作成功（試行 {attempt_num}/{config.max_attempts}、総時間 {total_duration:.2f}秒）")
                    
                    return RetryExecutionResult(
                        result=RetryResult.SUCCESS,
                        value=result,
                        attempts=attempts,
                        total_duration=total_duration,
                        configuration=config
                    )
                
                except Exception as e:
                    # エラー発生
                    attempt.end_time = datetime.now()
                    attempt.error = str(e)
                    attempts.append(attempt)
                    last_error = e
                    
                    self.logger.warning(f"試行 {attempt_num}/{config.max_attempts} 失敗: {str(e)}")
                    
                    # 再試行判定
                    if attempt_num < config.max_attempts:
                        should_retry = RetryConditionChecker.should_retry(
                            attempt_num, config, e, error_checker
                        )
                        
                        if not should_retry:
                            self.logger.info(f"再試行不可能なエラーのため中断: {str(e)}")
                            break
                    
            # すべての試行が失敗
            self.stats["failed_executions"] += 1
            total_duration = (datetime.now() - start_time).total_seconds()
            
            return RetryExecutionResult(
                result=RetryResult.FAILED_ALL_ATTEMPTS,
                attempts=attempts,
                total_duration=total_duration,
                final_error=str(last_error) if last_error else "不明なエラー",
                configuration=config
            )
            
        except Exception as e:
            # 予期しないエラー
            self.stats["failed_executions"] += 1
            total_duration = (datetime.now() - start_time).total_seconds()
            
            return RetryExecutionResult(
                result=RetryResult.FAILED_ALL_ATTEMPTS,
                attempts=attempts,
                total_duration=total_duration,
                final_error=f"予期しないエラー: {str(e)}",
                configuration=config
            )
    
    def execute_with_retry_sync(self,
                               operation: Callable[[], T],
                               config: RetryConfiguration,
                               error_checker: Optional[Callable[[Exception], bool]] = None) -> RetryExecutionResult[T]:
        """
        再試行付き実行（同期）
        
        Args:
            operation: 実行する操作
            config: 再試行設定
            error_checker: 再試行可能エラーの判定関数
            
        Returns:
            RetryExecutionResult: 実行結果
        """
        start_time = datetime.now()
        attempts = []
        last_error = None
        
        self.stats["total_executions"] += 1
        
        try:
            for attempt_num in range(1, config.max_attempts + 1):
                # タイムアウトチェック
                if config.timeout:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= config.timeout:
                        return RetryExecutionResult(
                            result=RetryResult.TIMEOUT,
                            attempts=attempts,
                            total_duration=elapsed,
                            final_error=f"タイムアウト（{config.timeout}秒）",
                            configuration=config
                        )
                
                # 遅延計算（初回は遅延なし）
                delay = 0.0
                if attempt_num > 1:
                    delay = DelayCalculator.calculate_delay(attempt_num - 1, config, last_error)
                    if delay > 0:
                        self.logger.debug(f"試行 {attempt_num}/{config.max_attempts}: {delay:.2f}秒待機")
                        time.sleep(delay)
                
                # 試行記録開始
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    start_time=datetime.now(),
                    delay_before=delay
                )
                
                try:
                    self.stats["total_attempts"] += 1
                    
                    # 操作実行
                    result = operation()
                    
                    # 成功
                    attempt.end_time = datetime.now()
                    attempt.success = True
                    attempts.append(attempt)
                    
                    self.stats["successful_executions"] += 1
                    
                    total_duration = (datetime.now() - start_time).total_seconds()
                    self.logger.info(f"操作成功（試行 {attempt_num}/{config.max_attempts}、総時間 {total_duration:.2f}秒）")
                    
                    return RetryExecutionResult(
                        result=RetryResult.SUCCESS,
                        value=result,
                        attempts=attempts,
                        total_duration=total_duration,
                        configuration=config
                    )
                
                except Exception as e:
                    # エラー発生
                    attempt.end_time = datetime.now()
                    attempt.error = str(e)
                    attempts.append(attempt)
                    last_error = e
                    
                    self.logger.warning(f"試行 {attempt_num}/{config.max_attempts} 失敗: {str(e)}")
                    
                    # 再試行判定
                    if attempt_num < config.max_attempts:
                        should_retry = RetryConditionChecker.should_retry(
                            attempt_num, config, e, error_checker
                        )
                        
                        if not should_retry:
                            self.logger.info(f"再試行不可能なエラーのため中断: {str(e)}")
                            break
                    
            # すべての試行が失敗
            self.stats["failed_executions"] += 1
            total_duration = (datetime.now() - start_time).total_seconds()
            
            return RetryExecutionResult(
                result=RetryResult.FAILED_ALL_ATTEMPTS,
                attempts=attempts,
                total_duration=total_duration,
                final_error=str(last_error) if last_error else "不明なエラー",
                configuration=config
            )
            
        except Exception as e:
            # 予期しないエラー
            self.stats["failed_executions"] += 1
            total_duration = (datetime.now() - start_time).total_seconds()
            
            return RetryExecutionResult(
                result=RetryResult.FAILED_ALL_ATTEMPTS,
                attempts=attempts,
                total_duration=total_duration,
                final_error=f"予期しないエラー: {str(e)}",
                configuration=config
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """統計情報取得"""
        stats = self.stats.copy()
        if stats["total_executions"] > 0:
            stats["success_rate"] = stats["successful_executions"] / stats["total_executions"]
            stats["average_attempts"] = stats["total_attempts"] / stats["total_executions"]
        else:
            stats["success_rate"] = 0.0
            stats["average_attempts"] = 0.0
        
        return stats
    
    def reset_stats(self):
        """統計情報リセット"""
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_attempts": 0,
            "aborted_executions": 0
        }


# 便利な設定ファクトリ
class RetryConfigurationFactory:
    """再試行設定ファクトリ"""
    
    @staticmethod
    def create_default() -> RetryConfiguration:
        """デフォルト設定"""
        return RetryConfiguration(
            max_attempts=3,
            policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=60.0,
            backoff_multiplier=2.0
        )
    
    @staticmethod
    def create_aggressive() -> RetryConfiguration:
        """積極的な再試行設定"""
        return RetryConfiguration(
            max_attempts=5,
            policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            base_delay=0.5,
            max_delay=30.0,
            backoff_multiplier=1.5
        )
    
    @staticmethod
    def create_conservative() -> RetryConfiguration:
        """保守的な再試行設定"""
        return RetryConfiguration(
            max_attempts=2,
            policy=RetryPolicy.FIXED_DELAY,
            base_delay=5.0,
            max_delay=10.0
        )
    
    @staticmethod
    def create_quick() -> RetryConfiguration:
        """高速再試行設定（短時間処理用）"""
        return RetryConfiguration(
            max_attempts=3,
            policy=RetryPolicy.FIXED_DELAY,
            base_delay=0.1,
            max_delay=1.0
        )
    
    @staticmethod
    def create_network_operation() -> RetryConfiguration:
        """ネットワーク操作用設定"""
        return RetryConfiguration(
            max_attempts=5,
            policy=RetryPolicy.RANDOM_JITTER,
            base_delay=2.0,
            max_delay=120.0,
            backoff_multiplier=2.0,
            jitter_factor=0.3,
            timeout=300.0
        )
    
    @staticmethod
    def create_file_operation() -> RetryConfiguration:
        """ファイル操作用設定"""
        return RetryConfiguration(
            max_attempts=3,
            policy=RetryPolicy.LINEAR_BACKOFF,
            base_delay=1.0,
            max_delay=10.0,
            timeout=60.0
        )
    
    @staticmethod
    def create_recording_operation() -> RetryConfiguration:
        """録画操作用設定"""
        return RetryConfiguration(
            max_attempts=3,
            policy=RetryPolicy.EXPONENTIAL_BACKOFF,
            base_delay=5.0,
            max_delay=300.0,
            backoff_multiplier=2.0,
            timeout=3600.0  # 1時間
        )


# 便利な関数
async def retry_async(operation: Callable[[], T],
                     config: Optional[RetryConfiguration] = None,
                     error_checker: Optional[Callable[[Exception], bool]] = None) -> T:
    """
    シンプルな非同期再試行実行
    
    Args:
        operation: 実行する操作
        config: 再試行設定（Noneでデフォルト）
        error_checker: エラー判定関数
        
    Returns:
        T: 操作の結果
        
    Raises:
        Exception: すべての試行が失敗した場合
    """
    executor = RetryExecutor()
    config = config or RetryConfigurationFactory.create_default()
    
    result = await executor.execute_with_retry(operation, config, error_checker)
    
    if result.success:
        return result.value
    else:
        raise Exception(result.final_error)


def retry_sync(operation: Callable[[], T],
              config: Optional[RetryConfiguration] = None,
              error_checker: Optional[Callable[[Exception], bool]] = None) -> T:
    """
    シンプルな同期再試行実行
    
    Args:
        operation: 実行する操作
        config: 再試行設定（Noneでデフォルト）
        error_checker: エラー判定関数
        
    Returns:
        T: 操作の結果
        
    Raises:
        Exception: すべての試行が失敗した場合
    """
    executor = RetryExecutor()
    config = config or RetryConfigurationFactory.create_default()
    
    result = executor.execute_with_retry_sync(operation, config, error_checker)
    
    if result.success:
        return result.value
    else:
        raise Exception(result.final_error)


# 一般的なエラーチェッカー
class CommonErrorCheckers:
    """一般的なエラー判定関数"""
    
    @staticmethod
    def network_errors(error: Exception) -> bool:
        """ネットワーク関連エラーの判定"""
        network_error_types = (
            ConnectionError,
            TimeoutError,
            OSError
        )
        
        if isinstance(error, network_error_types):
            return True
        
        # 文字列ベースの判定
        error_str = str(error).lower()
        network_keywords = [
            "connection", "network", "timeout", "unreachable",
            "dns", "socket", "refused", "reset"
        ]
        
        return any(keyword in error_str for keyword in network_keywords)
    
    @staticmethod
    def file_operation_errors(error: Exception) -> bool:
        """ファイル操作エラーの判定"""
        file_error_types = (
            PermissionError,
            FileNotFoundError,
            IsADirectoryError,
            OSError
        )
        
        if isinstance(error, file_error_types):
            return True
        
        error_str = str(error).lower()
        file_keywords = [
            "permission denied", "file not found", "directory",
            "disk", "space", "access"
        ]
        
        return any(keyword in error_str for keyword in file_keywords)
    
    @staticmethod
    def temporary_errors(error: Exception) -> bool:
        """一時的なエラーの判定"""
        # 一時的である可能性の高いエラー
        return (
            CommonErrorCheckers.network_errors(error) or
            isinstance(error, (TimeoutError, ConnectionError))
        )
    
    @staticmethod
    def never_retry(error: Exception) -> bool:
        """再試行しないエラーの判定"""
        never_retry_types = (
            KeyboardInterrupt,
            SystemExit,
            MemoryError,
            ValueError,
            TypeError
        )
        
        return not isinstance(error, never_retry_types)


# エクスポート
__all__ = [
    'RetryPolicy',
    'RetryResult',
    'RetryAttempt',
    'RetryConfiguration',
    'RetryExecutionResult',
    'DelayCalculator',
    'RetryConditionChecker',
    'RetryExecutor',
    'RetryConfigurationFactory',
    'retry_async',
    'retry_sync',
    'CommonErrorCheckers'
]
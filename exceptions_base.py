# exceptions_base.py (修正版)
"""
ワンクリ録（OneClickRec）- 例外システム基底（改善版）
世界で一番かんたんな録画アプリ

例外システムの基底クラスとエラーコード定義
Phase 2: 設計改善・階層簡素化・メタデータ集約版
"""

import traceback
import asyncio
from typing import Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime


class ErrorCategory(Enum):
    """エラーカテゴリ"""
    GENERAL = "general"
    AUTHENTICATION = "authentication"
    STREAM = "stream"
    RECORDING = "recording"
    NETWORK = "network"
    OBS = "obs"
    API = "api"
    ASYNC = "async"


class ErrorSeverity(Enum):
    """エラー深刻度レベル"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OutputPathType(Enum):
    """出力パスエラー種別（堅牢性向上のためEnum化）"""
    FILE = "file"
    DIRECTORY = "directory"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


class ErrorCode(Enum):
    """
    エラーコード定義 - カテゴリ・深刻度属性付き（メタデータ集約版）
    """
    
    # 一般エラー (1000番台)
    UNKNOWN_ERROR = (1000, ErrorCategory.GENERAL, ErrorSeverity.HIGH)
    CONFIGURATION_ERROR = (1001, ErrorCategory.GENERAL, ErrorSeverity.CRITICAL)
    VALIDATION_ERROR = (1002, ErrorCategory.GENERAL, ErrorSeverity.MEDIUM)
    PERMISSION_ERROR = (1003, ErrorCategory.GENERAL, ErrorSeverity.CRITICAL)
    INITIALIZATION_ERROR = (1004, ErrorCategory.GENERAL, ErrorSeverity.CRITICAL)
    
    # 認証エラー (2000番台)
    AUTH_FAILED = (2000, ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH)
    AUTH_EXPIRED = (2001, ErrorCategory.AUTHENTICATION, ErrorSeverity.MEDIUM)
    COOKIE_INVALID = (2002, ErrorCategory.AUTHENTICATION, ErrorSeverity.MEDIUM)
    LOGIN_REQUIRED = (2003, ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH)
    SELENIUM_ERROR = (2004, ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH)
    AUTH_RATE_LIMITED = (2005, ErrorCategory.AUTHENTICATION, ErrorSeverity.MEDIUM)
    
    # ストリームエラー (3000番台)
    STREAM_NOT_FOUND = (3000, ErrorCategory.STREAM, ErrorSeverity.MEDIUM)
    STREAM_OFFLINE = (3001, ErrorCategory.STREAM, ErrorSeverity.LOW)
    STREAM_PRIVATE = (3002, ErrorCategory.STREAM, ErrorSeverity.MEDIUM)
    STREAM_PREMIUM = (3003, ErrorCategory.STREAM, ErrorSeverity.MEDIUM)
    STREAM_GEO_BLOCKED = (3004, ErrorCategory.STREAM, ErrorSeverity.MEDIUM)
    STREAM_URL_INVALID = (3005, ErrorCategory.STREAM, ErrorSeverity.MEDIUM)
    STREAM_QUALITY_UNAVAILABLE = (3006, ErrorCategory.STREAM, ErrorSeverity.LOW)
    
    # 録画エラー (4000番台)
    RECORDING_FAILED = (4000, ErrorCategory.RECORDING, ErrorSeverity.HIGH)
    RECORDING_ALREADY_RUNNING = (4001, ErrorCategory.RECORDING, ErrorSeverity.LOW)
    RECORDING_NOT_FOUND = (4002, ErrorCategory.RECORDING, ErrorSeverity.LOW)
    OUTPUT_PATH_ERROR = (4003, ErrorCategory.RECORDING, ErrorSeverity.CRITICAL)
    DISK_SPACE_ERROR = (4004, ErrorCategory.RECORDING, ErrorSeverity.CRITICAL)
    STREAMLINK_ERROR = (4005, ErrorCategory.RECORDING, ErrorSeverity.HIGH)
    FFMPEG_ERROR = (4006, ErrorCategory.RECORDING, ErrorSeverity.HIGH)
    RECORDING_TIMEOUT = (4007, ErrorCategory.RECORDING, ErrorSeverity.MEDIUM)
    
    # OBSエラー (5000番台)
    OBS_CONNECTION_FAILED = (5000, ErrorCategory.OBS, ErrorSeverity.HIGH)
    OBS_NOT_RUNNING = (5001, ErrorCategory.OBS, ErrorSeverity.HIGH)
    OBS_WEBSOCKET_ERROR = (5002, ErrorCategory.OBS, ErrorSeverity.MEDIUM)
    OBS_SCENE_ERROR = (5003, ErrorCategory.OBS, ErrorSeverity.MEDIUM)
    OBS_RECORDING_ERROR = (5004, ErrorCategory.OBS, ErrorSeverity.HIGH)
    OBS_SOURCE_ERROR = (5005, ErrorCategory.OBS, ErrorSeverity.MEDIUM)
    
    # ネットワークエラー (6000番台)
    NETWORK_ERROR = (6000, ErrorCategory.NETWORK, ErrorSeverity.MEDIUM)
    TIMEOUT_ERROR = (6001, ErrorCategory.NETWORK, ErrorSeverity.MEDIUM)
    CONNECTION_ERROR = (6002, ErrorCategory.NETWORK, ErrorSeverity.MEDIUM)
    DNS_ERROR = (6003, ErrorCategory.NETWORK, ErrorSeverity.MEDIUM)
    SSL_ERROR = (6004, ErrorCategory.NETWORK, ErrorSeverity.HIGH)
    PROXY_ERROR = (6005, ErrorCategory.NETWORK, ErrorSeverity.MEDIUM)
    
    # APIエラー (7000番台)
    API_ERROR = (7000, ErrorCategory.API, ErrorSeverity.HIGH)
    WEBSOCKET_ERROR = (7001, ErrorCategory.API, ErrorSeverity.MEDIUM)
    INVALID_REQUEST = (7002, ErrorCategory.API, ErrorSeverity.LOW)
    RATE_LIMIT_EXCEEDED = (7003, ErrorCategory.API, ErrorSeverity.MEDIUM)
    API_AUTHENTICATION_ERROR = (7004, ErrorCategory.API, ErrorSeverity.HIGH)
    API_QUOTA_EXCEEDED = (7005, ErrorCategory.API, ErrorSeverity.MEDIUM)
    
    # 非同期処理エラー (8000番台)
    ASYNC_OPERATION_CANCELLED = (8000, ErrorCategory.ASYNC, ErrorSeverity.LOW)
    ASYNC_OPERATION_TIMEOUT = (8001, ErrorCategory.ASYNC, ErrorSeverity.MEDIUM)
    ASYNC_TASK_FAILED = (8002, ErrorCategory.ASYNC, ErrorSeverity.HIGH)
    CONCURRENT_LIMIT_EXCEEDED = (8003, ErrorCategory.ASYNC, ErrorSeverity.MEDIUM)
    
    def __init__(self, code: int, category: ErrorCategory, severity: ErrorSeverity):
        self.code = code
        self.category = category
        self.severity = severity
    
    @property
    def value(self) -> int:
        """エラーコード番号取得"""
        return self.code


class OneClickRecException(Exception):
    """
    ワンクリ録 基底例外クラス（改善版）
    全てのアプリケーション例外の基底となるクラス。
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_exception = original_exception
        self.context = context or {}
        self.timestamp = datetime.now()
        
        if original_exception:
            self.__cause__ = original_exception
    
    def set_detail_if_present(self, key: str, value: Any, transform_func=None):
        """詳細情報の安全な設定"""
        if value is not None:
            final_value = transform_func(value) if transform_func else value
            self.details[key] = final_value
    
    def get_category(self) -> ErrorCategory:
        """エラーカテゴリの取得"""
        return self.error_code.category
    
    def get_severity(self) -> ErrorSeverity:
        """エラー深刻度の取得"""
        return self.error_code.severity
    
    def is_recoverable(self) -> bool:
        """回復可能かどうかの判定"""
        return is_recoverable_error(self)
    
    def get_formatted_traceback(self) -> Optional[str]:
        """フォーマット済みトレースバック取得"""
        if self.original_exception and hasattr(self.original_exception, '__traceback__'):
            return ''.join(traceback.format_exception(
                type(self.original_exception),
                self.original_exception,
                self.original_exception.__traceback__
            ))
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（ログ・API出力用）"""
        return {
            "error_code": self.error_code.value,
            "error_name": self.error_code.name,
            "category": self.get_category().value,
            "message": self.message,
            "severity": self.get_severity().value,
            "details": self.details,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "is_recoverable": self.is_recoverable(),
            "original_exception": str(self.original_exception) if self.original_exception else None,
            "traceback": self.get_formatted_traceback()
        }
    
    def to_log_message(self) -> str:
        """ログ用メッセージ形式"""
        return f"[{self.error_code.name}] {self.message}"
    
    def __str__(self) -> str:
        return f"[{self.error_code.name}] {self.message}"
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message='{self.message}', "
            f"error_code={self.error_code.name}, "
            f"category={self.get_category().value}, "
            f"severity={self.get_severity().value})"
        )


class ConfigurationError(OneClickRecException):
    """設定関連エラー"""
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.CONFIGURATION_ERROR, **kwargs)
        self.set_detail_if_present("config_key", config_key)


class ValidationError(OneClickRecException):
    """バリデーションエラー"""
    def __init__(self, message: str, field_name: Optional[str] = None, field_value: Any = None, **kwargs):
        super().__init__(message, ErrorCode.VALIDATION_ERROR, **kwargs)
        self.set_detail_if_present("field_name", field_name)
        self.set_detail_if_present("field_value", field_value, str)


class PermissionError(OneClickRecException):
    """権限エラー"""
    def __init__(self, message: str, resource: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.PERMISSION_ERROR, **kwargs)
        self.set_detail_if_present("resource", resource)


class InitializationError(OneClickRecException):
    """初期化エラー"""
    def __init__(self, message: str, component: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.INITIALIZATION_ERROR, **kwargs)
        self.set_detail_if_present("component", component)


# === 非同期処理エラー ===

class AsyncOperationCancelled(OneClickRecException):
    """非同期操作キャンセルエラー"""
    def __init__(self, message: str = "非同期操作がキャンセルされました", **kwargs):
        super().__init__(message, ErrorCode.ASYNC_OPERATION_CANCELLED, **kwargs)


class AsyncOperationTimeout(OneClickRecException):
    """非同期操作タイムアウトエラー"""
    def __init__(self, message: str = "非同期操作がタイムアウトしました", timeout_seconds: Optional[float] = None, **kwargs):
        super().__init__(message, ErrorCode.ASYNC_OPERATION_TIMEOUT, **kwargs)
        self.set_detail_if_present("timeout_seconds", timeout_seconds)


class AsyncTaskFailed(OneClickRecException):
    """非同期タスク失敗エラー"""
    def __init__(self, message: str, task_name: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.ASYNC_TASK_FAILED, **kwargs)
        self.set_detail_if_present("task_name", task_name)


class ConcurrentLimitExceeded(OneClickRecException):
    """並行処理制限超過エラー"""
    def __init__(self, message: str = "並行処理の制限を超過しました", limit: Optional[int] = None, current: Optional[int] = None, **kwargs):
        super().__init__(message, ErrorCode.CONCURRENT_LIMIT_EXCEEDED, **kwargs)
        self.set_detail_if_present("limit", limit)
        self.set_detail_if_present("current", current)


# === ヘルパー関数群 ===

def is_recoverable_error(exception: OneClickRecException) -> bool:
    """回復可能なエラーかどうかを判定（プログラムによる自動リトライが有効かどうかの観点）"""
    recoverable_errors = {
        ErrorCode.TIMEOUT_ERROR,
        ErrorCode.CONNECTION_ERROR,
        ErrorCode.STREAMLINK_ERROR,
        ErrorCode.OBS_CONNECTION_FAILED,
        ErrorCode.ASYNC_OPERATION_TIMEOUT,
        ErrorCode.NETWORK_ERROR,
        ErrorCode.DNS_ERROR,
    }
    return exception.error_code in recoverable_errors


def get_errors_by_category(category: ErrorCategory) -> list[ErrorCode]:
    """カテゴリ別エラーコード一覧取得"""
    return [code for code in ErrorCode if code.category == category]


def create_error_response(exception: OneClickRecException) -> Dict[str, Any]:
    """例外からAPIエラーレスポンスを作成"""
    return {
        "success": False,
        "error": exception.to_dict(),
        "timestamp": datetime.now().isoformat()
    }


# === FastAPI統合用ヘルパー ===

def to_http_status_code(error_code: ErrorCode) -> int:
    """エラーコードからHTTPステータスコードを取得"""
    client_error_codes = {
        ErrorCode.VALIDATION_ERROR: 400,
        ErrorCode.AUTH_FAILED: 401,
        ErrorCode.PERMISSION_ERROR: 403,
        ErrorCode.STREAM_NOT_FOUND: 404,
        ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    }
    
    server_error_codes = {
        ErrorCode.CONFIGURATION_ERROR: 500,
        ErrorCode.RECORDING_FAILED: 500,
        ErrorCode.OBS_CONNECTION_FAILED: 503,
        ErrorCode.DISK_SPACE_ERROR: 507,
    }
    
    return client_error_codes.get(
        error_code, 
        server_error_codes.get(error_code, 500)
    )


def to_http_exception(exception: OneClickRecException):
    """FastAPI HTTPException への変換"""
    try:
        from fastapi import HTTPException
        return HTTPException(
            status_code=to_http_status_code(exception.error_code),
            detail=exception.to_dict()
        )
    except ImportError:
        raise exception from exception.original_exception


if __name__ == "__main__":
    # テスト実行
    try:
        raise ConfigurationError(
            "テスト設定エラー", 
            config_key="test_key",
            context={"module": "test"}
        )
    except OneClickRecException as e:
        print("=== 改善版例外システムテスト ===")
        print(f"例外: {e}")
        print(f"カテゴリ: {e.get_category().value}")
        print(f"深刻度: {e.get_severity().value}")
        print(f"回復可能: {e.is_recoverable()}")
        print(f"辞書形式: {e.to_dict()}")
        print(f"HTTPステータス: {to_http_status_code(e.error_code)}")
    
    auth_errors = get_errors_by_category(ErrorCategory.AUTHENTICATION)
    print(f"\n認証関連エラー: {[e.name for e in auth_errors]}")
    
    print("\n✅ 改善版例外システムテスト完了")
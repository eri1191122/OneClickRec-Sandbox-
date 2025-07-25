"""
ワンクリ録（OneClickRec）- 例外システム統合エクスポート（改善版）
世界で一番かんたんな録画アプリ

全例外クラスの統合エクスポート
Phase 2: 診断ロジックを集約し、保守性を向上
"""

# === 基底クラス・エラーコード・共通ヘルパー ===
from exceptions_base import (
    OneClickRecException,
    ErrorCode,
    ErrorSeverity,
    ErrorCategory,
    ConfigurationError,
    ValidationError,
    PermissionError,
    InitializationError,
    AsyncOperationCancelled,
    AsyncOperationTimeout,
    AsyncTaskFailed,
    ConcurrentLimitExceeded,
    get_errors_by_category,
    create_error_response,
    to_http_status_code,
    to_http_exception,
)

# === 認証関連例外 ===
from exceptions_auth import (
    AuthenticationError,
    AuthenticationExpiredError,
    CookieInvalidError,
    LoginRequiredError,
    SeleniumError,
    AuthRateLimitedError,
    get_auth_recovery_suggestion, # 診断用にインポート
)

# === 配信関連例外 ===
from exceptions_stream import (
    StreamError,
    StreamNotFoundError,
    StreamOfflineError,
    StreamAccessError,
    StreamPrivateError,
    StreamPremiumError,
    StreamGeoBlockedError,
    StreamURLInvalidError,
    StreamQualityUnavailableError,
    get_stream_recovery_suggestion, # 診断用にインポート
)

# === 録画関連例外 ===
from exceptions_recording import (
    RecordingFailedError,
    RecordingAlreadyRunningError,
    RecordingNotFoundError,
    OutputPathError,
    DiskSpaceError,
    StreamlinkError,
    FFmpegError,
    RecordingTimeoutError,
    get_recording_recovery_suggestion, # 診断用にインポート
)

# === ネットワーク関連例外 ===
from exceptions_network import (
    TimeoutError,
    ConnectionError,
    DNSError,
    SSLError,
    ProxyError,
    get_network_recovery_suggestion, # 診断用にインポート
)

# === 後方互換性確保のためのデコレーター ===

def handle_exception(func):
    """例外ハンドリングデコレーター"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OneClickRecException:
            raise
        except Exception as e:
            raise OneClickRecException(
                message=f"予期しないエラーが発生しました: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                original_exception=e
            ) from e
    return wrapper


async def handle_async_exception(func):
    """非同期例外ハンドリングデコレーター"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except OneClickRecException:
            raise
        except Exception as e:
            raise OneClickRecException(
                message=f"予期しないエラーが発生しました: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                original_exception=e
            ) from e
    return wrapper


# === 統合診断・分析機能（改善版） ===

def diagnose_exception(exception: OneClickRecException) -> dict:
    """
    例外の統合診断（カテゴリベースの診断ロジック集約版）
    """
    category = exception.get_category()

    # カテゴリに対応する回復提案関数をマッピング
    suggester_map = {
        ErrorCategory.AUTHENTICATION: get_auth_recovery_suggestion,
        ErrorCategory.STREAM: get_stream_recovery_suggestion,
        ErrorCategory.RECORDING: get_recording_recovery_suggestion,
        ErrorCategory.NETWORK: get_network_recovery_suggestion,
    }

    # 回復提案を取得
    suggester = suggester_map.get(category)
    recovery_suggestion = suggester(exception) if suggester else "システム設定や動作環境を確認してください"

    diagnosis = {
        "exception_type": type(exception).__name__,
        "error_code": exception.error_code.name,
        "error_category": category.value,
        "severity": exception.get_severity().value,
        "is_recoverable": exception.is_recoverable(),
        "recovery_suggestion": recovery_suggestion,
        "details": exception.details,
    }

    # プラットフォーム固有の情報を追加 (StreamErrorの場合)
    if isinstance(exception, StreamError):
        diagnosis["platform_info"] = {
            "platform": exception.platform,
            "username": exception.username
        }

    return diagnosis


# === エクスポート用 __all__ 定義（改善版） ===

__all__ = [
    # 基底・共通
    "OneClickRecException", "ErrorCode", "ErrorSeverity", "ErrorCategory",
    "ConfigurationError", "ValidationError", "PermissionError", "InitializationError",
    
    # 非同期処理
    "AsyncOperationCancelled", "AsyncOperationTimeout", "AsyncTaskFailed", "ConcurrentLimitExceeded",
    
    # 認証関連
    "AuthenticationError", "AuthenticationExpiredError", "CookieInvalidError", "LoginRequiredError",
    "SeleniumError", "AuthRateLimitedError",
    
    # 配信関連
    "StreamError", "StreamNotFoundError", "StreamOfflineError", "StreamAccessError",
    "StreamPrivateError", "StreamPremiumError", "StreamGeoBlockedError",
    "StreamURLInvalidError", "StreamQualityUnavailableError",
    
    # 録画関連
    "RecordingFailedError", "RecordingAlreadyRunningError", "RecordingNotFoundError",
    "OutputPathError", "DiskSpaceError", "StreamlinkError", "FFmpegError", "RecordingTimeoutError",
    
    # ネットワーク関連
    "TimeoutError", "ConnectionError", "DNSError", "SSLError", "ProxyError",
    
    # ヘルパー関数
    "get_errors_by_category", "create_error_response", "to_http_status_code",
    "to_http_exception", "handle_exception", "handle_async_exception",
    "diagnose_exception",
]


if __name__ == "__main__":
    print("=== ワンクリ録例外システム Phase 2 改善版 ===")
    
    # 各カテゴリのテスト例外作成
    test_exceptions = [
        AuthenticationError("認証テストエラー", auth_method="cookie"),
        StreamNotFoundError("配信未検出テスト", stream_url="https://twitcasting.tv/test_stream"),
        RecordingFailedError("録画失敗テスト", session_id="test_001"),
        TimeoutError("タイムアウトテスト"),
        ConfigurationError("設定キーがありません", config_key="api.key"),
    ]
    
    print("\n=== カテゴリベース統合診断テスト ===")
    for exception in test_exceptions:
        diagnosis = diagnose_exception(exception)
        print(f"\n--- 例外: {exception} ---")
        print(f"  タイプ: {diagnosis['exception_type']}")
        print(f"  カテゴリ: {diagnosis['error_category']}")
        print(f"  深刻度: {diagnosis['severity']}")
        print(f"  回復可能か: {diagnosis['is_recoverable']}")
        print(f"  回復提案: {diagnosis['recovery_suggestion']}")
        if 'platform_info' in diagnosis:
            print(f"  プラットフォーム情報: {diagnosis['platform_info']}")
        
    print("\n\n✅ Phase 2 例外システム改善版テスト完了")
"""
強化されたエラーハンドリングシステム
Phase 1以降でも拡張可能な例外階層
"""

from enum import Enum, auto
from typing import Optional, Dict, Any


class ErrorCode(Enum):
    """エラーコードの体系的分類"""
    
    # 一般的なエラー
    UNKNOWN_ERROR = auto()
    CONFIGURATION_ERROR = auto()
    SYSTEM_ERROR = auto()
    
    # URL関連エラー
    URL_INVALID = auto()
    URL_UNSUPPORTED_PLATFORM = auto()
    URL_USER_NOT_FOUND = auto()
    
    # 認証関連エラー
    AUTH_FAILED = auto()
    AUTH_REQUIRED = auto()
    AUTH_EXPIRED = auto()
    AUTH_PASSWORD_REQUIRED = auto()
    AUTH_AGE_VERIFICATION_REQUIRED = auto()
    
    # 録画関連エラー
    RECORDING_START_FAILED = auto()
    RECORDING_FFMPEG_ERROR = auto()
    RECORDING_NO_STREAM = auto()
    RECORDING_NETWORK_ERROR = auto()
    RECORDING_DISK_FULL = auto()
    RECORDING_PERMISSION_DENIED = auto()
    
    # ファイル関連エラー
    FILE_NOT_FOUND = auto()
    FILE_TOO_SMALL = auto()
    FILE_CORRUPTED = auto()
    FILE_WRITE_ERROR = auto()


class OneClickRecException(Exception):
    """
    OneClickRecの基底例外クラス
    すべてのアプリケーション例外はこれを継承する
    """
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_exception = original_exception
    
    def to_dict(self) -> Dict[str, Any]:
        """例外情報を辞書形式で出力"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code.name,
            "details": self.details,
            "original_exception": str(self.original_exception) if self.original_exception else None
        }


class URLException(OneClickRecException):
    """URL関連の例外"""
    
    def __init__(self, message: str, url: str = "", error_code: ErrorCode = ErrorCode.URL_INVALID):
        super().__init__(message, error_code, {"url": url})
        self.url = url


class AuthenticationException(OneClickRecException):
    """認証関連の例外"""
    
    def __init__(
        self, 
        message: str, 
        auth_type: str = "", 
        error_code: ErrorCode = ErrorCode.AUTH_FAILED
    ):
        super().__init__(message, error_code, {"auth_type": auth_type})
        self.auth_type = auth_type


class RecordingException(OneClickRecException):
    """録画関連の例外"""
    
    def __init__(
        self, 
        message: str, 
        url: str = "",
        ffmpeg_exit_code: Optional[int] = None,
        error_code: ErrorCode = ErrorCode.RECORDING_START_FAILED
    ):
        details = {"url": url}
        if ffmpeg_exit_code is not None:
            details["ffmpeg_exit_code"] = ffmpeg_exit_code
            
        super().__init__(message, error_code, details)
        self.url = url
        self.ffmpeg_exit_code = ffmpeg_exit_code


class FileException(OneClickRecException):
    """ファイル操作関連の例外"""
    
    def __init__(
        self, 
        message: str, 
        file_path: str = "",
        file_size: Optional[int] = None,
        error_code: ErrorCode = ErrorCode.FILE_NOT_FOUND
    ):
        details = {"file_path": file_path}
        if file_size is not None:
            details["file_size"] = file_size
            
        super().__init__(message, error_code, details)
        self.file_path = file_path
        self.file_size = file_size


class ConfigurationException(OneClickRecException):
    """設定関連の例外"""
    
    def __init__(
        self, 
        message: str, 
        config_key: str = "",
        error_code: ErrorCode = ErrorCode.CONFIGURATION_ERROR
    ):
        super().__init__(message, error_code, {"config_key": config_key})
        self.config_key = config_key


# 便利な例外生成関数
def create_url_error(message: str, url: str) -> URLException:
    """URL例外を生成"""
    return URLException(message, url, ErrorCode.URL_INVALID)


def create_auth_error(message: str, auth_type: str = "unknown") -> AuthenticationException:
    """認証例外を生成"""
    return AuthenticationException(message, auth_type, ErrorCode.AUTH_FAILED)


def create_recording_error(
    message: str, 
    url: str = "", 
    ffmpeg_exit_code: Optional[int] = None
) -> RecordingException:
    """録画例外を生成"""
    return RecordingException(message, url, ffmpeg_exit_code, ErrorCode.RECORDING_START_FAILED)


def create_file_error(
    message: str, 
    file_path: str = "", 
    file_size: Optional[int] = None
) -> FileException:
    """ファイル例外を生成"""
    return FileException(message, file_path, file_size, ErrorCode.FILE_NOT_FOUND)
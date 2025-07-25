"""
ワンクリ録（OneClickRec）- 録画関連例外（改善版）
世界で一番かんたんな録画アプリ

録画処理・Streamlink・FFmpeg関連の例外群
Phase 2: 階層簡素化版
"""

from typing import Optional, List, Dict, Any
from exceptions_base import OneClickRecException, ErrorCode, OutputPathType


class RecordingFailedError(OneClickRecException):
    """録画失敗エラー"""
    def __init__(self, message: str = "録画に失敗しました", session_id: Optional[str] = None, failure_reason: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.RECORDING_FAILED, **kwargs)
        self.set_detail_if_present("session_id", session_id)
        self.set_detail_if_present("failure_reason", failure_reason)


class RecordingAlreadyRunningError(OneClickRecException):
    """録画重複実行エラー"""
    def __init__(self, message: str = "録画は既に実行中です", session_id: Optional[str] = None, existing_session_id: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.RECORDING_ALREADY_RUNNING, **kwargs)
        self.set_detail_if_present("session_id", session_id)
        self.set_detail_if_present("existing_session_id", existing_session_id)


class RecordingNotFoundError(OneClickRecException):
    """録画セッション未検出エラー"""
    def __init__(self, message: str = "録画セッションが見つかりません", session_id: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.RECORDING_NOT_FOUND, **kwargs)
        self.set_detail_if_present("session_id", session_id)


class OutputPathError(OneClickRecException):
    """出力パスエラー"""
    def __init__(self, message: str, output_path: Optional[str] = None, path_type: OutputPathType = OutputPathType.UNKNOWN, **kwargs):
        super().__init__(message, error_code=ErrorCode.OUTPUT_PATH_ERROR, **kwargs)
        self.set_detail_if_present("output_path", output_path)
        self.set_detail_if_present("path_type", path_type.value)


class DiskSpaceError(OneClickRecException):
    """ディスク容量不足エラー"""
    def __init__(self, message: str = "ディスク容量が不足しています", available_space_mb: Optional[int] = None, required_space_mb: Optional[int] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.DISK_SPACE_ERROR, **kwargs)
        self.set_detail_if_present("available_space_mb", available_space_mb)
        self.set_detail_if_present("required_space_mb", required_space_mb)


class StreamlinkError(OneClickRecException):
    """Streamlinkエラー"""
    def __init__(self, message: str, command: Optional[List[str]] = None, return_code: Optional[int] = None, stderr_output: Optional[str] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.STREAMLINK_ERROR, **kwargs)
        if command:
            safe_command = [cmd for cmd in command if not any(s in cmd.lower() for s in ['cookie', 'password', 'token'])]
            self.set_detail_if_present("command_partial", safe_command[:10])
        self.set_detail_if_present("return_code", return_code)
        self.set_detail_if_present("stderr_output", stderr_output[:500] if stderr_output else None)


class FFmpegError(OneClickRecException):
    """FFmpegエラー"""
    def __init__(self, message: str, command: Optional[List[str]] = None, return_code: Optional[int] = None, stderr_output: Optional[str] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.FFMPEG_ERROR, **kwargs)
        self.set_detail_if_present("command", command[:10] if command else None)
        self.set_detail_if_present("return_code", return_code)
        self.set_detail_if_present("stderr_output", stderr_output[:500] if stderr_output else None)


class RecordingTimeoutError(OneClickRecException):
    """録画タイムアウトエラー"""
    def __init__(self, message: str = "録画がタイムアウトしました", session_id: Optional[str] = None, timeout_seconds: Optional[int] = None, **kwargs):
        super().__init__(message, ErrorCode.RECORDING_TIMEOUT, **kwargs)
        self.set_detail_if_present("session_id", session_id)
        self.set_detail_if_present("timeout_seconds", timeout_seconds)


# === 録画エラー専用ヘルパー関数 ===

def is_storage_related_error(exception: OneClickRecException) -> bool:
    """ストレージ関連エラーかどうかの判定"""
    return exception.error_code in {ErrorCode.DISK_SPACE_ERROR, ErrorCode.OUTPUT_PATH_ERROR}


def get_recording_recovery_suggestion(exception: OneClickRecException) -> str:
    """録画エラーの回復提案メッセージ"""
    if exception.error_code == ErrorCode.OUTPUT_PATH_ERROR:
        path_type = exception.details.get("path_type")
        if path_type == OutputPathType.PERMISSION.value:
            return "出力ディレクトリの書き込み権限を確認してください"
        elif path_type == OutputPathType.DIRECTORY.value:
            return "出力ディレクトリが存在することを確認してください"
        return "出力パスの設定を確認してください"
    elif exception.error_code == ErrorCode.DISK_SPACE_ERROR:
        return "ディスク容量を確保してください"
    elif exception.error_code == ErrorCode.STREAMLINK_ERROR:
        return "Streamlinkのログを確認し、配信URLや認証設定を見直してください"
    elif exception.error_code == ErrorCode.FFMPEG_ERROR:
        return "FFmpegの設定や入力形式を確認してください"
    else:
        return "録画設定やシステム状況を確認してください"


if __name__ == "__main__":
    test_errors = [
        RecordingFailedError("録画プロセス異常終了", session_id="rec_001"),
        DiskSpaceError("容量不足", available_space_mb=500, required_space_mb=2000),
        StreamlinkError("実行エラー", return_code=1, stderr_output="No streams found"),
        OutputPathError("アクセス拒否", output_path="/protected", path_type=OutputPathType.PERMISSION)
    ]
    
    print("=== 改善版録画例外テスト ===")
    for error in test_errors:
        print(f"\nエラー: {error}")
        print(f"ストレージ関連: {is_storage_related_error(error)}")
        print(f"回復提案: {get_recording_recovery_suggestion(error)}")
        print("---")
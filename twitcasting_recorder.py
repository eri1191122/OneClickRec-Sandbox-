"""
TwitCasting録画モジュール（9箇所修正版）
GPT指摘5箇所 + Claude追加4箇所の修正を統合実装
"""
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

from recording_result import RecordingResult, RecordingStatus


class StreamlinkErrorType(Enum):
    """Streamlinkエラーの分類"""
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    STREAM_NOT_FOUND = "stream_not_found"
    PLUGIN_ERROR = "plugin_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class RecordingRequest:
    """録画リクエストを統合するクラス（Claude修正6: 責任分離）"""
    url: str
    output_path: Path
    quality: str = "best"
    retry_attempts: int = 3
    force_overwrite: bool = False  # GPT修正1: --forceフラグの明示化


class StreamlinkRunner:
    """Streamlink実行の抽象化クラス（Claude修正7: テスタビリティ確保）"""
    
    def run_command(self, command: list) -> subprocess.CompletedProcess:
        """Streamlinkコマンドを実行"""
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300
        )


class ResourceManager:
    """リソース管理クラス（Claude修正9: リソース管理強化）"""
    
    def __init__(self, max_concurrent_recordings: int = 3):
        self.max_concurrent = max_concurrent_recordings
        self.active_recordings = 0
        self.lock = threading.Lock()
    
    def acquire_slot(self) -> bool:
        """録画スロットを取得"""
        with self.lock:
            if self.active_recordings < self.max_concurrent:
                self.active_recordings += 1
                return True
            return False
    
    def release_slot(self):
        """録画スロットを解放"""
        with self.lock:
            if self.active_recordings > 0:
                self.active_recordings -= 1


class TwitcastingRecorder:
    """TwitCasting録画クラス（9箇所修正版）"""
    
    def __init__(self, 
                 streamlink_runner: Optional[StreamlinkRunner] = None,
                 resource_manager: Optional[ResourceManager] = None,
                 debug_mode: bool = False):
        """
        初期化
        
        Args:
            streamlink_runner: Streamlink実行クラス（DI対応）
            resource_manager: リソース管理クラス
            debug_mode: デバッグモード
        """
        self.streamlink_runner = streamlink_runner or StreamlinkRunner()
        self.resource_manager = resource_manager or ResourceManager()
        self.debug_mode = debug_mode
        self.session_data = {}
        self.progress_thread = None
        self.recording_process = None
    
    def start_recording(self, request: RecordingRequest) -> RecordingResult:
        """
        録画開始（Claude修正8: メモリリーク対策のtry-finally追加）
        
        Args:
            request: 録画リクエスト
            
        Returns:
            RecordingResult: 録画結果
        """
        # リソース取得
        if not self.resource_manager.acquire_slot():
            return RecordingResult(
                status=RecordingStatus.FAILED,
                message="最大同時録画数に達しています",
                metadata={"error_type": "resource_limit"}
            )
        
        try:
            # セッション初期化
            self._initialize_session(request)
            
            # Streamlinkコマンド構築
            command = self._build_streamlink_command(request)
            
            # 進行状況監視開始
            start_time = datetime.now()
            self._start_progress_monitoring(start_time)
            
            # 録画実行
            result = self.streamlink_runner.run_command(command)
            
            # 結果分析
            return self._analyze_recording_result(result, request, command, start_time)
            
        except Exception as e:
            return RecordingResult(
                status=RecordingStatus.FAILED,
                message=f"予期しないエラー: {str(e)}",
                metadata={"exception": str(e), "error_type": "unexpected"}
            )
        finally:
            # Claude修正8: 確実にクリーンアップ実行
            self._cleanup_session()
            self.resource_manager.release_slot()
    
    def _initialize_session(self, request: RecordingRequest):
        """セッション初期化"""
        self.session_data = {
            "request": request,
            "start_time": datetime.now(),
            "progress": 0
        }
    
    def _build_streamlink_command(self, request: RecordingRequest) -> list:
        """
        Streamlinkコマンド構築（GPT修正1: --forceロジック明確化）
        
        Args:
            request: 録画リクエスト
            
        Returns:
            list: Streamlinkコマンド
        """
        command = [
            "streamlink",
            request.url,
            request.quality,
            "--output", str(request.output_path)
        ]
        
        # GPT修正1: force_overwriteフラグによる明確な制御
        if request.force_overwrite:
            command.append("--force")
        elif request.output_path.exists() and request.retry_attempts == 0:
            # 新規録画でファイル存在時は自動的に強制上書き
            command.append("--force")
        
        # 再試行設定
        if request.retry_attempts > 0:
            command.extend([
                "--retry-streams", str(request.retry_attempts),
                "--retry-max", str(request.retry_attempts)
            ])
        
        return command
    
    def _start_progress_monitoring(self, start_time: datetime):
        """
        進行状況監視開始（GPT修正1: elapsed_seconds計算修正）
        
        Args:
            start_time: 録画開始時刻
        """
        def monitor():
            while self.recording_process and self.recording_process.poll() is None:
                # GPT修正1: 正しい経過時間計算
                elapsed = (datetime.now() - start_time).total_seconds()
                
                self.session_data["progress"] = elapsed
                time.sleep(1)
        
        self.progress_thread = threading.Thread(target=monitor, daemon=True)
        self.progress_thread.start()
    
    def _analyze_recording_result(self, 
                                result: subprocess.CompletedProcess,
                                request: RecordingRequest,
                                command: list,
                                start_time: datetime) -> RecordingResult:
        """
        録画結果分析（GPT修正2,4,5対応）
        
        Args:
            result: subprocess実行結果
            request: 録画リクエスト
            command: 実行したコマンド
            start_time: 開始時刻
            
        Returns:
            RecordingResult: 分析済み録画結果
        """
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # GPT修正4: セキュリティ配慮のログ改善
        metadata = {
            "duration_seconds": duration,
            "return_code": result.returncode,
            "command_used": "streamlink",  # 基本情報
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        # デバッグモード時は詳細コマンドも記録
        if self.debug_mode:
            metadata["command_debug"] = " ".join(command)
            metadata["stdout_debug"] = result.stdout
            metadata["stderr_debug"] = result.stderr
        
        if result.returncode == 0:
            return RecordingResult(
                status=RecordingStatus.COMPLETED,
                message="録画が正常に完了しました",
                output_file=request.output_path,
                metadata=metadata
            )
        else:
            # GPT修正3: 詳細なエラーステータス分類
            status, error_type, error_message = self._analyze_streamlink_error(result.stderr)
            
            metadata.update({
                "error_type": error_type.value,
                "is_retryable": self._is_retryable_error(error_type),
                "stdout": result.stdout,
                "stderr": result.stderr
            })
            
            return RecordingResult(
                status=status,
                message=error_message,
                metadata=metadata
            )
    
    def _analyze_streamlink_error(self, stderr: str) -> Tuple[RecordingStatus, StreamlinkErrorType, str]:
        """
        Streamlinkエラー分析（GPT修正3: RecordingStatus細分化対応）
        
        Args:
            stderr: 標準エラー出力
            
        Returns:
            Tuple[RecordingStatus, StreamlinkErrorType, str]: ステータス、エラータイプ、メッセージ
        """
        stderr_lower = stderr.lower()
        
        # ネットワーク関連エラー
        if any(keyword in stderr_lower for keyword in [
            "connection error", "network", "timeout", "connection timed out"
        ]):
            return (
                RecordingStatus.FAILED_NETWORK,  # GPT修正3: 詳細ステータス
                StreamlinkErrorType.NETWORK_ERROR,
                "ネットワークエラーが発生しました"
            )
        
        # 認証関連エラー
        if any(keyword in stderr_lower for keyword in [
            "authentication", "login", "unauthorized", "403", "401"
        ]):
            return (
                RecordingStatus.FAILED_AUTH,  # GPT修正3: 詳細ステータス
                StreamlinkErrorType.AUTH_ERROR,
                "認証エラーが発生しました"
            )
        
        # ストリーム見つからない
        if any(keyword in stderr_lower for keyword in [
            "no streams found", "stream not found", "404"
        ]):
            return (
                RecordingStatus.FAILED_STREAM_NOT_FOUND,  # GPT修正3: 詳細ステータス
                StreamlinkErrorType.STREAM_NOT_FOUND,
                "ストリームが見つかりません"
            )
        
        # プラグインエラー
        if any(keyword in stderr_lower for keyword in [
            "plugin", "unable to open url"
        ]):
            return (
                RecordingStatus.FAILED_PLUGIN,  # GPT修正3: 詳細ステータス
                StreamlinkErrorType.PLUGIN_ERROR,
                "Streamlinkプラグインエラーが発生しました"
            )
        
        # その他のエラー
        return (
            RecordingStatus.FAILED,  # 従来通りの汎用エラー
            StreamlinkErrorType.UNKNOWN_ERROR,
            f"不明なエラーが発生しました: {stderr[:200]}"
        )
    
    def _is_retryable_error(self, error_type: StreamlinkErrorType) -> bool:
        """
        再試行可能エラーの判定（GPT修正5: リカバリ戦略）
        
        Args:
            error_type: エラータイプ
            
        Returns:
            bool: 再試行可能かどうか
        """
        retryable_errors = {
            StreamlinkErrorType.NETWORK_ERROR,
            StreamlinkErrorType.UNKNOWN_ERROR
        }
        return error_type in retryable_errors
    
    def _cleanup_session(self):
        """
        セッションクリーンアップ（Claude修正8: メモリリーク対策）
        """
        try:
            # 進行状況監視スレッド終了
            if self.progress_thread and self.progress_thread.is_alive():
                # プロセス終了を待つ
                if self.recording_process:
                    self.recording_process = None
                self.progress_thread.join(timeout=5)
            
            # セッションデータクリア
            self.session_data.clear()
            
        except Exception as e:
            # クリーンアップ中のエラーはログのみ
            print(f"クリーンアップ中にエラー: {e}")


# 使用例とテスト用のファクトリ関数
def create_recorder(debug_mode: bool = False) -> TwitcastingRecorder:
    """
    レコーダーインスタンス作成
    
    Args:
        debug_mode: デバッグモード
        
    Returns:
        TwitcastingRecorder: レコーダーインスタンス
    """
    return TwitcastingRecorder(
        debug_mode=debug_mode,
        resource_manager=ResourceManager(max_concurrent_recordings=3)
    )


if __name__ == "__main__":
    # 使用例
    recorder = create_recorder(debug_mode=True)
    
    request = RecordingRequest(
        url="https://twitcasting.tv/example_user",
        output_path=Path("output/test_recording.mp4"),
        quality="best",
        retry_attempts=3,
        force_overwrite=True  # GPT修正1: 明示的な上書き設定
    )
    
    result = recorder.start_recording(request)
    print(f"録画結果: {result}")
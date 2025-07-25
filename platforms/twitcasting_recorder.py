"""
TwitCasting録画専門家 (TwitCasting Recorder)
汎用エンジンを活用してTwitCasting固有の録画処理を実装

設計原則:
- TwitCasting固有の知識のみを保持
- 汎用エンジン（core/）を活用した責務分離
- 他プラットフォーム録画の模範実装
"""
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

# 汎用エンジンのインポート
from core.process_engine import (
    AsyncProcessEngine, ProcessRequest, ProcessResult, ProcessMonitor, 
    MonitorEvent, MonitorEventType
)
from core.file_verifier import FileVerifier, VerificationRule, VerificationType
from core.retry_strategy import (
    RetryExecutor, RetryConfiguration, RetryConfigurationFactory, CommonErrorCheckers
)

# 既存モジュールのインポート
from recording_result import RecordingResult, RecordingStatus


class TwitCastingError(Enum):
    """TwitCasting固有エラータイプ"""
    STREAM_OFFLINE = "stream_offline"
    PRIVATE_STREAM = "private_stream"
    AGE_RESTRICTED = "age_restricted"
    INVALID_URL = "invalid_url"
    STREAMLINK_ERROR = "streamlink_error"


@dataclass
class TwitCastingRequest:
    """TwitCasting録画リクエスト"""
    url: str
    output_path: Path
    quality: str = "best"
    force_overwrite: bool = False
    enable_file_verification: bool = True
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    custom_streamlink_args: List[str] = None
    
    def __post_init__(self):
        if self.custom_streamlink_args is None:
            self.custom_streamlink_args = []


class TwitCastingLogParser:
    """TwitCasting/Streamlink ログ解析"""
    
    # Streamlinkログパターン
    PATTERNS = {
        'stream_start': re.compile(r'Starting player.*'),
        'segment_download': re.compile(r'segment (\d+).*downloaded'),
        'buffering': re.compile(r'buffering|buffer'),
        'quality_info': re.compile(r'Available streams.*'),
        'error_auth': re.compile(r'authentication|login|unauthorized', re.IGNORECASE),
        'error_network': re.compile(r'connection|network|timeout', re.IGNORECASE),
        'error_not_found': re.compile(r'no streams found|stream not found|404', re.IGNORECASE),
        'error_private': re.compile(r'private|限定|members only', re.IGNORECASE),
        'error_age': re.compile(r'age|年齢|adult', re.IGNORECASE)
    }
    
    @staticmethod
    def parse_stdout_line(line: str) -> Optional[Dict[str, Any]]:
        """
        stdout行を解析してTwitCasting固有の進捗情報を抽出
        
        Args:
            line: ログ行
            
        Returns:
            Optional[Dict]: 解析結果（Noneは解析対象外）
        """
        line_lower = line.lower()
        
        # ストリーム開始検出
        if TwitCastingLogParser.PATTERNS['stream_start'].search(line):
            return {
                "event_type": "stream_started",
                "message": "録画開始",
                "raw_line": line
            }
        
        # セグメントダウンロード検出
        segment_match = TwitCastingLogParser.PATTERNS['segment_download'].search(line)
        if segment_match:
            segment_num = int(segment_match.group(1))
            return {
                "event_type": "segment_downloaded",
                "segment_number": segment_num,
                "message": f"セグメント {segment_num} ダウンロード完了",
                "raw_line": line
            }
        
        # バッファリング検出
        if TwitCastingLogParser.PATTERNS['buffering'].search(line_lower):
            return {
                "event_type": "buffering",
                "message": "バッファリング中",
                "raw_line": line
            }
        
        # 品質情報検出
        if TwitCastingLogParser.PATTERNS['quality_info'].search(line):
            return {
                "event_type": "quality_detected",
                "message": "利用可能な品質情報を検出",
                "raw_line": line
            }
        
        return None
    
    @staticmethod
    def parse_stderr_line(line: str) -> Optional[Dict[str, Any]]:
        """
        stderr行を解析してTwitCasting固有のエラー情報を抽出
        
        Args:
            line: エラー行
            
        Returns:
            Optional[Dict]: 解析結果
        """
        line_lower = line.lower()
        
        # 認証エラー
        if TwitCastingLogParser.PATTERNS['error_auth'].search(line_lower):
            return {
                "error_type": TwitCastingError.PRIVATE_STREAM.value,
                "message": "認証が必要な配信です",
                "suggestion": "Cookieファイルの設定を確認してください",
                "raw_line": line
            }
        
        # ネットワークエラー
        if TwitCastingLogParser.PATTERNS['error_network'].search(line_lower):
            return {
                "error_type": TwitCastingError.STREAMLINK_ERROR.value,
                "message": "ネットワークエラーが発生しました",
                "suggestion": "インターネット接続を確認してください",
                "raw_line": line
            }
        
        # ストリーム見つからない
        if TwitCastingLogParser.PATTERNS['error_not_found'].search(line_lower):
            return {
                "error_type": TwitCastingError.STREAM_OFFLINE.value,
                "message": "配信が見つかりません",
                "suggestion": "配信が終了している可能性があります",
                "raw_line": line
            }
        
        # 限定配信
        if TwitCastingLogParser.PATTERNS['error_private'].search(line_lower):
            return {
                "error_type": TwitCastingError.PRIVATE_STREAM.value,
                "message": "限定配信のため録画できません",
                "suggestion": "配信者による制限がかかっています",
                "raw_line": line
            }
        
        # 年齢制限
        if TwitCastingLogParser.PATTERNS['error_age'].search(line_lower):
            return {
                "error_type": TwitCastingError.AGE_RESTRICTED.value,
                "message": "年齢制限のある配信です",
                "suggestion": "年齢確認が必要な配信です",
                "raw_line": line
            }
        
        return {
            "error_type": TwitCastingError.STREAMLINK_ERROR.value,
            "message": f"Streamlinkエラー: {line}",
            "raw_line": line
        }


class TwitCastingCommandBuilder:
    """TwitCasting用Streamlinkコマンド構築"""
    
    @staticmethod
    def build_command(request: TwitCastingRequest) -> List[str]:
        """
        TwitCasting録画用Streamlinkコマンド構築
        
        Args:
            request: TwitCasting録画リクエスト
            
        Returns:
            List[str]: Streamlinkコマンド
        """
        command = [
            "streamlink",
            request.url,
            request.quality,
            "--output", str(request.output_path)
        ]
        
        # 上書き設定
        if request.force_overwrite:
            command.append("--force")
        elif request.output_path.exists():
            # 既存ファイルがある場合は自動的にタイムスタンプ付きファイル名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_path = request.output_path.with_stem(f"{request.output_path.stem}_{timestamp}")
            command[-1] = str(new_path)
            request.output_path = new_path
        
        # TwitCasting最適化オプション
        twitcasting_args = [
            "--retry-streams", "3",
            "--retry-max", "3",
            "--hls-timeout", "60",
            "--hls-segment-timeout", "30",
            "--hls-segment-attempts", "3"
        ]
        command.extend(twitcasting_args)
        
        # カスタム引数追加
        if request.custom_streamlink_args:
            command.extend(request.custom_streamlink_args)
        
        return command
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """TwitCasting URLの検証"""
        twitcast_patterns = [
            r'https?://twitcasting\.tv/[^/]+',
            r'https?://twitcasting\.tv/[^/]+/movie/\d+',
            r'https?://cas\.st/[^/]+'
        ]
        
        return any(re.match(pattern, url) for pattern in twitcast_patterns)


class TwitCastingProgressMonitor(ProcessMonitor):
    """TwitCasting専用進捗監視"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        super().__init__()
        self.progress_callback = progress_callback
        self.segment_count = 0
        self.last_progress_time = datetime.now()
        
        # 自身をObserverとして登録
        self.add_observer(self._handle_progress_event)
    
    async def _handle_progress_event(self, event: MonitorEvent):
        """進捗イベント処理"""
        progress_data = {
            "session_id": event.session_id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type.value
        }
        
        # TwitCasting固有の進捗処理
        if event.event_type == MonitorEventType.STDOUT_LINE:
            parsed = TwitCastingLogParser.parse_stdout_line(event.data.get("line", ""))
            if parsed:
                progress_data.update(parsed)
                
                # セグメント数カウント
                if parsed.get("event_type") == "segment_downloaded":
                    self.segment_count += 1
                    progress_data["total_segments"] = self.segment_count
        
        elif event.event_type == MonitorEventType.STDERR_LINE:
            parsed = TwitCastingLogParser.parse_stderr_line(event.data.get("line", ""))
            if parsed:
                progress_data.update(parsed)
        
        elif event.event_type == MonitorEventType.PROGRESS:
            progress_data.update(event.data)
        
        # 進捗コールバック実行
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception:
                pass  # コールバックエラーは無視


class TwitCastingRecorder:
    """
    TwitCasting録画専門家
    汎用エンジンを活用してTwitCasting固有の録画を実行
    """
    
    def __init__(self, 
                 process_engine: Optional[AsyncProcessEngine] = None,
                 file_verifier: Optional[FileVerifier] = None,
                 retry_executor: Optional[RetryExecutor] = None,
                 debug_mode: bool = False):
        """
        初期化
        
        Args:
            process_engine: プロセス実行エンジン
            file_verifier: ファイル検証エンジン
            retry_executor: 再試行実行エンジン
            debug_mode: デバッグモード
        """
        self.process_engine = process_engine or AsyncProcessEngine()
        self.file_verifier = file_verifier or FileVerifier()
        self.retry_executor = retry_executor or RetryExecutor()
        self.debug_mode = debug_mode
        
        # TwitCasting録画統計
        self.stats = {
            "total_recordings": 0,
            "successful_recordings": 0,
            "failed_recordings": 0,
            "total_segments_downloaded": 0,
            "average_recording_duration": 0.0
        }
    
    async def start_recording(self, request: TwitCastingRequest) -> RecordingResult:
        """
        TwitCasting録画開始
        
        Args:
            request: TwitCasting録画リクエスト
            
        Returns:
            RecordingResult: 録画結果
        """
        self.stats["total_recordings"] += 1
        start_time = datetime.now()
        
        # URL検証
        if not TwitCastingCommandBuilder.validate_url(request.url):
            self.stats["failed_recordings"] += 1
            return RecordingResult(
                status=RecordingStatus.FAILED,
                message="無効なTwitCasting URLです",
                metadata={
                    "error_type": TwitCastingError.INVALID_URL.value,
                    "url": request.url
                }
            )
        
        # 出力ディレクトリ作成
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # 再試行設定
            retry_config = RetryConfigurationFactory.create_recording_operation()
            
            # 録画操作定義
            async def recording_operation():
                return await self._execute_recording(request, start_time)
            
            # エラーチェッカー定義
            def is_retryable_error(error: Exception) -> bool:
                error_str = str(error).lower()
                # ネットワークエラーは再試行
                if CommonErrorCheckers.network_errors(error):
                    return True
                # TwitCasting固有の再試行可能エラー
                retryable_keywords = ["timeout", "connection", "temporary"]
                return any(keyword in error_str for keyword in retryable_keywords)
            
            # 再試行付き録画実行
            retry_result = await self.retry_executor.execute_with_retry(
                recording_operation, retry_config, is_retryable_error
            )
            
            if retry_result.success:
                self.stats["successful_recordings"] += 1
                return retry_result.value
            else:
                self.stats["failed_recordings"] += 1
                return RecordingResult(
                    status=RecordingStatus.FAILED,
                    message=f"すべての再試行が失敗しました: {retry_result.final_error}",
                    metadata={
                        "retry_attempts": retry_result.attempt_count,
                        "total_duration": retry_result.total_duration,
                        "final_error": retry_result.final_error
                    }
                )
                
        except Exception as e:
            self.stats["failed_recordings"] += 1
            return RecordingResult(
                status=RecordingStatus.FAILED,
                message=f"録画中に予期しないエラーが発生しました: {str(e)}",
                metadata={"exception": str(e)}
            )
    
    async def _execute_recording(self, request: TwitCastingRequest, start_time: datetime) -> RecordingResult:
        """録画実行（内部メソッド）"""
        # Streamlinkコマンド構築
        command = TwitCastingCommandBuilder.build_command(request)
        
        if self.debug_mode:
            print(f"TwitCasting録画コマンド: {' '.join(command)}")
        
        # プロセス実行リクエスト作成
        process_request = ProcessRequest(
            command=command,
            timeout=3600.0  # 1時間タイムアウト
        )
        
        # 進捗監視設定
        progress_monitor = TwitCastingProgressMonitor(request.progress_callback)
        
        # カスタムパーサー設定
        custom_parsers = [
            TwitCastingLogParser.parse_stdout_line,
            TwitCastingLogParser.parse_stderr_line
        ]
        
        # プロセス実行
        process_result = await self.process_engine.execute_process(
            process_request,
            monitors=[progress_monitor],
            custom_parsers=custom_parsers
        )
        
        # 結果分析
        return await self._analyze_recording_result(
            process_result, request, command, start_time, progress_monitor
        )
    
    async def _analyze_recording_result(self, 
                                      process_result: ProcessResult,
                                      request: TwitCastingRequest,
                                      command: List[str],
                                      start_time: datetime,
                                      progress_monitor: TwitCastingProgressMonitor) -> RecordingResult:
        """録画結果分析"""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 基本メタデータ
        metadata = {
            "session_id": process_result.session_id,
            "duration_seconds": duration,
            "return_code": process_result.return_code,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "url": request.url,
            "quality": request.quality,
            "segments_downloaded": progress_monitor.segment_count
        }
        
        # デバッグ情報
        if self.debug_mode:
            metadata.update({
                "command": " ".join(command),
                "stdout": process_result.stdout,
                "stderr": process_result.stderr
            })
        
        # 成功判定
        if process_result.is_success:
            # ファイル検証
            if request.enable_file_verification:
                verification_rules = FileVerifier.create_media_rules("video")
                verification_result = await self.file_verifier.verify_file(
                    request.output_path, verification_rules
                )
                
                metadata["file_verification"] = {
                    "result": verification_result.overall_result.value,
                    "file_size": verification_result.file_size,
                    "verification_time": verification_result.verification_time
                }
                
                if not verification_result.is_valid:
                    return RecordingResult(
                        status=RecordingStatus.FAILED,
                        message=f"録画ファイル検証に失敗: {verification_result.error_message}",
                        metadata=metadata
                    )
            
            # 統計更新
            self.stats["total_segments_downloaded"] += progress_monitor.segment_count
            self.stats["average_recording_duration"] = (
                (self.stats["average_recording_duration"] * (self.stats["successful_recordings"] - 1) + duration) 
                / self.stats["successful_recordings"]
            )
            
            return RecordingResult(
                status=RecordingStatus.COMPLETED,
                message="TwitCasting録画が正常に完了しました",
                output_file=request.output_path,
                metadata=metadata
            )
        else:
            # エラー分析
            status, error_message = self._analyze_twitcasting_error(process_result.stderr)
            
            metadata["error_analysis"] = {
                "detected_error_type": status.value if status != RecordingStatus.FAILED else "unknown",
                "stderr": process_result.stderr[:500]
            }
            
            return RecordingResult(
                status=status,
                message=error_message,
                metadata=metadata
            )
    
    def _analyze_twitcasting_error(self, stderr: str) -> tuple[RecordingStatus, str]:
        """TwitCasting固有エラー分析"""
        if not stderr:
            return RecordingStatus.FAILED, "不明なエラーが発生しました"
        
        stderr_lower = stderr.lower()
        
        # TwitCasting固有エラーパターン
        if any(keyword in stderr_lower for keyword in ["no streams found", "offline", "終了"]):
            return RecordingStatus.FAILED_STREAM_NOT_FOUND, "配信が見つかりません（配信終了の可能性）"
        
        if any(keyword in stderr_lower for keyword in ["private", "限定", "members only"]):
            return RecordingStatus.FAILED_AUTH, "限定配信のため録画できません"
        
        if any(keyword in stderr_lower for keyword in ["age", "年齢", "adult"]):
            return RecordingStatus.FAILED_AUTH, "年齢制限のある配信です"
        
        if any(keyword in stderr_lower for keyword in ["authentication", "login", "unauthorized"]):
            return RecordingStatus.FAILED_AUTH, "認証エラーが発生しました"
        
        if any(keyword in stderr_lower for keyword in ["connection", "network", "timeout"]):
            return RecordingStatus.FAILED_NETWORK, "ネットワークエラーが発生しました"
        
        return RecordingStatus.FAILED, f"TwitCasting録画エラー: {stderr[:200]}"
    
    def get_stats(self) -> Dict[str, Any]:
        """TwitCasting録画統計取得"""
        stats = self.stats.copy()
        
        # 成功率計算
        if stats["total_recordings"] > 0:
            stats["success_rate"] = stats["successful_recordings"] / stats["total_recordings"]
        else:
            stats["success_rate"] = 0.0
        
        # エンジン統計も含める
        stats["engine_stats"] = {
            "process_engine": self.process_engine.get_stats(),
            "file_verifier": self.file_verifier.get_stats(),
            "retry_executor": self.retry_executor.get_stats()
        }
        
        return stats


# ファクトリ関数
def create_twitcasting_recorder(debug_mode: bool = False) -> TwitCastingRecorder:
    """
    TwitCasting録画専門家インスタンス作成
    
    Args:
        debug_mode: デバッグモード
        
    Returns:
        TwitCastingRecorder: TwitCasting録画専門家
    """
    return TwitCastingRecorder(debug_mode=debug_mode)


# 使用例
async def main():
    """使用例（真の非同期実行）"""
    
    def progress_callback(progress: Dict[str, Any]):
        """進捗コールバック例"""
        event_type = progress.get("event_type", "unknown")
        message = progress.get("message", "")
        
        if event_type == "segment_downloaded":
            segment_num = progress.get("segment_number", 0)
            total_segments = progress.get("total_segments", 0)
            print(f"📥 セグメント {segment_num} ダウンロード完了 (総計: {total_segments})")
        elif event_type == "buffering":
            print("⏳ バッファリング中...")
        elif event_type == "stream_started":
            print("🎬 録画開始！")
        elif "error_type" in progress:
            error_type = progress.get("error_type")
            suggestion = progress.get("suggestion", "")
            print(f"❌ エラー: {message}")
            if suggestion:
                print(f"💡 対処法: {suggestion}")
        else:
            print(f"📊 {message}")
    
    # TwitCasting録画専門家を作成
    recorder = create_twitcasting_recorder(debug_mode=True)
    
    # 録画リクエスト作成
    request = TwitCastingRequest(
        url="https://twitcasting.tv/example_user",
        output_path=Path("recordings/twitcast_recording.mp4"),
        quality="best",
        force_overwrite=False,
        enable_file_verification=True,
        progress_callback=progress_callback,
        custom_streamlink_args=["--hls-segment-max-count", "10"]  # カスタム設定
    )
    
    print("🚀 TwitCasting録画開始...")
    print(f"📺 URL: {request.url}")
    print(f"💾 出力: {request.output_path}")
    
    # 非同期録画実行
    result = recorder.start_recording(request)
    
    print(f"\n📋 録画結果:")
    print(f"  ステータス: {result.status.value}")
    print(f"  メッセージ: {result.message}")
    
    if result.output_file:
        print(f"  出力ファイル: {result.output_file}")
        if result.output_file.exists():
            file_size = result.output_file.stat().st_size
            print(f"  ファイルサイズ: {file_size / 1024 / 1024:.2f} MB")
    
    # 統計情報表示
    stats = recorder.get_stats()
    print(f"\n📊 録画統計:")
    print(f"  総録画数: {stats['total_recordings']}")
    print(f"  成功率: {stats['success_rate']:.1%}")
    print(f"  平均録画時間: {stats['average_recording_duration']:.1f}秒")
    print(f"  総セグメント数: {stats['total_segments_downloaded']}")


if __name__ == "__main__":
    asyncio.run(main())


# エクスポート
__all__ = [
    'TwitCastingError',
    'TwitCastingRequest', 
    'TwitCastingLogParser',
    'TwitCastingCommandBuilder',
    'TwitCastingProgressMonitor',
    'TwitCastingRecorder',
    'create_twitcasting_recorder'
]
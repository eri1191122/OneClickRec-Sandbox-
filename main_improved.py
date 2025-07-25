"""
改良版 main.py
既存ファイルと競合しないように、新しい名前で作成
"""

import sys
import time
import json
import signal
import argparse
import os
from pathlib import Path
from enum import Enum, auto
from datetime import datetime
from typing import Optional, Dict, Any

# 新しく作成したモジュール
from recording_result import RecordingResult, RecordingStatus
from url_utils import TwitCastingURLParser, URLValidationError

# 既存の例外システムを使用
from exceptions_base import OneClickRecException, ErrorCode

# ダミークラス（段階的実装用）
class AuthStatus(Enum): 
    AUTHENTICATED = auto()
    FAILED = auto()

class IPCMessageLevel(Enum): 
    INFO = auto()
    SUCCESS = auto() 
    ERROR = auto()
    FATAL = auto()

class ConfigLoader:
    def load(self):
        print("[DUMMY] Config loaded.")
        return {
            "output_dir": "recordings", 
            "log_dir": "logs", 
            "log_file": "app.log", 
            "log_level": "INFO", 
            "ipc_port": 8765, 
            "filename_template": "{user}_{timestamp}"
        }

class LoggingInitializer:
    def __init__(self, config): pass
    def init(self):
        import logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        return logging.getLogger("OneClickRec")

class IPCManager:
    def __init__(self, config, logger): 
        self.logger = logger
    def start(self): 
        self.logger.info("[DUMMY] IPC WebSocket server started.")
    def stop(self): 
        self.logger.info("[DUMMY] IPC WebSocket server stopped.")
    def broadcast(self, data): 
        self.logger.info(f"[DUMMY_IPC_BROADCAST] {json.dumps(data, indent=2, ensure_ascii=False)}")

class AuthManager:
    def __init__(self, config, logger): 
        self.logger = logger
    def check_and_perform_auth(self): 
        return AuthStatus.AUTHENTICATED

class TwitcastingRecorder:
    def __init__(self, config, logger): 
        self.config = config
        self.logger = logger
    
    def start_recording(self, url: str, password: Optional[str], output_path: Path) -> RecordingResult:
        """録画を開始し、RecordingResultを返す"""
        self.logger.info(f"[DUMMY] Recording started. Output path: {output_path}")
        start_time = datetime.now()
        
        # ログファイルパス
        log_path = output_path.with_suffix('.log.json')
        
        # ダミー録画処理
        time.sleep(3)
        end_time = datetime.now()
        
        # テスト用：意図的にファイル作成失敗
        actual_file_created = False 
        file_size = 0 if not actual_file_created else 1024 * 1024  # 1MB
        
        # RecordingResultを構築
        result = RecordingResult(
            status=RecordingStatus.SUCCESS if actual_file_created else RecordingStatus.FAILED_NO_FILE,
            video_path=output_path,
            log_path=log_path,
            start_time=start_time,
            end_time=end_time,
            file_size_bytes=file_size,
            error_message=None if actual_file_created else "ダミー実装：ファイル作成をスキップ",
            ffmpeg_exit_code=0 if actual_file_created else 1,
            metadata={
                "url": url,
                "password_protected": password is not None,
                "recorder_version": "dummy_v1.0"
            }
        )
        
        # 詳細ログ保存
        try:
            result.save_detailed_log()
            self.logger.info(f"Recording log saved: {log_path}")
        except Exception as e:
            self.logger.error(f"Failed to save recording log: {e}")
        
        return result

    def stop_all(self): 
        self.logger.info("[DUMMY] All recording processes stopped.")


class AppState(Enum):
    INITIALIZING = auto()
    IDLE = auto()
    AUTHENTICATING = auto()
    RECORDING = auto()
    VERIFYING = auto()
    MONITORING = auto()
    SHUTTING_DOWN = auto()
    ERROR = auto()


class Application:
    """改良版アプリケーション制御クラス"""

    def __init__(self, config: Dict[str, Any], logger, ipc: IPCManager):
        self.config = config
        self.logger = logger
        self.ipc = ipc
        self.args: Optional[argparse.Namespace] = None
        self.state = AppState.INITIALIZING
        self.is_running = True
        self.auth_manager = AuthManager(config=self.config, logger=self.logger)
        self.recorder = TwitcastingRecorder(config=self.config, logger=self.logger)
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._graceful_shutdown)
        signal.signal(signal.SIGTERM, self._graceful_shutdown)

    def _graceful_shutdown(self, signum, frame):
        if not self.is_running: 
            return
        self.logger.warning(f"シャットダウンシグナル ({signal.Signals(signum).name}) を受信。")
        self.is_running = False

    def _broadcast_status(self, level: IPCMessageLevel, ui_action: str, message: str, details: Optional[dict] = None):
        """GUIに状態をブロードキャスト"""
        payload = {
            "level": level.name,
            "ui_action": ui_action,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "app_state": self.state.name,
            "details": details or {}
        }
        self.ipc.broadcast(payload)

    def _generate_filepath(self, url: str) -> Path:
        """安全なファイル名生成"""
        try:
            # 安全なURL解析
            user_id = TwitCastingURLParser.extract_user_id(url)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            template = self.config.get("filename_template", "{user}_{timestamp}")
            filename = template.format(user=user_id, timestamp=timestamp) + ".mp4"
            
            output_dir = Path(self.config["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            
            return output_dir / filename
            
        except URLValidationError as e:
            raise OneClickRecException(f"URLからファイル名を生成できません: {e}")

    def run(self, args: argparse.Namespace):
        self.args = args
        self.logger.info("改良版アプリケーション実行開始")
        self.state = AppState.IDLE
        self._broadcast_status(IPCMessageLevel.INFO, "UPDATE_STATUS", "待機中")

        try:
            if self.args.url: 
                self._run_single_task()
            else: 
                self._main_loop()
        except OneClickRecException as e:
            self.logger.error(f"アプリケーションエラー: {e}", exc_info=True)
            self._broadcast_status(IPCMessageLevel.FATAL, "SHOW_ERROR_DIALOG", str(e))
        except Exception as e:
            self.logger.error(f"予期しないエラー: {e}", exc_info=True)
            self._broadcast_status(IPCMessageLevel.FATAL, "SHOW_ERROR_DIALOG", f"予期しないエラー: {e}")
        finally:
            self.shutdown()

    def _run_single_task(self):
        """単発録画タスクの実行"""
        try:
            # URL検証
            self.logger.info(f"URL検証開始: {self.args.url}")
            self._broadcast_status(IPCMessageLevel.INFO, "UPDATE_STATUS", "URLを検証中...")
            
            # 安全なURL検証
            user_id = TwitCastingURLParser.extract_user_id(self.args.url)
            self.logger.info(f"URL検証成功: ユーザーID={user_id}")
            
            # 認証確認
            self.state = AppState.AUTHENTICATING
            self._broadcast_status(IPCMessageLevel.INFO, "UPDATE_STATUS", "認証を確認中...")
            auth_status = self.auth_manager.check_and_perform_auth()
            
            if auth_status != AuthStatus.AUTHENTICATED:
                raise OneClickRecException("認証に失敗しました")

            # 出力パス生成
            output_path = self._generate_filepath(self.args.url)
            self.logger.info(f"出力ファイルパス: {output_path}")
            
            # 録画実行
            self.state = AppState.RECORDING
            self._broadcast_status(
                IPCMessageLevel.INFO, 
                "UPDATE_STATUS", 
                f"録画を開始: {output_path.name}",
                {"user_id": user_id, "output_path": str(output_path)}
            )
            
            recording_result = self.recorder.start_recording(
                url=self.args.url, 
                password=self.args.password, 
                output_path=output_path
            )

            # 録画結果検証
            self.state = AppState.VERIFYING
            self._broadcast_status(IPCMessageLevel.INFO, "UPDATE_STATUS", "録画結果を検証中...")
            final_result = self._verify_recording_result(recording_result)
            
            # 結果通知
            self._broadcast_recording_result(final_result)
            
        except URLValidationError as e:
            raise OneClickRecException(f"無効なURL: {e}")
        except Exception as e:
            raise OneClickRecException(f"録画タスク中にエラー: {e}")

    def _verify_recording_result(self, result: RecordingResult) -> RecordingResult:
        """録画結果の検証"""
        self.logger.info(f"録画結果検証開始: status={result.status.name}")
        
        # 基本ステータスチェック
        if result.status != RecordingStatus.SUCCESS:
            self.logger.warning(f"録画処理がエラー終了: {result.status.name}")
            return result
        
        # ファイル存在チェック
        if not result.video_path or not result.video_path.exists():
            self.logger.error(f"録画ファイルが存在しません: {result.video_path}")
            result.status = RecordingStatus.FAILED_NO_FILE
            result.error_message = "録画ファイルが作成されませんでした"
            return result
        
        # ファイルサイズチェック
        if not result.is_file_valid:
            self.logger.error(f"録画ファイルが小さすぎます: {result.file_size_formatted}")
            result.status = RecordingStatus.FAILED_FILE_TOO_SMALL
            result.error_message = f"録画ファイルのサイズが不正: {result.file_size_formatted}"
            return result
        
        # FFmpeg終了コードチェック
        if result.ffmpeg_exit_code is not None and result.ffmpeg_exit_code != 0:
            self.logger.error(f"FFmpegがエラー終了: exit_code={result.ffmpeg_exit_code}")
            result.status = RecordingStatus.FAILED_FFMPEG_ERROR
            result.error_message = f"FFmpegエラー (終了コード: {result.ffmpeg_exit_code})"
            return result
        
        # 全検証をパス
        self.logger.info(f"録画結果検証成功: {result.file_size_formatted}, {result.recording_duration_formatted}")
        return result

    def _broadcast_recording_result(self, result: RecordingResult):
        """録画結果の通知"""
        
        if result.is_success and result.is_file_valid:
            # 成功
            self.logger.info(f"録画タスク成功: {result.video_path}")
            self._broadcast_status(
                IPCMessageLevel.SUCCESS, 
                "SHOW_SUCCESS_TOAST", 
                "録画が正常に完了しました",
                {
                    "file_path": str(result.video_path),
                    "log_path": str(result.log_path),
                    "file_size": result.file_size_formatted,
                    "duration": result.recording_duration_formatted,
                    "details": result.to_dict()
                }
            )
            
        elif result.status == RecordingStatus.FAILED_NO_FILE:
            # ファイル未作成エラー
            self.logger.error(f"録画ファイル未作成: {result.video_path}")
            self._broadcast_status(
                IPCMessageLevel.FATAL, 
                "SHOW_ERROR_DIALOG", 
                "録画処理は完了しましたが、ファイルが保存されませんでした",
                {
                    "reason": "ディスク容量不足または権限エラーの可能性があります",
                    "expected_path": str(result.video_path),
                    "log_path": str(result.log_path),
                    "details": result.to_dict()
                }
            )
            
        else:
            # その他のエラー
            self.logger.error(f"録画タスク失敗: {result.status.name}")
            self._broadcast_status(
                IPCMessageLevel.ERROR, 
                "SHOW_ERROR_ALERT", 
                "録画に失敗しました",
                {
                    "status": result.status.name,
                    "error_message": result.error_message,
                    "log_path": str(result.log_path),
                    "details": result.to_dict()
                }
            )
    
    def _main_loop(self):
        """常駐監視モード"""
        self.state = AppState.MONITORING
        self.logger.info("常駐監視モードで起動")
        
        while self.is_running:
            self._broadcast_status(IPCMessageLevel.INFO, "UPDATE_STATUS", "常駐監視中")
            time.sleep(10)

    def shutdown(self):
        """シャットダウン処理"""
        self.state = AppState.SHUTTING_DOWN
        self.logger.info("アプリケーションをシャットダウンします...")
        
        try:
            self.recorder.stop_all()
            self.ipc.stop()
            self._broadcast_status(IPCMessageLevel.INFO, "UPDATE_STATUS", "シャットダウン完了")
        except Exception as e:
            self.logger.error(f"シャットダウン中にエラー: {e}")
        finally:
            self.logger.info("シャットダウンが完了しました")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="OneClickRec - 改良版録画システム")
    parser.add_argument("--url", type=str, help="録画対象の配信URL")
    parser.add_argument("--password", type=str, help="パスワード付き配信の場合のパスワード")
    args = parser.parse_args()
    
    try:
        config = ConfigLoader().load()
        logger = LoggingInitializer(config).init()
        ipc_manager = IPCManager(config, logger)
        ipc_manager.start()
        
        app = Application(config=config, logger=logger, ipc=ipc_manager)
        app.run(args)
        
    except Exception as e:
        print(f"起動シーケンスで致命的なエラーが発生: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
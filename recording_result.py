"""
録画結果を表現する完璧な構造化クラス
Phase 1以降でも拡張可能な設計
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum, auto


class RecordingStatus(Enum):
    """録画ステータスの詳細分類"""
    SUCCESS = auto()
    FAILED_RECORDER_ERROR = auto()
    FAILED_NO_FILE = auto()
    FAILED_FILE_TOO_SMALL = auto()
    FAILED_FFMPEG_ERROR = auto()
    FAILED_AUTHENTICATION = auto()
    FAILED_NETWORK_ERROR = auto()
    FAILED_UNKNOWN = auto()


@dataclass
class RecordingResult:
    """
    録画結果の完全な情報を保持するクラス
    
    Phase 0: 基本的な成功/失敗とファイルパス
    Phase 1: 録画時間、ファイルサイズ、エラー詳細
    Phase 2: メタデータ、品質情報、統計
    """
    
    # === 基本情報（Phase 0で必須） ===
    status: RecordingStatus
    video_path: Optional[Path] = None
    log_path: Optional[Path] = None
    
    # === 時間情報（Phase 1で活用） ===
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # === ファイル情報（Phase 1で活用） ===
    file_size_bytes: Optional[int] = None
    
    # === エラー情報（デバッグに必須） ===
    error_message: Optional[str] = None
    ffmpeg_exit_code: Optional[int] = None
    ffmpeg_stderr: Optional[str] = None
    
    # === 拡張用メタデータ（Phase 2以降） ===
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """データクラス初期化後の検証と補完"""
        if self.metadata is None:
            self.metadata = {}
            
        # ファイルサイズの自動取得
        if self.video_path and self.video_path.exists() and self.file_size_bytes is None:
            self.file_size_bytes = self.video_path.stat().st_size
            
        # 録画時間の自動計算
        if self.start_time and self.end_time and self.duration_seconds is None:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    @property
    def is_success(self) -> bool:
        """録画が成功したかどうか"""
        return self.status == RecordingStatus.SUCCESS
    
    @property
    def is_file_valid(self) -> bool:
        """録画ファイルが有効かどうか"""
        if not self.video_path or not self.video_path.exists():
            return False
        
        # ファイルサイズチェック（1KB未満は無効とみなす）
        if self.file_size_bytes is not None:
            return self.file_size_bytes >= 1024
        
        return self.video_path.stat().st_size >= 1024
    
    @property
    def recording_duration_formatted(self) -> str:
        """録画時間を人間が読める形式で返す"""
        if self.duration_seconds is None:
            return "不明"
        
        hours = int(self.duration_seconds // 3600)
        minutes = int((self.duration_seconds % 3600) // 60)
        seconds = int(self.duration_seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def file_size_formatted(self) -> str:
        """ファイルサイズを人間が読める形式で返す"""
        if self.file_size_bytes is None:
            return "不明"
        
        # バイト単位での表示
        if self.file_size_bytes < 1024:
            return f"{self.file_size_bytes} B"
        elif self.file_size_bytes < 1024 * 1024:
            return f"{self.file_size_bytes / 1024:.1f} KB"
        elif self.file_size_bytes < 1024 * 1024 * 1024:
            return f"{self.file_size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式で出力（JSONシリアライズ用）"""
        return {
            "status": self.status.name,
            "video_path": str(self.video_path) if self.video_path else None,
            "log_path": str(self.log_path) if self.log_path else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "file_size_bytes": self.file_size_bytes,
            "error_message": self.error_message,
            "ffmpeg_exit_code": self.ffmpeg_exit_code,
            "metadata": self.metadata,
            "is_success": self.is_success,
            "is_file_valid": self.is_file_valid,
            "duration_formatted": self.recording_duration_formatted,
            "file_size_formatted": self.file_size_formatted
        }
    
    def save_detailed_log(self) -> bool:
        """詳細ログをJSONファイルに保存"""
        if not self.log_path:
            return False
            
        try:
            import json
            with open(self.log_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
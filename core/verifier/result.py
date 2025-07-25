"""
File Verifier - Result Data Structures (v2)

このモジュールは、ファイル検証の実行結果を表現するための
データ構造（Enumとdataclass）を定義します。
他のすべての検証関連モジュールから参照される、最も基本的な部品です。

v2での改善点:
- StrategyType: 検証戦略名をEnumで定義し、型安全性を向上。
- Severity: 検証結果の重大度（情報、警告、エラー）を定義。
- to_dict(): JSONシリアライズを容易にするための変換メソッドを追加。
- error_summary: 失敗時のエラーメッセージを動的に生成し、整合性を保証。
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
from typing import List, Dict, Any, Optional

class StrategyType(str, Enum):
    """検証戦略のタイプを定義するEnum"""
    FILE_SIZE = "FileSize"
    EXTENSION = "Extension"
    MAGIC_BYTE = "MagicByte"
    FFMPEG_INTEGRITY = "FFmpegIntegrity"
    CUSTOM = "Custom" # 将来のカスタムチェッカー用

class Severity(str, Enum):
    """検証結果の重大度を定義するEnum"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class StrategyResult:
    """
    個々の検証戦略（チェッカー）の実行結果を保持します。
    """
    strategy_type: StrategyType
    is_valid: bool
    message: str
    severity: Severity = Severity.INFO
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """is_validに基づいて自動的に重大度を設定"""
        if not self.is_valid:
            self.severity = Severity.ERROR

    def to_dict(self) -> Dict[str, Any]:
        """このオブジェクトを辞書に変換します。"""
        return asdict(self)

@dataclass
class FileVerificationResult:
    """
    ファイル一つに対する総合的な検証結果を保持します。
    """
    file_path: Path
    is_overall_valid: bool
    verification_details: List[StrategyResult] = field(default_factory=list)
    verification_time_seconds: float = 0.0
    file_size_bytes: Optional[int] = None

    @property
    def error_summary(self) -> Optional[str]:
        """
        検証が失敗した場合、最初の致命的なエラーメッセージを返します。
        これにより、is_overall_validとの整合性が常に保たれます。
        """
        if not self.is_overall_valid:
            failed_checks = self.get_failed_checks()
            if failed_checks:
                return failed_checks[0].message
        return None

    def get_failed_checks(self) -> List[StrategyResult]:
        """失敗した検証項目のみを抽出して返します。"""
        return [
            detail for detail in self.verification_details if not detail.is_valid
        ]
        
    def to_dict(self) -> Dict[str, Any]:
        """
        このオブジェクトをJSONシリアライズ可能な辞書に変換します。
        Pathオブジェクトは文字列に変換されます。
        """
        return {
            "file_path": str(self.file_path),
            "is_overall_valid": self.is_overall_valid,
            "error_summary": self.error_summary,
            "verification_time_seconds": round(self.verification_time_seconds, 4),
            "file_size_bytes": self.file_size_bytes,
            "verification_details": [
                detail.to_dict() for detail in self.verification_details
            ]
        }


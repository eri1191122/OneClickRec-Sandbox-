"""
汎用ファイル検証エンジン (File Verifier)
録画ファイルに限らず、あらゆるファイルの完全性検証を担当

設計原則:
- メディアファイル非依存（動画・音声・画像すべてに対応）
- 高速・軽量な検証方式
- 拡張可能な検証ルール
"""
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib
import json


class VerificationType(Enum):
    """検証タイプ"""
    SIZE_CHECK = "size_check"
    EXTENSION_CHECK = "extension_check"
    MAGIC_BYTE_CHECK = "magic_byte_check"
    FFMPEG_INTEGRITY = "ffmpeg_integrity"
    CUSTOM_CHECK = "custom_check"


class VerificationResult(Enum):
    """検証結果"""
    VALID = "valid"
    INVALID = "invalid"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class VerificationRule:
    """検証ルール"""
    verification_type: VerificationType
    enabled: bool = True
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class FileVerificationResult:
    """ファイル検証結果"""
    file_path: Path
    overall_result: VerificationResult
    verification_details: List[Dict[str, Any]]
    verification_time: float
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def is_valid(self) -> bool:
        """ファイルが有効かどうか"""
        return self.overall_result == VerificationResult.VALID
    
    def get_failed_checks(self) -> List[Dict[str, Any]]:
        """失敗した検証項目を取得"""
        return [
            detail for detail in self.verification_details
            if detail.get("result") != VerificationResult.VALID.value
        ]


class FileSizeChecker:
    """ファイルサイズ検証"""
    
    @staticmethod
    def check(file_path: Path, min_size: int = 1024, max_size: Optional[int] = None) -> Dict[str, Any]:
        """
        ファイルサイズチェック
        
        Args:
            file_path: 検証対象ファイル
            min_size: 最小サイズ（バイト）
            max_size: 最大サイズ（バイト、Noneで無制限）
            
        Returns:
            Dict: 検証結果
        """
        try:
            if not file_path.exists():
                return {
                    "type": VerificationType.SIZE_CHECK.value,
                    "result": VerificationResult.INVALID.value,
                    "message": "ファイルが存在しません",
                    "file_size": 0
                }
            
            file_size = file_path.stat().st_size
            
            if file_size < min_size:
                return {
                    "type": VerificationType.SIZE_CHECK.value,
                    "result": VerificationResult.INVALID.value,
                    "message": f"ファイルサイズが小さすぎます ({file_size} < {min_size} bytes)",
                    "file_size": file_size
                }
            
            if max_size and file_size > max_size:
                return {
                    "type": VerificationType.SIZE_CHECK.value,
                    "result": VerificationResult.INVALID.value,
                    "message": f"ファイルサイズが大きすぎます ({file_size} > {max_size} bytes)",
                    "file_size": file_size
                }
            
            return {
                "type": VerificationType.SIZE_CHECK.value,
                "result": VerificationResult.VALID.value,
                "message": "ファイルサイズは正常です",
                "file_size": file_size
            }
            
        except Exception as e:
            return {
                "type": VerificationType.SIZE_CHECK.value,
                "result": VerificationResult.ERROR.value,
                "message": f"サイズチェックエラー: {str(e)}",
                "file_size": None
            }


class FileExtensionChecker:
    """ファイル拡張子検証"""
    
    # 一般的なメディアファイル拡張子
    MEDIA_EXTENSIONS = {
        'video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts'],
        'audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'],
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    }
    
    @staticmethod
    def check(file_path: Path, 
              allowed_extensions: Optional[List[str]] = None,
              category: Optional[str] = None) -> Dict[str, Any]:
        """
        ファイル拡張子チェック
        
        Args:
            file_path: 検証対象ファイル
            allowed_extensions: 許可する拡張子リスト
            category: カテゴリ（'video', 'audio', 'image'）
            
        Returns:
            Dict: 検証結果
        """
        try:
            extension = file_path.suffix.lower()
            
            # 許可拡張子リストが指定されている場合
            if allowed_extensions:
                allowed_extensions = [ext.lower() for ext in allowed_extensions]
                if extension in allowed_extensions:
                    return {
                        "type": VerificationType.EXTENSION_CHECK.value,
                        "result": VerificationResult.VALID.value,
                        "message": f"拡張子 '{extension}' は許可されています",
                        "extension": extension
                    }
                else:
                    return {
                        "type": VerificationType.EXTENSION_CHECK.value,
                        "result": VerificationResult.INVALID.value,
                        "message": f"拡張子 '{extension}' は許可されていません",
                        "extension": extension,
                        "allowed_extensions": allowed_extensions
                    }
            
            # カテゴリが指定されている場合
            if category and category in FileExtensionChecker.MEDIA_EXTENSIONS:
                category_extensions = FileExtensionChecker.MEDIA_EXTENSIONS[category]
                if extension in category_extensions:
                    return {
                        "type": VerificationType.EXTENSION_CHECK.value,
                        "result": VerificationResult.VALID.value,
                        "message": f"拡張子 '{extension}' は{category}ファイルとして有効です",
                        "extension": extension,
                        "category": category
                    }
                else:
                    return {
                        "type": VerificationType.EXTENSION_CHECK.value,
                        "result": VerificationResult.INVALID.value,
                        "message": f"拡張子 '{extension}' は{category}ファイルとして無効です",
                        "extension": extension,
                        "category": category
                    }
            
            # 拡張子があるかどうかの基本チェック
            if not extension:
                return {
                    "type": VerificationType.EXTENSION_CHECK.value,
                    "result": VerificationResult.INVALID.value,
                    "message": "ファイル拡張子がありません",
                    "extension": None
                }
            
            return {
                "type": VerificationType.EXTENSION_CHECK.value,
                "result": VerificationResult.VALID.value,
                "message": f"拡張子 '{extension}' が確認されました",
                "extension": extension
            }
            
        except Exception as e:
            return {
                "type": VerificationType.EXTENSION_CHECK.value,
                "result": VerificationResult.ERROR.value,
                "message": f"拡張子チェックエラー: {str(e)}",
                "extension": None
            }


class MagicByteChecker:
    """マジックバイト検証"""
    
    # 一般的なファイル形式のマジックバイト
    MAGIC_BYTES = {
        'mp4': [b'\x00\x00\x00\x18ftypmp4', b'\x00\x00\x00\x20ftypmp4'],
        'avi': [b'RIFF'],
        'mkv': [b'\x1a\x45\xdf\xa3'],
        'mp3': [b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'],
        'wav': [b'RIFF'],
        'png': [b'\x89PNG\r\n\x1a\n'],
        'jpg': [b'\xff\xd8\xff'],
        'gif': [b'GIF87a', b'GIF89a']
    }
    
    @staticmethod
    def check(file_path: Path, expected_format: Optional[str] = None) -> Dict[str, Any]:
        """
        マジックバイトチェック
        
        Args:
            file_path: 検証対象ファイル
            expected_format: 期待するファイル形式
            
        Returns:
            Dict: 検証結果
        """
        try:
            if not file_path.exists():
                return {
                    "type": VerificationType.MAGIC_BYTE_CHECK.value,
                    "result": VerificationResult.INVALID.value,
                    "message": "ファイルが存在しません"
                }
            
            # ファイルの先頭32バイトを読み取り
            with open(file_path, 'rb') as f:
                header = f.read(32)
            
            if not header:
                return {
                    "type": VerificationType.MAGIC_BYTE_CHECK.value,
                    "result": VerificationResult.INVALID.value,
                    "message": "ファイルが空またはヘッダーが読み取れません"
                }
            
            # 特定フォーマットが指定されている場合
            if expected_format:
                format_lower = expected_format.lower()
                if format_lower in MagicByteChecker.MAGIC_BYTES:
                    magic_patterns = MagicByteChecker.MAGIC_BYTES[format_lower]
                    for pattern in magic_patterns:
                        if header.startswith(pattern):
                            return {
                                "type": VerificationType.MAGIC_BYTE_CHECK.value,
                                "result": VerificationResult.VALID.value,
                                "message": f"{expected_format}形式のマジックバイトが確認されました",
                                "detected_format": expected_format,
                                "magic_bytes": header[:len(pattern)].hex()
                            }
                    
                    return {
                        "type": VerificationType.MAGIC_BYTE_CHECK.value,
                        "result": VerificationResult.INVALID.value,
                        "message": f"{expected_format}形式のマジックバイトが見つかりません",
                        "header_bytes": header[:16].hex()
                    }
            
            # 汎用的な形式検出
            detected_formats = []
            for format_name, magic_patterns in MagicByteChecker.MAGIC_BYTES.items():
                for pattern in magic_patterns:
                    if header.startswith(pattern):
                        detected_formats.append(format_name)
                        break
            
            if detected_formats:
                return {
                    "type": VerificationType.MAGIC_BYTE_CHECK.value,
                    "result": VerificationResult.VALID.value,
                    "message": f"検出された形式: {', '.join(detected_formats)}",
                    "detected_formats": detected_formats
                }
            else:
                return {
                    "type": VerificationType.MAGIC_BYTE_CHECK.value,
                    "result": VerificationResult.INVALID.value,
                    "message": "既知のファイル形式のマジックバイトが見つかりません",
                    "header_bytes": header[:16].hex()
                }
            
        except Exception as e:
            return {
                "type": VerificationType.MAGIC_BYTE_CHECK.value,
                "result": VerificationResult.ERROR.value,
                "message": f"マジックバイトチェックエラー: {str(e)}"
            }


class FFmpegIntegrityChecker:
    """FFmpeg完全性検証"""
    
    @staticmethod
    async def check(file_path: Path, timeout: float = 30.0) -> Dict[str, Any]:
        """
        FFmpegによるファイル完全性チェック
        
        Args:
            file_path: 検証対象ファイル
            timeout: タイムアウト時間（秒）
            
        Returns:
            Dict: 検証結果
        """
        try:
            if not file_path.exists():
                return {
                    "type": VerificationType.FFMPEG_INTEGRITY.value,
                    "result": VerificationResult.INVALID.value,
                    "message": "ファイルが存在しません"
                }
            
            # FFmpegコマンド構築
            cmd = [
                "ffmpeg", "-v", "error", "-i", str(file_path),
                "-f", "null", "-"
            ]
            
            # プロセス実行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5)
                except:
                    process.kill()
                
                return {
                    "type": VerificationType.FFMPEG_INTEGRITY.value,
                    "result": VerificationResult.ERROR.value,
                    "message": f"FFmpeg検証がタイムアウトしました（{timeout}秒）"
                }
            
            stderr_text = stderr.decode() if stderr else ""
            
            if process.returncode == 0:
                return {
                    "type": VerificationType.FFMPEG_INTEGRITY.value,
                    "result": VerificationResult.VALID.value,
                    "message": "FFmpegによるファイル完全性検証に合格しました",
                    "ffmpeg_output": stderr_text
                }
            else:
                return {
                    "type": VerificationType.FFMPEG_INTEGRITY.value,
                    "result": VerificationResult.INVALID.value,
                    "message": f"FFmpegによるファイル完全性検証に失敗しました",
                    "ffmpeg_error": stderr_text,
                    "return_code": process.returncode
                }
                
        except FileNotFoundError:
            return {
                "type": VerificationType.FFMPEG_INTEGRITY.value,
                "result": VerificationResult.SKIPPED.value,
                "message": "FFmpegが見つかりません（スキップ）"
            }
        except Exception as e:
            return {
                "type": VerificationType.FFMPEG_INTEGRITY.value,
                "result": VerificationResult.ERROR.value,
                "message": f"FFmpeg検証中にエラーが発生しました: {str(e)}"
            }


class FileVerifier:
    """
    汎用ファイル検証エンジン
    複数の検証ルールを組み合わせてファイルの完全性を検証
    """
    
    def __init__(self):
        """初期化"""
        self.default_rules = self._create_default_rules()
        self.stats = {
            "total_verifications": 0,
            "successful_verifications": 0,
            "failed_verifications": 0
        }
    
    def _create_default_rules(self) -> List[VerificationRule]:
        """デフォルト検証ルール作成"""
        return [
            VerificationRule(
                verification_type=VerificationType.SIZE_CHECK,
                parameters={"min_size": 1024}  # 1KB以上
            ),
            VerificationRule(
                verification_type=VerificationType.EXTENSION_CHECK,
                parameters={"category": "video"}  # 動画ファイル拡張子
            ),
            VerificationRule(
                verification_type=VerificationType.MAGIC_BYTE_CHECK,
                enabled=True
            ),
            VerificationRule(
                verification_type=VerificationType.FFMPEG_INTEGRITY,
                enabled=True,
                parameters={"timeout": 30.0}
            )
        ]
    
    async def verify_file(self, 
                         file_path: Path,
                         custom_rules: Optional[List[VerificationRule]] = None) -> FileVerificationResult:
        """
        ファイル検証実行
        
        Args:
            file_path: 検証対象ファイル
            custom_rules: カスタム検証ルール
            
        Returns:
            FileVerificationResult: 検証結果
        """
        start_time = datetime.now()
        self.stats["total_verifications"] += 1
        
        # 使用する検証ルール決定
        rules = custom_rules if custom_rules is not None else self.default_rules
        
        verification_details = []
        overall_result = VerificationResult.VALID
        error_message = None
        file_size = None
        
        try:
            # ファイル基本情報取得
            if file_path.exists():
                file_size = file_path.stat().st_size
            
            # 各検証ルールを実行
            for rule in rules:
                if not rule.enabled:
                    continue
                
                detail = await self._execute_verification_rule(file_path, rule)
                verification_details.append(detail)
                
                # 検証結果の評価
                result = VerificationResult(detail["result"])
                if result == VerificationResult.INVALID:
                    overall_result = VerificationResult.INVALID
                    if not error_message:
                        error_message = detail.get("message", "検証に失敗しました")
                elif result == VerificationResult.ERROR and overall_result == VerificationResult.VALID:
                    overall_result = VerificationResult.ERROR
                    if not error_message:
                        error_message = detail.get("message", "検証中にエラーが発生しました")
            
            # 統計更新
            if overall_result == VerificationResult.VALID:
                self.stats["successful_verifications"] += 1
            else:
                self.stats["failed_verifications"] += 1
            
        except Exception as e:
            overall_result = VerificationResult.ERROR
            error_message = f"検証処理中に予期しないエラーが発生しました: {str(e)}"
            self.stats["failed_verifications"] += 1
        
        end_time = datetime.now()
        verification_time = (end_time - start_time).total_seconds()
        
        return FileVerificationResult(
            file_path=file_path,
            overall_result=overall_result,
            verification_details=verification_details,
            verification_time=verification_time,
            file_size=file_size,
            error_message=error_message,
            metadata={
                "verification_timestamp": end_time.isoformat(),
                "rules_count": len(rules),
                "enabled_rules_count": len([r for r in rules if r.enabled])
            }
        )
    
    async def _execute_verification_rule(self, file_path: Path, rule: VerificationRule) -> Dict[str, Any]:
        """検証ルール実行"""
        try:
            if rule.verification_type == VerificationType.SIZE_CHECK:
                return FileSizeChecker.check(
                    file_path, 
                    rule.parameters.get("min_size", 1024),
                    rule.parameters.get("max_size")
                )
            
            elif rule.verification_type == VerificationType.EXTENSION_CHECK:
                return FileExtensionChecker.check(
                    file_path,
                    rule.parameters.get("allowed_extensions"),
                    rule.parameters.get("category")
                )
            
            elif rule.verification_type == VerificationType.MAGIC_BYTE_CHECK:
                return MagicByteChecker.check(
                    file_path,
                    rule.parameters.get("expected_format")
                )
            
            elif rule.verification_type == VerificationType.FFMPEG_INTEGRITY:
                return await FFmpegIntegrityChecker.check(
                    file_path,
                    rule.parameters.get("timeout", 30.0)
                )
            
            else:
                return {
                    "type": rule.verification_type.value,
                    "result": VerificationResult.SKIPPED.value,
                    "message": f"未対応の検証タイプ: {rule.verification_type.value}"
                }
                
        except Exception as e:
            return {
                "type": rule.verification_type.value,
                "result": VerificationResult.ERROR.value,
                "message": f"検証ルール実行エラー: {str(e)}"
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """統計情報取得"""
        return self.stats.copy()
    
    @staticmethod
    def create_media_rules(file_type: str = "video") -> List[VerificationRule]:
        """メディアファイル用検証ルール作成"""
        rules = [
            VerificationRule(
                verification_type=VerificationType.SIZE_CHECK,
                parameters={"min_size": 1024}
            ),
            VerificationRule(
                verification_type=VerificationType.EXTENSION_CHECK,
                parameters={"category": file_type}
            ),
            VerificationRule(
                verification_type=VerificationType.MAGIC_BYTE_CHECK,
                enabled=True
            )
        ]
        
        # 動画・音声ファイルの場合はFFmpeg検証も追加
        if file_type in ["video", "audio"]:
            rules.append(VerificationRule(
                verification_type=VerificationType.FFMPEG_INTEGRITY,
                parameters={"timeout": 30.0}
            ))
        
        return rules
    
    @staticmethod
    def create_quick_rules() -> List[VerificationRule]:
        """高速検証用ルール作成（FFmpegなし）"""
        return [
            VerificationRule(
                verification_type=VerificationType.SIZE_CHECK,
                parameters={"min_size": 1024}
            ),
            VerificationRule(
                verification_type=VerificationType.EXTENSION_CHECK,
                parameters={"category": "video"}
            ),
            VerificationRule(
                verification_type=VerificationType.MAGIC_BYTE_CHECK,
                enabled=True
            )
        ]


# エクスポート
__all__ = [
    'VerificationType',
    'VerificationResult', 
    'VerificationRule',
    'FileVerificationResult',
    'FileSizeChecker',
    'FileExtensionChecker',
    'MagicByteChecker',
    'FFmpegIntegrityChecker',
    'FileVerifier'
]
"""
URL解析ユーティリティ（超シンプル版）
既存ファイルと競合しないように新規作成
"""

import re
from typing import Optional

# 既存の例外システムと統一
try:
    from exceptions_base import OneClickRecException, ErrorCode
    
    class URLValidationError(OneClickRecException):
        """URL検証エラー（統一版）"""
        def __init__(self, message: str, url: str = ""):
            super().__init__(message, ErrorCode.VALIDATION_ERROR, {"url": url})
            
except ImportError:
    # フォールバック：例外システムが無い場合
    class URLValidationError(Exception):
        """URL検証エラー（フォールバック版）"""
        pass


class TwitCastingURLParser:
    """TwitCastingのURL解析クラス"""
    
    # TwitCastingの正規表現パターン
    USER_PATTERN = re.compile(
        r'^https?://(?:www\.)?twitcasting\.tv/([a-zA-Z0-9_]{1,20})/?$'
    )
    
    MOVIE_PATTERN = re.compile(
        r'^https?://(?:www\.)?twitcasting\.tv/([a-zA-Z0-9_]{1,20})/movie/(\d+)/?$'
    )
    
    # ユーザーID検証パターン
    VALID_USER_ID = re.compile(r'^[a-zA-Z0-9_]{1,20}$')
    
    @classmethod
    def extract_user_id(cls, url: str) -> str:
        """
        URLからユーザーIDを安全に抽出
        """
        if not url or not isinstance(url, str):
            raise URLValidationError("URLが指定されていません")
        
        url = url.strip()
        
        # ユーザーページをチェック
        user_match = cls.USER_PATTERN.match(url)
        if user_match:
            user_id = user_match.group(1)
            cls._validate_user_id(user_id)
            return user_id
        
        # 動画ページをチェック
        movie_match = cls.MOVIE_PATTERN.match(url)
        if movie_match:
            user_id = movie_match.group(1)
            cls._validate_user_id(user_id)
            return user_id
        
        # どちらにもマッチしない
        raise URLValidationError(f"TwitCastingの有効なURLではありません: {url}")
    
    @classmethod
    def _validate_user_id(cls, user_id: str) -> None:
        """ユーザーIDの妥当性検証"""
        if not cls.VALID_USER_ID.match(user_id):
            raise URLValidationError(
                f"無効なユーザーID: {user_id} "
                f"(1-20文字の英数字とアンダースコアのみ)"
            )
    
    @classmethod
    def is_valid_twitcasting_url(cls, url: str) -> bool:
        """URLが有効なTwitCastingURLか判定"""
        try:
            cls.extract_user_id(url)
            return True
        except URLValidationError:
            return False


# 便利関数
def extract_user_id(url: str) -> str:
    """URLからユーザーIDを抽出（簡易版）"""
    return TwitCastingURLParser.extract_user_id(url)


def validate_twitcasting_url(url: str) -> bool:
    """TwitCastingURLの妥当性を検証"""
    return TwitCastingURLParser.is_valid_twitcasting_url(url)
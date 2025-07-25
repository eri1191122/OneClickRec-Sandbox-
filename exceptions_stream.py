# exceptions_stream.py (修正版)
"""
ワンクリ録（OneClickRec）- 配信関連例外（改善版）
世界で一番かんたんな録画アプリ

配信検出・ストリーム処理関連の例外群
Phase 2: 共通機能を持つStreamErrorは基底として維持
"""

import re
from typing import Optional, List
from exceptions_base import OneClickRecException, ErrorCode


class StreamError(OneClickRecException):
    """
    ストリーム基底エラー（共通機能保持のため維持）
    URL・プラットフォーム情報の自動解析機能を持つ。
    """
    
    def __init__(
        self, 
        message: str, 
        stream_url: Optional[str] = None, 
        error_code: ErrorCode = ErrorCode.STREAM_NOT_FOUND, 
        **kwargs
    ):
        super().__init__(message, error_code, **kwargs)
        
        self.set_detail_if_present("stream_url", stream_url)
        
        if stream_url:
            self.set_detail_if_present("platform", self._extract_platform(stream_url))
            self.set_detail_if_present("username", self._extract_username(stream_url))
    
    def _extract_platform(self, url: str) -> str:
        """URLからプラットフォーム名を自動抽出"""
        if "twitcasting.tv" in url:
            return "TwitCasting"
        elif "youtube.com" in url or "youtu.be" in url:
            return "YouTube"
        elif "twitch.tv" in url:
            return "Twitch"
        elif "tiktok.com" in url:
            return "TikTok"
        else:
            return "Unknown"
    
    def _extract_username(self, url: str) -> Optional[str]:
        """URLからユーザー名を抽出"""
        # TwitCasting
        if "twitcasting.tv" in url:
            match = re.search(r'twitcasting\.tv/([^/?]+)', url)
            return match.group(1) if match else None
        
        # YouTube (修正版)
        elif "youtube.com" in url or "youtu.be" in url:
            patterns = [
                r'youtube\.com/channel/([^/?]+)',
                r'youtube\.com/c/([^/?]+)',
                r'youtube\.com/@([^/?]+)',
                r'youtu\.be/([^/?]+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            return None

        # Twitch
        elif "twitch.tv" in url:
            match = re.search(r'twitch\.tv/([^/?]+)', url)
            return match.group(1) if match else None
        
        return None
    
    @property
    def stream_url(self) -> Optional[str]:
        return self.details.get("stream_url")
    
    @property
    def platform(self) -> Optional[str]:
        return self.details.get("platform")
    
    @property
    def username(self) -> Optional[str]:
        return self.details.get("username")


class StreamNotFoundError(StreamError):
    """ストリーム未検出エラー"""
    def __init__(self, message: str = "配信が見つかりません", stream_url: Optional[str] = None, search_attempted: Optional[bool] = None, **kwargs):
        super().__init__(message, stream_url, ErrorCode.STREAM_NOT_FOUND, **kwargs)
        self.set_detail_if_present("search_attempted", search_attempted)


class StreamOfflineError(StreamError):
    """ストリームオフラインエラー"""
    def __init__(self, message: str = "配信がオフラインです", stream_url: Optional[str] = None, last_online: Optional[str] = None, **kwargs):
        super().__init__(message, stream_url, ErrorCode.STREAM_OFFLINE, **kwargs)
        self.set_detail_if_present("last_online", last_online)


class StreamAccessError(StreamError):
    """配信アクセス制限エラーの基底"""
    def __init__(self, message: str, stream_url: Optional[str] = None, error_code: ErrorCode = ErrorCode.STREAM_PRIVATE, access_level: Optional[str] = None, **kwargs):
        super().__init__(message, stream_url, error_code, **kwargs)
        self.set_detail_if_present("access_level", access_level)


class StreamPrivateError(StreamAccessError):
    """限定配信エラー"""
    def __init__(self, message: str = "限定配信のため視聴できません", stream_url: Optional[str] = None, **kwargs):
        super().__init__(message, stream_url, ErrorCode.STREAM_PRIVATE, access_level="private", **kwargs)


class StreamPremiumError(StreamAccessError):
    """プレミアム配信エラー"""
    def __init__(self, message: str = "プレミアム配信のため視聴できません", stream_url: Optional[str] = None, **kwargs):
        super().__init__(message, stream_url, ErrorCode.STREAM_PREMIUM, access_level="premium", **kwargs)


class StreamGeoBlockedError(StreamError):
    """地域制限エラー"""
    def __init__(self, message: str = "地域制限により視聴できません", stream_url: Optional[str] = None, blocked_region: Optional[str] = None, **kwargs):
        super().__init__(message, stream_url, ErrorCode.STREAM_GEO_BLOCKED, **kwargs)
        self.set_detail_if_present("blocked_region", blocked_region)


class StreamURLInvalidError(StreamError):
    """ストリームURL無効エラー"""
    def __init__(self, message: str = "ストリームURLが無効です", stream_url: Optional[str] = None, validation_error: Optional[str] = None, **kwargs):
        super().__init__(message, stream_url, ErrorCode.STREAM_URL_INVALID, **kwargs)
        self.set_detail_if_present("validation_error", validation_error)


class StreamQualityUnavailableError(StreamError):
    """配信品質利用不可エラー"""
    def __init__(self, message: str = "指定された品質が利用できません", stream_url: Optional[str] = None, requested_quality: Optional[str] = None, available_qualities: Optional[List[str]] = None, **kwargs):
        super().__init__(message, stream_url, ErrorCode.STREAM_QUALITY_UNAVAILABLE, **kwargs)
        self.set_detail_if_present("requested_quality", requested_quality)
        self.set_detail_if_present("available_qualities", available_qualities)


# === 配信エラー専用ヘルパー関数 ===

def is_stream_access_error(exception: OneClickRecException) -> bool:
    access_errors = {ErrorCode.STREAM_PRIVATE, ErrorCode.STREAM_PREMIUM, ErrorCode.STREAM_GEO_BLOCKED}
    return exception.error_code in access_errors


def get_stream_recovery_suggestion(exception: OneClickRecException) -> str:
    recovery_messages = {
        ErrorCode.STREAM_NOT_FOUND: "URLを確認するか、配信者の状況を確認してください",
        ErrorCode.STREAM_OFFLINE: "配信開始まで待機するか、定期チェックを設定してください",
        ErrorCode.STREAM_PRIVATE: "認証してアクセス権限を取得してください",
        ErrorCode.STREAM_PREMIUM: "プレミアム会員登録が必要です",
        ErrorCode.STREAM_GEO_BLOCKED: "VPNの使用を検討してください",
        ErrorCode.STREAM_URL_INVALID: "正しいURL形式で入力してください",
        ErrorCode.STREAM_QUALITY_UNAVAILABLE: "利用可能な品質を確認してください"
    }
    base_message = recovery_messages.get(exception.error_code, "配信URLや設定を確認してください")
    
    if exception.error_code == ErrorCode.STREAM_QUALITY_UNAVAILABLE:
        available = exception.details.get("available_qualities", [])
        if available:
            base_message += f" 利用可能な品質: {', '.join(available)}"
    
    return base_message


if __name__ == "__main__":
    test_errors = [
        StreamNotFoundError("URL未検出", stream_url="https://www.youtube.com/channel/UC-hM6YJuNYVAmUWxeY9AhOQ"),
        StreamPrivateError("限定配信", stream_url="https://twitcasting.tv/private_user"),
        StreamQualityUnavailableError("品質エラー", stream_url="https://www.twitch.tv/test_user", requested_quality="1080p", available_qualities=["720p", "480p"]),
    ]
    
    print("=== 改善版配信例外テスト ===")
    for error in test_errors:
        print(f"\n例外: {error}")
        print(f"プラットフォーム: {error.platform}")
        print(f"ユーザー名: {error.username}")
        print(f"回復提案: {get_stream_recovery_suggestion(error)}")
        print("---")
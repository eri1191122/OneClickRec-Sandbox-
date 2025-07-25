"""
ワンクリ録（OneClickRec）- 認証関連例外（改善版）
世界で一番かんたんな録画アプリ

認証・Cookie・Selenium関連の例外群
Phase 2: 階層簡素化版
"""

from typing import Optional
from exceptions_base import OneClickRecException, ErrorCode


class AuthenticationError(OneClickRecException):
    """認証エラー"""
    def __init__(self, message: str, auth_method: Optional[str] = None, platform: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.AUTH_FAILED, **kwargs)
        self.set_detail_if_present("auth_method", auth_method)
        self.set_detail_if_present("platform", platform)


class AuthenticationExpiredError(OneClickRecException):
    """認証期限切れエラー"""
    def __init__(self, message: str = "認証情報が期限切れです", expired_at: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.AUTH_EXPIRED, **kwargs)
        self.set_detail_if_present("expired_at", expired_at)


class CookieInvalidError(OneClickRecException):
    """Cookie無効エラー"""
    def __init__(self, message: str = "Cookieが無効です", cookie_name: Optional[str] = None, cookie_count: Optional[int] = None, **kwargs):
        super().__init__(message, ErrorCode.COOKIE_INVALID, **kwargs)
        self.set_detail_if_present("cookie_name", cookie_name)
        self.set_detail_if_present("cookie_count", cookie_count)


class LoginRequiredError(OneClickRecException):
    """ログイン必須エラー"""
    def __init__(self, message: str = "ログインが必要です", platform: Optional[str] = None, required_scope: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.LOGIN_REQUIRED, **kwargs)
        self.set_detail_if_present("platform", platform)
        self.set_detail_if_present("required_scope", required_scope)


class SeleniumError(OneClickRecException):
    """Seleniumエラー"""
    def __init__(self, message: str, element_selector: Optional[str] = None, page_url: Optional[str] = None, selenium_action: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.SELENIUM_ERROR, **kwargs)
        self.set_detail_if_present("element_selector", element_selector)
        self.set_detail_if_present("page_url", page_url)
        self.set_detail_if_present("selenium_action", selenium_action)


class AuthRateLimitedError(OneClickRecException):
    """認証レート制限エラー"""
    def __init__(self, message: str = "認証試行回数の制限を超過しました", retry_after_seconds: Optional[int] = None, attempts_count: Optional[int] = None, **kwargs):
        super().__init__(message, ErrorCode.AUTH_RATE_LIMITED, **kwargs)
        self.set_detail_if_present("retry_after_seconds", retry_after_seconds)
        self.set_detail_if_present("attempts_count", attempts_count)


# === 認証エラー専用ヘルパー関数 ===

def is_cookie_related_error(exception: OneClickRecException) -> bool:
    """Cookie関連エラーかどうかの判定"""
    cookie_errors = {
        ErrorCode.COOKIE_INVALID,
        ErrorCode.AUTH_EXPIRED,
        ErrorCode.LOGIN_REQUIRED
    }
    return exception.error_code in cookie_errors


def is_selenium_related_error(exception: OneClickRecException) -> bool:
    """Selenium関連エラーかどうかの判定"""
    return exception.error_code == ErrorCode.SELENIUM_ERROR


def get_auth_recovery_suggestion(exception: OneClickRecException) -> str:
    """認証エラーの回復提案メッセージ"""
    if exception.error_code == ErrorCode.AUTH_EXPIRED:
        return "認証情報を更新してください"
    elif exception.error_code == ErrorCode.COOKIE_INVALID:
        return "Cookieを再取得してください"
    elif exception.error_code == ErrorCode.LOGIN_REQUIRED:
        return "ログインを実行してください"
    elif exception.error_code == ErrorCode.SELENIUM_ERROR:
        return "ブラウザ設定を確認してください"
    elif exception.error_code == ErrorCode.AUTH_RATE_LIMITED:
        retry_after = exception.details.get("retry_after_seconds", 60)
        return f"{retry_after}秒後に再試行してください"
    else:
        return "認証設定を確認してください"


if __name__ == "__main__":
    test_errors = [
        AuthenticationError("TwitCasting認証失敗", auth_method="cookie", platform="twitcasting"),
        CookieInvalidError("無効なCookie", cookie_name="user_session", cookie_count=5),
        SeleniumError("要素が見つかりません", element_selector="#login_button", page_url="https://twitcasting.tv/"),
        AuthRateLimitedError("レート制限", retry_after_seconds=300, attempts_count=5)
    ]
    
    print("=== 改善版認証例外テスト ===")
    for error in test_errors:
        print(f"\nエラー: {error}")
        print(f"Cookie関連: {is_cookie_related_error(error)}")
        print(f"Selenium関連: {is_selenium_related_error(error)}")
        print(f"回復提案: {get_auth_recovery_suggestion(error)}")
        print("---")
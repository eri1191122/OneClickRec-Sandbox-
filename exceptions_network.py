"""
ワンクリ録（OneClickRec）- ネットワーク関連例外（改善版）
世界で一番かんたんな録画アプリ

ネットワーク・通信・接続関連の例外群
Phase 2: 階層簡素化版
"""

from typing import Optional
from exceptions_base import OneClickRecException, ErrorCode


class TimeoutError(OneClickRecException):
    """タイムアウトエラー"""
    def __init__(self, message: str = "処理がタイムアウトしました", url: Optional[str] = None, timeout_seconds: Optional[float] = None, **kwargs):
        super().__init__(message, ErrorCode.TIMEOUT_ERROR, **kwargs)
        self.set_detail_if_present("url", url)
        self.set_detail_if_present("timeout_seconds", timeout_seconds)


class ConnectionError(OneClickRecException):
    """接続エラー"""
    def __init__(self, message: str = "接続に失敗しました", url: Optional[str] = None, host: Optional[str] = None, port: Optional[int] = None, **kwargs):
        super().__init__(message, ErrorCode.CONNECTION_ERROR, **kwargs)
        self.set_detail_if_present("url", url)
        self.set_detail_if_present("host", host)
        self.set_detail_if_present("port", port)


class DNSError(OneClickRecException):
    """DNS解決エラー"""
    def __init__(self, message: str = "DNS解決に失敗しました", hostname: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.DNS_ERROR, **kwargs)
        self.set_detail_if_present("hostname", hostname)


class SSLError(OneClickRecException):
    """SSL証明書エラー"""
    def __init__(self, message: str = "SSL証明書エラーが発生しました", url: Optional[str] = None, certificate_issue: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.SSL_ERROR, **kwargs)
        self.set_detail_if_present("url", url)
        self.set_detail_if_present("certificate_issue", certificate_issue)


class ProxyError(OneClickRecException):
    """プロキシエラー"""
    def __init__(self, message: str = "プロキシ接続エラーが発生しました", url: Optional[str] = None, proxy_host: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCode.PROXY_ERROR, **kwargs)
        self.set_detail_if_present("url", url)
        self.set_detail_if_present("proxy_host", proxy_host)


# === ネットワークエラー専用ヘルパー関数 ===

def is_connection_related_error(exception: OneClickRecException) -> bool:
    """接続関連エラーかどうかの判定"""
    connection_errors = {ErrorCode.CONNECTION_ERROR, ErrorCode.TIMEOUT_ERROR, ErrorCode.DNS_ERROR, ErrorCode.PROXY_ERROR}
    return exception.error_code in connection_errors


def get_network_recovery_suggestion(exception: OneClickRecException) -> str:
    """ネットワークエラーの回復提案メッセージ"""
    if exception.error_code == ErrorCode.TIMEOUT_ERROR:
        return "タイムアウト時間を延長するか、ネットワーク接続を確認してください"
    elif exception.error_code == ErrorCode.CONNECTION_ERROR:
        host = exception.details.get("host", "サーバー")
        return f"{host}への接続を確認してください。ファイアウォール設定も確認してください"
    elif exception.error_code == ErrorCode.DNS_ERROR:
        hostname = exception.details.get("hostname", "ホスト")
        return f"{hostname}のDNS設定を確認してください。別のDNSサーバーの使用も検討してください"
    elif exception.error_code == ErrorCode.SSL_ERROR:
        return "SSL証明書の有効性やシステム時刻を確認してください"
    elif exception.error_code == ErrorCode.PROXY_ERROR:
        return "プロキシ設定を確認してください"
    else:
        return "ネットワーク設定やインターネット接続を確認してください"


if __name__ == "__main__":
    test_errors = [
        TimeoutError("タイムアウト", url="https://example.com", timeout_seconds=30.0),
        ConnectionError("接続失敗", host="example.com", port=443),
        DNSError("DNS解決失敗", hostname="invalid.host.name"),
        SSLError("証明書エラー", url="https://expired.badssl.com/", certificate_issue="expired")
    ]
    
    print("=== 改善版ネットワーク例外テスト ===")
    for error in test_errors:
        print(f"\nエラー: {error}")
        print(f"接続関連: {is_connection_related_error(error)}")
        print(f"回復提案: {get_network_recovery_suggestion(error)}")
        print("---")
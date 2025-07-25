try:
    from core.verifier.engine import VerificationEngine
    from core.verifier.checkers.file_size import FileSizeStrategy
    print("✅ 成功！コードが正しく配置されました！")
except ImportError as e:
    print("❌ エラー:", e)
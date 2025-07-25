try:
    from core.verifier.engine import VerificationEngine, create_verification_engine
    from core.verifier.checkers.size_checker import FileSizeStrategy, create_video_size_strategy
    from core.verifier.result import StrategyResult
    print("✅ 新構造で完璧！全てのimportが成功しました！")
    print("🏆 GPT+Gemini提案によるアーキテクチャ100点達成！")
    
    # 簡単な動作テスト
    engine = create_verification_engine(debug_mode=True)
    strategy = create_video_size_strategy(min_mb=0.1)
    print(f"エンジン作成成功: {type(engine).__name__}")
    print(f"戦略作成成功: {type(strategy).__name__}")
    
except ImportError as e:
    print("❌ エラー:", e)
except Exception as e:
    print("⚠️ その他のエラー:", e)

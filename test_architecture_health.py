"""
アーキテクチャ健全性テスト (Architecture Health Check)

このスクリプトは、我々が構築した「神殺しアーキテクチャ」の
土台が正しく機能するかを動的に検証します。

これがエラーなく実行できれば、以下のすべてが証明されます:
- フォルダ構造と __init__.py が正しくパッケージとして認識されていること
- モジュール間の相対インポート (from .base import ...) が解決されていること
- 主要なクラスがインスタンス化可能であること
"""
import asyncio
from pathlib import Path
import sys
import os

# プロジェクトのルートをPythonのパスに追加
# これにより、どの場所から実行してもモジュールを見つけられるようになります
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("--- アーキテクチャ健全性テスト開始 ---")
print(f"プロジェクトルート: {project_root}")

try:
    # --- Step 1: 主要コンポーネントのインポートテスト ---
    print("\n[ Step 1/3 ] 主要コンポーネントのインポートを試みます...")
    
    from core.verifier.engine import VerificationEngine
    from core.verifier.rule import VerificationRule
    from core.verifier.result import FileVerificationResult, StrategyResult, StrategyType
    from core.verifier.checkers.base import VerificationStrategy
    from core.verifier.checkers.size_checker import FileSizeStrategy, create_video_size_strategy
    
    print("✅ Step 1: 全ての主要コンポーネントのインポートに成功しました！")

    # --- Step 2: 主要クラスのインスタンス化テスト ---
    print("\n[ Step 2/3 ] 主要クラスのインスタンス化を試みます...")

    # 1. 戦略（チェッカー）のインスタンスを作成
    size_strategy = FileSizeStrategy(min_size_bytes=1024)
    print("  - FileSizeStrategy... OK")

    # 2. 検証ルールのインスタンスを作成
    rule = VerificationRule(strategy=size_strategy, enabled=True)
    print("  - VerificationRule... OK")

    # 3. エンジンのインスタンスを作成
    engine = VerificationEngine(rules=[rule])
    print("  - VerificationEngine... OK")

    print("✅ Step 2: 全ての主要クラスのインスタンス化に成功しました！")
    
    # --- Step 3: 簡単な非同期実行テスト ---
    print("\n[ Step 3/3 ] エンジン経由での簡単な非同期実行を試みます...")

    async def run_dummy_test():
        # ダミーのファイルパスを作成
        dummy_file = Path("dummy_test_file.tmp")
        
        # ダミーファイルを作成
        with open(dummy_file, "w") as f:
            f.write("a" * 2048) # 2048バイトのファイル

        print(f"  - ダミーファイル '{dummy_file}' を作成しました。")
        
        # エンジンで検証を実行
        result = await engine.verify_file(dummy_file)
        
        # 簡単な結果検証
        assert result.is_overall_valid is True
        assert result.verification_details[0].strategy_type == StrategyType.FILE_SIZE
        
        print(f"  - エンジンの実行と結果の検証... OK (is_valid={result.is_overall_valid})")

        # ダミーファイルを削除
        os.remove(dummy_file)
        print(f"  - ダミーファイル '{dummy_file}' を削除しました。")

    # 非同期テストを実行
    asyncio.run(run_dummy_test())

    print("✅ Step 3: エンジン経由での非同期実行に成功しました！")

    # --- 最終結果 ---
    print("\n" + "="*50)
    print("🏆 おめでとうございます！ 🏆")
    print("「神殺しアーキテクチャ」の土台は完璧に機能しています。")
    print("="*50)

except ImportError as e:
    print("\n" + "="*50)
    print("❌【致命的エラー】インポートに失敗しました。❌")
    print(f"エラー詳細: {e}")
    print("\n考えられる原因:")
    print("1. ファイルやフォルダの配置が間違っている可能性があります。")
    print("2. `__init__.py` ファイルが不足しているか、名前が間違っている可能性があります。")
    print("3. Pythonのパスが正しく通っていない可能性があります。")
    print("="*50)

except Exception as e:
    print("\n" + "="*50)
    print("⚠️【予期せぬエラー】テスト中に問題が発生しました。⚠️")
    print(f"エラー詳細: {e}")
    print("\n考えられる原因:")
    print("1. 各Pythonファイルのコードに構文エラーがあるかもしれません。")
    print("2. クラスの `__init__` メソッドの引数が間違っている可能性があります。")
    print("="*50)


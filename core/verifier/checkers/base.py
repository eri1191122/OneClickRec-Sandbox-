"""
File Verifier - Base Checker (Abstract Base Class)

このモジュールは、すべての具体的な検証戦略（チェッカー）が
継承すべき抽象基底クラス `VerificationStrategy` を定義します。

これにより、すべてのチェッカーが統一されたインターフェースを持つことが保証されます。
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path

# 依存関係: 先ほど作成した result モジュールをインポート
from ..result import StrategyResult, StrategyType

class VerificationStrategy(ABC):
    """
    すべての検証戦略の基底クラス。
    具体的な検証ロジックは、このクラスを継承して実装します。
    """

    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType:
        """
        この戦略のタイプを返します。
        具象クラスで必ずオーバーライドしてください。
        
        例: return StrategyType.FILE_SIZE
        """
        raise NotImplementedError

    @abstractmethod
    async def check(self, file_path: Path) -> StrategyResult:
        """
        ファイルを非同期に検証し、結果を返します。
        このメソッドは、すべての具象チェッカーで実装される必要があります。
        
        Args:
            file_path: 検証対象のファイルパス
        
        Returns:
            StrategyResult: 検証結果
        """
        raise NotImplementedError


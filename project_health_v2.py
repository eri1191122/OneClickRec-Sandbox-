"""
Project Health Orchestrator v2
専門ツール統合による真の品質保証システム

設計思想:
- 自作チェックを排除し、業界標準ツールのオーケストレーターに特化
- 設定完全外部化によるハードコード撲滅
- プラグインアーキテクチャによる拡張性確保
- CI/CDパイプライン統合前提の設計
"""
import subprocess
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import sys
import time

@dataclass
class CheckResult:
    """個別チェックの結果"""
    name: str
    success: bool
    score: float  # 0.0-1.0
    details: Dict[str, Any]
    execution_time: float
    tool_output: str
    recommendations: List[str]

@dataclass
class QualityMetrics:
    """品質メトリクス"""
    code_coverage: Optional[float] = None
    type_coverage: Optional[float] = None
    lint_score: Optional[float] = None
    test_success_rate: Optional[float] = None
    security_score: Optional[float] = None
    
    def overall_score(self) -> float:
        """総合スコア計算"""
        scores = [s for s in [self.code_coverage, self.type_coverage, 
                             self.lint_score, self.test_success_rate, self.security_score] 
                 if s is not None]
        return sum(scores) / len(scores) if scores else 0.0

@dataclass
class HealthReport:
    """最終健康診断レポート"""
    overall_score: float
    check_results: List[CheckResult]
    metrics: QualityMetrics
    execution_time: float
    recommendations: List[str]
    ci_ready: bool
    
    def to_json(self) -> str:
        """JSON形式でエクスポート（CI/CD統合用）"""
        return json.dumps(asdict(self), indent=2, default=str)


class HealthCheckPlugin(ABC):
    """品質チェックプラグインの基底クラス"""
    
    @abstractmethod
    def name(self) -> str:
        """プラグイン名"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """ツールが利用可能かチェック"""
        pass
    
    @abstractmethod
    def run_check(self, config: Dict[str, Any]) -> CheckResult:
        """チェック実行"""
        pass


class PytestPlugin(HealthCheckPlugin):
    """Pytestプラグイン"""
    
    def name(self) -> str:
        return "pytest"
    
    def is_available(self) -> bool:
        """pytestの存在確認"""
        try:
            result = subprocess.run(['pytest', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def run_check(self, config: Dict[str, Any]) -> CheckResult:
        """pytest実行"""
        start_time = time.time()
        
        try:
            # カバレッジ付きでpytest実行
            cmd = ['pytest', '--cov=.', '--cov-report=json', '--tb=short', '-v']
            
            # 設定からオプション追加
            if 'test_path' in config:
                cmd.append(config['test_path'])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            execution_time = time.time() - start_time
            
            # カバレッジデータ解析
            coverage_data = self._parse_coverage()
            
            success = result.returncode == 0
            score = coverage_data.get('coverage', 0.0) / 100.0 if success else 0.0
            
            recommendations = []
            if not success:
                recommendations.append("テストが失敗しています。修正が必要です。")
            if score < 0.8:
                recommendations.append(f"コードカバレッジが{score*100:.1f}%です。80%以上を目指しましょう。")
            
            return CheckResult(
                name=self.name(),
                success=success,
                score=score,
                details={
                    "coverage_percent": coverage_data.get('coverage', 0),
                    "tests_collected": self._extract_test_count(result.stdout),
                    "failed_tests": self._extract_failed_count(result.stdout)
                },
                execution_time=execution_time,
                tool_output=result.stdout,
                recommendations=recommendations
            )
            
        except subprocess.TimeoutExpired:
            return CheckResult(
                name=self.name(),
                success=False,
                score=0.0,
                details={"error": "timeout"},
                execution_time=300.0,
                tool_output="",
                recommendations=["テストがタイムアウトしました。重いテストを見直してください。"]
            )
        except Exception as e:
            return CheckResult(
                name=self.name(),
                success=False,
                score=0.0,
                details={"error": str(e)},
                execution_time=time.time() - start_time,
                tool_output="",
                recommendations=[f"pytest実行エラー: {str(e)}"]
            )
    
    def _parse_coverage(self) -> Dict[str, Any]:
        """カバレッジJSONを解析"""
        try:
            with open('coverage.json', 'r') as f:
                data = json.load(f)
                return {"coverage": data.get('totals', {}).get('percent_covered', 0)}
        except (FileNotFoundError, json.JSONDecodeError):
            return {"coverage": 0}
    
    def _extract_test_count(self, output: str) -> int:
        """テスト数を抽出"""
        try:
            if "collected" in output:
                parts = output.split("collected")[1].split()[0]
                return int(parts)
        except:
            pass
        return 0
    
    def _extract_failed_count(self, output: str) -> int:
        """失敗テスト数を抽出"""
        try:
            if "failed" in output:
                parts = output.split("failed")[0].split()[-1]
                return int(parts)
        except:
            pass
        return 0


class MypyPlugin(HealthCheckPlugin):
    """Mypyプラグイン"""
    
    def name(self) -> str:
        return "mypy"
    
    def is_available(self) -> bool:
        try:
            result = subprocess.run(['mypy', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def run_check(self, config: Dict[str, Any]) -> CheckResult:
        """mypy実行"""
        start_time = time.time()
        
        try:
            cmd = ['mypy', '.', '--ignore-missing-imports', '--show-error-codes']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            execution_time = time.time() - start_time
            
            # エラー数から品質スコア計算
            error_count = result.stdout.count("error:")
            warning_count = result.stdout.count("note:")
            
            # 簡易スコア計算（エラーが少ないほど高スコア）
            total_issues = error_count + warning_count * 0.5
            score = max(0.0, 1.0 - (total_issues / 100.0))  # 100個でスコア0
            
            success = result.returncode == 0
            
            recommendations = []
            if error_count > 0:
                recommendations.append(f"型エラーが{error_count}個あります。修正を推奨します。")
            if warning_count > 10:
                recommendations.append(f"型ヒントの警告が{warning_count}個あります。")
            
            return CheckResult(
                name=self.name(),
                success=success,
                score=score,
                details={
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "type_coverage_estimated": score * 100
                },
                execution_time=execution_time,
                tool_output=result.stdout,
                recommendations=recommendations
            )
            
        except Exception as e:
            return CheckResult(
                name=self.name(),
                success=False,
                score=0.0,
                details={"error": str(e)},
                execution_time=time.time() - start_time,
                tool_output="",
                recommendations=[f"mypy実行エラー: {str(e)}"]
            )


class Flake8Plugin(HealthCheckPlugin):
    """Flake8プラグイン"""
    
    def name(self) -> str:
        return "flake8"
    
    def is_available(self) -> bool:
        try:
            result = subprocess.run(['flake8', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def run_check(self, config: Dict[str, Any]) -> CheckResult:
        """flake8実行"""
        start_time = time.time()
        
        try:
            cmd = ['flake8', '.', '--statistics', '--tee', '--output-file=flake8_report.txt']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            execution_time = time.time() - start_time
            
            # 警告数から品質スコア計算
            line_count = len(result.stdout.splitlines())
            score = max(0.0, 1.0 - (line_count / 50.0))  # 50個でスコア0
            
            success = result.returncode == 0
            
            recommendations = []
            if line_count > 0:
                recommendations.append(f"コードスタイルの問題が{line_count}個あります。")
            if line_count > 20:
                recommendations.append("flake8の設定を見直し、段階的に修正することを推奨します。")
            
            return CheckResult(
                name=self.name(),
                success=success,
                score=score,
                details={
                    "style_issues": line_count,
                    "lint_score": score * 100
                },
                execution_time=execution_time,
                tool_output=result.stdout,
                recommendations=recommendations
            )
            
        except Exception as e:
            return CheckResult(
                name=self.name(),
                success=False,
                score=0.0,
                details={"error": str(e)},
                execution_time=time.time() - start_time,
                tool_output="",
                recommendations=[f"flake8実行エラー: {str(e)}"]
            )


class ProjectHealthOrchestrator:
    """プロジェクト品質オーケストレーター"""
    
    def __init__(self, config_path: str = "health_check.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.plugins = self._initialize_plugins()
    
    def _load_config(self) -> Dict[str, Any]:
        """設定ファイル読み込み"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    if self.config_path.suffix == '.yaml':
                        return yaml.safe_load(f)
                    else:
                        return json.load(f)
            except Exception as e:
                print(f"⚠️ 設定ファイル読み込みエラー: {e}")
        
        # デフォルト設定
        return {
            "enabled_checks": ["pytest", "mypy", "flake8"],
            "pytest": {"test_path": "tests/"},
            "mypy": {"strict": False},
            "flake8": {"max_line_length": 88}
        }
    
    def _initialize_plugins(self) -> Dict[str, HealthCheckPlugin]:
        """プラグイン初期化"""
        available_plugins = {
            "pytest": PytestPlugin(),
            "mypy": MypyPlugin(),
            "flake8": Flake8Plugin()
        }
        
        # 利用可能なプラグインのみ登録
        return {
            name: plugin for name, plugin in available_plugins.items()
            if plugin.is_available()
        }
    
    def run_health_check(self) -> HealthReport:
        """品質チェック実行"""
        print("🎯 プロジェクト品質オーケストレーター v2 開始")
        print("=" * 60)
        
        start_time = time.time()
        check_results = []
        
        enabled_checks = self.config.get("enabled_checks", [])
        
        for check_name in enabled_checks:
            if check_name not in self.plugins:
                print(f"⚠️  {check_name}: ツールが利用できません")
                continue
            
            print(f"🔍 {check_name} 実行中...")
            
            plugin = self.plugins[check_name]
            check_config = self.config.get(check_name, {})
            result = plugin.run_check(check_config)
            
            check_results.append(result)
            
            status = "✅" if result.success else "❌"
            print(f"  {status} {check_name}: スコア{result.score*100:.1f}% ({result.execution_time:.1f}s)")
        
        # メトリクス集計
        metrics = self._calculate_metrics(check_results)
        
        # 総合評価
        overall_score = metrics.overall_score()
        execution_time = time.time() - start_time
        
        # 推奨事項集計
        all_recommendations = []
        for result in check_results:
            all_recommendations.extend(result.recommendations)
        
        # CI準備状況
        ci_ready = overall_score >= 0.8 and all(r.success for r in check_results)
        
        report = HealthReport(
            overall_score=overall_score,
            check_results=check_results,
            metrics=metrics,
            execution_time=execution_time,
            recommendations=all_recommendations,
            ci_ready=ci_ready
        )
        
        self._print_report(report)
        return report
    
    def _calculate_metrics(self, results: List[CheckResult]) -> QualityMetrics:
        """品質メトリクス計算"""
        metrics = QualityMetrics()
        
        for result in results:
            if result.name == "pytest":
                metrics.code_coverage = result.details.get("coverage_percent", 0) / 100.0
                metrics.test_success_rate = 1.0 if result.success else 0.0
            elif result.name == "mypy":
                metrics.type_coverage = result.details.get("type_coverage_estimated", 0) / 100.0
            elif result.name == "flake8":
                metrics.lint_score = result.details.get("lint_score", 0) / 100.0
        
        return metrics
    
    def _print_report(self, report: HealthReport):
        """レポート出力"""
        print("\n" + "=" * 60)
        print("📊 プロジェクト品質レポート")
        print("=" * 60)
        
        print(f"\n🎯 総合スコア: {report.overall_score*100:.1f}%")
        print(f"⏱️  実行時間: {report.execution_time:.1f}秒")
        print(f"🚀 CI準備状況: {'✅ 準備完了' if report.ci_ready else '❌ 改善必要'}")
        
        print("\n📈 品質メトリクス:")
        if report.metrics.code_coverage is not None:
            print(f"  コードカバレッジ: {report.metrics.code_coverage*100:.1f}%")
        if report.metrics.type_coverage is not None:
            print(f"  型カバレッジ: {report.metrics.type_coverage*100:.1f}%")
        if report.metrics.lint_score is not None:
            print(f"  コードスタイル: {report.metrics.lint_score*100:.1f}%")
        
        print("\n🔍 個別チェック結果:")
        for result in report.check_results:
            status = "✅" if result.success else "❌"
            print(f"  {status} {result.name}: {result.score*100:.1f}%")
        
        if report.recommendations:
            print("\n💡 改善推奨事項:")
            for i, rec in enumerate(report.recommendations[:5], 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "=" * 60)


def main():
    """メイン実行"""
    orchestrator = ProjectHealthOrchestrator()
    report = orchestrator.run_health_check()
    
    # CI/CD用JSON出力
    with open("health_report.json", "w") as f:
        f.write(report.to_json())
    
    # 終了コード設定（CI用）
    sys.exit(0 if report.ci_ready else 1)


if __name__ == "__main__":
    main()
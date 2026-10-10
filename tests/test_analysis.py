import unittest

import pandas as pd

from src.analysis import analyze_reviews
from src.strategy import build_recommendations, render_markdown_report


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame(
            [
                {"review": "质地清爽吸收快，很舒服", "rating": 5, "platform": "小红书"},
                {"review": "用了以后刺痛而且很刺激", "rating": 1, "platform": "小红书"},
                {"review": "价格太贵，性价比一般", "rating": 2, "platform": "天猫"},
                {"review": "按压泵不好用，经常挤出太多", "rating": 1, "platform": "京东"},
                {"review": "按压泵不好用，经常挤出太多", "rating": 1, "platform": "京东"},
            ]
        )

    def test_analysis_deduplicates_and_preserves_evidence(self):
        result = analyze_reviews(self.data, deduplicate=True)

        self.assertEqual(result.source_count, 5)
        self.assertEqual(result.analyzed_count, 4)
        self.assertEqual(result.duplicates_removed, 1)
        self.assertIn("使用体验", set(result.theme_summary["主题"]))
        self.assertTrue(result.evidence["包装设计"])
        self.assertEqual(result.evidence["包装设计"][0]["source_row"], 5)

    def test_negative_reviews_are_ranked_as_pains(self):
        result = analyze_reviews(self.data, deduplicate=True)
        summary = result.theme_summary.set_index("主题")

        self.assertGreater(summary.loc["包装设计", "负向率"], 0)
        self.assertGreater(summary.loc["价格价值", "痛点优先级"], 0)

    def test_strategy_report_contains_data_and_evidence(self):
        result = analyze_reviews(self.data, deduplicate=True)
        context = {
            "brand": "测试品牌",
            "product": "精华",
            "objective": "口碑诊断",
            "platform": "全平台",
        }
        recommendations = build_recommendations(result, context)
        report = render_markdown_report(result, recommendations, context)

        self.assertGreaterEqual(len(recommendations), 3)
        self.assertIn("测试品牌｜消费者洞察 Campaign Brief", report)
        self.assertIn("数据事实", report)
        self.assertIn("源 CSV 第", report)


if __name__ == "__main__":
    unittest.main()

import unittest


from src.ranking_rules import apply_hard_filters, location_tier, direction_score, rank_jobs


PROFILE = {
    "education": "bachelor degree",
    "location_scope": "Zhejiang",
    "hard_exclusions": ["劳务派遣", "外包"],
}


class RankingRuleTests(unittest.TestCase):
    def test_location_tiers_follow_confirmed_priority(self):
        self.assertEqual(location_tier("浙江省丽水市莲都区"), "lishui")
        self.assertEqual(location_tier("杭州市余杭区"), "hangzhou_jinhua")
        self.assertEqual(location_tier("金华市婺城区"), "hangzhou_jinhua")
        self.assertEqual(location_tier("浙江省宁波市"), "other_zhejiang")
        self.assertEqual(location_tier("上海市浦东新区"), "outside")
        self.assertEqual(location_tier("浙江省外长期驻场"), "outside")

    def test_dispatch_and_outsourcing_are_hard_exclusions(self):
        for phrase in ("劳务派遣", "岗位为外包制"): 
            with self.subTest(phrase=phrase):
                result = apply_hard_filters(
                    {
                        "title": "产品经理",
                        "location": "丽水",
                        "description": phrase,
                    },
                    PROFILE,
                )
                self.assertFalse(result.passed)
                self.assertTrue(result.reasons)

    def test_explicit_postgraduate_requirement_is_rejected(self):
        result = apply_hard_filters(
            {
                "title": "高级产品经理",
                "location": "杭州",
                "education": "硕士及以上",
            },
            PROFILE,
        )

        self.assertFalse(result.passed)
        self.assertIn("education_above_bachelor", result.reasons)

    def test_zhejiang_job_passes_without_salary_floor(self):
        result = apply_hard_filters(
            {
                "title": "初级产品经理",
                "location": "浙江省丽水市",
                "salary": {"min": 1, "max": 2},
                "education": "本科",
                "description": "通信硬件产品，接受现场办公。",
            },
            PROFILE,
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.location_tier, "lishui")
        self.assertEqual(result.reasons, [])

    def test_long_term_onsite_is_flagged_but_not_rejected(self):
        result = apply_hard_filters(
            {
                "title": "产品经理",
                "location": "浙江省杭州市",
                "description": "需要长期驻场，偶尔出差。",
            },
            PROFILE,
        )

        self.assertTrue(result.passed)
        self.assertIn("long_term_onsite", result.flags)

    def test_missing_location_is_outside_and_explained(self):
        result = apply_hard_filters({"title": "产品经理"}, PROFILE)

        self.assertFalse(result.passed)
        self.assertEqual(result.location_tier, "outside")
        self.assertIn("location_outside_zhejiang", result.reasons)


class DirectionScoreTests(unittest.TestCase):
    """方向匹配评分测试。"""

    def _job(self, title, desc="", tags=""):
        return {"title": title, "description": desc, "tags": tags}

    def test_communication_hardware_scores_high(self):
        score = direction_score(
            self._job("通信产品经理", "负责5G通信产品规划，物联网方案设计")
        )
        self.assertGreaterEqual(score, 70)

    def test_pet_product_scores_low(self):
        score = direction_score(
            self._job("宠物产品经理", "负责宠物食品产品设计")
        )
        self.assertLess(score, 55)

    def test_construction_scores_low(self):
        score = direction_score(
            self._job("工程施工项目经理", "负责建筑施工管理")
        )
        self.assertLess(score, 40)

    def test_ai_product_scores_high(self):
        score = direction_score(
            self._job("AI产品经理", "大模型产品规划，智能硬件")
        )
        self.assertGreaterEqual(score, 70)

    def test_generic_pm_scores_mid(self):
        score = direction_score(
            self._job("产品经理", "负责产品规划和需求分析")
        )
        self.assertGreaterEqual(score, 55)
        self.assertLessEqual(score, 85)


if __name__ == "__main__":
    unittest.main()

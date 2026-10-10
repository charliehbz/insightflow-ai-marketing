"""Turn analysis outputs into evidence-linked marketing recommendations."""

from __future__ import annotations

from datetime import datetime

from src.analysis import AnalysisResult


PLAYBOOK = {
    "功效表现": {
        "tension": "消费者需要更具体、可验证的功效证据，而不是抽象承诺。",
        "idea": "制作“7 天真实使用日记”内容，用统一光线和同一指标展示使用前后变化，并解释个体差异。",
        "message": "把功效承诺改写为可观察、可验证的阶段性变化。",
        "kpi": "内容完播率、功效关键词正向评论率、收藏率",
    },
    "使用体验": {
        "tension": "肤感问题会在消费者感知功效前中断使用，直接影响口碑和复购。",
        "idea": "制作不同肤质与叠涂场景的实测短视频，清楚说明用量、顺序和等待时间。",
        "message": "减少试错：告诉消费者什么肤质、什么步骤下体验最佳。",
        "kpi": "负向体验提及率、教程保存率、试用转化率",
    },
    "价格价值": {
        "tension": "消费者不是只嫌贵，而是尚未建立价格与使用价值之间的换算。",
        "idea": "把单瓶价格拆成单次使用成本，并与容量、使用周期和核心成分证据一起呈现。",
        "message": "用每次使用价值替代单一价格比较。",
        "kpi": "商品页转化率、优惠领取率、价格负向提及率",
    },
    "包装设计": {
        "tension": "包装故障是高确定性的体验损失，会放大消费者对品质的不信任。",
        "idea": "先推动包装问题闭环，再用开箱说明和售后承诺降低顾虑；避免只用传播掩盖产品问题。",
        "message": "让取用体验和售后承诺都可预期。",
        "kpi": "包装相关投诉率、售后解决时长、负向评论率",
    },
    "服务物流": {
        "tension": "履约体验影响活动期口碑，营销放量可能同步放大服务缺口。",
        "idea": "按平台拆分履约问题，在活动素材中明确发货预期，并建立客服高频问题快捷回复。",
        "message": "在购买前说清预期，在问题发生后快速闭环。",
        "kpi": "平均响应时长、物流负向提及率、退款率",
    },
    "信任预期": {
        "tension": "宣传表达与真实体验之间存在落差，消费者需要证据链来恢复信任。",
        "idea": "将绝对化话术改成“适用人群 + 使用条件 + 证据来源”，并制作成分与功效问答内容。",
        "message": "从强承诺转向有边界的可信解释。",
        "kpi": "信任相关负向率、问答互动率、品牌搜索转化率",
    },
    "其他": {
        "tension": "未归类反馈说明现有主题框架仍有盲区，需要人工抽查。",
        "idea": "对高互动或极端评分评论进行人工复核，补充主题词典后再运行分析。",
        "message": "保留人机协作，避免模型把未知问题误判为无问题。",
        "kpi": "人工复核覆盖率、新主题发现数",
    },
}


def build_recommendations(
    result: AnalysisResult, context: dict[str, str], limit: int = 3
) -> list[dict[str, object]]:
    """Select high-priority themes and turn them into actionable opportunities."""

    ranked = result.theme_summary.copy()
    non_other = ranked[ranked["主题"] != "其他"]
    if not non_other.empty:
        ranked = non_other

    recommendations: list[dict[str, object]] = []
    for rank, (_, row) in enumerate(ranked.head(limit).iterrows(), start=1):
        theme = str(row["主题"])
        play = PLAYBOOK.get(theme, PLAYBOOK["其他"])
        sample_evidence = result.evidence.get(theme, [])
        recommendations.append(
            {
                "rank": rank,
                "theme": theme,
                "title": f"机会 {rank}｜{theme}",
                "data_fact": (
                    f"{theme}占 {row['声量占比']:.1f}% 的评论，其中负向率 "
                    f"{row['负向率']:.1f}%，痛点优先级为 {row['痛点优先级']:.1f}。"
                ),
                "consumer_story": play["tension"],
                "strategic_inference": (
                    f"建议围绕“{play['message']}”组织 {context.get('objective', '营销')} 内容，"
                    "并先用小样本 A/B 测试验证，而不是直接扩大投放。"
                ),
                "content_idea": play["idea"],
                "kpi": play["kpi"],
                "evidence": sample_evidence,
            }
        )
    return recommendations


def render_markdown_report(
    result: AnalysisResult,
    recommendations: list[dict[str, object]],
    context: dict[str, str],
) -> str:
    """Build a portable Campaign Brief in Markdown."""

    positive = result.sentiment_summary.set_index("情绪").loc["正向", "占比"]
    negative = result.sentiment_summary.set_index("情绪").loc["负向", "占比"]
    lines = [
        f"# {context.get('brand', '品牌')}｜消费者洞察 Campaign Brief",
        "",
        f"- 产品/品类：{context.get('product', '未填写')}",
        f"- 营销目标：{context.get('objective', '未填写')}",
        f"- 重点平台：{context.get('platform', '全平台')}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 数据与方法",
        "",
        f"共导入 {result.source_count} 条评论，分析 {result.analyzed_count} 条，去除重复 {result.duplicates_removed} 条。",
        f"正向占比 {positive:.1f}%，负向占比 {negative:.1f}%。",
        f"方法说明：{result.method_note}",
        "",
        "> 结论基于当前样本，仅作为营销策略初稿；模拟数据不代表真实市场表现。",
        "",
        "## 优先机会",
        "",
    ]

    for item in recommendations:
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"**数据事实：** {item['data_fact']}",
                "",
                f"**消费者张力：** {item['consumer_story']}",
                "",
                f"**策略判断：** {item['strategic_inference']}",
                "",
                f"**内容动作：** {item['content_idea']}",
                "",
                f"**建议指标：** {item['kpi']}",
                "",
                "**证据样本：**",
            ]
        )
        for evidence in item["evidence"][:2]:
            lines.append(
                f"- “{evidence['review']}” — {evidence.get('platform', '未知平台')}，"
                f"情绪得分 {evidence['score']:.2f}，源 CSV 第 {evidence['source_row']} 行"
            )
        lines.append("")

    lines.extend(
        [
            "## 建议验证方式",
            "",
            "1. 人工复核每个主题的代表评论，修正反讽、歧义和行业术语。",
            "2. 对优先内容方向进行小样本 A/B 测试，记录完播、收藏、互动及转化指标。",
            "3. 将新评论按周追加，观察主题负向率是否下降，再决定是否扩大投放。",
            "",
            "---",
            "由 InsightFlow MVP 生成。所有策略建议均需营销人员复核。",
        ]
    )
    return "\n".join(lines)

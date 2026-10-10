"""Streamlit entry point for InsightFlow."""

from __future__ import annotations

from html import escape
from pathlib import Path
from time import perf_counter

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analysis import AnalysisResult, analyze_reviews
from src.data import STANDARD_COLUMNS, load_and_validate
from src.strategy import build_recommendations, render_markdown_report


APP_ROOT = Path(__file__).resolve().parent
SAMPLE_PATH = APP_ROOT / "data" / "sample_reviews.csv"


st.set_page_config(
    page_title="InsightFlow｜消费者洞察助手",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1180px;}
        [data-testid="stSidebar"] {background: #f7f9fc;}
        .hero {
            padding: 1.5rem 1.6rem;
            border: 1px solid #dce5f2;
            border-radius: 18px;
            background: linear-gradient(135deg, #f7fbff 0%, #eef4ff 100%);
            margin-bottom: 1.2rem;
        }
        .hero h1 {margin: 0 0 .35rem 0; color: #173a67; font-size: 2rem;}
        .hero p {margin: 0; color: #48617d; line-height: 1.65;}
        .step-chip {
            display: inline-block;
            padding: .28rem .65rem;
            margin: .3rem .25rem .3rem 0;
            border-radius: 99px;
            color: #2456a6;
            background: #eaf2ff;
            font-size: .88rem;
        }
        .notice {
            padding: .8rem 1rem;
            border-left: 4px solid #efaa35;
            background: #fff8e8;
            border-radius: 8px;
            color: #644b22;
        }
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid #e2e8f0;
            padding: .8rem;
            border-radius: 14px;
        }
        .keyword-chip {
            display: inline-block;
            padding: .3rem .7rem;
            margin: .22rem .18rem;
            border: 1px solid #cad9ef;
            border-radius: 99px;
            background: #f4f8ff;
            color: #264f84;
        }
        .strategy-card {
            border: 1px solid #dce5f2;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            margin: .7rem 0;
            background: #ffffff;
        }
        .fact-label {color: #2456a6; font-weight: 700;}
        .inference-label {color: #89580d; font-weight: 700;}
    </style>
    """,
    unsafe_allow_html=True,
)


def render_header() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>InsightFlow</h1>
            <p>将碎片化消费者评论转化为可追溯的用户痛点、内容机会与营销行动建议。</p>
            <div style="margin-top:.75rem">
                <span class="step-chip">① 上传评论</span>
                <span class="step-chip">② 数据校验</span>
                <span class="step-chip">③ AI 洞察</span>
                <span class="step-chip">④ Campaign Brief</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> dict[str, str]:
    with st.sidebar:
        st.header("分析背景")
        brand = st.text_input("品牌名称", value="LumiSkin（模拟品牌）")
        product = st.text_input("产品/品类", value="舒缓保湿精华")
        objective = st.selectbox(
            "营销目标",
            ["新品上市", "内容优化", "口碑诊断", "活动复盘", "竞品洞察"],
        )
        platform = st.selectbox(
            "重点平台",
            ["全平台", "小红书", "抖音", "天猫", "京东"],
        )
        st.divider()
        st.caption("当前版本：本地可解释 AI 洞察 MVP，不调用付费模型 API。")
    return {
        "brand": brand,
        "product": product,
        "objective": objective,
        "platform": platform,
    }


def dataframe_to_template() -> bytes:
    template = pd.DataFrame(
        [
            {
                "review": "示例：质地清爽，但价格偏高。",
                "rating": 3,
                "date": "2026-10-01",
                "platform": "小红书",
            }
        ]
    )
    return template.to_csv(index=False).encode("utf-8-sig")


def render_validation_summary(result) -> None:
    data = result.dataframe
    metric_columns = st.columns(4)
    metric_columns[0].metric("有效评论", f"{len(data):,}")
    metric_columns[1].metric("重复评论", f"{result.duplicate_reviews:,}")
    metric_columns[2].metric("有评分", f"{int(data['rating'].notna().sum()):,}")
    metric_columns[3].metric("覆盖平台", f"{data['platform'].dropna().nunique():,}")

    if result.renamed_columns:
        rename_text = "、".join(
            f"{source} → {target}" for source, target in result.renamed_columns.items()
        )
        st.caption(f"自动字段映射：{rename_text}")

    for warning in result.warnings:
        st.warning(warning, icon="⚠️")

    st.dataframe(data.head(20), use_container_width=True, hide_index=True)


def _sentiment_value(result: AnalysisResult, label: str) -> float:
    row = result.sentiment_summary[result.sentiment_summary["情绪"] == label]
    return float(row.iloc[0]["占比"]) if not row.empty else 0.0


def render_insight_dashboard(result: AnalysisResult) -> None:
    positive = _sentiment_value(result, "正向")
    negative = _sentiment_value(result, "负向")
    metrics = st.columns(4)
    metrics[0].metric("分析评论", f"{result.analyzed_count:,}")
    metrics[1].metric("正向占比", f"{positive:.1f}%")
    metrics[2].metric("负向占比", f"{negative:.1f}%")
    metrics[3].metric("已去重", f"{result.duplicates_removed:,}")

    left, right = st.columns([0.9, 1.4])
    with left:
        sentiment_figure = px.pie(
            result.sentiment_summary,
            names="情绪",
            values="评论数",
            hole=0.58,
            color="情绪",
            color_discrete_map={"正向": "#3fa67a", "中性": "#9aa6b2", "负向": "#e06a5f"},
        )
        sentiment_figure.update_layout(
            title="情绪结构", margin=dict(l=10, r=10, t=50, b=10), legend_orientation="h"
        )
        st.plotly_chart(sentiment_figure, use_container_width=True)
    with right:
        theme_figure = px.bar(
            result.theme_summary.sort_values("痛点优先级"),
            x="痛点优先级",
            y="主题",
            orientation="h",
            color="负向率",
            color_continuous_scale=["#d9e8fb", "#2456a6"],
            hover_data=["评论数", "声量占比", "负向率"],
        )
        theme_figure.update_layout(
            title="痛点优先级（声量 × 负向率 × 严重度，组内归一）",
            margin=dict(l=10, r=10, t=50, b=10),
            coloraxis_colorbar_title="负向率%",
        )
        st.plotly_chart(theme_figure, use_container_width=True)

    st.subheader("高频关键词")
    chips = "".join(
        f'<span class="keyword-chip">{escape(str(row["关键词"]))} · {row["重要度"]:.1f}</span>'
        for _, row in result.keywords.iterrows()
    )
    st.markdown(chips or "暂无可用关键词", unsafe_allow_html=True)

    st.subheader("主题诊断")
    st.dataframe(
        result.theme_summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "声量占比": st.column_config.NumberColumn(format="%.1f%%"),
            "负向率": st.column_config.NumberColumn(format="%.1f%%"),
            "平均情绪": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f"),
            "痛点优先级": st.column_config.ProgressColumn(min_value=0.0, max_value=100.0, format="%.1f"),
        },
    )

    if not result.platform_summary.empty and len(result.platform_summary) > 1:
        platform_long = result.platform_summary.melt(
            id_vars="平台", value_vars=["正向", "中性", "负向"], var_name="情绪", value_name="评论数"
        )
        platform_figure = px.bar(
            platform_long,
            x="平台",
            y="评论数",
            color="情绪",
            barmode="stack",
            color_discrete_map={"正向": "#3fa67a", "中性": "#9aa6b2", "负向": "#e06a5f"},
            title="平台情绪对比",
        )
        platform_figure.update_layout(margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(platform_figure, use_container_width=True)

    st.subheader("证据回溯")
    st.caption("痛点结论与原始评论绑定；CSV 行号已包含表头偏移，便于人工复核。")
    for _, row in result.theme_summary.head(4).iterrows():
        theme = str(row["主题"])
        with st.expander(f"{theme}｜负向率 {row['负向率']:.1f}%｜优先级 {row['痛点优先级']:.1f}"):
            for item in result.evidence.get(theme, []):
                st.write(f"“{item['review']}”")
                st.caption(
                    f"{item.get('platform', '未知平台')} · {item['sentiment']} · "
                    f"情绪得分 {item['score']:.2f} · CSV 第 {item['source_row']} 行"
                )

    with st.expander("查看分析方法与逐条结果"):
        st.caption(result.method_note)
        st.dataframe(
            result.dataframe[["review", "rating", "platform", "情绪", "情绪得分", "主题"]],
            use_container_width=True,
            hide_index=True,
        )


def render_campaign_brief(
    result: AnalysisResult,
    recommendations: list[dict[str, object]],
    markdown_report: str,
) -> None:
    st.subheader("营销机会优先级")
    st.caption("蓝色为样本事实，棕色为策略推断；两者明确分开，避免把模型建议包装成数据结论。")
    for item in recommendations:
        st.markdown(
            f"""
            <div class="strategy-card">
                <h4>{escape(str(item['title']))}</h4>
                <p><span class="fact-label">数据事实：</span>{escape(str(item['data_fact']))}</p>
                <p><span class="inference-label">策略推断：</span>{escape(str(item['strategic_inference']))}</p>
                <p><strong>内容动作：</strong>{escape(str(item['content_idea']))}</p>
                <p><strong>验证指标：</strong>{escape(str(item['kpi']))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.download_button(
        "下载 Campaign Brief（Markdown）",
        data=markdown_report.encode("utf-8"),
        file_name="InsightFlow_Campaign_Brief.md",
        mime="text/markdown",
        type="primary",
        use_container_width=True,
    )

    with st.expander("预览完整 Brief"):
        st.markdown(markdown_report)


def main() -> None:
    render_header()
    context = render_sidebar()

    st.markdown(
        '<div class="notice"><strong>数据说明：</strong>内置数据为程序生成的模拟评论，仅用于功能演示，不代表任何真实品牌或消费者。</div>',
        unsafe_allow_html=True,
    )

    st.subheader("1. 导入消费者评论")
    source_type = st.radio(
        "选择数据来源",
        ["使用模拟数据", "上传 CSV"],
        horizontal=True,
        label_visibility="collapsed",
    )

    uploaded_file = None
    if source_type == "上传 CSV":
        uploaded_file = st.file_uploader("上传 UTF-8 CSV 文件", type=["csv"])
        st.caption("评论文本为必需字段；评分、日期和平台为推荐字段。支持中英文常见列名自动映射。")
        st.download_button(
            "下载 CSV 模板",
            data=dataframe_to_template(),
            file_name="insightflow_template.csv",
            mime="text/csv",
        )
    else:
        st.caption("模拟数据包含评论、1–5 分评分、日期、平台及模拟数据声明。")

    validate_clicked = st.button("校验并载入数据", type="primary", use_container_width=True)

    if validate_clicked:
        try:
            if source_type == "使用模拟数据":
                if not SAMPLE_PATH.exists():
                    raise FileNotFoundError("示例数据尚未生成，请先运行 scripts/generate_sample_data.py。")
                result = load_and_validate(SAMPLE_PATH)
            elif uploaded_file is None:
                st.error("请先选择一个 CSV 文件。")
                return
            else:
                result = load_and_validate(uploaded_file.getvalue())
        except (ValueError, FileNotFoundError) as exc:
            st.error(str(exc))
            return

        if not result.is_valid:
            for error in result.errors:
                st.error(error)
            return

        st.session_state["validated_data"] = result.dataframe
        st.session_state["validation_result"] = result
        st.session_state["analysis_context"] = context
        st.session_state.pop("analysis_result", None)
        st.session_state.pop("recommendations", None)
        st.session_state.pop("markdown_report", None)

    if "validation_result" in st.session_state:
        st.success("数据校验通过，可以进入洞察分析。", icon="✅")
        render_validation_summary(st.session_state["validation_result"])

        analysis_controls = st.columns([1, 2])
        with analysis_controls[0]:
            deduplicate = st.checkbox("分析前去除重复评论", value=True)
        with analysis_controls[1]:
            st.caption("建议保留去重：避免重复文本放大某一主题；原始数据不会被修改。")

        if st.button("开始洞察分析", type="primary", use_container_width=True):
            started = perf_counter()
            try:
                with st.spinner("正在识别情绪、主题、关键词与可追溯证据…"):
                    analysis = analyze_reviews(
                        st.session_state["validated_data"], deduplicate=deduplicate
                    )
                    recommendations = build_recommendations(analysis, context)
                    report = render_markdown_report(analysis, recommendations, context)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["analysis_result"] = analysis
                st.session_state["recommendations"] = recommendations
                st.session_state["markdown_report"] = report
                st.session_state["analysis_context"] = context
                st.session_state["analysis_seconds"] = perf_counter() - started
                st.success(
                    f"分析完成：{analysis.analyzed_count} 条评论，用时 "
                    f"{st.session_state['analysis_seconds']:.2f} 秒。",
                    icon="✨",
                )

    st.divider()
    overview_tab, insight_tab, brief_tab = st.tabs(
        ["数据质量", "洞察看板", "Campaign Brief"]
    )
    with overview_tab:
        st.write("字段标准：")
        st.code(", ".join(STANDARD_COLUMNS), language="text")
        st.caption("已完成 CSV 解析、字段映射、空值检查、评分校验、日期解析和重复检测。")
    with insight_tab:
        if "analysis_result" not in st.session_state:
            st.info("完成数据校验后，点击“开始洞察分析”生成结果。")
        else:
            render_insight_dashboard(st.session_state["analysis_result"])
    with brief_tab:
        if "analysis_result" not in st.session_state:
            st.info("运行洞察分析后，将自动生成三条营销机会与可下载 Brief。")
        else:
            render_campaign_brief(
                st.session_state["analysis_result"],
                st.session_state["recommendations"],
                st.session_state["markdown_report"],
            )

    st.caption("InsightFlow MVP｜所有分析结果均需营销人员复核。")


if __name__ == "__main__":
    main()

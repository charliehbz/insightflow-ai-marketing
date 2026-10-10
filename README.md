# InsightFlow

InsightFlow 是一个面向品牌策略、内容运营和消费者洞察人员的 AI 营销工具原型。它将消费者评论 CSV 转化为可追溯的用户痛点、内容机会和 Campaign Brief。

**在线演示：** [https://insightflow-ai-marketing.streamlit.app/](https://insightflow-ai-marketing.streamlit.app/)

**推荐体验路径：** 使用模拟数据 → 校验并载入数据 → 开始洞察分析 → 查看洞察看板与 Campaign Brief。

> 当前状态：可运行 MVP。已完成数据导入、可解释 AI 洞察、证据回溯、营销机会建议和 Campaign Brief 下载。

## 为什么做这个工具

营销团队经常需要人工阅读数百条消费者评论，再整理主题、情绪和代表性反馈。这个过程耗时，而且分析结论与原始评论之间容易失去对应关系。InsightFlow 的目标是先自动完成重复的数据处理，再让营销人员集中精力判断洞察是否合理、策略是否可执行。

## 当前功能

- 使用内置模拟评论或上传自定义 CSV；
- 自动识别常见中英文列名；
- 强制校验评论文本字段；
- 清理空评论；
- 检查重复评论；
- 将评分转为数值并校验 1–5 范围；
- 解析日期并提示无效值；
- 展示数据质量摘要和前 20 条记录；
- 下载标准 CSV 模板；
- 使用“文本情绪 + 评分”识别正向、中性和负向反馈；
- 将评论归入功效、体验、价格、包装、服务、信任等营销主题；
- 以“主题声量 × 负向程度”计算痛点优先级；
- 输出 TF-IDF 关键词、平台情绪对比和主题看板；
- 每项洞察回溯至代表性原文与源 CSV 行号；
- 自动生成 3 条内容机会及可下载的 Markdown Campaign Brief。

## AI 工作流

```text
评论 CSV
  → 字段映射与质量校验
  → 去重（可选）
  → SnowNLP/营销情感词典 + 评分校正
  → 可解释主题规则 + TF-IDF 关键词
  → 痛点优先级与代表评论证据
  → 用户张力、内容动作、验证指标
  → Campaign Brief
```

当前版本不调用任何付费模型 API。策略输出基于透明规则和营销框架，目的是快速形成“可复核的分析初稿”，不替代研究员判断。

## CSV 格式

只有评论文本为必需字段，其余字段为推荐字段。

| 标准字段 | 是否必需 | 示例 | 支持的常见别名 |
|---|---|---|---|
| `review` | 是 | 质地清爽，但价格偏高 | `comment`、`text`、`评论`、`评论内容` |
| `rating` | 否 | 3 | `score`、`star`、`评分`、`星级` |
| `date` | 否 | 2026-10-01 | `created_at`、`time`、`日期` |
| `platform` | 否 | 小红书 | `channel`、`source`、`平台`、`渠道` |

文件建议保存为 UTF-8 CSV。系统也会尝试读取 GB18030 编码。

## 本地运行

建议使用 Python 3.11 或 3.12。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_sample_data.py
streamlit run app.py
```

Windows 激活虚拟环境：

```powershell
.venv\Scripts\activate
```

## 项目结构

```text
insightflow/
├── app.py                         # Streamlit 入口
├── requirements.txt               # Python 依赖
├── data/
│   └── sample_reviews.csv          # 生成的模拟数据
├── scripts/
│   └── generate_sample_data.py     # 可复现的模拟数据生成器
├── src/
│   ├── __init__.py
│   ├── data.py                     # CSV 读取、字段映射和校验
│   ├── analysis.py                 # 情绪、主题、关键词、痛点与证据
│   └── strategy.py                 # 营销建议和 Markdown Brief
├── tests/
│   └── test_analysis.py            # 核心工作流测试
└── README.md
```

## 模拟数据声明

`data/sample_reviews.csv` 由脚本生成，仅用于产品功能演示：

- 不来自任何真实品牌；
- 不包含真实消费者个人信息；
- 不代表真实市场结论；
- 所有演示结果都应标注为模拟数据分析。

固定随机种子可以复现同一份数据：

```bash
python scripts/generate_sample_data.py --count 180 --seed 20271009 --duplicate-rate 0.08
```

## 下一步路线

1. 增加用户自定义主题词典与人工纠错；
2. 接入经授权的真实评论数据并建立基准评测集；
3. 增加日期趋势、竞品对比及可配置指标；
4. 在获得 API 预算后，用大模型增强主题归纳和跨语言解释；
5. GitHub 和 Streamlit Community Cloud 部署。

## 隐私与限制

- 当前版本在应用会话中处理上传文件，不写入项目数据库；
- 请勿上传姓名、电话、订单号等个人敏感信息；
- 后续模型结果只能作为营销分析初稿，需要人工复核；
- 模型对于反讽、行业术语和极短文本可能判断错误。

## 技术栈

- Streamlit
- Pandas / NumPy
- jieba
- scikit-learn
- SnowNLP
- Plotly

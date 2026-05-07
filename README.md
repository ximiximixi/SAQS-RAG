# RAG-Judge-Reliability

中文 | [English](#english)

## 中文

这是一个围绕 **RAG faithfulness evaluation 中 LLM-as-a-Judge 可靠性审计** 的实验代码仓库。推荐仓库名为 `RAG-Judge-Reliability`，也可以简称 `RJRA`。

本仓库只保留代码、配置、轻量实验产物和阶段性实验文档；论文正文、LaTeX 源码、投稿 PDF、投稿打包文件、写作素材、API key、本地原始大数据和本地日志都不进入 Git。

### 核心问题

RAG 系统常用 LLM-as-a-Judge 来判断答案是否忠实于检索证据，但单次 judge verdict 本身可能不可靠。这个项目关注的问题是：

> 在不训练新大模型的前提下，能否用低成本、可审计的信号预测哪些 judge verdict 应该被送去人工复核？

我们不直接比较“哪个 judge 最强”，而是建模“某一次自动裁决什么时候不该被直接相信”。

### 当前实验闭环

- 构建 100 条风险富集的 human gold 审计样本。
- 收集多模型、多提示词、多审计条件下的 judge 输出。
- 提取 disagreement、confidence、issue categories、strict/assisted signals、文本统计和协议元数据等可观测特征。
- 训练 reliability predictor，预测 verdict-level / item-level unreliability。
- 使用 grouped cross-validation、bootstrap confidence intervals、ablation、calibration、audit-gain 和 qualitative case analysis 做验证。

### 仓库结构

```text
.
├── annotation_ui/       # 本地轻量人工标注 UI
├── configs/             # prompt 和实验配置
├── data/
│   └── audit/           # 轻量审计结果、human gold、弱监督和 reliability 输出
├── docs/                # 实验协议、标注规范和阶段冻结文档
│   └── freezes/         # 实验阶段记录，不含投稿正文/PDF
└── scripts/             # 数据处理、模型调用、对比分析和 reliability 实验脚本
```

### 重要文档

- `docs/main_experiment_protocol.md`: 主实验协议。
- `docs/reliability_prediction_plan.md`: reliability predictor 的目标、特征和评估计划。
- `docs/audit_annotation_guidelines.md`: 人工审计标注规范。
- `docs/freezes/2026-05-06_26_human_gold_audit_results.md`: human gold 审计结果冻结。
- `docs/freezes/2026-05-06_29_reliability_prediction_results.md`: reliability prediction 主结果冻结。
- `docs/freezes/2026-05-06_30_interpretability_and_qualitative_cases.md`: feature importance 和典型案例分析冻结。

### 复现实验

常用脚本位于 `scripts/`：

```powershell
python scripts/run_reliability_prediction_experiments.py
python scripts/analyze_reliability_interpretability.py
python scripts/build_reliability_prediction_tables.py
python scripts/build_qualitative_case_studies.py
python scripts/validate_reliability.py
```

具体运行前请先确认 `.env` 已在本地配置，且 raw benchmark 数据已经放在本地未跟踪目录中。

### 本地标注 UI

```powershell
python annotation_ui/serve_audit_ui.py --port 8765
```

浏览器访问：

```text
http://127.0.0.1:8765
```

### 不进入 Git 的内容

- `.env` 和所有 API key。
- `paper/`、`submission/` 和投稿打包文件。
- 写作 skill、论文图表生成素材和投稿策略文档。
- `data/raw/`、`data/pilot/` 等大体积或可重建的本地数据。
- LaTeX build artifacts、本地日志、临时缓存。

### 数据边界

仓库保留的是用于代码复现和实验核对的轻量结果。大规模 benchmark 原始数据、完整 API 调用缓存和密钥均应保留在本地或受控存储中。

---

## English

This repository contains the experimental codebase for **auditing LLM-as-a-Judge reliability in RAG faithfulness evaluation**. The recommended repository name is `RAG-Judge-Reliability`, with `RJRA` as a short acronym.

The repository keeps code, configurations, compact experiment outputs, and frozen experiment records only. Manuscript sources, review PDFs, submission packages, writing assets, API keys, large raw datasets, and local logs are intentionally excluded from Git.

### Research Question

RAG systems often use LLM-as-a-Judge to decide whether an answer is faithful to retrieved evidence, but a single judge verdict can itself be unreliable. This project asks:

> Without training a new large model, can low-cost and auditable signals predict which judge verdicts should be routed to human audit?

The goal is not to decide which judge is best on average. The goal is to estimate when a concrete automatic verdict should not be trusted directly.

### Experiment Closure

- Build a 100-item risk-enriched human gold audit set.
- Collect judge outputs under multiple models, prompts, and audit conditions.
- Extract observable features from disagreement, confidence, issue categories, strict/assisted signals, text statistics, and protocol metadata.
- Train reliability predictors for verdict-level and item-level unreliability.
- Evaluate with grouped cross-validation, bootstrap confidence intervals, ablations, calibration, audit-gain analysis, and qualitative case studies.

### Repository Layout

```text
.
├── annotation_ui/       # Lightweight local human annotation UI
├── configs/             # Prompt and experiment configuration
├── data/
│   └── audit/           # Compact audit, human gold, weak supervision, and reliability outputs
├── docs/                # Experiment protocols, annotation guidelines, and freeze records
│   └── freezes/         # Experiment-stage records, excluding manuscript/submission assets
└── scripts/             # Data processing, model calls, comparison, and reliability experiments
```

### Key Documents

- `docs/main_experiment_protocol.md`: main experiment protocol.
- `docs/reliability_prediction_plan.md`: reliability predictor targets, features, and evaluation plan.
- `docs/audit_annotation_guidelines.md`: human audit annotation guidelines.
- `docs/freezes/2026-05-06_26_human_gold_audit_results.md`: frozen human gold audit results.
- `docs/freezes/2026-05-06_29_reliability_prediction_results.md`: frozen reliability prediction results.
- `docs/freezes/2026-05-06_30_interpretability_and_qualitative_cases.md`: frozen feature-importance and qualitative analyses.

### Reproducing Experiments

Common scripts are located in `scripts/`:

```powershell
python scripts/run_reliability_prediction_experiments.py
python scripts/analyze_reliability_interpretability.py
python scripts/build_reliability_prediction_tables.py
python scripts/build_qualitative_case_studies.py
python scripts/validate_reliability.py
```

Before running experiments, make sure `.env` is configured locally and raw benchmark files are available in untracked local directories.

### Local Annotation UI

```powershell
python annotation_ui/serve_audit_ui.py --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

### Excluded From Git

- `.env` and all API keys.
- `paper/`, `submission/`, and submission packages.
- Writing skills, manuscript figure-generation assets, and submission-planning documents.
- `data/raw/`, `data/pilot/`, and other large or reconstructable local data.
- LaTeX build artifacts, local logs, and temporary caches.

### Data Boundary

The repository retains compact outputs needed for reproducibility checks. Large benchmark downloads, full API-call caches, and credentials should remain local or in controlled storage.

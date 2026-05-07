# RAG 人工审计标注中文指南

来源：本文件翻译并整理自已经冻结的 `docs/audit_annotation_guidelines.md`、Freeze 16、Freeze 20、Freeze 21。  
用途：辅助人工标注时统一标准。最终标注以本文件和原始英文冻结文档共同为准。

## 1. 标注目标

判断一个 RAG 系统生成的答案，是否忠实于给定证据。

只使用当前页面展示的证据进行判断。不要使用外部知识，即使你知道真实答案，也不要把外部知识带入标注。

你要判断的是：

```text
答案里的重要说法，是否被提供的证据支持。
```

而不是：

```text
这个答案在现实世界里是不是正确。
```

## 2. 三个主标签

每条样本必须且只能选择一个主标签：

- `faithful`：忠实
- `unfaithful`：不忠实
- `insufficient`：证据不足

## 3. faithful / 忠实

选择 `faithful` 的条件：

```text
答案中的每个重要 claim 都能被给定证据支持。
```

如果只是措辞略有不同，但意思被证据支持，可以标 `faithful`。

例子：

```text
问题：某学校什么时候成立？
答案：1996 年。
证据：该学校成立于 1996 年。
```

这种情况标：

```text
faithful
```

但是注意：如果证据里存在多个同名实体、多个候选答案，或者证据内部冲突，那么不能只看某一段证据能支持答案就直接标 `faithful`。还要检查答案是否忽略了关键歧义或冲突。

## 4. unfaithful / 不忠实

选择 `unfaithful` 的条件：

答案存在以下任意情况：

- 和证据矛盾；
- 添加了证据没有支持的重要事实；
- 在冲突证据中，没有足够依据就选择其中一边；
- 实体、日期、数字、地点等关键信息错误；
- 在证据冲突或证据不完整时，把不确定内容说成确定答案。

特别重要的冻结标准：

```text
selects one side of conflicting evidence without support
presents uncertainty as certainty when evidence is conflicting or incomplete
```

中文意思：

```text
在冲突证据中，没有充分依据就选择其中一方；
或者在证据冲突/不完整时，把不确定内容表达成确定答案。
```

例子：

```text
问题：人民大学什么时候成立？
答案：1913 年。
证据：
阿姆斯特丹人民大学：1913 年；
孟加拉国人民大学：1996 年；
科利马大众大学：1940 年。
```

这里答案 `1913 年` 被其中一段证据支持，但问题没有说明是哪一个“人民大学”。答案直接选择了一个实体，忽略了其他同名实体。

更严格、也更符合冻结文档的标法是：

```text
unfaithful
entity_ambiguity
benchmark_ambiguous
```

备注可以写：

```text
答案被阿姆斯特丹人民大学的证据支持，但问题未指定实体，证据中存在多个“人民大学”且成立时间不同。
```

## 5. insufficient / 证据不足

选择 `insufficient` 的条件：

```text
证据本身不够，无法判断答案是 faithful 还是 unfaithful。
```

这个标签要谨慎使用。冻结文档强调：

```text
Use this sparingly. If the answer makes unsupported claims, prefer unfaithful.
```

中文意思：

```text
少用 insufficient。如果答案提出了证据不支持的说法，优先标 unfaithful。
```

例子：

```text
问题：A 公司的 CEO 是谁？
答案：张三。
证据：只介绍了 A 公司的业务，没有提 CEO。
```

这种情况标：

```text
insufficient
insufficient_evidence
```

但如果证据明确说 CEO 是李四，答案说张三，就不是 `insufficient`，而是：

```text
unfaithful
contradiction
```

## 6. 三类标签的简单区分

可以用下面这张表快速判断：

| 情况 | 主标签 |
|---|---|
| 答案的重要内容都被证据支持，且没有忽略关键冲突/歧义 | `faithful` |
| 答案和证据矛盾，或编造，或无依据地选择冲突证据中的一边 | `unfaithful` |
| 证据不够，无法判断答案对错 | `insufficient` |

最容易混淆的是：

```text
某一段证据支持答案，但其他证据显示存在明显歧义或冲突。
```

这种情况不要机械标 `faithful`。要看答案是否合理处理了歧义/冲突。如果答案直接给确定结论，通常更偏向：

```text
unfaithful
```

并加对应问题类别。

## 7. 置信度 Confidence

置信度范围是 0 到 1。

推荐理解：

| 置信度 | 含义 |
|---:|---|
| 1.0 | 非常清楚，很容易判断 |
| 0.9 | 很确定，但有一点小复杂 |
| 0.8 | 基本确定，有轻微歧义 |
| 0.6 | 比较难，但倾向某个判断 |
| 0.5 | 非常不确定 |

建议常用：

```text
0.95：证据非常清楚地支持或反驳答案
0.85：总体清楚，但有歧义或证据较乱
0.70：复杂，需要备注说明
0.50：几乎无法判断
```

## 8. Issue Categories / 问题类别

问题类别可以多选，也可以不选。它们是辅助说明，不是主标签。

| 类别 | 中文解释 | 什么时候选 |
|---|---|---|
| `unsupported_claim` | 无证据支持的声明 | 答案说了证据没有支持的重要内容 |
| `contradiction` | 与证据矛盾 | 答案和证据直接冲突 |
| `evidence_conflict` | 证据冲突 | 证据内部互相矛盾 |
| `insufficient_evidence` | 证据不足 | 证据不够判断答案 |
| `entity_ambiguity` | 实体歧义 | 同名实体、指代不清、多个可能对象 |
| `temporal_conflict` | 时间冲突 | 时间状态不一致，或不同时点的信息冲突 |
| `numeric_error` | 数字错误 | 年份、日期、数量、比例等错误 |
| `over_specific_answer` | 回答过于具体 | 答案比证据给出的信息更具体 |
| `answer_format_issue` | 回答格式问题 | 答案没有按问题要求的格式回答 |
| `benchmark_ambiguous` | 题目/基准歧义 | 问题本身不清楚，可能有多个合理答案 |
| `other` | 其他 | 以上都不适合，但确实有问题 |

## 9. 常见组合

实体不清楚：

```text
entity_ambiguity
benchmark_ambiguous
```

证据里多个说法互相冲突：

```text
evidence_conflict
```

答案选择了冲突证据中的一方，而且没有说明不确定性：

```text
unfaithful
evidence_conflict
```

答案说了证据没有的信息：

```text
unfaithful
unsupported_claim
```

答案数字或年份错：

```text
unfaithful
numeric_error
```

证据根本不够判断：

```text
insufficient
insufficient_evidence
```

## 10. 标注检查清单

每条样本按这个顺序看：

1. 读问题。
2. 读证据。
3. 读答案。
4. 找出答案里的关键 claim。
5. 检查每个关键 claim 是否被证据支持。
6. 检查证据中是否存在多个实体、多个答案、冲突信息。
7. 如果有冲突/歧义，检查答案是否处理了这种冲突/歧义。
8. 选择一个主标签。
9. 选择问题类别。
10. 写一句简短备注。

## 11. 关于 AI 参考意见

UI 中展示的五个 AI 参考意见只用于辅助审查。

冻结文档已经说明：

```text
The human annotation form remains separate and empty unless the user manually saves a label.
```

中文意思：

```text
人工标注表单是独立的，除非你手动保存，否则 AI 的判断不会写入人工标注。
```

AI 的理由可以参考，但不要盲从 AI 的标签。尤其在 `faithful` 的定义上，不同 AI 可能采用不同隐含标准：

- 有些 AI 只看“是否有某段证据支持答案”；
- 有些 AI 会考虑“题目是否歧义、证据是否冲突、答案是否过度确定”。

我们的人工标注要以冻结文档的严格标准为准。

## 12. 这批数据的性质

Freeze 16 已经说明，这 100 条不是随机代表性样本，而是风险增强的 audit batch。

它适合用于：

- 验证错误机制；
- 分析高风险样本；
- 做 qualitative case study；
- 检查 benchmark 标签和模型判断是否有分歧。

它不适合直接用于：

- 无偏估计整体 judge accuracy。

## 13. 推荐备注写法

备注不需要很长，一句话即可。

例子：

```text
答案被证据 [1] 支持，但证据中还有其他同名实体，对应不同成立时间。
```

```text
证据明确给出 1996 年，答案给出 1913 年，年份与证据冲突。
```

```text
证据没有提到 CEO 信息，无法判断答案是否正确。
```

```text
答案添加了证据中没有出现的获奖信息。
```


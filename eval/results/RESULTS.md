# Evaluation Results and Analysis

## 1. Objective

The experiment compares three data-analysis configurations:

- **baseline1**
- **baseline3**
- **team** — the multi-agent configuration

The evaluation measures answer correctness, failure types, token usage, cost, timing, and retry behavior across 50 questions on three small datasets.

## 2. Corrected Primary Results

| Arm | Correct | Accuracy |
|---|---:|---:|
| baseline1 | 47/50 | 94% |
| baseline3 | 50/50 | 100% |
| team | 48/50 | 96% |

These are the corrected primary scores after fixing a scorer bug involving number words. The original as-built results are preserved separately in `full_report_as_built.md`.

### Interpretation

Baseline3 achieved the highest observed accuracy. The team did not outperform it, and the observed results do not establish that the team is better than either baseline.

The team also used substantially more tokens and cost approximately 3.5 times as much as baseline3 in the recorded run. Timing measurements are noisy, so no strong speed conclusion should be drawn.

This was one run of 50 questions across three small datasets. The results should not be generalized to all data-analysis tasks.

## 3. Scorer Correction

The scorer previously failed to recognize a number written as a word in a numeric answer.

For `team tips-08`, the expected answer was 4, while the response said:

> Four rows have a size of 6. No special handling of missing values was needed.

The scorer incorrectly treated this answer as wrong because it recognized the digit 6 but not the word “Four.” The scorer was corrected to recognize number words, and the test suite now checks that “four” passes for an expected value of 4 while “five” does not.

This correction changes one verdict: `team tips-08` changes from fail to pass. It does not change model-generated outputs or rerun the agents.

### Why this bug matters

The team tends to write natural-language sentences, while the baselines tend to print raw numbers. Because the scorer recognized digits but not number words, this bug could disproportionately penalize the team's answers. It was a measurement bias, not a team-model failure. The bug was discovered by reading failed answers; sampling already-passing answers would not necessarily have revealed it.

## 4. Failure Analysis

### `team tips-05` — Incorrect or incomplete final answer

The generated code computes tip percentage for every row:

```python id="jv6b0v"
result = df['tip'] / df['total_bill'] * 100
```

However, the final answer does not provide the requested average. It says the average is not given in the result.

**Finding:** This is most likely a real failure, but the cause is not known. The code computes a series of percentages, but the final answer fails to report the requested aggregate. We cannot conclude from the available evidence whether the Explainer failed to retrieve the computed value or whether the code returned an unexpected result.

**Potential future investigation:** Inspect the recorded execution output and how the system summarizes computed results. Any implementation change should be tested in a new evaluation version rather than retroactively changing this run.

### `team tips-15` — Gave up after allowed attempts

The team returned `not_sure` after the allowed attempts. The saved code ends with `result = None`, and no chart image was saved for this run.

**Finding:** The team failed to complete this question under the current execution and result contract.

**Potential future investigation:** Inspect the retry feedback and the way the coder handles runner errors. Test any proposed changes on a new evaluation version.

### Baseline1 chart failures

The three baseline1 chart failures share a result-contract issue: the code did not set a non-`None` value in `result`. These are three failed questions, but they may reflect one recurring implementation or prompt gap rather than three independent underlying causes.

The sensitivity analysis explores a relaxed scoring rule for eligible chart cases. It does not change the original saved evaluation records.

## 5. Chart-Scoring Sensitivity Analysis

The sensitivity report is a post-hoc analysis. It examines certain chart cases where code was present but the runner rejected the result because `result` was not set.

The relaxed rule does not cover every similar case. In particular, the team's `tips-15` case was recorded as `not_sure` and was not rescued by the relaxed rule.

The sensitivity report must therefore be read separately from the corrected primary report. It is not evidence that the failed execution was fixed.

**Hypothetical sensitivity footnote:** If the relaxed chart-scoring rule were also applied to the team's equivalent `tips-15` case, the team would score 49/50, while baseline1 and baseline3 would each score 50/50. The corrected primary result remains 48/50 for the team. This is a hypothetical comparison, not the primary result, and it does not change the conclusion that the team did not outperform baseline3.

## 6. Cost and Efficiency

In the recorded run, the team cost approximately 3.5 times as much as baseline3 and used approximately 3.6 times as many tokens.

This makes the team's extra orchestration cost difficult to justify on this particular benchmark, since it did not achieve higher accuracy than baseline3.

These are observations from this run, not universal cost or performance estimates.

## 7. Statistical Interpretation

The paired comparisons in the generated reports do not show a statistically distinguishable winner at this sample size.

A small difference in the number of correct answers is not sufficient evidence that one configuration is generally better. More questions, more diverse datasets, harder tasks, and repeated runs would be needed for stronger conclusions.

Baseline3's 100% score also creates a ceiling effect: this test cannot reveal whether a multi-agent approach would be more useful on tasks where simpler systems struggle.

## 8. Reproducibility and Limitations

- The evaluation contains 50 questions across three small datasets.
- It represents one run, not repeated trials.
- Timing measurements are noisy.
- The run metadata flags the working tree as dirty.
- The application, baseline, sandbox, and runner paths were checked against commit `2b6e1b3`, with no differences found in those paths. The exact cause of the dirty-tree flag has not been proven.
- The number-word change is a scorer correction, not a model or prompt change.

The corrected primary report, original as-built report, and sensitivity report are retained separately for transparency.

## 9. Conclusion

The team achieved 48/50 after the scorer correction, while baseline3 achieved 50/50 at substantially lower cost. This experiment does not support the claim that the multi-agent team is better than the simpler baseline.

The most useful next step is not to claim a winner, but to investigate the observed failures, design harder and more varied questions, and run a new evaluation version after any system changes.

## 10. Interview Questions and Answers

### Q1. Why did you compare a multi-agent system with simpler baselines?

**Answer:** I wanted to test whether splitting data-analysis work across multiple agents provides a measurable improvement over simpler configurations. I compared answer correctness, failures, token usage, cost, timing, and retries instead of assuming that more agents automatically improve performance.

### Q2. What did your results show, and what are their limitations?

**Answer:** After correcting a scorer bug, the team scored 48/50, while baseline3 scored 50/50. The team also cost substantially more. However, the experiment used only 50 questions on three small datasets in one run, so the result is limited and does not prove that baseline3 will always be better. A larger evaluation with harder questions and repeated runs would be needed.

### Q3. What did you learn from the failure analysis?

**Answer:** I found that not every failure comes from the same place. In `tips-05`, the code computed values but the final answer failed to report the requested average; the exact cause is still unknown. In `tips-15`, the team gave up after the allowed attempts and did not produce a usable result. I also found a scorer bug that misclassified the word “Four.” I corrected the scorer, added tests, and kept the original as-built report separate so the change remained transparent.
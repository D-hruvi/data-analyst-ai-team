# Evaluation report: full

## Accuracy

Strict = `review` counts as wrong. Lenient = `review` counts as right. The truth is in between.

| Arm | Questions | Strict | Lenient | Strict 95% range | Review |
|---|---|---|---|---|---|
| baseline1 | 50 | 47 (94%) | 47 (94%) | 84% - 98% | 0 |
| baseline3 | 50 | 50 (100%) | 50 (100%) | 93% - 100% | 0 |
| team | 50 | 48 (96%) | 48 (96%) | 87% - 99% | 0 |

## Strict score by question kind

| Arm | lookup | calculation | chart | unanswerable |
|---|---|---|---|---|
| baseline1 | 11/11 | 27/27 | 5/8 | 4/4 |
| baseline3 | 11/11 | 27/27 | 8/8 | 4/4 |
| team | 11/11 | 26/27 | 7/8 | 4/4 |

## Failure types (count)

| Arm | wrong_answer | chart_wrong | chart_missing | false_refusal | guessed | not_sure | error | infra_error | scorer_error |
|---|---|---|---|---|---|---|---|---|---|
| baseline1 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 |
| baseline3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| team | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |

## Cost, time and retries

| Arm | Mean tokens | Total cost (USD) | Mean seconds | Median seconds | Mean AI calls | Review retries* | Connection retries | Rate-limit waits |
|---|---|---|---|---|---|---|---|---|
| baseline1 | 912 | 0.0045 | 2.8 | 2.4 | 1.0 | 0 | 0 | 0 |
| baseline3 | 978 | 0.0049 | 2.4 | 2.2 | 1.1 | 3 | 0 | 0 |
| team | 3543 | 0.0171 | 4.0 | 3.8 | 3.9 | 5 | 0 | 0 |

*Team review retries are estimated from the number of AI calls. Seconds include rate-limit waits, but not the pause between questions. Cost can be slightly low if a request timed out after the server had already done the work.

## Cost per correct answer (strict)

- baseline1: USD 0.00010 per correct answer
- baseline3: USD 0.00010 per correct answer
- team: USD 0.00036 per correct answer

## Team compared with each baseline (same questions)

| Compared with | Both right | Only team right | Only baseline right | Both wrong | Sign-test p (strict) |
|---|---|---|---|---|---|
| baseline1 | 46 | 2 | 1 | 1 | 1.000 |
| baseline3 | 48 | 0 | 2 | 0 | 0.500 |

### Reading

- Team vs baseline1: NOT distinguishable at this sample size (2 vs 1 one-sided wins, p=1.00). Do not claim a winner.
- Team vs baseline3: NOT distinguishable at this sample size (0 vs 2 one-sided wins, p=0.50). Do not claim a winner.
- This is ONE run of 50 questions on 3 small datasets. A gap of a few questions is noise.
- The answer to 'is the team better?' must also weigh the extra tokens, cost and time above.

## Every question that did not pass

### baseline1 (3)

- taxis-15 [fail/error] The code did not set 'result' (or set it to None). | answer: 
- tips-14 [fail/error] The code did not set 'result' (or set it to None). | answer: 
- tips-15 [fail/error] The code did not set 'result' (or set it to None). | answer: 

### baseline3 (0)


### team (2)

- tips-05 [fail/wrong_answer] no number in the answer (expected 16.080258) | answer: The list shows the tip percentage for each bill.   The average of those percentages is not
- tips-15 [fail/not_sure] gave up after the allowed attempts | answer: I am not sure.


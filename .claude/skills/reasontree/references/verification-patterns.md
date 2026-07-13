# Verification patterns

Load the relevant pattern only when the task matches it.

## Multiple signals or repeated tests

Do not multiply likelihoods unless conditional independence is stated or measured.

For two binary events with marginal probabilities `a` and `b`, bound their joint probability with:

```text
max(0, a + b - 1) <= P(A and B) <= min(a, b)
```

For two alerts with base rate `p`, joint true-positive rate `t`, and joint false-positive rate `f`:

```text
posterior = p*t / (p*t + (1-p)*f)
```

Evaluate the admissible extremes. Treat independence as one scenario, not as a bound. A qualitative statement such as “same vendor” suggests possible dependence but does not quantify it.

Run the installed `reasontree-check --verifier dependence ...` command when the inputs fit this pattern.

## Calendar and time zones

Use named IANA zones rather than fixed UTC offsets. Evaluate every relevant date because daylight-saving transitions can change the mapping within one recurring series.

## Totals, rates, and comparisons

Check units, denominators, inclusion windows, and double counting. Construct a small example that would expose an inconsistent definition.

## Code and operations

Run a minimal reproduction or test. Do not accept another model's agreement as verification.

## Underdetermined decisions

Construct two worlds that satisfy every stated fact. If they imply different answers, reject the demanded exact answer and name the missing fact that would identify it.

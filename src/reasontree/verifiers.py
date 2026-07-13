from __future__ import annotations

import argparse
import json


def joint_bounds(a: float, b: float) -> tuple[float, float]:
    return max(0.0, a + b - 1.0), min(a, b)


def posterior(prevalence: float, joint_true_positive: float, joint_false_positive: float) -> float:
    numerator = prevalence * joint_true_positive
    denominator = numerator + (1.0 - prevalence) * joint_false_positive
    if denominator == 0:
        raise ValueError("posterior is undefined because the conditioning event has zero probability")
    return numerator / denominator


def dependence_bounds(
    prevalence: float,
    sensitivity_1: float,
    sensitivity_2: float,
    false_positive_1: float,
    false_positive_2: float,
) -> dict[str, object]:
    values = [prevalence, sensitivity_1, sensitivity_2, false_positive_1, false_positive_2]
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("all probabilities must be between 0 and 1")

    tpr_low, tpr_high = joint_bounds(sensitivity_1, sensitivity_2)
    fpr_low, fpr_high = joint_bounds(false_positive_1, false_positive_2)

    minimum = posterior(prevalence, tpr_low, fpr_high)
    maximum = 1.0 if fpr_low == 0.0 and tpr_high > 0.0 else posterior(prevalence, tpr_high, fpr_low)
    independent_tpr = sensitivity_1 * sensitivity_2
    independent_fpr = false_positive_1 * false_positive_2

    return {
        "verifier": "frechet-dependence-bounds",
        "identifiable": minimum == maximum,
        "posterior_bounds": {"minimum": minimum, "maximum": maximum},
        "joint_true_positive_bounds": {"minimum": tpr_low, "maximum": tpr_high},
        "joint_false_positive_bounds": {"minimum": fpr_low, "maximum": fpr_high},
        "independence_scenario": posterior(prevalence, independent_tpr, independent_fpr),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bound a two-signal posterior without assuming independence.")
    parser.add_argument("--prevalence", required=True, type=float)
    parser.add_argument("--sensitivity-1", required=True, type=float)
    parser.add_argument("--sensitivity-2", required=True, type=float)
    parser.add_argument("--false-positive-1", required=True, type=float)
    parser.add_argument("--false-positive-2", required=True, type=float)
    args = parser.parse_args()
    result = dependence_bounds(
        args.prevalence,
        args.sensitivity_1,
        args.sensitivity_2,
        args.false_positive_1,
        args.false_positive_2,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

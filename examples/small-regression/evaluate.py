"""Fixed synthetic regression fixture; only model.json varies between runs."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(Path("data.json").read_text(encoding="utf-8"))
    method = json.loads(Path("model.json").read_text(encoding="utf-8"))["method"]
    train = data["train"]
    xmean = sum(x for x, y in train) / len(train)
    ymean = sum(y for x, y in train) / len(train)
    if method == "mean":
        slope = 0.0
    elif method == "linear":
        slope = sum((x - xmean) * (y - ymean) for x, y in train) / sum(
            (x - xmean) ** 2 for x, y in train
        )
    else:
        raise ValueError(f"Unknown method: {method}")
    intercept = ymean - slope * xmean
    mse = sum((slope * x + intercept - y) ** 2 for x, y in data["test"]) / len(data["test"])
    result = {"metrics": {"mse": mse}, "method": method, "test_samples": len(data["test"])}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()

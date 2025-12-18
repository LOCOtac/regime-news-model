import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from regime_news import run_pipeline  # noqa: E402

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True)
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--n_regimes", type=int, default=4)
    args = p.parse_args()

    out = run_pipeline(
        ticker=args.ticker.upper(),
        start_date=args.start,
        end_date=args.end,
        offline=args.offline,
        n_regimes=args.n_regimes,
    )

    print("\n===== REGIME+NEWS REPORT =====")
    for k, v in out.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()

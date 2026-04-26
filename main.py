# main.py
import argparse
from src import constants
from src.reading.quiz import run_reading
from src.context.quiz import run_context
from src.usage import pipeline as usage_pipeline

def parse_args():
    p = argparse.ArgumentParser(description="J-Learning Quiz Generator System")
    p.add_argument("--level", type=int, required=True, help="JLPT level number (e.g., 5,4,3,2,1)")
    p.add_argument("--limit", type=int, default=0, help="Limit number of words to process (0 = no limit)")
    p.add_argument(
        "--mode",
        choices=("all", "reading", "usage", "ai", "context"),
        default="all",
        help="Mode: all(reading+usage) | reading | usage(ai alias) | context(scaffold)",
    )
    p.add_argument("--batch", type=int, default=4, help="Batch size for AI calls (applies when --mode=ai or all)")
    return p.parse_args()

def main():
    args = parse_args()
    level = args.level
    limit = args.limit or None

    if args.mode in ("all", "reading"):
        print(f"Running reading quiz for N{level} (limit={limit})")
        run_reading(
            level=level,
            vocab_path=constants.vocab_path(level),
            output_dir=constants.output_dir_for(level),
            limit=limit,
        )

    if args.mode in ("all", "usage", "ai"):
        print(f"Running usage generation for N{level} (limit={limit}, batch={args.batch})")
        usage_pipeline.run(level=level, limit=limit, batch_size=args.batch)

    if args.mode == "context":
        run_context(level=level, limit=limit)

if __name__ == "__main__":
    main()

# main.py
import argparse
import sys

# Reconfigure stdout/stderr to use UTF-8 to prevent UnicodeEncodeError on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src import constants
from src.reading.quiz import run_reading
from src.context.quiz import run_context
from src.usage import pipeline as usage_pipeline
from src.writing.quiz import run_writing

def parse_args():
    p = argparse.ArgumentParser(description="J-Learning Quiz Generator System")
    p.add_argument("--level", type=int, required=True, help="JLPT level number (e.g., 5,4,3,2,1)")
    p.add_argument("--limit", type=int, default=0, help="Limit number of words to process (0 = no limit)")
    p.add_argument(
        "--mode",
        choices=("all", "local", "reading", "context", "writing", "ai", "usage"),
        default="all",
        help=(
            "all     = reading + context + writing + ai usage\n"
            "local   = reading + context + writing (no LLM)\n"
            "reading = only reading quiz\n"
            "context = only context quiz\n"
            "writing = only writing quiz\n"
            "ai      = only usage quiz (LLM)\n"
        ),
    )
    p.add_argument("--batch", type=int, default=4, help="Batch size for AI calls (applies when --mode=ai or all)")
    return p.parse_args()

def main():
    args = parse_args()
    level = args.level
    limit = args.limit or None

    if args.mode in ("all", "local", "reading"):
        print(f"Running reading quiz for N{level} (limit={limit})")
        run_reading(
            level=level,
            vocab_path=constants.vocab_path(level),
            output_dir=constants.output_dir_for(level),
            limit=limit,
        )

    if args.mode in ("all", "local", "context"):
        print(f"Running context quiz for N{level} (limit={limit})")
        run_context(
            level=level,
            vocab_path=constants.vocab_path(level),
            output_dir=constants.output_dir_for(level),
            tatoeba_db_path=constants.TATOEBA_DB,
            limit=limit,
        )

    if args.mode in ("all", "local", "writing"):
        print(f"Running writing quiz for N{level} (limit={limit})")
        run_writing(level=level, limit=limit)

    if args.mode in ("all", "ai", "usage"):
        print(f"Running usage generation for N{level} (limit={limit}, batch={args.batch})")
        usage_pipeline.run(level=level, limit=limit, batch_size=args.batch)

if __name__ == "__main__":
    main()

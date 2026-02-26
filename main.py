# main.py
import argparse
from src import pipeline, quiz_reading

def parse_args():
    p = argparse.ArgumentParser(description="J-Learning Quiz Generator System")
    p.add_argument("--level", type=int, required=True, help="JLPT level number (e.g., 5,4,3,2,1)")
    p.add_argument("--limit", type=int, default=0, help="Limit number of words to process (0 = no limit)")
    p.add_argument("--mode", choices=("all","ai","reading"), default="all", help="Mode: all (reading+ai), ai (only AI), reading (only reading)")
    p.add_argument("--batch", type=int, default=4, help="Batch size for AI calls (applies when --mode=ai or all)")
    return p.parse_args()

def main():
    args = parse_args()
    level = args.level
    limit = args.limit or None

    if args.mode in ("all", "reading"):
        print(f"Running reading quiz for N{level} (limit={limit})")
        quiz_reading.run_reading(level, limit)

    if args.mode in ("all", "ai"):
        print(f"Running AI generation for N{level} (limit={limit}, batch={args.batch})")
        pipeline.run(level=level, limit=limit, batch_size=args.batch)

if __name__ == "__main__":
    main()

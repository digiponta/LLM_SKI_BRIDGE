"""Start an opt-in console alongside existing LLM_CHA chat.py.

The /ski command is diagnostic only and does not inject evidence into the model.
"""
import argparse
from adapters.llm_cha_console_v06 import run_console


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-cha-dir", required=True,
                        help="Trusted checkout containing LLM_CHA/chat.py")
    parser.add_argument("--llm-tmp-dir", required=True,
                        help="Trusted checkout containing semantic_relation_graph_v035.py")
    parser.add_argument("--graph-file", help="Optional JSON nodes/relations snapshot (read only)")
    parser.add_argument("--no-chat", action="store_true",
                        help="Inspect SKI commands without launching the LLM")
    args = parser.parse_args()
    run_console(args.llm_cha_dir, args.llm_tmp_dir, graph_file=args.graph_file,
                launch_chat=not args.no_chat)


if __name__ == "__main__":
    main()

"""CLI: read-only audit of local LLM_TMP Intent SD Registry snapshot.

No report file is written. JSON emitted to stdout only. No external model.
"""
import argparse
import json

from adapters.native_registry_audit_v010 import audit_file
from adapters.llm_tmp_native_v09 import convert_file


def run(native, tmp_dir, predicates=()):
    report = audit_file(native, tmp_dir,
                        supported_by_predicates=predicates)
    converted, conversion = convert_file(
        native, tmp_dir, supported_by_predicates=predicates)
    if report["source_sha256"] != conversion["native_file_sha256"]:
        raise ValueError("SOURCE_CHANGED_BETWEEN_READS")
    expected = report["counts"]["eligible_for_explicit_mapping"]
    actual = len(converted["relations"])
    if expected != actual:
        raise ValueError("AUDIT_CONVERSION_COUNT_MISMATCH")
    report["conversion_crosscheck"] = {
        "expected_eligible": expected,
        "actual_exported": actual,
        "match": True,
        "original_file_unchanged": True,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm-tmp-dir", required=True)
    parser.add_argument("--native", required=True)
    parser.add_argument("--supported-by-predicate", action="append", default=[],
                        help="Explicit predicate SD ID; may be repeated. Default exports none.")
    args = parser.parse_args()
    print(json.dumps(run(args.native, args.llm_tmp_dir,
                         tuple(args.supported_by_predicate)),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

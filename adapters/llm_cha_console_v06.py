"""Opt-in LLM_CHA console bridge. No changes to chat.py or model state.

Use /ski SOURCE_SD TARGET_SD | question for an explicit, read-only evidence
lookup. Other input is forwarded unchanged to the actual LLM_CHA chat.py.
Evidence is printed as a separate diagnostic, NEVER added to model context.
"""
import json
import subprocess
import sys
from pathlib import Path

from adapters.llm_cha_client_v05 import CHAClient
from adapters.llm_tmp_real import LLM_TMPAdapter
from verify_llm_tmp_integration_v03 import load_graph_class

STATES = frozenset(("PENDING", "APPROVED", "REJECTED"))


def parse_input(line):
    if not isinstance(line, str) or not line.strip() or "\x00" in line or "\n" in line or "\r" in line:
        raise ValueError("INVALID_INPUT")
    if len(line) > 4000:
        raise ValueError("INPUT_TOO_LONG")
    if line.strip() == "/exit":
        return {"kind": "EXIT"}
    if not line.startswith("/ski"):
        return {"kind": "CHAT", "text": line}
    if line == "/ski" or line.startswith("/ski "):
        args, sep, question = line.partition("|")
        parts = args.split()
        if len(parts) != 3 or not all(parts) or any(len(item) > 256 for item in parts[1:]):
            raise ValueError("USAGE: /ski SOURCE_SD TARGET_SD | question")
        if sep and not question.strip():
            raise ValueError("EMPTY_QUESTION")
        return {"kind": "SKI", "source_sd": parts[1],
                "target_sd": parts[2],
                "question": question.strip() if sep else "指定されたSemantic関係の根拠を確認してください。"}
    return {"kind": "CHAT", "text": line}


def build_graph(Graph, graph_file=None):
    """Load user-specified JSON fixture into the real LLM_TMP graph class.

    This is an in-memory copy. Importing source is opt-in. Approval states in
    user JSON are not authenticated or factually verified.
    """
    if graph_file is None:
        return Graph([])
    data = json.loads(Path(graph_file).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"nodes", "relations"}:
        raise ValueError("INVALID_GRAPH_DOCUMENT")
    nodes, relations = data["nodes"], data["relations"]
    if (not isinstance(nodes, list) or not 1 <= len(nodes) <= 10000
            or len(nodes) != len(set(x for x in nodes if isinstance(x, str)))
            or not all(isinstance(x, str) and x.strip() and len(x) <= 256 for x in nodes)
            or not isinstance(relations, list) or len(relations) > 50000):
        raise ValueError("INVALID_GRAPH_SIZE")
    graph = Graph(nodes)
    for item in relations:
        if not isinstance(item, dict) or not {"source", "target", "kind", "state"} <= item.keys():
            raise ValueError("INVALID_RELATION")
        if (item["state"] not in STATES
                or not all(isinstance(item[k], str) and item[k].strip()
                           for k in ("source", "target", "kind", "state"))):
            raise ValueError("INVALID_RELATION_STATE")
        graph.add_relation(
            item["source"], item["kind"], item["target"],
            state=item["state"],
            evidence_id=item.get("evidence_id"),
            provenance=item.get("provenance"))
    return graph


def run_command(line, client, chat_send):
    command = parse_input(line)
    if command["kind"] == "EXIT":
        return {"kind": "EXIT"}
    if command["kind"] == "CHAT":
        chat_send(command["text"])
        return {"kind": "FORWARDED_TO_CHAT"}
    result = client.exchange(
        command["question"], source_sd=command["source_sd"],
        target_sd=command["target_sd"])
    resp = result["evidence_response"]
    return {
        "kind": "SKI_DIAGNOSTIC", "evidence_status": resp["status"],
        "approved_path": resp["path"] if resp["status"] == "FOUND" else None,
        "request_id": result["dataset_a"][0]["message_id"],
        "response_to_message_id": result["dataset_b"][0]["derivation"]["response_to_message_id"],
        "verified_fact": False,
        "human_approved": False,
        "llm_inference_invoked_for_ski": False,
        "note": "Evidence relationship only; no factual-truth assertion. Local JSON approval is not authenticated.",
    }


def run_console(cha_dir, tmp_dir, *, graph_file=None, launch_chat=True):
    cha_root = Path(cha_dir).expanduser().resolve()
    Graph = load_graph_class(tmp_dir)
    client = CHAClient(LLM_TMPAdapter(build_graph(Graph, graph_file)))
    proc = None
    try:
        if launch_chat:
            chat_path = cha_root / "chat.py"
            if not chat_path.is_file():
                raise FileNotFoundError("LLM_CHA_CHAT_NOT_FOUND")
            proc = subprocess.Popen(
                [sys.executable, "-u", str(chat_path)],
                cwd=str(cha_root), stdin=subprocess.PIPE)
        print("SKI console: /ski SOURCE_SD TARGET_SD | question ; /exit ; other lines -> LLM_CHA")
        print("SKI diagnostics never enter LLM_CHA training or inference context.")
        while True:
            try:
                line = input("CHA/SKI> ")
            except (KeyboardInterrupt, EOFError):
                break
            def forward(text):
                if proc is None:
                    raise RuntimeError("CHAT_NOT_LAUNCHED")
                if proc.poll() is not None or proc.stdin is None:
                    raise RuntimeError("CHAT_PROCESS_EXITED")
                proc.stdin.write((text + "\n").encode("utf-8"))
                proc.stdin.flush()
            try:
                result = run_command(line, client, forward)
                if result["kind"] == "EXIT":
                    break
                if result["kind"] == "SKI_DIAGNOSTIC":
                    print(json.dumps(result, ensure_ascii=False, indent=2))
            except (ValueError, RuntimeError) as exc:
                print("[SKI/CHAT error]", str(exc))
    finally:
        if proc is not None:
            if proc.poll() is None and proc.stdin:
                try:
                    proc.stdin.write(b"/exit\n")
                    proc.stdin.flush()
                    proc.wait(timeout=3)
                except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
            if proc.stdin:
                proc.stdin.close()

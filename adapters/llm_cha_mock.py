"""Mock conversation client and in-process roundtrip."""
from ski.message import request, response, validate_roundtrip
from adapters.llm_tmp_mock import MockTMP


def roundtrip(source_sd="SD-CLAIM", target_sd="SD-EVIDENCE", *, max_hops=5, max_visits=2000):
    req = request(source_sd, target_sd, max_hops=max_hops, max_visits=max_visits)
    tmp = MockTMP()
    result = tmp.search(req["source_sd"], req["target_sd"], req["max_hops"], req["max_visits"])
    resp = response(req, result)
    if not validate_roundtrip(req, resp):
        raise RuntimeError("ROUNDTRIP_VALIDATION_FAILED")
    return {"request": req, "response": resp}

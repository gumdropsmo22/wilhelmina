import pathlib
import sys
import json
import logging

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from utils import logging as wlog


def test_json_logging_smoke(capfd):
    wlog.configure()
    logging.getLogger("wilhelmina").info("hello", extra={"event": "smoke"})
    out, _ = capfd.readouterr()
    line = out.strip().splitlines()[-1]
    obj = json.loads(line)
    assert obj["msg"] == "hello"
    assert obj["event"] == "smoke"

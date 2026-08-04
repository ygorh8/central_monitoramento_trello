from suite_visibility.suite_bot_mapper import bots_from_manifest, suite_manifest_from_config


class Response:
    status_code = 200
    text = "<project><defaultValue>suite_aba_pay_02.json</defaultValue></project>"


class Session:
    def get(self, *_args, **_kwargs):
        return Response()


def test_manifest_is_read_from_safe_xml_value():
    assert suite_manifest_from_config("http://jenkins/job/x/", username="u", api_token="t", session=Session()) == "suite_aba_pay_02.json"


def test_bots_are_extracted_in_manifest_order(tmp_path):
    suites = tmp_path / "suites"
    suites.mkdir()
    (suites / "suite.json").write_text('[{"path":"tests/test_B205_a.py"},{"path":"tests/test_B605_b.py"},{"path":"tests/test_B205_duplicate.py"}]', encoding="utf-8")
    assert bots_from_manifest(tmp_path, "suite.json") == [205, 605]

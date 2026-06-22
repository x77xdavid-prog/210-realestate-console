"""public_data.http_get 의 일시 오류(5xx·타임아웃) 재시도 회귀 테스트.

VWorld·data.go.kr 게이트웨이가 간헐적으로 502를 돌려줄 때 한 번의 일시 오류가
사용자에게 '확인 필요'로 노출되지 않도록 재시도한다.
"""

import unittest
import urllib.error
from unittest import mock

from realestate_alert import public_data


class _FakeResp:
    def __init__(self, body: str):
        self._b = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._b


def _http_error(req, code):
    return urllib.error.HTTPError(req.full_url, code, "err", {}, None)


class HttpGetRetryTests(unittest.TestCase):
    def test_retries_on_502_then_succeeds(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(1)
            if len(calls) < 3:
                raise _http_error(req, 502)
            return _FakeResp('{"ok":1}')

        with mock.patch.object(public_data.urllib.request, "urlopen", fake_urlopen), \
             mock.patch.object(public_data.time, "sleep", lambda *_a: None):
            body = public_data.http_get("https://api.vworld.kr/ned/data/getLandUseAttr")

        self.assertEqual(body, '{"ok":1}')
        self.assertEqual(len(calls), 3)  # 502, 502, 성공

    def test_gives_up_after_max_retries_on_502(self):
        calls = []

        def always_502(req, timeout=None):
            calls.append(1)
            raise _http_error(req, 502)

        with mock.patch.object(public_data.urllib.request, "urlopen", always_502), \
             mock.patch.object(public_data.time, "sleep", lambda *_a: None):
            with self.assertRaises(public_data.PublicDataError):
                public_data.http_get("https://api.vworld.kr/x")

        self.assertGreaterEqual(len(calls), 2)  # 최소 1회 이상 재시도

    def test_does_not_retry_on_404(self):
        calls = []

        def always_404(req, timeout=None):
            calls.append(1)
            raise _http_error(req, 404)

        with mock.patch.object(public_data.urllib.request, "urlopen", always_404), \
             mock.patch.object(public_data.time, "sleep", lambda *_a: None):
            with self.assertRaises(public_data.PublicDataError):
                public_data.http_get("https://x")

        self.assertEqual(len(calls), 1)  # 4xx는 재시도하지 않음

    def test_succeeds_first_try_no_retry(self):
        calls = []

        def ok(req, timeout=None):
            calls.append(1)
            return _FakeResp("body")

        with mock.patch.object(public_data.urllib.request, "urlopen", ok):
            body = public_data.http_get("https://x")

        self.assertEqual(body, "body")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()

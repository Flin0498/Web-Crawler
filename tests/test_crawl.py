import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from crawl import (
    PRESET_MODES,
    build_html_index,
    crawl_url,
    fields_from_modes,
    joinqq_index_from_api,
    pick_fields,
    resolve_fields,
    validate_url,
)

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


class TestResolveFields(unittest.TestCase):
    def test_mode_links(self):
        self.assertEqual(resolve_fields(['links'], [], None), ['链接'])

    def test_mode_body_no_body_in_result_keys(self):
        fields = resolve_fields(['body'], [], None)
        self.assertEqual(fields, ['正文'])

    def test_explicit_fields(self):
        self.assertEqual(
            resolve_fields([], ['标题', '链接'], None),
            ['标题', '链接'],
        )

    def test_mode_and_fields_combined(self):
        got = resolve_fields(['table'], ['标题'], None)
        self.assertEqual(got, ['表格', '标题'])

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            resolve_fields([], [], None)

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            fields_from_modes(['nope'])

    def test_preset_keys(self):
        self.assertEqual(set(PRESET_MODES), {'links', 'body', 'table'})


class TestValidateUrl(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(
            validate_url('https://example.com').startswith('https://')
        )

    def test_bad_scheme(self):
        with self.assertRaises(ValueError):
            validate_url('ftp://example.com')


class TestPickFields(unittest.TestCase):
    def test_douban_fixture(self):
        html = (FIXTURES / 'douban_movie.html').read_bytes()
        index = build_html_index(html, 'https://movie.douban.com/subject/1/')
        data, missing = pick_fields(index, ['电影名称', '评分', '简介'])
        self.assertEqual(data['电影名称'], '肖申克的救赎')
        self.assertEqual(data['评分'], '9.7')
        self.assertIn('安迪', data['简介'])
        self.assertEqual(missing, [])

    def test_links_only_no_body(self):
        html = (FIXTURES / 'generic_page.html').read_bytes()
        index = build_html_index(html, 'https://example.com/a')
        data, missing = pick_fields(index, ['链接'])
        self.assertIn('链接', data)
        self.assertNotIn('正文', data)
        self.assertEqual(missing, [])

    def test_joinqq_index(self):
        body = json.loads((FIXTURES / 'joinqq_detail.json').read_text(encoding='utf-8'))
        index = joinqq_index_from_api(body['data'])
        data, missing = pick_fields(index, ['岗位名称', '岗位职责'])
        self.assertEqual(data['岗位名称'], '解决方案-技术咨询方向')
        self.assertEqual(data['岗位职责'], '职责示例')
        self.assertEqual(missing, [])


class TestCrawlUrl(unittest.TestCase):
    def test_html_mock(self):
        html = (FIXTURES / 'generic_page.html').read_bytes()

        def fake_get(url, **kwargs):
            resp = Mock()
            resp.status_code = 200
            resp.url = url
            resp.headers = {'Content-Type': 'text/html'}
            resp.content = html
            resp.text = html.decode('utf-8')
            resp.raise_for_status = Mock()
            return resp

        out = crawl_url('https://example.com/a', ['标题', '链接'], get=fake_get)
        self.assertTrue(out.ok)
        self.assertEqual(out.data.get('标题'), '示例页面')
        self.assertTrue(out.data.get('链接'))


if __name__ == '__main__':
    unittest.main()

import datetime as dt
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

checker = Path(__file__).resolve().parents[1] / 'scripts' / 'check_positions.py'
spec = importlib.util.spec_from_file_location('checker', checker)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CheckPositionTests(unittest.TestCase):
    def test_domain_match_cyrillic_punycode_and_evil_similar(self):
        self.assertTrue(module.domain_matches('https://битвадиванов.рф/'))
        self.assertTrue(module.domain_matches('https://xn--80aabebbl3ad6cl4b.xn--p1ai'))
        self.assertFalse(module.domain_matches('https://битвадиванов.рф.evil.net'))
        self.assertFalse(module.domain_matches('https://bitvadivanov.ru/'))

    def test_real_statistics_position_can_be_fractional(self):
        payload = {'text_indicator_to_statistics': [
            {'text_indicator': {'type': 'QUERY', 'value': 'Корпоратив Калининград'},
             'popular_complementary_indicator': {'type': 'URL', 'value': 'https://битвадиванов.рф/korporativ'},
             'statistics': [
                 {'date': '2026-10-28', 'field': 'POSITION', 'value': 4.35},
                 {'date': '2026-10-28', 'field': 'IMPRESSIONS', 'value': 19.0},
                 {'date': '2026-10-28', 'field': 'CLICKS', 'value': 3.0},
                 {'date': '2026-10-27', 'field': 'IMPRESSIONS', 'value': 0.0},
             ]},
             {'text_indicator': {'type': 'QUERY', 'value': 'другой запрос'},
             'statistics': [{'date': '2026-10-28', 'field':'POSITION','value':3}]}
        ]}
        rows = module.normalize_analytics(payload, 'корпоратив калининград', '22', 'mobile')
        self.assertEqual(2, len(rows))
        self.assertEqual(4.35, rows[0]['position'])
        self.assertEqual(19, rows[0]['impressions'])
        self.assertIsNone(rows[1]['position'])  # Нет данных =/= позиция 100+
        self.assertEqual('https://битвадиванов.рф/korporativ', rows[0]['url'])

    def test_discover_uses_verified_site_and_not_fake(self):
        with patch.object(module, 'yandex_json') as mock:
            mock.side_effect=[{'user_id':23}, {'hosts': [
                {'host_id':'http:fake.ru:80','verified':True,'unicode_host_url':'https://fake.ru'},
                {'host_id':'https:xn--80aabebbl3ad6cl4b.xn--p1ai:443','verified':True,'unicode_host_url':'https://битвадиванов.рф/'},
            ]}]
            uid,hid=module.discover_host('test_token')
            self.assertEqual(uid,23)
            self.assertIn('https:',hid)

    def test_keeps_history_and_latest_wins(self):
        base=[{'date':'2026-10-26','query':'а','region':'22','device':'mobile','position':3},
              {'date':'2026-10-27','query':'а','region':'22','device':'mobile','position':5}]
        latest=[{'date':'2026-10-27','query':'а','region':'22','device':'mobile','position':4},
                {'date':'2026-10-28','query':'а','region':'22','device':'mobile','position':2}]
        rows=module.merge_records(base,latest,today=dt.date(2026,10,29))
        self.assertEqual(3,len(rows))
        self.assertEqual(4,rows[1]['position'])
        self.assertEqual(2,rows[2]['position'])

    def test_request_has_correct_region_and_exact_filter(self):
        with patch.object(module, 'yandex_json', return_value={'text_indicator_to_statistics':[]}) as mock:
            module.fetch_keyword('secret',1,'https:test.com:443','тимбилдинг калининград','10857','desktop')
            args=mock.call_args[0]
            self.assertTrue(args[1].endswith('/query-analytics/list'))
            body=args[3]
            self.assertEqual([10857],body['region_ids'])
            self.assertEqual('DESKTOP',body['device_type_indicator'])
            self.assertEqual('TEXT_MATCH',body['filters']['text_filters'][0]['operation'])

    def test_discover_prefers_verified_main_mirror_even_for_ascii_urls(self):
        primary = {'host_id': 'https:main:443', 'verified': True,
                   'ascii_host_url': 'https://xn--80aabebbl3ad6cl4b.xn--p1ai/'}
        with patch.object(module, 'yandex_json', side_effect=[{'user_id': 23}, {'hosts': [
            {'host_id': 'http:mirror:80', 'verified': True,
             'unicode_host_url': 'http://www.битвадиванов.рф/', 'main_mirror': primary}
        ]}]):
            self.assertEqual((23, 'https:main:443'), module.discover_host('test_token'))

    def test_unverified_site_is_not_accepted(self):
        with patch.object(module, 'yandex_json', side_effect=[{'user_id': 23}, {'hosts': [
            {'host_id': 'https:unverified:443', 'verified': False,
             'unicode_host_url': 'https://битвадиванов.рф/'}
        ]}]):
            with self.assertRaises(module.APIError):
                module.discover_host('test_token')

    def test_non_finite_and_unknown_positions_are_not_published_as_ranks(self):
        payload = {'text_indicator_to_statistics': [{
            'text_indicator': {'type': 'QUERY', 'value': 'запрос'},
            'statistics': [
                {'date': '2026-10-28', 'field': 'POSITION', 'value': float('nan')},
                {'date': '2026-10-28', 'field': 'IMPRESSIONS', 'value': 5},
                {'date': '2026-10-27', 'field': 'POSITION', 'value': float('inf')},
                {'date': '2026-10-27', 'field': 'IMPRESSIONS', 'value': 2},
                {'date': '2026-10-26', 'field': 'POSITION', 'value': 0},
                {'date': '20261025', 'field': 'POSITION', 'value': 4},
            ]
        }]}
        rows = module.normalize_analytics(payload, 'запрос', '22', 'mobile')
        self.assertEqual(3, len(rows))
        self.assertTrue(all(row['position'] is None for row in rows))

    def test_fetch_follows_pagination_instead_of_dropping_statistics(self):
        def entry(day, rank):
            return {'text_indicator': {'type': 'QUERY', 'value': 'запрос'},
                    'statistics': [{'date': day, 'field': 'POSITION', 'value': rank}]}
        with patch.object(module, 'yandex_json', side_effect=[
            {'count': 2, 'text_indicator_to_statistics': [entry('2026-10-27', 4)]},
            {'count': 2, 'text_indicator_to_statistics': [entry('2026-10-28', 3)]},
        ]) as mock:
            rows = module.fetch_keyword('test_token', 1, 'https:test:443', 'запрос', '22', 'mobile')
            self.assertEqual(2, len(rows))
            self.assertEqual([0, 1], [call.args[3]['offset'] for call in mock.call_args_list])

    def test_malformed_api_response_is_an_error_not_successful_empty_collection(self):
        for payload in ({'error': 'unexpected'}, {'count': 1, 'text_indicator_to_statistics': []}):
            with self.subTest(payload=payload), patch.object(module, 'yandex_json', return_value=payload):
                with self.assertRaises(module.APIError):
                    module.fetch_keyword('test_token', 1, 'https:test:443', 'запрос', '22', 'mobile')

    def test_future_statistics_are_not_added_to_history(self):
        rows = module.merge_records([], [
            {'date': '2026-10-30', 'query': 'а', 'region': '22', 'device': 'mobile', 'position': 2}
        ], today=dt.date(2026, 10, 29))
        self.assertEqual([], rows)

    def test_failed_connection_does_not_claim_old_statistics_were_updated(self):
        old_state = module.build_default([{'query': 'запрос', 'group': 'Тест'}])
        old_state['updated_at'] = '2026-10-27T05:12:00+00:00'
        config = SimpleNamespace(read_text=lambda **kwargs: '[{"query":"запрос","group":"Тест"}]')
        with patch.object(module, 'CONFIG', config), \
             patch.dict(module.os.environ, {'YANDEX_TOKEN': 'test_token'}), \
             patch.object(module, 'load_state', return_value=old_state), \
             patch.object(module, 'discover_host', side_effect=module.APIError('Тестовая ошибка')), \
             patch.object(module, 'store') as store:
            self.assertEqual(1, module.run())
        saved = store.call_args.args[0]
        self.assertEqual('2026-10-27T05:12:00+00:00', saved['updated_at'])
        self.assertEqual('error', saved['status'])
        self.assertIsNotNone(saved['last_attempt_at'])
        self.assertEqual(0, saved['collection']['successful_requests'])

    def test_successful_empty_collection_is_connected_without_invented_positions(self):
        old_state = module.build_default([{'query': 'запрос', 'group': 'Тест'}])
        config = SimpleNamespace(read_text=lambda **kwargs: '[{"query":"запрос","group":"Тест"}]')
        with patch.object(module, 'CONFIG', config), \
             patch.dict(module.os.environ, {'YANDEX_TOKEN': 'test_token'}), \
             patch.object(module, 'load_state', return_value=old_state), \
             patch.object(module, 'discover_host', return_value=(1, 'https:test:443')), \
             patch.object(module, 'fetch_keyword', return_value=[]), \
             patch.object(module, 'store') as store:
            self.assertEqual(0, module.run())
        saved = store.call_args.args[0]
        self.assertEqual('ok', saved['status'])
        self.assertEqual([], saved['measurements'])
        self.assertIsNone(saved['latest_position_date'])
        self.assertEqual(4, saved['collection']['successful_requests'])
        self.assertEqual(0, saved['collection']['current_position_records'])
        self.assertIsNotNone(saved['last_success_at'])


if __name__=='__main__':
    unittest.main()

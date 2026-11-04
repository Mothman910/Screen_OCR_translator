#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Testy łańcucha silników tłumaczenia (bez połączeń sieciowych).

Uruchomienie:  python -m unittest discover -s tests
"""

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

import translator as tr  # noqa: E402
from translator import Translator, _split_for_mymemory  # noqa: E402


class FakeSettings:
    def __init__(self, **translation):
        self.translation = translation

    def get(self, category, key, default=None):
        if category == 'translation':
            return self.translation.get(key, default)
        return default


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


def google_ok(text='Cześć świecie'):
    return FakeResponse(200, [[[text, 'Hello world', None, None]], None, 'en'])


class FakeSession:
    """Zwraca odpowiedzi w zależności od adresu URL i zapamiętuje zapytania."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        for fragment, responses in self.routes.items():
            if fragment in url:
                result = responses.pop(0) if isinstance(responses, list) else responses
                if isinstance(result, Exception):
                    raise result
                return result
        raise AssertionError(f"Nieoczekiwany URL: {url}")


class TranslatorChainTests(unittest.TestCase):
    def setUp(self):
        Translator.clear_cache()
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        for var in ('DEEPL_API_KEY', 'ANTHROPIC_API_KEY', 'MYMEMORY_EMAIL'):
            os.environ.pop(var, None)
        self.sleep = mock.patch.object(tr.time, 'sleep')
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()
        self.env.stop()

    def test_default_engine_is_deepl_with_free_endpoint(self):
        session = FakeSession({'deepl.com': FakeResponse(200, {'translations': [{'text': 'Witaj świecie'}]})})
        t = Translator(FakeSettings(deepl_api_key='abc:fx', source_lang='en', target_lang='pl'), session)

        self.assertEqual(t.translate('Hello world'), 'Witaj świecie')
        self.assertEqual(t.last_engine, 'deepl')
        method, url, kwargs = session.calls[0]
        self.assertEqual(url, 'https://api-free.deepl.com/v2/translate')
        self.assertEqual(kwargs['headers']['Authorization'], 'DeepL-Auth-Key abc:fx')
        self.assertEqual(kwargs['json']['target_lang'], 'PL')
        self.assertEqual(kwargs['json']['source_lang'], 'EN')
        self.assertIn('timeout', kwargs)

    def test_pro_key_uses_pro_endpoint(self):
        session = FakeSession({'deepl.com': FakeResponse(200, {'translations': [{'text': 'x'}]})})
        Translator(FakeSettings(deepl_api_key='pro-key'), session).translate('y')
        self.assertEqual(session.calls[0][1], 'https://api.deepl.com/v2/translate')

    def test_without_keys_skips_deepl_and_claude_and_uses_google(self):
        session = FakeSession({'translate.googleapis.com': google_ok()})
        t = Translator(FakeSettings(source_lang='en', target_lang='pl'), session)

        self.assertEqual(t.translate('Hello world'), 'Cześć świecie')
        self.assertEqual(t.last_engine, 'google')
        self.assertEqual(set(t.last_errors), {'deepl', 'claude'})

    def test_deepl_quota_exceeded_falls_back_to_google(self):
        session = FakeSession({
            'deepl.com': FakeResponse(456),
            'translate.googleapis.com': google_ok(),
        })
        t = Translator(FakeSettings(deepl_api_key='k:fx'), session)
        self.assertEqual(t.translate('Hello world'), 'Cześć świecie')
        self.assertIn('limit', t.last_errors['deepl'])

    def test_google_429_is_retried_then_falls_back_to_mymemory(self):
        session = FakeSession({
            'translate.googleapis.com': [FakeResponse(429), FakeResponse(429)],
            'mymemory': FakeResponse(200, {'responseStatus': 200, 'responseData': {'translatedText': 'Witaj'}}),
        })
        t = Translator(FakeSettings(engine='google'), session)
        self.assertEqual(t.translate('Hello'), 'Witaj')
        self.assertEqual(t.last_engine, 'mymemory')
        google_calls = [c for c in session.calls if 'googleapis' in c[1]]
        self.assertEqual(len(google_calls), 2)

    def test_network_error_falls_back(self):
        session = FakeSession({
            'translate.googleapis.com': [tr.requests.ConnectionError('boom')] * 2,
            'mymemory': FakeResponse(200, {'responseStatus': 200, 'responseData': {'translatedText': 'Witaj'}}),
        })
        t = Translator(FakeSettings(engine='google', fallback_engines=['google', 'mymemory']), session)
        self.assertEqual(t.translate('Hello'), 'Witaj')

    def test_mymemory_quota_warning_is_an_error(self):
        session = FakeSession({
            'mymemory': FakeResponse(200, {'responseStatus': 429, 'responseData': {
                'translatedText': 'MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY'}}),
        })
        t = Translator(FakeSettings(engine='mymemory', fallback_engines=[]), session)
        self.assertEqual(t.translate('Hello'), '[Błąd tłumaczenia] Hello')
        self.assertIsNone(t.last_engine)

    def test_all_engines_fail_returns_marked_original(self):
        session = FakeSession({
            'translate.googleapis.com': FakeResponse(403),
            'mymemory': FakeResponse(503),
        })
        t = Translator(FakeSettings(), session)
        self.assertEqual(t.translate('Hello'), '[Błąd tłumaczenia] Hello')

    def test_cache_avoids_second_request(self):
        session = FakeSession({'translate.googleapis.com': [google_ok()]})
        settings = FakeSettings(engine='google')
        self.assertEqual(Translator(settings, session).translate('Hello world'), 'Cześć świecie')
        t2 = Translator(settings, session)
        self.assertEqual(t2.translate('Hello world'), 'Cześć świecie')
        self.assertEqual(t2.last_engine, 'google')
        self.assertEqual(len(session.calls), 1)

    def test_old_google_setting_still_works_and_unknown_engine_is_ignored(self):
        t = Translator(FakeSettings(engine='bogus'), FakeSession({}))
        self.assertEqual(t.engine_order(), ['deepl', 'claude', 'google', 'mymemory'])
        t = Translator(FakeSettings(engine='google'), FakeSession({}))
        self.assertEqual(t.engine_order()[0], 'google')

    def test_forced_engine_skips_chain_and_cache(self):
        session = FakeSession({
            'translate.googleapis.com': [google_ok('A'), google_ok('B')],
            'mymemory': FakeResponse(200, {'responseStatus': 200, 'responseData': {'translatedText': 'M'}}),
        })
        settings = FakeSettings(engine='google')
        self.assertEqual(Translator(settings, session).translate('Hi'), 'A')
        t = Translator(settings, session)
        self.assertEqual(t.translate('Hi', engines=['mymemory']), 'M')
        self.assertEqual(t.last_engine, 'mymemory')
        self.assertEqual(Translator(settings, session).translate('Hi'), 'A')  # cache bez zmian

    def test_available_engines_depend_on_keys(self):
        t = Translator(FakeSettings(), FakeSession({}))
        self.assertEqual(t.available_engines(), ['google', 'mymemory'])
        t = Translator(FakeSettings(deepl_api_key='k:fx', anthropic_api_key='a'), FakeSession({}))
        self.assertEqual(t.available_engines(), ['deepl', 'claude', 'google', 'mymemory'])

    def test_empty_text(self):
        self.assertEqual(Translator(FakeSettings(), FakeSession({})).translate('   '), '')


class ClaudeEngineTests(unittest.TestCase):
    def setUp(self):
        Translator.clear_cache()

    def _fake_anthropic(self, response=None, error=None):
        module = types.ModuleType('anthropic')

        class APIStatusError(Exception):
            status_code = 500

        class AuthenticationError(APIStatusError):
            status_code = 401

        class RateLimitError(APIStatusError):
            status_code = 429

        class APIConnectionError(Exception):
            pass

        module.APIStatusError = APIStatusError
        module.AuthenticationError = AuthenticationError
        module.RateLimitError = RateLimitError
        module.APIConnectionError = APIConnectionError
        module.created = []

        class Messages:
            def create(self_inner, **params):
                module.created.append(params)
                if error:
                    raise getattr(module, error)()
                return response

        class Client:
            def __init__(self, **kwargs):
                module.client_kwargs = kwargs
                self.beta = types.SimpleNamespace(messages=Messages())
                self.messages = Messages()

        module.Anthropic = Client
        return module

    def test_default_claude_model_is_cheap_haiku(self):
        response = types.SimpleNamespace(stop_reason='end_turn',
                                         content=[types.SimpleNamespace(type='text', text='ok')])
        fake = self._fake_anthropic(response)
        with mock.patch.dict(sys.modules, {'anthropic': fake}):
            Translator(FakeSettings(engine='claude', anthropic_api_key='k'), FakeSession({})).translate('x')
        self.assertEqual(fake.created[0]['model'], 'claude-haiku-5-5')
        self.assertNotIn('fallbacks', fake.created[0])
        self.assertEqual(fake.created[0]['output_config'], {'effort': 'low'})

    def test_claude_translation_with_fallbacks(self):
        response = types.SimpleNamespace(
            stop_reason='end_turn',
            content=[types.SimpleNamespace(type='thinking', thinking=''),
                     types.SimpleNamespace(type='text', text='Witaj, wędrowcze!')],
        )
        fake = self._fake_anthropic(response)
        with mock.patch.dict(sys.modules, {'anthropic': fake}):
            t = Translator(FakeSettings(engine='claude', anthropic_api_key='sk-ant-x',
                                        claude_model='claude-opus-5-5'), FakeSession({}))
            self.assertEqual(t.translate('Helo, travler!'), 'Witaj, wędrowcze!')
        params = fake.created[0]
        self.assertEqual(params['model'], 'claude-opus-5-5')
        self.assertEqual(params['fallbacks'], 'default')
        self.assertEqual(params['betas'], ['server-side-fallback-2026-07-01'])
        self.assertIn('<text>', params['messages'][0]['content'])
        self.assertEqual(fake.client_kwargs['api_key'], 'sk-ant-x')

    def test_haiku_model_has_no_server_fallback(self):
        response = types.SimpleNamespace(stop_reason='end_turn',
                                         content=[types.SimpleNamespace(type='text', text='ok')])
        fake = self._fake_anthropic(response)
        with mock.patch.dict(sys.modules, {'anthropic': fake}):
            Translator(FakeSettings(engine='claude', anthropic_api_key='k', claude_model='claude-haiku-5-5'),
                       FakeSession({})).translate('x')
        self.assertNotIn('fallbacks', fake.created[0])

    def test_claude_error_falls_back_to_google(self):
        fake = self._fake_anthropic(error='RateLimitError')
        session = FakeSession({'translate.googleapis.com': google_ok('Hej')})
        with mock.patch.dict(sys.modules, {'anthropic': fake}):
            t = Translator(FakeSettings(engine='claude', anthropic_api_key='k'), session)
            self.assertEqual(t.translate('Hey'), 'Hej')
        self.assertEqual(t.last_engine, 'google')
        self.assertIn('429', t.last_errors['claude'])

    def test_claude_refusal_falls_back(self):
        response = types.SimpleNamespace(stop_reason='refusal', content=[])
        fake = self._fake_anthropic(response)
        session = FakeSession({'translate.googleapis.com': google_ok('Hej')})
        with mock.patch.dict(sys.modules, {'anthropic': fake}):
            t = Translator(FakeSettings(engine='claude', anthropic_api_key='k'), session)
            self.assertEqual(t.translate('Hey'), 'Hej')


class MyMemorySplitTests(unittest.TestCase):
    def test_short_text_single_chunk(self):
        self.assertEqual(_split_for_mymemory('Hello there.'), [('Hello there.', ' ')])

    def test_long_text_is_split_under_limit_and_keeps_lines(self):
        text = ('This is a sentence. ' * 60).strip() + '\nSecond line'
        chunks = _split_for_mymemory(text)
        self.assertTrue(all(len(c.encode('utf-8')) <= 450 for c, _ in chunks))
        self.assertGreater(len(chunks), 2)
        self.assertEqual(chunks[-1][0], 'Second line')
        self.assertIn('\n', [sep for _, sep in chunks])


if __name__ == '__main__':
    unittest.main()

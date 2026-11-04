#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Testy słownika nauki, wskazówek i OCR przez Claude (bez sieci i bez Qt)."""

import os
import sys
import json
import types
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from learning import VocabularyStore, LearningAssistant, REVIEW_INTERVALS  # noqa: E402


class FakeSettings:
    def __init__(self, translation=None, learning=None, ocr=None):
        self.data = {'translation': translation or {}, 'learning': learning or {}, 'ocr': ocr or {}}

    def get(self, category, key, default=None):
        return self.data.get(category, {}).get(key, default)

    def set(self, category, key, value):
        self.data.setdefault(category, {})[key] = value


def fake_anthropic(reply_text):
    """Atrapa modułu anthropic zwracająca podany tekst i zapisująca zapytania."""
    module = types.ModuleType('anthropic')

    class APIStatusError(Exception):
        status_code = 500

    class AuthenticationError(APIStatusError):
        pass

    class RateLimitError(APIStatusError):
        pass

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
            return types.SimpleNamespace(
                stop_reason='end_turn',
                content=[types.SimpleNamespace(type='text', text=reply_text)])

    class Client:
        def __init__(self, **kwargs):
            self.messages = Messages()
            self.beta = types.SimpleNamespace(messages=Messages())

    module.Anthropic = Client
    return module


class FakeTranslator:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def translate(self, text):
        self.calls.append(text)
        return '\n'.join(self.mapping.get(line, line) for line in text.split('\n'))


class VocabularyStoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, 'vocabulary.json')
        self.store = VocabularyStore(self.path)

    def test_record_and_persist(self):
        self.store.record_seen('Reluctant', 'niechętny', 'przymiotnik')
        self.store.record_seen('reluctant')
        reloaded = VocabularyStore(self.path)
        entry = reloaded.get('RELUCTANT')
        self.assertEqual(entry['seen'], 2)
        self.assertEqual(entry['translation'], 'niechętny')
        self.assertFalse(reloaded.is_learned('reluctant'))

    def test_mark_learned_and_leitner_reviews(self):
        now = datetime(2026, 11, 4, 12, 0)
        self.store.mark_learned('run out of', 'skończyć się', now=now)
        self.assertTrue(self.store.is_learned('Run Out Of'))
        self.assertEqual(self.store.due_reviews(now=now), [])
        later = now + timedelta(days=REVIEW_INTERVALS[0])
        self.assertEqual([e['term'] for e in self.store.due_reviews(now=later)], ['run out of'])

        entry = self.store.review('run out of', True, now=later)
        self.assertEqual(entry['box'], 1)
        self.assertEqual(self.store.due_reviews(now=later + timedelta(days=2)), [])
        entry = self.store.review('run out of', False, now=later)
        self.assertEqual(entry['box'], 0)
        self.assertEqual(entry['lapses'], 1)

    def test_unlearn_remove_stats_frequent(self):
        for _ in range(3):
            self.store.record_seen('ambush')
        self.store.mark_learned('quest')
        self.assertEqual([e['term'] for e in self.store.frequent_unlearned()], ['ambush'])
        self.assertEqual(self.store.stats()['learned'], 1)
        self.store.mark_unlearned('quest')
        self.assertFalse(self.store.is_learned('quest'))
        self.assertTrue(self.store.remove('quest'))
        self.assertEqual(self.store.stats()['total'], 1)

    def test_corrupted_file_does_not_crash(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write('{nie json')
        self.assertEqual(VocabularyStore(self.path).entries, {})


class LearningAssistantTests(unittest.TestCase):
    TEXT = "The merchant seemed reluctant to reveal the hidden treasure before nightfall."

    def setUp(self):
        self.store = VocabularyStore(os.path.join(tempfile.mkdtemp(), 'v.json'))
        os.environ.pop('ANTHROPIC_API_KEY', None)

    def test_free_mode_picks_rare_unlearned_words_and_translates_once(self):
        self.store.mark_learned('reluctant')
        translator = FakeTranslator({'nightfall': 'zmrok', 'treasure': 'skarb', 'merchant': 'kupiec'})
        assistant = LearningAssistant(FakeSettings(), self.store, translator)
        result = assistant.build(self.TEXT, 'Kupiec...')

        self.assertEqual(result['source'], 'free')
        terms = [h['term'] for h in result['hints']]
        self.assertEqual(len(terms), 3)
        self.assertNotIn('reluctant', terms)  # nauczone słowa pomijane
        self.assertNotIn('the', terms)
        self.assertIn('nightfall', terms)
        self.assertEqual(len(translator.calls), 1)  # jedno zapytanie na wszystkie słowa
        self.assertEqual(self.store.get('nightfall')['translation'], 'zmrok')
        self.assertEqual(self.store.get('nightfall')['seen'], 1)

    def test_ai_mode_uses_haiku_with_structured_output_and_known_words(self):
        self.store.mark_learned('reluctant')
        reply = json.dumps({'items': [
            {'term': 'reluctant', 'translation': 'niechętny', 'tip': '', 'level': 'B2'},
            {'term': 'reveal', 'translation': 'ujawnić', 'tip': 'reveal a secret = zdradzić sekret', 'level': 'B1'},
        ]})
        fake = fake_anthropic(reply)
        settings = FakeSettings(translation={'anthropic_api_key': 'sk-test'}, learning={'level': 'B2'})
        with mock.patch.dict(sys.modules, {'anthropic': fake}):
            result = LearningAssistant(settings, self.store, None).build(self.TEXT, 'tłumaczenie')

        self.assertEqual(result['source'], 'claude')
        self.assertEqual([h['term'] for h in result['hints']], ['reveal'])  # nauczone odfiltrowane
        params = fake.created[0]
        self.assertEqual(params['model'], 'claude-haiku-5-5')
        self.assertEqual(params['output_config']['format']['type'], 'json_schema')
        self.assertIn('reluctant', params['messages'][0]['content'])  # przekazane jako znane
        self.assertIn('B2', params['system'])

    def test_ai_failure_falls_back_to_free_mode(self):
        fake = fake_anthropic('to nie jest json')
        settings = FakeSettings(translation={'anthropic_api_key': 'sk-test'})
        with mock.patch.dict(sys.modules, {'anthropic': fake}):
            result = LearningAssistant(settings, self.store, FakeTranslator({})).build(self.TEXT)
        self.assertEqual(result['source'], 'free')
        self.assertTrue(result['hints'])

    def test_reviews_prefer_words_in_text(self):
        past = datetime.now() - timedelta(days=10)
        self.store.mark_learned('anvil', 'kowadło', now=past - timedelta(days=1))
        self.store.mark_learned('treasure', 'skarb', now=past)
        result = LearningAssistant(FakeSettings(learning={'max_hints': 0, 'use_ai': False}),
                                   self.store, FakeTranslator({})).build(self.TEXT)
        self.assertEqual([e['term'] for e in result['reviews']], ['treasure', 'anvil'])

    def test_disabled(self):
        result = LearningAssistant(FakeSettings(learning={'enabled': False}), self.store).build(self.TEXT)
        self.assertEqual(result['hints'], [])


class ClaudeOcrTests(unittest.TestCase):
    def setUp(self):
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
            import pytesseract  # noqa: F401
        except ImportError:
            self.skipTest("brak opencv/pytesseract")
        os.environ.pop('ANTHROPIC_API_KEY', None)

    def _image(self, width=120, height=40):
        import cv2
        import numpy as np
        path = os.path.join(tempfile.mkdtemp(), 'shot.png')
        cv2.imwrite(path, np.full((height, width, 3), 255, dtype=np.uint8))
        return path

    def test_auto_mode_uses_claude_vision_and_upscales_small_images(self):
        from ocr_engine import OCREngine
        import base64
        import cv2
        import numpy as np
        fake = fake_anthropic('PRESS START')
        settings = FakeSettings(translation={'anthropic_api_key': 'sk-test'}, ocr={'engine': 'auto'})
        with mock.patch.dict(sys.modules, {'anthropic': fake}):
            engine = OCREngine(settings)
            self.assertEqual(engine.process_image(self._image()), 'PRESS START')
        self.assertEqual(engine.last_engine, 'claude')
        block = fake.created[0]['messages'][0]['content'][0]
        self.assertEqual(block['type'], 'image')
        png = base64.b64decode(block['source']['data'])
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(img.shape[:2], (120, 360))  # 3x powiększenie małego wycinka

    def test_without_key_falls_back_to_tesseract(self):
        from ocr_engine import OCREngine
        with mock.patch('ocr_engine.OCREngine.process_with_tesseract', return_value='tess') as tess:
            engine = OCREngine(FakeSettings(ocr={'engine': 'auto'}))
            self.assertEqual(engine.process_image(self._image()), 'tess')
        tess.assert_called_once()
        self.assertEqual(engine.last_engine, 'tesseract')

    def test_tesseract_mode_never_calls_claude(self):
        from ocr_engine import OCREngine
        fake = fake_anthropic('x')
        settings = FakeSettings(translation={'anthropic_api_key': 'sk'}, ocr={'engine': 'tesseract'})
        with mock.patch.dict(sys.modules, {'anthropic': fake}), \
                mock.patch('ocr_engine.OCREngine.process_with_tesseract', return_value='tess'):
            self.assertEqual(OCREngine(settings).process_image(self._image()), 'tess')
        self.assertEqual(fake.created, [])


if __name__ == '__main__':
    unittest.main()

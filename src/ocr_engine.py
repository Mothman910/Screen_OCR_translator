#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moduł do rozpoznawania tekstu z obrazów.
"""

import os
import base64
import cv2
import numpy as np
import pytesseract
import logging
from pathlib import Path

from translator import (
    EngineUnavailable, DEFAULT_CLAUDE_MODEL, claude_api_key, claude_request,
)

logger = logging.getLogger('ocr_engine')

# Etykiety silników OCR w interfejsie
OCR_ENGINE_LABELS = {
    'auto': 'Automatycznie (Claude, gdy jest klucz; inaczej Tesseract)',
    'claude': 'Claude AI (najlepszy przy czcionkach z gier)',
    'tesseract': 'Tesseract OCR (lokalny, darmowy)',
}

CLAUDE_OCR_PROMPT = (
    "Transcribe all readable text in this screenshot region exactly as written, in natural "
    "reading order. Keep line breaks between separate lines or UI elements, join words that "
    "are visually wrapped within one sentence. Ignore icons and decorations. Do not translate, "
    "explain or add anything. If there is no readable text, reply with an empty message."
)


class OCREngine:
    """Silnik OCR: Claude (vision) lub Tesseract jako lokalny zapas."""
    
    def __init__(self, settings):
        """Inicjalizacja silnika OCR."""
        self.settings = settings
        self.last_engine = None
        
        # Konfiguracja Tesseract
        self.configure_tesseract()
        
        logger.info("Silnik OCR zainicjowany")
    
    def configure_tesseract(self):
        """Konfiguruje Tesseract OCR."""
        # Sprawdzenie, czy ustawiona jest ścieżka do Tesseract
        tesseract_path = self.settings.get('paths', 'tesseract')
        
        # Jeśli ścieżka jest pusta lub nieprawidłowa, spróbuj znaleźć Tesseract w projekcie
        if not tesseract_path or not os.path.exists(tesseract_path):
            # Ścieżka względna do Tesseract w folderze projektu
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            tesseract_project_path = os.path.join(project_root, 'external', 'Tesseract-OCR', 'tesseract.exe')
            
            if os.path.exists(tesseract_project_path):
                tesseract_path = tesseract_project_path
                # Zapisz wykrytą ścieżkę w ustawieniach
                self.settings.set('paths', 'tesseract', tesseract_path)
                logger.info(f"Znaleziono Tesseract w folderze projektu: {tesseract_path}")
        
        # Konfiguracja ścieżki do Tesseract
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            logger.info(f"Ustawiono Tesseract OCR: {tesseract_path}")
        else:
            logger.warning("Nie znaleziono Tesseract OCR. OCR może nie działać prawidłowo.")
        
        # Sprawdzenie, czy ustawiona jest ścieżka do danych tessdata
        tessdata_path = self.settings.get('paths', 'tessdata')
        
        # Jeśli ścieżka jest pusta lub nieprawidłowa, spróbuj znaleźć tessdata w projekcie
        if not tessdata_path or not os.path.exists(tessdata_path):
            # Ścieżka względna do tessdata w folderze projektu
            tessdata_project_path = os.path.join(project_root, 'external', 'Tesseract-OCR', 'tessdata')
            
            if os.path.exists(tessdata_project_path):
                tessdata_path = tessdata_project_path
                # Zapisz wykrytą ścieżkę w ustawieniach
                self.settings.set('paths', 'tessdata', tessdata_path)
                logger.info(f"Znaleziono tessdata w folderze projektu: {tessdata_path}")
        
        # Konfiguracja ścieżki do tessdata
        if tessdata_path and os.path.exists(tessdata_path):
            os.environ['TESSDATA_PREFIX'] = tessdata_path
            logger.info(f"Ustawiono TESSDATA_PREFIX: {tessdata_path}")
    
    def process_image(self, image_path):
        """Rozpoznaje tekst: najpierw Claude (jeśli wybrany i jest klucz), potem Tesseract."""
        self.last_engine = None
        engine = self.settings.get('ocr', 'engine', 'auto')
        if engine in ('auto', 'claude'):
            try:
                text = self.process_with_claude(image_path)
                self.last_engine = 'claude'
                logger.info("Rozpoznawanie tekstu przez Claude zakończone pomyślnie")
                return text
            except EngineUnavailable as e:
                log = logger.warning if engine == 'claude' else logger.info
                log(f"OCR Claude niedostępny ({e}), używam Tesseract")
            except Exception as e:  # noqa: BLE001 - zawsze mamy Tesseract jako zapas
                logger.warning(f"OCR Claude nie powiódł się ({e}), używam Tesseract")
        self.last_engine = 'tesseract'
        return self.process_with_tesseract(image_path)

    def process_with_claude(self, image_path):
        """OCR przez Claude Haiku (vision): ok. 0,1 gr za zrzut."""
        api_key = claude_api_key(self.settings)
        if not api_key:
            raise EngineUnavailable("brak klucza API Anthropic")
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Nie można wczytać obrazu: {image_path}")
        height, width = image.shape[:2]
        # Bardzo małe wycinki powiększamy, aby drobny tekst był czytelny
        if max(height, width) < 400:
            scale = 2 if max(height, width) >= 200 else 3
            image = cv2.resize(image, (width * scale, height * scale), interpolation=cv2.INTER_CUBIC)
        ok, buffer = cv2.imencode('.png', image)
        if not ok:
            raise ValueError("Nie udało się zakodować obrazu")
        data = base64.standard_b64encode(buffer.tobytes()).decode('ascii')
        content = [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': data}},
            {'type': 'text', 'text': CLAUDE_OCR_PROMPT},
        ]
        return claude_request(
            api_key,
            model=self.settings.get('translation', 'claude_model', DEFAULT_CLAUDE_MODEL),
            system="You are a precise OCR engine. Output only the transcribed text.",
            user_content=content,
            timeout=30.0,
        )

    def process_with_tesseract(self, image_path):
        """Przetwarza obraz i rozpoznaje tekst przez Tesseract."""
        try:
            logger.info(f"Przetwarzanie obrazu: {image_path}")
            
            # Wczytanie obrazu
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Nie można wczytać obrazu: {image_path}")
            
            # Zaawansowane przetwarzanie obrazu dla lepszego rozpoznawania tekstu
            processed_images = self.create_processing_variants(image)
            
            # Rozpoznawanie tekstu z wielu wariantów obrazu i wybór najlepszego rezultatu
            ocr_language = self.settings.get('ocr', 'language')
            texts_with_confidence = []
            
            config_psm_values = [6, 4, 3]  # Różne tryby segmentacji strony (Page Segmentation Modes)
            
            for idx, img in enumerate(processed_images):
                for psm in config_psm_values:
                    config = f'--psm {psm} --oem 1 -l {ocr_language}'
                    
                    # Dodanie flagi dla tesseracta, która wymusza wyższą dokładność kosztem szybkości
                    if self.settings.get('ocr', 'accuracy_mode') == 'high':
                        config += ' --tessdata-dir ' + self.settings.get('paths', 'tessdata')
                        
                    try:
                        # Użycie image_to_data aby uzyskać pewność rozpoznania
                        data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
                        
                        # Zbieranie tylko słów o wystarczającej pewności
                        threshold = self.get_confidence_threshold()
                        confident_words = []
                        confidences = []
                        
                        for i in range(len(data['text'])):
                            if int(data['conf'][i]) >= threshold:
                                if data['text'][i].strip():  # Tylko niepuste słowa
                                    confident_words.append(data['text'][i])
                                    confidences.append(int(data['conf'][i]))
                        
                        # Obliczenie średniej pewności dla całego tekstu
                        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                        text = ' '.join(confident_words)
                        
                        if text.strip():  # Jeśli jest jakiś tekst
                            texts_with_confidence.append((text, avg_confidence, f"variant_{idx}_psm_{psm}"))
                            
                    except Exception as e:
                        logger.warning(f"Błąd podczas rozpoznawania wariantu {idx} z PSM {psm}: {e}")
            
            # Wybór najlepszego wynikowego tekstu na podstawie pewności i długości
            best_text = self.select_best_text(texts_with_confidence)
            
            # Dodatkowe przetwarzanie rozpoznanego tekstu
            if best_text:
                best_text = self.intelligent_text_correction(best_text)
                logger.info("Rozpoznawanie tekstu zakończone pomyślnie")
            else:
                logger.warning("Nie rozpoznano tekstu na obrazie")
            
            return best_text
            
        except Exception as e:
            logger.error(f"Błąd podczas rozpoznawania tekstu przez Tesseract: {e}")
            return ""
    
    def create_processing_variants(self, image):
        """Tworzy różne warianty przetworzenia obrazu dla zwiększenia skuteczności OCR."""
        variants = []
        
        # Wariant 1: Podstawowy obraz w skali szarości
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variants.append(gray)
        
        # Wariant 2: Binaryzacja adaptacyjna z rozmyciem gaussowskim
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        variants.append(binary)
        
        # Wariant 3: Powiększony obraz dla małych czcionek
        resized = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        variants.append(resized)
        
        # Wariant 4: Zwiększony kontrast
        contrast_img = gray.copy()
        contrast_img = cv2.equalizeHist(contrast_img)
        variants.append(contrast_img)
        
        # Wariant 5: Redukcja szumu
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        variants.append(denoised)
        
        # Wariant 6: Wyostrzenie krawędzi
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(gray, -1, kernel)
        variants.append(sharpened)
        
        return variants
    
    def select_best_text(self, texts_with_confidence):
        """Wybiera najlepszy tekst z rozpoznanych wariantów."""
        if not texts_with_confidence:
            return ""
            
        # Sortowanie według pewności (malejąco)
        texts_with_confidence.sort(key=lambda x: x[1], reverse=True)
        
        # Wybór tekstu o najwyższej pewności, który ma sensowną długość
        for text, confidence, variant in texts_with_confidence:
            # Sprawdzamy, czy tekst zawiera sensowne znaki (np. litery i spacje)
            if len(text) > 3 and any(c.isalpha() for c in text):
                logger.info(f"Wybrano wariant: {variant} z pewnością {confidence:.2f}%")
                return text
        
        # Jeśli żaden tekst nie spełnia kryteriów, zwróć pierwszy
        if texts_with_confidence:
            return texts_with_confidence[0][0]
        return ""
    
    def get_confidence_threshold(self):
        """Zwraca próg pewności na podstawie wybranego trybu."""
        mode = self.settings.get('ocr', 'accuracy_mode', 'balanced')
        
        if mode == 'high':
            return 85  # Wysoki próg pewności - mniej tekstu, ale bardziej dokładny
        elif mode == 'low':
            return 40  # Niski próg pewności - więcej tekstu, ale możliwe błędy
        else:  # 'balanced'
            return 60  # Zbalansowany próg pewności
    
    def intelligent_text_correction(self, text):
        """Inteligentna korekta rozpoznanego tekstu."""
        if not text:
            return ""
        
        # 1. Usuwanie nadmiarowych białych znaków
        text = ' '.join(text.split())
        
        # 2. Korekta typowych błędów OCR
        common_errors = {
            '0': 'o', 'O': 'o',  # Cyfra zero jako litera "o"
            '1': 'l', 'I': 'l',  # Cyfra jeden jako litera "l"
            '5': 's', 'S': 's',  # Cyfra pięć jako litera "s"
            '8': 'B',            # Cyfra osiem jako litera "B"
            'rnm': 'mm',         # "rnm" jako "mm"
            'rn': 'm',           # "rn" jako "m"
            'ii': 'n',           # "ii" jako "n"
            'vv': 'w',           # "vv" jako "w"
            'cl': 'd',           # "cl" jako "d"
            'nn': 'rm',          # "nn" jako "rm"
        }
        
        for error, correction in common_errors.items():
            text = text.replace(error, correction)
        
        # 3. Korekta interpunkcji
        text = text.replace(' .', '.').replace(' ,', ',').replace(' !', '!')
        text = text.replace(' ?', '?').replace(' :', ':').replace(' ;', ';')
        
        # 4. Inteligentne rozpoznawanie zdań
        sentences = []
        for sentence in text.split('. '):
            if sentence:
                # Jeśli zdanie nie kończy się kropką, a powinno - dodaj ją
                if sentence[-1] not in ['.', '!', '?']:
                    sentence += '.'
                sentences.append(sentence)
        
        text = ' '.join(sentences)
        
        return text
    
    def preprocess_image(self, image):
        """Przetwarza obraz przed OCR dla zwiększenia dokładności."""
        try:
            # Ta metoda pozostawiona dla kompatybilności wstecz, ale główna implementacja
            # przeniesiona do create_processing_variants i process_image
            return self.create_processing_variants(image)[1]  # Zwracamy wariant binaryzacji adaptacyjnej
            
        except Exception as e:
            logger.error(f"Błąd podczas przetwarzania obrazu: {e}")
            return image  # Zwrócenie oryginalnego obrazu w przypadku błędu
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moduł obsługujący ustawienia aplikacji.
"""

import os
import copy
import json
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget,
    QComboBox, QCheckBox, QSpinBox, QColorDialog, QFileDialog, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

logger = logging.getLogger('settings')

class Settings:
    """Klasa zarządzająca ustawieniami aplikacji."""
    
    def __init__(self):
        """Inicjalizacja ustawień aplikacji."""
        # Określenie ścieżki do pliku ustawień
        self.settings_dir = os.path.join(
            os.path.expanduser('~'), 
            'AppData', 'Local', 'ScreenOCR & Translator'
        )
        self.settings_file = os.path.join(self.settings_dir, 'settings.json')
        
        # Domyślne ustawienia
        self.default_settings = {
            'general': {
                'language': 'pl',
                'start_with_windows': False,
                'check_updates': True
            },
            'hotkeys': {
                'capture': 'Alt+F7',
                'predefined_hotkeys': ['Alt+F7', 'Ctrl+Alt+T', 'F9', 'Ctrl+Alt+S', 'Alt+Z', 'Ctrl+`']
            },
            'ocr': {
                'engine': 'auto',  # auto (Claude gdy jest klucz, inaczej Tesseract), claude, tesseract
                'language': 'eng',  # język dla OCR
                'preprocess': True,  # wstępne przetwarzanie obrazu
                'accuracy_mode': 'balanced',  # tryb dokładności: 'high', 'balanced', 'low'
                'text_processing': True  # inteligentne przetwarzanie tekstu
            },
            'translation': {
                'engine': 'deepl',  # deepl, claude, google, mymemory
                # kolejność silników zapasowych, gdy główny zawiedzie
                'fallback_engines': ['deepl', 'claude', 'google', 'mymemory'],
                'source_lang': 'en',
                'target_lang': 'pl',
                'auto_copy': False,  # automatycznie kopiuj przetłumaczony tekst
                'deepl_api_key': '',  # lub zmienna środowiskowa DEEPL_API_KEY
                'anthropic_api_key': '',  # lub zmienna środowiskowa ANTHROPIC_API_KEY
                'claude_model': 'claude-haiku-5-5',  # najtańszy: ułamek grosza za ekran
                'mymemory_email': '',  # opcjonalnie: podnosi dzienny limit MyMemory
                'timeout': 10,  # limit czasu zapytania (s)
                'config_version': 3
            },
            'learning': {
                'enabled': True,  # wskazówki do nauki w pop-upie
                'use_ai': True,  # Claude Haiku, gdy jest klucz; inaczej darmowy tryb
                'level': 'B1',  # poziom angielskiego: A2, B1, B2, C1
                'max_hints': 3,  # ile nowych słów pokazywać
                'max_reviews': 2  # ile powtórek pokazywać
            },
            'popup': {
                'position': 'top-right',  # pozycja popup'u
                'width': 300,  # szerokość popup'u
                'height': 200,  # wysokość popup'u
                'opacity': 80,  # przezroczystość (%)
                'auto_hide': True,  # automatycznie ukryj po czasie
                'display_time': 5,  # czas wyświetlania w sekundach
                'bg_color': '#2E2E2E',  # kolor tła
                'text_color': '#FFFFFF',  # kolor tekstu
                'show_original': True  # pokazuj oryginalny tekst
            },
            'paths': {
                'tesseract': '',  # ścieżka do Tesseract OCR
                'tessdata': ''  # ścieżka do danych językowych Tesseract
            }
        }
        
        # Wczytanie ustawień lub utworzenie domyślnych
        self.settings = self.load_settings()
        
    def load_settings(self):
        """Wczytuje ustawienia z pliku lub tworzy domyślne."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                logger.info("Wczytano ustawienia z pliku")
                migrated = self._migrate_settings(settings)
                # Uzupełnianie brakujących ustawień domyślnymi
                settings = self._merge_settings(settings, self.default_settings)
                if migrated:
                    self.save_settings(settings)
                return settings
            except Exception as e:
                logger.error(f"Błąd wczytywania ustawień: {e}")
                return copy.deepcopy(self.default_settings)
        else:
            logger.info("Tworzenie domyślnych ustawień")
            # Utworzenie katalogu ustawień, jeśli nie istnieje
            os.makedirs(self.settings_dir, exist_ok=True)
            self.save_settings(self.default_settings)
            return copy.deepcopy(self.default_settings)

    def _migrate_settings(self, user_settings):
        """Aktualizuje ustawienia zapisane przez starsze wersje programu.

        Wersja 2: domyślnym silnikiem zostaje DeepL (z Google jako fallback),
        bo nieoficjalne API Google często odmawia działania.
        Wersja 3: domyślny model Claude to tani Haiku 5.5 zamiast Opus,
        a OCR przechodzi w tryb "auto" (Claude, gdy jest klucz; inaczej Tesseract).
        """
        translation = user_settings.get('translation')
        if not isinstance(translation, dict):
            return False
        version = translation.get('config_version', 1)
        if version >= 3:
            return False
        if version < 2 and translation.get('engine', 'google') == 'google':
            translation['engine'] = 'deepl'
            logger.info("Migracja ustawień: domyślny silnik tłumaczenia zmieniony na DeepL")
        ocr = user_settings.get('ocr')
        if isinstance(ocr, dict) and ocr.get('engine', 'tesseract') == 'tesseract':
            ocr['engine'] = 'auto'
            logger.info("Migracja ustawień: OCR w trybie automatycznym (Claude/Tesseract)")
        if translation.get('claude_model') == 'claude-opus-5-5':
            translation['claude_model'] = 'claude-haiku-5-5'
            logger.info("Migracja ustawień: model Claude zmieniony na tańszy Haiku 5.5")
        translation['config_version'] = 3
        return True
    
    def _merge_settings(self, user_settings, default_settings):
        """Łączy ustawienia użytkownika z domyślnymi, uzupełniając brakujące wartości."""
        merged_settings = copy.deepcopy(default_settings)
        
        for category, values in user_settings.items():
            if category in merged_settings:
                if isinstance(values, dict):
                    for key, value in values.items():
                        if key in merged_settings[category]:
                            merged_settings[category][key] = value
                else:
                    merged_settings[category] = values
        
        return merged_settings
    
    def save_settings(self, settings=None):
        """Zapisuje ustawienia do pliku."""
        if settings is None:
            settings = self.settings
        
        try:
            os.makedirs(self.settings_dir, exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            logger.info("Zapisano ustawienia do pliku")
            return True
        except Exception as e:
            logger.error(f"Błąd zapisywania ustawień: {e}")
            return False
    
    def get(self, category, key, default=None):
        """Pobiera wartość ustawienia."""
        try:
            return self.settings[category][key]
        except KeyError:
            if default is None and category in self.default_settings and key in self.default_settings[category]:
                return self.default_settings[category][key]
            return default
    
    def set(self, category, key, value):
        """Ustawia wartość ustawienia i zapisuje do pliku."""
        if category not in self.settings:
            self.settings[category] = {}
        
        self.settings[category][key] = value
        return self.save_settings()
    
    def get_hotkey(self, action, default=None):
        """Pobiera skrót klawiszowy dla danej akcji."""
        return self.get('hotkeys', action, default)
    
    def set_hotkey(self, action, hotkey):
        """Ustawia skrót klawiszowy dla danej akcji."""
        return self.set('hotkeys', action, hotkey)

class SettingsDialog(QDialog):
    """Dialog ustawień aplikacji."""
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Ustawienia")
        self.setMinimumSize(500, 400)
        self.setup_ui()
        self.load_settings_to_ui()
        
    def setup_ui(self):
        """Konfiguracja interfejsu użytkownika dialogu ustawień."""
        layout = QVBoxLayout()
        
        # Zakładki ustawień
        self.tabs = QTabWidget()
        self.general_tab = QWidget()
        self.hotkeys_tab = QWidget()
        self.ocr_tab = QWidget()
        self.translation_tab = QWidget()
        self.popup_tab = QWidget()
        self.learning_tab = QWidget()
        self.advanced_tab = QWidget()
        
        self.setup_general_tab()
        self.setup_hotkeys_tab()
        self.setup_ocr_tab()
        self.setup_translation_tab()
        self.setup_popup_tab()
        self.setup_learning_tab()
        self.setup_advanced_tab()
        
        self.tabs.addTab(self.general_tab, "Ogólne")
        self.tabs.addTab(self.hotkeys_tab, "Skróty klawiszowe")
        self.tabs.addTab(self.ocr_tab, "OCR")
        self.tabs.addTab(self.translation_tab, "Tłumaczenie")
        self.tabs.addTab(self.popup_tab, "Wyświetlanie")
        self.tabs.addTab(self.learning_tab, "Nauka")
        self.tabs.addTab(self.advanced_tab, "Zaawansowane")
        
        layout.addWidget(self.tabs)
        
        # Przyciski OK/Anuluj
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.save_and_close)
        
        self.cancel_button = QPushButton("Anuluj")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def setup_general_tab(self):
        """Konfiguracja zakładki ogólnych ustawień."""
        layout = QFormLayout()
        
        # Język interfejsu
        self.language_combo = QComboBox()
        self.language_combo.addItem("Polski", "pl")
        self.language_combo.addItem("English", "en")
        layout.addRow("Język interfejsu:", self.language_combo)
        
        # Autostart z Windowsem
        self.autostart_check = QCheckBox()
        layout.addRow("Uruchamiaj z systemem:", self.autostart_check)
        
        # Sprawdzanie aktualizacji
        self.check_updates_check = QCheckBox()
        layout.addRow("Sprawdzaj aktualizacje:", self.check_updates_check)
        
        self.general_tab.setLayout(layout)
    
    def setup_hotkeys_tab(self):
        """Konfiguracja zakładki skrótów klawiszowych."""
        layout = QFormLayout()
        
        # Skrót do przechwytywania ekranu - teraz z listą predefiniowanych opcji
        self.capture_hotkey_combo = QComboBox()
        
        # Pobieranie predefiniowanych skrótów z ustawień
        predefined_hotkeys = self.settings.get('hotkeys', 'predefined_hotkeys', 
                                              ['Alt+F7', 'Ctrl+Alt+T', 'F9', 'Ctrl+Alt+S', 'Alt+Z', 'Ctrl+`'])
        
        # Dodawanie predefiniowanych skrótów do ComboBox
        for hotkey in predefined_hotkeys:
            self.capture_hotkey_combo.addItem(hotkey)
        
        # Dodanie opcji "Własny skrót..."
        self.capture_hotkey_combo.addItem("Własny skrót...")
        self.capture_hotkey_combo.currentTextChanged.connect(self.on_hotkey_selection_changed)
        
        # Pole do ręcznego wprowadzania skrótu (początkowo ukryte)
        self.capture_hotkey_edit = QLineEdit()
        self.capture_hotkey_edit.setPlaceholderText("Kliknij i naciśnij kombinację klawiszy")
        self.capture_hotkey_edit.setReadOnly(True)
        self.capture_hotkey_edit.hide()  # Domyślnie ukryte
        
        # Przycisk do testowania skrótu klawiszowego
        self.test_hotkey_button = QPushButton("Testuj skrót")
        self.test_hotkey_button.clicked.connect(self.on_test_hotkey_clicked)
        
        # Dodanie wszystkich elementów do layoutu
        hotkey_layout = QHBoxLayout()
        hotkey_layout.addWidget(self.capture_hotkey_combo)
        hotkey_layout.addWidget(self.capture_hotkey_edit)
        hotkey_layout.addWidget(self.test_hotkey_button)
        
        layout.addRow("Przechwyć ekran:", hotkey_layout)
        
        # Dodanie wyjaśnienia odnośnie skrótów klawiszowych
        hotkey_info = QLabel(
            "Zalecane skróty to kombinacje rzadko używane w innych aplikacjach, "
            "np. Alt+F7, F9 czy Ctrl+Alt+S. Jeśli skrót nie działa, spróbuj "
            "innej kombinacji klawiszy."
        )
        hotkey_info.setWordWrap(True)
        layout.addRow("", hotkey_info)
        
        self.hotkeys_tab.setLayout(layout)
    
    def on_hotkey_selection_changed(self, text):
        """Obsługa zmiany wyboru skrótu klawiszowego."""
        if text == "Własny skrót...":
            self.capture_hotkey_edit.show()
            self.capture_hotkey_edit.setText("")
            self.capture_hotkey_edit.setFocus()
        else:
            self.capture_hotkey_edit.hide()
            
    def on_test_hotkey_clicked(self):
        """Otwiera okno testowe do sprawdzenia działania skrótu klawiszowego."""
        try:
            # Poprawiony import z pełną ścieżką
            import sys
            import os
            
            # Dodanie katalogu src do sys.path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.append(current_dir)
                
            from utils.hotkey_tester import HotkeyTesterDialog
            
            # Pobranie aktualnie wybranego skrótu
            if self.capture_hotkey_combo.currentText() == "Własny skrót...":
                hotkey = self.capture_hotkey_edit.text()
            else:
                hotkey = self.capture_hotkey_combo.currentText()
                
            # Jeśli skrót jest pusty, użyj domyślnego
            if not hotkey:
                hotkey = self.settings.get_hotkey('capture', 'Alt+F7')
            
            # Otwórz okno testowe
            tester = HotkeyTesterDialog(hotkey, self)
            tester.exec()
        except ImportError as e:
            import traceback
            print(f"Błąd importu: {e}")
            print(traceback.format_exc())
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Błąd importu", f"Nie można zaimportować modułu do testowania: {e}")
        except Exception as e:
            import traceback
            print(f"Błąd: {e}")
            print(traceback.format_exc())
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd podczas testowania skrótu: {e}")
    
    def setup_ocr_tab(self):
        """Konfiguracja zakładki OCR."""
        layout = QFormLayout()
        
        # Silnik OCR
        from ocr_engine import OCR_ENGINE_LABELS

        self.ocr_engine_combo = QComboBox()
        for engine, label in OCR_ENGINE_LABELS.items():
            self.ocr_engine_combo.addItem(label, engine)
        layout.addRow("Silnik OCR:", self.ocr_engine_combo)
        ocr_engine_info = QLabel(
            "Claude czyta tekst prosto z obrazu (także stylizowane czcionki z gier) i kosztuje "
            "ułamek grosza za zrzut. Wymaga klucza Claude z zakładki Tłumaczenie. "
            "Gdy Claude jest niedostępny, program sam użyje Tesseract."
        )
        ocr_engine_info.setWordWrap(True)
        layout.addRow("", ocr_engine_info)
        
        # Język OCR
        self.ocr_language_combo = QComboBox()
        self.ocr_language_combo.addItem("Angielski", "eng")
        self.ocr_language_combo.addItem("Polski", "pol")
        layout.addRow("Język rozpoznawania:", self.ocr_language_combo)
        
        # Wstępne przetwarzanie obrazu
        self.preprocess_check = QCheckBox()
        layout.addRow("Przetwarzanie obrazu:", self.preprocess_check)
        
        # Tryb dokładności
        self.accuracy_mode_combo = QComboBox()
        self.accuracy_mode_combo.addItem("Wysoka dokładność", "high")
        self.accuracy_mode_combo.addItem("Zrównoważony", "balanced")
        self.accuracy_mode_combo.addItem("Maksymalne rozpoznawanie", "low")
        
        # Dodanie opisu trybu dokładności
        accuracy_description = QLabel(
            "Tryb dokładności wpływa na rozpoznawanie tekstu:\n"
            "• Wysoka dokładność - mniej tekstu, ale większa pewność poprawności\n"
            "• Zrównoważony - optymalny stosunek ilości tekstu do dokładności\n"
            "• Maksymalne rozpoznawanie - więcej tekstu, nawet przy niższej pewności"
        )
        accuracy_description.setWordWrap(True)
        
        # Układy dla trybu dokładności
        accuracy_layout = QVBoxLayout()
        accuracy_layout.addWidget(self.accuracy_mode_combo)
        accuracy_layout.addWidget(accuracy_description)
        
        layout.addRow("Tryb dokładności:", accuracy_layout)
        
        # Inteligentne przetwarzanie tekstu
        self.text_processing_check = QCheckBox()
        text_processing_description = QLabel(
            "Włącza inteligentne przetwarzanie tekstu, które wykrywa i koryguje "
            "typowe błędy OCR, poprawia interpunkcję oraz rozpoznaje pełne zdania."
        )
        text_processing_description.setWordWrap(True)
        
        text_processing_layout = QVBoxLayout()
        text_processing_layout.addWidget(self.text_processing_check)
        text_processing_layout.addWidget(text_processing_description)
        
        layout.addRow("Inteligentne przetwarzanie tekstu:", text_processing_layout)
        
        self.ocr_tab.setLayout(layout)
    
    def setup_translation_tab(self):
        """Konfiguracja zakładki tłumaczenia."""
        layout = QFormLayout()
        
        from translator import ENGINE_LABELS

        # Silnik tłumaczenia
        self.translation_engine_combo = QComboBox()
        for engine, label in ENGINE_LABELS.items():
            self.translation_engine_combo.addItem(label, engine)
        layout.addRow("Silnik tłumaczenia:", self.translation_engine_combo)

        engine_info = QLabel(
            "Jeśli wybrany silnik zawiedzie, program automatycznie spróbuje kolejnych: "
            "DeepL → Claude → Google → MyMemory. Silniki bez klucza API są pomijane."
        )
        engine_info.setWordWrap(True)
        layout.addRow("", engine_info)

        # Klucz API DeepL
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_key_edit.setPlaceholderText("Darmowy klucz z deepl.com/pro-api (kończy się na :fx)")
        layout.addRow("Klucz API DeepL:", self.deepl_key_edit)

        # Klucz API Anthropic (Claude)
        self.anthropic_key_edit = QLineEdit()
        self.anthropic_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key_edit.setPlaceholderText("sk-ant-... z platform.claude.com")
        layout.addRow("Klucz API Claude:", self.anthropic_key_edit)

        # Model Claude
        self.claude_model_combo = QComboBox()
        self.claude_model_combo.setEditable(True)
        self.claude_model_combo.addItem("claude-haiku-5-5 (zalecany: najtańszy, ~0,1 gr za ekran)", "claude-haiku-5-5")
        self.claude_model_combo.addItem("claude-sonnet-5-5 (~20x drożej)", "claude-sonnet-5-5")
        self.claude_model_combo.addItem("claude-opus-5-5 (~40x drożej)", "claude-opus-5-5")
        layout.addRow("Model Claude:", self.claude_model_combo)

        # Test tłumaczenia
        self.test_translation_button = QPushButton("Testuj tłumaczenie")
        self.test_translation_button.clicked.connect(self.on_test_translation_clicked)
        self.test_translation_result = QLabel("")
        self.test_translation_result.setWordWrap(True)
        test_layout = QVBoxLayout()
        test_layout.addWidget(self.test_translation_button)
        test_layout.addWidget(self.test_translation_result)
        layout.addRow("", test_layout)
        
        # Język źródłowy
        self.source_language_combo = QComboBox()
        self.source_language_combo.addItem("Angielski", "en")
        layout.addRow("Język źródłowy:", self.source_language_combo)
        
        # Język docelowy
        self.target_language_combo = QComboBox()
        self.target_language_combo.addItem("Polski", "pl")
        layout.addRow("Język docelowy:", self.target_language_combo)
        
        # Automatyczne kopiowanie
        self.auto_copy_check = QCheckBox()
        layout.addRow("Auto-kopiowanie tłumaczenia:", self.auto_copy_check)
        
        self.translation_tab.setLayout(layout)
    
    def setup_popup_tab(self):
        """Konfiguracja zakładki wyświetlania pop-up."""
        layout = QFormLayout()
        
        # Pozycja pop-up
        self.position_combo = QComboBox()
        self.position_combo.addItem("Prawy górny róg", "top-right")
        self.position_combo.addItem("Lewy górny róg", "top-left")
        self.position_combo.addItem("Prawy dolny róg", "bottom-right")
        self.position_combo.addItem("Lewy dolny róg", "bottom-left")
        self.position_combo.addItem("Środek", "center")
        layout.addRow("Pozycja pop-up:", self.position_combo)
        
        # Szerokość pop-up
        self.width_spin = QSpinBox()
        self.width_spin.setRange(100, 800)
        self.width_spin.setSuffix(" px")
        layout.addRow("Szerokość:", self.width_spin)
        
        # Wysokość pop-up
        self.height_spin = QSpinBox()
        self.height_spin.setRange(50, 600)
        self.height_spin.setSuffix(" px")
        layout.addRow("Wysokość:", self.height_spin)
        
        # Przezroczystość
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(10, 100)
        self.opacity_spin.setSuffix("%")
        layout.addRow("Przezroczystość:", self.opacity_spin)
        
        # Automatyczne ukrywanie
        self.auto_hide_check = QCheckBox()
        layout.addRow("Automatyczne ukrywanie:", self.auto_hide_check)
        
        # Czas wyświetlania
        self.display_time_spin = QSpinBox()
        self.display_time_spin.setRange(1, 30)
        self.display_time_spin.setSuffix(" s")
        layout.addRow("Czas wyświetlania:", self.display_time_spin)
        
        # Kolor tła
        self.bg_color_button = QPushButton()
        self.bg_color_button.clicked.connect(self.select_bg_color)
        layout.addRow("Kolor tła:", self.bg_color_button)
        
        # Kolor tekstu
        self.text_color_button = QPushButton()
        self.text_color_button.clicked.connect(self.select_text_color)
        layout.addRow("Kolor tekstu:", self.text_color_button)
        
        # Pokazuj oryginalny tekst
        self.show_original_check = QCheckBox()
        layout.addRow("Pokazuj oryginalny tekst:", self.show_original_check)
        
        self.popup_tab.setLayout(layout)
    
    def setup_learning_tab(self):
        """Konfiguracja zakładki nauki słownictwa."""
        layout = QFormLayout()

        self.learning_enabled_check = QCheckBox()
        layout.addRow("Wskazówki do nauki w pop-upie:", self.learning_enabled_check)

        self.learning_ai_check = QCheckBox()
        layout.addRow("Wskazówki AI (Claude Haiku):", self.learning_ai_check)

        self.learning_level_combo = QComboBox()
        for level, label in [('A2', 'A2 - podstawowy'), ('B1', 'B1 - średni'),
                             ('B2', 'B2 - średnio zaawansowany'), ('C1', 'C1 - zaawansowany')]:
            self.learning_level_combo.addItem(label, level)
        layout.addRow("Mój poziom angielskiego:", self.learning_level_combo)

        self.max_hints_spin = QSpinBox()
        self.max_hints_spin.setRange(0, 6)
        layout.addRow("Nowe słowa na ekran:", self.max_hints_spin)

        self.max_reviews_spin = QSpinBox()
        self.max_reviews_spin.setRange(0, 5)
        layout.addRow("Powtórki na ekran:", self.max_reviews_spin)

        info = QLabel(
            "Po każdym tłumaczeniu pop-up pokazuje kilka słów wartych nauki. Kliknij „✓ Znam”, "
            "aby oznaczyć słowo jako nauczone: nie będzie już proponowane, a wróci do powtórki "
            "po 1, 3, 7, 16, 35 i 90 dniach. Z kluczem Claude wskazówki tworzy AI "
            "(koszt ułamka grosza), bez klucza działa darmowy tryb. Słownik otworzysz z menu "
            "ikony w zasobniku: „Mój słownik”."
        )
        info.setWordWrap(True)
        layout.addRow("", info)

        self.learning_tab.setLayout(layout)

    def setup_advanced_tab(self):
        """Konfiguracja zakładki zaawansowanych ustawień."""
        layout = QFormLayout()
        
        # Ścieżka do Tesseract OCR
        self.tesseract_path_edit = QLineEdit()
        self.tesseract_path_edit.setReadOnly(True)
        self.tesseract_path_button = QPushButton("Wybierz...")
        self.tesseract_path_button.clicked.connect(self.select_tesseract_path)
        
        tesseract_layout = QHBoxLayout()
        tesseract_layout.addWidget(self.tesseract_path_edit)
        tesseract_layout.addWidget(self.tesseract_path_button)
        
        layout.addRow("Ścieżka do Tesseract:", tesseract_layout)
        
        # Ścieżka do danych tessdata
        self.tessdata_path_edit = QLineEdit()
        self.tessdata_path_edit.setReadOnly(True)
        self.tessdata_path_button = QPushButton("Wybierz...")
        self.tessdata_path_button.clicked.connect(self.select_tessdata_path)
        
        tessdata_layout = QHBoxLayout()
        tessdata_layout.addWidget(self.tessdata_path_edit)
        tessdata_layout.addWidget(self.tessdata_path_button)
        
        layout.addRow("Ścieżka do tessdata:", tessdata_layout)
        
        self.advanced_tab.setLayout(layout)
    
    def load_settings_to_ui(self):
        """Wczytuje ustawienia do interfejsu użytkownika."""
        # Zakładka Ogólne
        self.set_combo_by_value(self.language_combo, self.settings.get('general', 'language'))
        self.autostart_check.setChecked(self.settings.get('general', 'start_with_windows'))
        self.check_updates_check.setChecked(self.settings.get('general', 'check_updates'))
        
        # Zakładka Skróty klawiszowe
        current_hotkey = self.settings.get_hotkey('capture')
        
        # Szukanie skrótu na liście predefinowanych
        found = False
        for i in range(self.capture_hotkey_combo.count() - 1):  # Bez "Własny skrót..."
            if self.capture_hotkey_combo.itemText(i) == current_hotkey:
                self.capture_hotkey_combo.setCurrentIndex(i)
                found = True
                break
        
        # Jeśli skrót nie jest na liście predefinowanych, użyj opcji "Własny skrót..."
        if not found:
            self.capture_hotkey_combo.setCurrentIndex(self.capture_hotkey_combo.count() - 1)  # Ostatni element
            self.capture_hotkey_edit.setText(current_hotkey)
            self.capture_hotkey_edit.show()
        
        # Zakładka OCR
        self.set_combo_by_value(self.ocr_engine_combo, self.settings.get('ocr', 'engine'))
        self.set_combo_by_value(self.ocr_language_combo, self.settings.get('ocr', 'language'))
        self.preprocess_check.setChecked(self.settings.get('ocr', 'preprocess'))
        self.set_combo_by_value(self.accuracy_mode_combo, self.settings.get('ocr', 'accuracy_mode', 'balanced'))
        self.text_processing_check.setChecked(self.settings.get('ocr', 'text_processing', True))
        
        # Zakładka Tłumaczenie
        self.set_combo_by_value(self.translation_engine_combo, self.settings.get('translation', 'engine'))
        self.set_combo_by_value(self.source_language_combo, self.settings.get('translation', 'source_lang'))
        self.set_combo_by_value(self.target_language_combo, self.settings.get('translation', 'target_lang'))
        self.auto_copy_check.setChecked(self.settings.get('translation', 'auto_copy'))
        self.deepl_key_edit.setText(self.settings.get('translation', 'deepl_api_key', ''))
        self.anthropic_key_edit.setText(self.settings.get('translation', 'anthropic_api_key', ''))
        self.set_claude_model(self.settings.get('translation', 'claude_model', 'claude-haiku-5-5'))
        
        # Zakładka Nauka
        self.learning_enabled_check.setChecked(bool(self.settings.get('learning', 'enabled', True)))
        self.learning_ai_check.setChecked(bool(self.settings.get('learning', 'use_ai', True)))
        self.set_combo_by_value(self.learning_level_combo, self.settings.get('learning', 'level', 'B1'))
        self.max_hints_spin.setValue(int(self.settings.get('learning', 'max_hints', 3)))
        self.max_reviews_spin.setValue(int(self.settings.get('learning', 'max_reviews', 2)))

        # Zakładka Wyświetlanie
        self.set_combo_by_value(self.position_combo, self.settings.get('popup', 'position'))
        self.width_spin.setValue(self.settings.get('popup', 'width'))
        self.height_spin.setValue(self.settings.get('popup', 'height'))
        self.opacity_spin.setValue(self.settings.get('popup', 'opacity'))
        self.auto_hide_check.setChecked(self.settings.get('popup', 'auto_hide'))
        self.display_time_spin.setValue(self.settings.get('popup', 'display_time'))
        self.update_color_button(self.bg_color_button, self.settings.get('popup', 'bg_color'))
        self.update_color_button(self.text_color_button, self.settings.get('popup', 'text_color'))
        self.show_original_check.setChecked(self.settings.get('popup', 'show_original'))
        
        # Zakładka Zaawansowane
        self.tesseract_path_edit.setText(self.settings.get('paths', 'tesseract'))
        self.tessdata_path_edit.setText(self.settings.get('paths', 'tessdata'))
    
    def save_settings_from_ui(self):
        """Zapisuje ustawienia z interfejsu użytkownika."""
        # Zakładka Ogólne
        self.settings.set('general', 'language', self.get_combo_value(self.language_combo))
        self.settings.set('general', 'start_with_windows', self.autostart_check.isChecked())
        self.settings.set('general', 'check_updates', self.check_updates_check.isChecked())
        
        # Zakładka Skróty klawiszowe
        if self.capture_hotkey_combo.currentText() == "Własny skrót...":
            if self.capture_hotkey_edit.text():
                self.settings.set_hotkey('capture', self.capture_hotkey_edit.text())
            # Jeśli pole własnego skrótu jest puste, zachowujemy poprzednią wartość
        else:
            self.settings.set_hotkey('capture', self.capture_hotkey_combo.currentText())
        
        # Zakładka OCR
        self.settings.set('ocr', 'engine', self.get_combo_value(self.ocr_engine_combo))
        self.settings.set('ocr', 'language', self.get_combo_value(self.ocr_language_combo))
        self.settings.set('ocr', 'preprocess', self.preprocess_check.isChecked())
        self.settings.set('ocr', 'accuracy_mode', self.get_combo_value(self.accuracy_mode_combo))
        self.settings.set('ocr', 'text_processing', self.text_processing_check.isChecked())
        
        # Zakładka Tłumaczenie
        self.settings.set('translation', 'engine', self.get_combo_value(self.translation_engine_combo))
        self.settings.set('translation', 'source_lang', self.get_combo_value(self.source_language_combo))
        self.settings.set('translation', 'target_lang', self.get_combo_value(self.target_language_combo))
        self.settings.set('translation', 'auto_copy', self.auto_copy_check.isChecked())
        self.settings.set('translation', 'deepl_api_key', self.deepl_key_edit.text().strip())
        self.settings.set('translation', 'anthropic_api_key', self.anthropic_key_edit.text().strip())
        self.settings.set('translation', 'claude_model', self.get_claude_model())
        
        # Zakładka Nauka
        self.settings.set('learning', 'enabled', self.learning_enabled_check.isChecked())
        self.settings.set('learning', 'use_ai', self.learning_ai_check.isChecked())
        self.settings.set('learning', 'level', self.get_combo_value(self.learning_level_combo))
        self.settings.set('learning', 'max_hints', self.max_hints_spin.value())
        self.settings.set('learning', 'max_reviews', self.max_reviews_spin.value())

        # Zakładka Wyświetlanie
        self.settings.set('popup', 'position', self.get_combo_value(self.position_combo))
        self.settings.set('popup', 'width', self.width_spin.value())
        self.settings.set('popup', 'height', self.height_spin.value())
        self.settings.set('popup', 'opacity', self.opacity_spin.value())
        self.settings.set('popup', 'auto_hide', self.auto_hide_check.isChecked())
        self.settings.set('popup', 'display_time', self.display_time_spin.value())
        self.settings.set('popup', 'bg_color', self.bg_color_button.property('color'))
        self.settings.set('popup', 'text_color', self.text_color_button.property('color'))
        self.settings.set('popup', 'show_original', self.show_original_check.isChecked())
        
        # Zakładka Zaawansowane
        self.settings.set('paths', 'tesseract', self.tesseract_path_edit.text())
        self.settings.set('paths', 'tessdata', self.tessdata_path_edit.text())
        
        # Konfiguracja autostartu z Windows
        self.configure_autostart()
    
    def set_claude_model(self, model):
        """Ustawia model Claude w polu wyboru (także własny, spoza listy)."""
        for i in range(self.claude_model_combo.count()):
            if self.claude_model_combo.itemData(i) == model:
                self.claude_model_combo.setCurrentIndex(i)
                return
        self.claude_model_combo.setEditText(model)

    def get_claude_model(self):
        """Zwraca identyfikator wybranego (lub wpisanego) modelu Claude."""
        index = self.claude_model_combo.currentIndex()
        text = self.claude_model_combo.currentText().strip()
        if index >= 0 and self.claude_model_combo.itemText(index) == text:
            return self.claude_model_combo.itemData(index)
        return text.split(' ')[0] if text else 'claude-haiku-5-5'

    def on_test_translation_clicked(self):
        """Tłumaczy przykładowe zdanie aktualnymi (niezapisanymi) ustawieniami."""
        from translator import Translator, ENGINE_LABELS

        overrides = {
            'engine': self.get_combo_value(self.translation_engine_combo),
            'deepl_api_key': self.deepl_key_edit.text().strip(),
            'anthropic_api_key': self.anthropic_key_edit.text().strip(),
            'claude_model': self.get_claude_model(),
        }

        class _PreviewSettings:
            def __init__(self, base):
                self.base = base

            def get(self, category, key, default=None):
                if category == 'translation' and key in overrides:
                    return overrides[key]
                return self.base.get(category, key, default)

        self.test_translation_result.setText("Tłumaczenie...")
        self.test_translation_result.repaint()
        Translator.clear_cache()
        translator = Translator(_PreviewSettings(self.settings))
        result = translator.translate("The quick brown fox jumps over the lazy dog.")
        if translator.last_engine:
            label = ENGINE_LABELS.get(translator.last_engine, translator.last_engine)
            lines = [f"✔ {label}: {result}"]
        else:
            lines = ["✘ Żaden silnik nie zadziałał."]
        for engine, error in translator.last_errors.items():
            lines.append(f"• {ENGINE_LABELS.get(engine, engine)}: {error}")
        self.test_translation_result.setText("\n".join(lines))

    def configure_autostart(self):
        """Konfiguruje autostart aplikacji z systemem Windows."""
        # Implementacja autostartu z Windows (używając rejestru Windows)
        # Będzie zaimplementowana w przyszłości
        pass
    
    def select_bg_color(self):
        """Wybór koloru tła pop-up."""
        current_color = QColor(self.settings.get('popup', 'bg_color'))
        color = QColorDialog.getColor(current_color, self, "Wybierz kolor tła")
        
        if color.isValid():
            self.update_color_button(self.bg_color_button, color.name())
    
    def select_text_color(self):
        """Wybór koloru tekstu pop-up."""
        current_color = QColor(self.settings.get('popup', 'text_color'))
        color = QColorDialog.getColor(current_color, self, "Wybierz kolor tekstu")
        
        if color.isValid():
            self.update_color_button(self.text_color_button, color.name())
    
    def select_tesseract_path(self):
        """Wybór ścieżki do Tesseract OCR."""
        path = QFileDialog.getExistingDirectory(self, "Wybierz ścieżkę do Tesseract OCR")
        if path:
            self.tesseract_path_edit.setText(path)
    
    def select_tessdata_path(self):
        """Wybór ścieżki do danych tessdata."""
        path = QFileDialog.getExistingDirectory(self, "Wybierz ścieżkę do danych tessdata")
        if path:
            self.tessdata_path_edit.setText(path)
    
    def update_color_button(self, button, color):
        """Aktualizuje przycisk koloru."""
        button.setProperty('color', color)
        button.setStyleSheet(f"background-color: {color}; min-width: 50px;")
    
    def set_combo_by_value(self, combo, value):
        """Ustawia indeks komboboxa na podstawie wartości."""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
    
    def get_combo_value(self, combo):
        """Pobiera wartość z wybranego elementu komboboxa."""
        return combo.itemData(combo.currentIndex())
    
    def save_and_close(self):
        """Zapisuje ustawienia i zamyka dialog."""
        self.save_settings_from_ui()
        self.accept()
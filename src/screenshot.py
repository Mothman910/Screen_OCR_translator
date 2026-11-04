#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moduł odpowiedzialny za przechwytywanie ekranu i wybór obszaru.
"""

import os
import time
import logging
import tempfile
import platform
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QApplication, QLabel, QRubberBand, QVBoxLayout,
    QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt, QRect, QSize, QPoint, pyqtSignal, QThread, QMutex, QObject
from PyQt6.QtGui import QPixmap, QColor, QPainter, QPen, QGuiApplication, QScreen, QCursor, QPalette, QBrush

# Importy wewnętrzne
from ocr_engine import OCREngine
from translator import Translator
from learning import VocabularyStore, LearningAssistant
from popup import TranslationPopup

logger = logging.getLogger('screenshot')

class ScreenshotWorker(QThread):
    """Wątek do przetwarzania zrzutu ekranu, OCR i tłumaczenia."""
    
    processing_done = pyqtSignal(str, str, object)  # tekst oryginalny, tłumaczenie, szczegóły (silniki, nauka)
    error_occurred = pyqtSignal(str)  # Sygnał: komunikat błędu
    
    def __init__(self, image_path, settings, vocabulary=None):
        super().__init__()
        self.image_path = image_path
        self.settings = settings
        self.vocabulary = vocabulary
        self.mutex = QMutex()
        
    def run(self):
        """Główna metoda wątku."""
        try:
            logger.info(f"Rozpoczęcie przetwarzania zrzutu ekranu: {self.image_path}")
            
            # Inicjalizacja silnika OCR i tłumacza
            ocr_engine = OCREngine(self.settings)
            translator = Translator(self.settings)
            
            # Rozpoznawanie tekstu
            original_text = ocr_engine.process_image(self.image_path)
            
            # Jeśli tekst został rozpoznany, przetłumacz go
            learning = None
            details = {'ocr_engine': ocr_engine.last_engine, 'engine': None, 'errors': {}}
            if original_text:
                translated_text = translator.translate(original_text)
                details['engine'] = translator.last_engine
                details['errors'] = dict(translator.last_errors)
                logger.info("Przetwarzanie zrzutu ekranu zakończone pomyślnie")
                if self.vocabulary is not None:
                    try:
                        assistant = LearningAssistant(self.settings, self.vocabulary, translator)
                        learning = assistant.build(original_text, translated_text)
                    except Exception as e:  # wskazówki nie mogą blokować tłumaczenia
                        logger.error(f"Błąd wskazówek do nauki: {e}")
            else:
                translated_text = "Nie rozpoznano tekstu na obrazie."
                logger.warning("Nie rozpoznano tekstu na obrazie")
            
            details['learning'] = learning
            self.processing_done.emit(original_text or "", translated_text, details)
            
        except Exception as e:
            logger.error(f"Błąd podczas przetwarzania zrzutu ekranu: {e}")
            self.error_occurred.emit(f"Wystąpił błąd: {str(e)}")

class ScreenshotOverlay(QWidget):
    """Nakładka do zaznaczania obszaru zrzutu ekranu."""
    
    screenshot_taken = pyqtSignal(str)  # Sygnał: ścieżka do zrzutu ekranu
    canceled = pyqtSignal()  # Sygnał: anulowano zrzut ekranu
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.screen = None
        self.screenshot = None
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_selecting = False
        self.rubber_band = None
        self.selected_rect = QRect()
        self.toolbar = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Konfiguracja interfejsu użytkownika."""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        # Inicjalizacja paska narzędzi do kontroli zaznaczenia
        self.toolbar = QWidget(self)
        toolbar_layout = QHBoxLayout(self.toolbar)
        
        self.capture_button = QPushButton("Przechwyć")
        self.capture_button.clicked.connect(self.on_capture_button_clicked)
        
        self.cancel_button = QPushButton("Anuluj")
        self.cancel_button.clicked.connect(self.on_cancel_button_clicked)
        
        toolbar_layout.addWidget(self.capture_button)
        toolbar_layout.addWidget(self.cancel_button)
        
        self.toolbar.setLayout(toolbar_layout)
        self.toolbar.hide()
        
        # Inicjalizacja zaznaczania obszaru
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
    
    def start_capture(self):
        """Rozpoczyna przechwytywanie ekranu."""
        logger.info("Rozpoczęcie przechwytywania ekranu")
        
        # Zrzut całego ekranu
        screen = QGuiApplication.primaryScreen()
        self.screen = screen
        self.screenshot = screen.grabWindow(0)
        
        # Ustawienie rozmiarów nakładki
        geometry = screen.geometry()
        self.setGeometry(geometry)
        
        # Ustawienie tła nakładki
        self.show_screenshot_background()
        
        # Pokazanie nakładki
        self.showFullScreen()
    
    def show_screenshot_background(self):
        """Wyświetla zrzut ekranu jako tło z przezroczystością."""
        pixmap = self.screenshot.copy()
        
        # Ściemniamy tło dla lepszej widoczności zaznaczenia
        painter = QPainter(pixmap)
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 100))  # Semi-transparentny czarny
        painter.end()
        
        # Ustawienie zrzutu jako tła nakładki
        palette = self.palette()
        # Używamy QBrush aby stworzyć pędzel z pixmapy
        brush = QBrush(pixmap)
        palette.setBrush(QPalette.ColorGroup.Normal, self.backgroundRole(), brush)
        self.setPalette(palette)
        self.setAutoFillBackground(True)
    
    def mousePressEvent(self, event):
        """Obsługa naciśnięcia przycisku myszy."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = True
            self.start_point = event.pos()
            self.rubber_band.setGeometry(QRect(self.start_point, QSize()))
            self.rubber_band.show()
            self.toolbar.hide()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close_overlay()
    
    def mouseMoveEvent(self, event):
        """Obsługa ruchu myszy."""
        if self.is_selecting:
            self.end_point = event.pos()
            self.rubber_band.setGeometry(QRect(self.start_point, self.end_point).normalized())
    
    def mouseReleaseEvent(self, event):
        """Obsługa zwolnienia przycisku myszy."""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.end_point = event.pos()
            self.selected_rect = QRect(self.start_point, self.end_point).normalized()
            
            # Sprawdzenie, czy zaznaczony obszar ma rozsądny rozmiar
            if self.selected_rect.width() > 10 and self.selected_rect.height() > 10:
                self.show_toolbar()
            else:
                self.rubber_band.hide()
    
    def show_toolbar(self):
        """Wyświetla pasek narzędzi pod zaznaczonym obszarem."""
        # Pozycjonowanie paska narzędzi pod zaznaczonym obszarem
        toolbar_x = self.selected_rect.x()
        toolbar_y = self.selected_rect.y() + self.selected_rect.height() + 5
        
        # Upewnienie się, że pasek narzędzi jest widoczny na ekranie
        screen_rect = self.screen.geometry()
        if toolbar_y + self.toolbar.height() > screen_rect.height():
            toolbar_y = self.selected_rect.y() - self.toolbar.height() - 5
        
        self.toolbar.move(toolbar_x, toolbar_y)
        self.toolbar.show()
    
    def on_capture_button_clicked(self):
        """Obsługa kliknięcia przycisku przechwytywania."""
        self.capture_selected_area()
    
    def on_cancel_button_clicked(self):
        """Obsługa kliknięcia przycisku anulowania."""
        self.close_overlay()
    
    def capture_selected_area(self):
        """Przechwytuje zaznaczony obszar ekranu."""
        if not self.selected_rect.isValid() or self.selected_rect.isEmpty():
            logger.warning("Próba przechwycenia nieprawidłowego obszaru")
            self.close_overlay()
            return
        
        try:
            # Wycinanie zaznaczonego obszaru z pełnego zrzutu ekranu
            cropped_screenshot = self.screenshot.copy(self.selected_rect)
            
            # Tworzenie tymczasowego pliku dla zrzutu ekranu
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(temp_dir, f"screenshot_{timestamp}.png")
            
            # Zapisanie zrzutu ekranu
            cropped_screenshot.save(file_path, "PNG")
            logger.info(f"Zrzut ekranu zapisany w: {file_path}")
            
            # Emitowanie sygnału z ścieżką do zrzutu
            self.screenshot_taken.emit(file_path)
            
            # Zamknięcie nakładki
            self.close_overlay()
            
        except Exception as e:
            logger.error(f"Błąd podczas przechwytywania obszaru: {e}")
            self.close_overlay()
    
    def close_overlay(self):
        """Zamyka nakładkę."""
        self.rubber_band.hide()
        self.toolbar.hide()
        self.hide()
        self.canceled.emit()

class ScreenshotTool(QObject):
    """Narzędzie do zarządzania procesem przechwytywania ekranu, OCR i tłumaczenia."""
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.overlay = None
        self.worker = None
        
        # Słownik nauki (wspólny dla pop-upu i wątku przetwarzania)
        self.vocabulary = VocabularyStore.for_settings(self.settings)
        
        # Inicjalizacja popup do wyświetlania tłumaczeń
        self.popup = TranslationPopup(self.settings, vocabulary=self.vocabulary)
        
        logger.info("Narzędzie zrzutu ekranu zainicjowane")
    
    def start_capture(self):
        """Rozpoczyna proces przechwytywania ekranu."""
        logger.info("Uruchamianie procesu przechwytywania ekranu")
        
        # Zatrzymanie poprzedniego wątku, jeśli istnieje
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        
        # Utworzenie nowej nakładki, jeśli nie istnieje
        if not self.overlay:
            self.overlay = ScreenshotOverlay()
            self.overlay.screenshot_taken.connect(self.process_screenshot)
            self.overlay.canceled.connect(self.on_capture_canceled)
        
        # Rozpoczęcie przechwytywania
        self.overlay.start_capture()
    
    def process_screenshot(self, image_path):
        """Przetwarza zrzut ekranu za pomocą OCR i tłumaczenia."""
        logger.info(f"Rozpoczęcie przetwarzania zrzutu ekranu: {image_path}")
        
        # Utworzenie i uruchomienie wątku do przetwarzania
        self.worker = ScreenshotWorker(image_path, self.settings, self.vocabulary)
        self.worker.processing_done.connect(self.show_translation_popup)
        self.worker.error_occurred.connect(self.on_processing_error)
        self.worker.start()
    
    def show_translation_popup(self, original_text, translated_text, details=None):
        """Wyświetla popup z tłumaczeniem."""
        logger.info("Wyświetlanie popup z tłumaczeniem")
        
        # Wyświetlenie tłumaczenia w popup
        self.popup.show_translation(original_text, translated_text, details)
        
        # W wersji deweloperskiej możemy wyświetlić tekst w konsoli
        if os.environ.get('DEV_MODE') == '1':
            print(f"Oryginalny tekst: {original_text}")
            print(f"Tłumaczenie: {translated_text}")
    
    def on_processing_error(self, error_message):
        """Obsługa błędów przetwarzania."""
        logger.error(f"Błąd przetwarzania: {error_message}")
        # Tutaj można wyświetlić popup z błędem
    
    def on_capture_canceled(self):
        """Obsługa anulowania przechwytywania."""
        logger.info("Przechwytywanie ekranu anulowane")
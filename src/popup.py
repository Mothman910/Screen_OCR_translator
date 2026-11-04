#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moduł odpowiedzialny za wyświetlanie pop-upu z tłumaczeniem.
"""

import html
import logging
from functools import partial
import pyperclip
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, 
    QGraphicsDropShadowEffect, QScrollArea, QSizePolicy, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont, QPalette, QGuiApplication, QScreen

from translator import Translator, ENGINE_LABELS

logger = logging.getLogger('popup')

OCR_LABELS = {'claude': 'Claude', 'tesseract': 'Tesseract'}


def short_engine_name(engine):
    """Krótka nazwa silnika do paska pop-upu, np. 'DeepL'."""
    label = ENGINE_LABELS.get(engine, engine or '?')
    return label.split(' (')[0]


class RetranslateWorker(QThread):
    """Tłumaczy tekst wskazanym silnikiem w tle (przycisk "Inny silnik")."""

    done = pyqtSignal(str, object, object)  # tłumaczenie, silnik (lub None), błędy

    def __init__(self, settings, text, engine):
        super().__init__()
        self.settings = settings
        self.text = text
        self.engine = engine

    def run(self):
        translator = Translator(self.settings)
        try:
            result = translator.translate(self.text, engines=[self.engine])
        except Exception as e:  # noqa: BLE001
            self.done.emit(f"[Błąd tłumaczenia] {self.text}", None, {self.engine: str(e)})
            return
        self.done.emit(result, translator.last_engine, dict(translator.last_errors))


class TranslationPopup(QWidget):
    """Widget wyświetlający tłumaczenie jako nakładka na ekranie."""
    
    closed = pyqtSignal()  # Sygnał emitowany przy zamknięciu pop-upu
    
    def __init__(self, settings, parent=None, vocabulary=None):
        super().__init__(parent)
        self.settings = settings
        self.vocabulary = vocabulary  # VocabularyStore (moduł learning) lub None
        self.dragging = False
        self.drag_position = QPoint()
        self.auto_hide_timer = None
        self.original_text = ""
        self.translated_text = ""
        self.current_engine = None
        self.ocr_engine = None
        self.retranslate_worker = None
        self.resize_mode = False
        
        self.setup_ui()
        
        logger.info("Popup tłumaczenia zainicjowany")
    
    def setup_ui(self):
        """Konfiguracja interfejsu użytkownika."""
        # Ustawienia okna
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Wymiary pop-upu
        width = self.settings.get('popup', 'width')
        height = self.settings.get('popup', 'height')
        self.setMinimumSize(300, 200)
        self.resize(width, height)
        
        # Główny układ
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)
        
        # Panel główny
        self.main_panel = QFrame()
        self.main_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.main_panel.setAutoFillBackground(True)
        self.apply_styles()
        
        # Efekt cienia
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 0)
        self.main_panel.setGraphicsEffect(shadow)
        
        # Układ panelu głównego
        panel_layout = QVBoxLayout(self.main_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(5)
        
        # Obszar przewijania dla oryginalnego tekstu
        self.original_scroll = QScrollArea()
        self.original_scroll.setWidgetResizable(True)
        self.original_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.original_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.original_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Kontener dla oryginalnego tekstu
        self.original_container = QWidget()
        self.original_container_layout = QVBoxLayout(self.original_container)
        self.original_container_layout.setContentsMargins(0, 0, 10, 0)  # Dodajemy prawy margines dla paska przewijania
        
        # Etykieta z oryginalnym tekstem
        self.original_label = QLabel()
        self.original_label.setWordWrap(True)
        self.original_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.original_label.setFont(QFont("Arial", 10, QFont.Weight.Normal))
        self.original_container_layout.addWidget(self.original_label)
        
        self.original_scroll.setWidget(self.original_container)
        panel_layout.addWidget(self.original_scroll)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        panel_layout.addWidget(separator)
        
        # Obszar przewijania dla tłumaczenia
        self.translation_scroll = QScrollArea()
        self.translation_scroll.setWidgetResizable(True)
        self.translation_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.translation_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.translation_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Kontener dla tłumaczenia
        self.translation_container = QWidget()
        self.translation_container_layout = QVBoxLayout(self.translation_container)
        self.translation_container_layout.setContentsMargins(0, 0, 10, 0)  # Dodajemy prawy margines dla paska przewijania
        
        # Etykieta z tłumaczeniem
        self.translation_label = QLabel()
        self.translation_label.setWordWrap(True)
        self.translation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.translation_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.translation_container_layout.addWidget(self.translation_label)
        
        # Panel wskazówek do nauki (pod tłumaczeniem, przewijany razem z nim)
        self.learning_panel = QWidget()
        self.learning_layout = QVBoxLayout(self.learning_panel)
        self.learning_layout.setContentsMargins(0, 8, 0, 0)
        self.learning_layout.setSpacing(3)
        self.learning_panel.hide()
        self.translation_container_layout.addWidget(self.learning_panel)
        self.translation_container_layout.addStretch()
        
        self.translation_scroll.setWidget(self.translation_container)
        panel_layout.addWidget(self.translation_scroll, 1)  # Dajemy większy współczynnik rozciągania
        
        # Panel przycisków w oddzielnym widgecie, aby zawsze był widoczny
        self.button_panel = QWidget()
        button_layout = QHBoxLayout(self.button_panel)
        button_layout.setContentsMargins(0, 5, 0, 0)
        
        # Informacja, który silnik przetłumaczył tekst
        self.engine_label = QLabel("")
        self.engine_label.setFont(QFont("Arial", 8))
        self.engine_label.setWordWrap(True)
        button_layout.addWidget(self.engine_label, 1)
        
        # Przetłumacz ponownie innym silnikiem
        self.other_engine_button = QPushButton("Inny silnik ▾")
        self.other_engine_button.setToolTip("Przetłumacz ten tekst innym silnikiem")
        self.other_engine_button.clicked.connect(self.show_engine_menu)
        self.other_engine_button.setMinimumHeight(30)
        button_layout.addWidget(self.other_engine_button)
        
        # Przycisk kopiowania
        self.copy_button = QPushButton("Kopiuj")
        self.copy_button.setToolTip("Kopiuj tłumaczenie do schowka")
        self.copy_button.clicked.connect(self.copy_translation)
        self.copy_button.setMinimumHeight(30)
        button_layout.addWidget(self.copy_button)
        
        # Przycisk zamknięcia
        self.close_button = QPushButton("Zamknij")
        self.close_button.setToolTip("Zamknij okno tłumaczenia")
        self.close_button.clicked.connect(self.close_popup)
        self.close_button.setMinimumHeight(30)
        button_layout.addWidget(self.close_button)
        
        panel_layout.addWidget(self.button_panel)
        
        main_layout.addWidget(self.main_panel)
        self.setLayout(main_layout)
        
        # Konfiguracja auto-ukrywania
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.timeout.connect(self.close_popup)
    
    def apply_styles(self):
        """Zastosowanie stylów na podstawie ustawień."""
        # Kolor tła
        bg_color = self.settings.get('popup', 'bg_color')
        text_color = self.settings.get('popup', 'text_color')
        opacity = self.settings.get('popup', 'opacity') / 100.0
        
        # Ustawienie koloru tła z przezroczystością
        bg_qcolor = QColor(bg_color)
        bg_qcolor.setAlphaF(opacity)
        
        palette = self.main_panel.palette()
        palette.setColor(QPalette.ColorRole.Window, bg_qcolor)
        palette.setColor(QPalette.ColorRole.WindowText, QColor(text_color))
        self.main_panel.setPalette(palette)
        
        # Style CSS dla etykiet i przycisków
        style_sheet = f"""
            QLabel {{
                color: {text_color};
            }}
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {text_color};
                border-radius: 3px;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: {text_color};
                color: {bg_color};
            }}
            QScrollBar:vertical {{
                border: none;
                background: rgba(0, 0, 0, 0.1);
                width: 8px;
                margin: 0px 0px 0px 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba({text_color}, 0.5);
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: rgba(0, 0, 0, 0.1);
                height: 8px;
                margin: 0px 0px 0px 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: rgba({text_color}, 0.5);
                min-width: 20px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """
        self.setStyleSheet(style_sheet)
    
    def show_translation(self, original_text, translated_text, details=None):
        """Wyświetla tłumaczenie w pop-upie (oraz silnik i wskazówki do nauki, jeśli są)."""
        details = details or {}
        learning = details.get('learning')
        self.original_text = original_text
        self.translated_text = translated_text
        self.current_engine = details.get('engine')
        self.ocr_engine = details.get('ocr_engine')
        self.update_engine_label(details.get('errors'))
        self.other_engine_button.setEnabled(bool(original_text.strip()))
        
        # Sprawdzenie, czy pokazywać oryginalny tekst
        show_original = self.settings.get('popup', 'show_original')
        if show_original and original_text.strip():
            self.original_label.setText(f"<i>{original_text}</i>")
            self.original_scroll.setMaximumHeight(int(self.height() * 0.3))
            self.original_scroll.show()
        else:
            self.original_scroll.hide()
            separator = self.main_panel.findChild(QFrame)
            if separator:
                separator.hide()
        
        # Ustawienie tekstu tłumaczenia
        self.translation_label.setText(translated_text)
        self.render_learning(learning)
        
        # Dostosowanie rozmiaru głównego kontenera
        self.translation_container.adjustSize()
        self.original_container.adjustSize()
        
        # Pozycjonowanie pop-upu
        self.position_popup()
        
        # Wyświetlenie pop-upu
        self.show()
        self.activateWindow()
        
        # Konfiguracja automatycznego ukrywania
        if self.settings.get('popup', 'auto_hide'):
            display_time = self.settings.get('popup', 'display_time') * 1000  # ms
            self.auto_hide_timer.start(display_time)
        
        logger.info("Wyświetlono popup z tłumaczeniem")
    
    # --------------------------------------------------------- silniki

    def update_engine_label(self, errors=None):
        """Pokazuje, który silnik przetłumaczył tekst (i dlaczego inne zawiodły)."""
        parts = []
        if self.current_engine:
            parts.append(f"Tłumaczenie: {short_engine_name(self.current_engine)}")
        elif self.original_text.strip():
            parts.append("Tłumaczenie nie powiodło się")
        if self.ocr_engine:
            parts.append(f"OCR: {OCR_LABELS.get(self.ocr_engine, self.ocr_engine)}")
        self.engine_label.setText(" · ".join(parts))
        tooltip = "\n".join(f"{short_engine_name(e)}: {msg}" for e, msg in (errors or {}).items())
        self.engine_label.setToolTip(tooltip or "")

    def show_engine_menu(self):
        """Menu z innymi silnikami tłumaczenia."""
        self._pause_auto_hide()
        menu = QMenu(self)
        available = set(Translator(self.settings).available_engines())
        for engine, label in ENGINE_LABELS.items():
            if engine == self.current_engine:
                continue
            action = menu.addAction(label if engine in available else f"{label} - brak klucza API")
            action.setEnabled(engine in available)
            action.triggered.connect(partial(self.retranslate_with, engine))
        menu.exec(self.other_engine_button.mapToGlobal(QPoint(0, self.other_engine_button.height())))

    def retranslate_with(self, engine, *_):
        """Tłumaczy aktualny tekst wybranym silnikiem (w tle)."""
        if not self.original_text.strip():
            return
        if self.retranslate_worker is not None and self.retranslate_worker.isRunning():
            return
        self._pause_auto_hide()
        self.other_engine_button.setEnabled(False)
        self.engine_label.setText(f"Tłumaczę: {short_engine_name(engine)}...")
        self.retranslate_worker = RetranslateWorker(self.settings, self.original_text, engine)
        self.retranslate_worker.done.connect(self.on_retranslated)
        self.retranslate_worker.start()

    def on_retranslated(self, translated_text, engine, errors):
        self.other_engine_button.setEnabled(True)
        if engine:
            self.translated_text = translated_text
            self.current_engine = engine
            self.translation_label.setText(translated_text)
            self.translation_container.adjustSize()
            self.update_engine_label()
            logger.info(f"Przetłumaczono ponownie silnikiem {engine}")
        else:
            self.update_engine_label()
            message = "; ".join(f"{short_engine_name(e)}: {m}" for e, m in (errors or {}).items())
            self.engine_label.setText(f"Nie udało się: {message}")

    # ------------------------------------------------------------ nauka

    def _clear_learning(self):
        while self.learning_layout.count():
            item = self.learning_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _small_button(self, text, tooltip):
        button = QPushButton(text)
        button.setToolTip(tooltip)
        button.setFixedHeight(24)
        button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        return button

    def _row(self, label, *buttons):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(label, 1)
        for button in buttons:
            layout.addWidget(button)
        self.learning_layout.addWidget(row)
        return row

    def _label(self, text):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setFont(QFont("Arial", 9))
        return label

    def render_learning(self, learning):
        """Pokazuje słowa do nauki, powtórki i często spotykane słowa."""
        self._clear_learning()
        if not learning or self.vocabulary is None:
            self.learning_panel.hide()
            return
        hints = learning.get('hints') or []
        reviews = learning.get('reviews') or []
        frequent = learning.get('frequent') or []
        if not (hints or reviews or frequent):
            self.learning_panel.hide()
            return

        if hints:
            self.learning_layout.addWidget(self._label("<b>💡 Do nauki</b>"))
            for hint in hints:
                text = f"<b>{html.escape(hint['term'])}</b>"
                if hint.get('translation'):
                    text += f" – {html.escape(hint['translation'])}"
                if hint.get('tip'):
                    text += f"<br><i>{html.escape(hint['tip'])}</i>"
                button = self._small_button("✓ Znam", "Oznacz jako nauczone - nie będzie już proponowane")
                row = self._row(self._label(text), button)
                button.clicked.connect(partial(self._on_mark_learned, hint['term'], hint.get('translation', ''), row))

        if reviews:
            self.learning_layout.addWidget(self._label("<b>🔁 Powtórka</b> – pamiętasz znaczenie?"))
            for entry in reviews:
                label = self._label(f"<b>{html.escape(entry['term'])}</b> = ?")
                yes = self._small_button("Pamiętam", "Następna powtórka za dłuższy czas")
                no = self._small_button("Nie pamiętam", "Słowo wróci do powtórki jutro")
                self._row(label, yes, no)
                yes.clicked.connect(partial(self._on_review, entry, True, label, yes, no))
                no.clicked.connect(partial(self._on_review, entry, False, label, yes, no))

        if frequent:
            words = ', '.join(
                f"<b>{html.escape(e['term'])}</b> ({e.get('seen', 0)}×)" for e in frequent)
            self.learning_layout.addWidget(self._label(f"📈 Często spotykasz: {words}"))

        self.learning_panel.show()

    def _pause_auto_hide(self):
        if self.auto_hide_timer and self.auto_hide_timer.isActive():
            self.auto_hide_timer.stop()

    def _on_mark_learned(self, term, translation, row, *_):
        self._pause_auto_hide()
        try:
            self.vocabulary.mark_learned(term, translation)
            logger.info(f"Oznaczono jako nauczone: {term}")
        except Exception as e:
            logger.error(f"Nie udało się oznaczyć słowa {term}: {e}")
            return
        row.hide()

    def _on_review(self, entry, remembered, label, yes, no, *_):
        self._pause_auto_hide()
        try:
            self.vocabulary.review(entry['term'], remembered)
        except Exception as e:
            logger.error(f"Błąd zapisu powtórki {entry['term']}: {e}")
        mark = "✓" if remembered else "✗"
        label.setText(f"{mark} <b>{html.escape(entry['term'])}</b> – "
                      f"{html.escape(entry.get('translation') or '(brak tłumaczenia)')}")
        yes.hide()
        no.hide()

    def enterEvent(self, event):
        """Najechanie myszą wstrzymuje automatyczne ukrywanie."""
        self._pause_auto_hide()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Po opuszczeniu pop-upu wznawiamy automatyczne ukrywanie."""
        if self.isVisible() and self.settings.get('popup', 'auto_hide') and not self.dragging:
            self.auto_hide_timer.start(self.settings.get('popup', 'display_time') * 1000)
        super().leaveEvent(event)

    def position_popup(self):
        """Pozycjonuje pop-up zgodnie z ustawieniami."""
        position = self.settings.get('popup', 'position')
        screen = QGuiApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        x, y = 0, 0
        
        if position == 'top-right':
            x = screen_geometry.width() - self.width() - 20
            y = 20
        elif position == 'top-left':
            x = 20
            y = 20
        elif position == 'bottom-right':
            x = screen_geometry.width() - self.width() - 20
            y = screen_geometry.height() - self.height() - 20
        elif position == 'bottom-left':
            x = 20
            y = screen_geometry.height() - self.height() - 20
        elif position == 'center':
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
        
        self.move(x, y)
    
    def copy_translation(self):
        """Kopiuje tłumaczenie do schowka."""
        pyperclip.copy(self.translated_text)
        
        # Zmiana tekstu przycisku kopiowania na potwierdzenie
        self.copy_button.setText("Skopiowano!")
        QTimer.singleShot(1500, lambda: self.copy_button.setText("Kopiuj"))
        
        logger.info("Tłumaczenie skopiowane do schowka")
    
    def close_popup(self):
        """Zamyka pop-up."""
        if self.auto_hide_timer and self.auto_hide_timer.isActive():
            self.auto_hide_timer.stop()
        
        self.hide()
        self.closed.emit()
        
        logger.info("Zamknięto popup z tłumaczeniem")
    
    def resizeEvent(self, event):
        """Obsługuje zmianę rozmiaru okna."""
        super().resizeEvent(event)
        
        # Zapisanie nowych wymiarów w ustawieniach
        self.settings.set('popup', 'width', self.width())
        self.settings.set('popup', 'height', self.height())
        
        # Dostosowanie obszarów przewijania
        if self.settings.get('popup', 'show_original'):
            self.original_scroll.setMaximumHeight(int(self.height() * 0.3))
    
    def mousePressEvent(self, event):
        """Obsługa naciśnięcia przycisku myszy."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Sprawdzenie, czy kliknięcie nastąpiło w przycisk
            if self.close_button.geometry().contains(event.position().toPoint() - self.button_panel.pos()) or \
               self.copy_button.geometry().contains(event.position().toPoint() - self.button_panel.pos()):
                # Przekazanie zdarzenia do przetworzenia przez normalny mechanizm
                return
            
            self.dragging = True
            self.drag_position = event.pos()
            
            # Zatrzymanie timera auto-ukrywania podczas przeciągania
            if self.auto_hide_timer and self.auto_hide_timer.isActive():
                self.auto_hide_timer.stop()
    
    def mouseMoveEvent(self, event):
        """Obsługa ruchu myszy."""
        if self.dragging and event.buttons() & Qt.MouseButton.LeftButton:
            # Tylko przeciąganie, bez zmiany rozmiaru
            self.move(self.pos() + event.pos() - self.drag_position)
    
    def mouseReleaseEvent(self, event):
        """Obsługa zwolnienia przycisku myszy."""
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self.dragging
            self.dragging = False
            
            # Ponowne uruchomienie timera auto-ukrywania po przeciągnięciu
            if was_dragging and self.settings.get('popup', 'auto_hide'):
                display_time = self.settings.get('popup', 'display_time') * 1000  # ms
                self.auto_hide_timer.start(display_time)
    
    def mouseDoubleClickEvent(self, event):
        """Obsługa podwójnego kliknięcia myszy."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Implementacja możliwości maksymalizacji/przywracania poprzedniego rozmiaru
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
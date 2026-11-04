#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moduł obsługujący ikonę w zasobniku systemowym i jej menu kontekstowe.
"""

import os
import logging
from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QDialog, 
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QKeySequence, QAction

# Importy wewnętrzne
from screenshot import ScreenshotTool
from settings import SettingsDialog
from vocabulary_dialog import VocabularyDialog

logger = logging.getLogger('tray_icon')

class AboutDialog(QDialog):
    """Dialog z informacjami o aplikacji."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("O aplikacji")
        self.setFixedSize(400, 200)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Informacje o aplikacji
        title_label = QLabel("<h2>ScreenOCR & Translator</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        info_label = QLabel(
            "<p style='text-align: center;'>Wersja 1.0.0</p>"
            "<p style='text-align: center;'>Aplikacja do rozpoznawania i tłumaczenia tekstu z ekranu w grach.</p>"
            "<p style='text-align: center;'>Autor: Adam Fijałkowski © 2025</p>"
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)
        
        # Przycisk zamknięcia
        button_layout = QHBoxLayout()
        close_button = QPushButton("Zamknij")
        close_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

class SystemTrayIcon(QSystemTrayIcon):
    """Ikona w zasobniku systemowym z menu kontekstowym."""
    
    screenshot_requested = pyqtSignal()  # Sygnał do rozpoczęcia procesu zrzutu ekranu
    
    def __init__(self, icon, app, settings, parent=None):
        super().__init__(icon, parent)
        self.app = app
        self.settings = settings
        self.setup_menu()
        self.activated.connect(self.on_tray_icon_activated)
        
        # Inicjalizacja narzędzia do przechwytywania ekranu
        self.screenshot_tool = ScreenshotTool(self.settings)
        self.screenshot_requested.connect(self.screenshot_tool.start_capture)
        
        logger.info("Ikona zasobnika systemowego zainicjowana")
    
    def setup_menu(self):
        """Konfiguracja menu kontekstowego ikony w zasobniku."""
        menu = QMenu()
        
        # Akcja przechwytywania ekranu
        capture_action = QAction("Przechwyć ekran", self)
        shortcut = self.settings.get_hotkey('capture', 'Ctrl+Shift+X')
        capture_action.setShortcut(QKeySequence(shortcut))
        capture_action.triggered.connect(self.on_capture_action)
        menu.addAction(capture_action)
        
        # Słownik nauki
        vocabulary_action = QAction("Mój słownik", self)
        vocabulary_action.triggered.connect(self.show_vocabulary)
        menu.addAction(vocabulary_action)
        
        menu.addSeparator()
        
        # Akcja ustawień
        settings_action = QAction("Ustawienia", self)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        
        # Akcja informacji o aplikacji
        about_action = QAction("O aplikacji", self)
        about_action.triggered.connect(self.show_about)
        menu.addAction(about_action)
        
        menu.addSeparator()
        
        # Akcja zamykania aplikacji
        exit_action = QAction("Zamknij", self)
        exit_action.triggered.connect(self.app.quit)
        menu.addAction(exit_action)
        
        self.setContextMenu(menu)
    
    def on_tray_icon_activated(self, reason):
        """Obsługa kliknięcia w ikonę zasobnika."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Pojedyncze kliknięcie - wyświetlenie dymka
            self.showMessage(
                "ScreenOCR & Translator", 
                "Użyj skrótu klawiszowego lub wybierz 'Przechwyć ekran' aby rozpocząć.", 
                QIcon(), 
                3000
            )
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Podwójne kliknięcie - wyświetlenie ustawień
            self.show_settings()
            
    def on_capture_action(self):
        """Obsługa akcji przechwytywania ekranu."""
        logger.info("Wywołano akcję przechwytywania ekranu")
        self.screenshot_requested.emit()
        
    def show_settings(self):
        """Wyświetla okno ustawień."""
        logger.info("Wyświetlanie okna ustawień")
        # Następujący kod będzie odkomentowany po implementacji okna ustawień
        settings_dialog = SettingsDialog(self.settings)
        settings_dialog.exec()
        
    def show_vocabulary(self):
        """Wyświetla słownik nauki (słowa nauczone i do nauki)."""
        logger.info("Wyświetlanie słownika")
        dialog = VocabularyDialog(self.screenshot_tool.vocabulary)
        dialog.exec()
        
    def show_about(self):
        """Wyświetla okno informacyjne o aplikacji."""
        logger.info("Wyświetlanie okna informacyjnego")
        about_dialog = AboutDialog()
        about_dialog.exec()
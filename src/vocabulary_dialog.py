#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Okno "Mój słownik": przegląd słów, oznaczanie jako nauczone i powtórki.
"""

import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QComboBox, QLineEdit, QAbstractItemView, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt

from learning import STATUS_LEARNED

logger = logging.getLogger('vocabulary')

COLUMNS = ["Słowo", "Tłumaczenie", "Wskazówka", "Status", "Spotkane", "Następna powtórka"]


class VocabularyDialog(QDialog):
    """Lista zapamiętanych słów z możliwością zmiany statusu."""

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Mój słownik")
        self.setMinimumSize(760, 460)
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.stats_label = QLabel()
        layout.addWidget(self.stats_label)

        filters = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Wszystkie", 'all')
        self.filter_combo.addItem("Do nauki", 'new')
        self.filter_combo.addItem("Nauczone", 'learned')
        self.filter_combo.addItem("Do powtórki teraz", 'due')
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Szukaj...")
        self.search_edit.textChanged.connect(self.refresh)
        filters.addWidget(QLabel("Pokaż:"))
        filters.addWidget(self.filter_combo)
        filters.addWidget(self.search_edit, 1)
        layout.addLayout(filters)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        for text, handler in [
            ("✓ Nauczone", self.on_mark_learned),
            ("↺ Do nauki", self.on_mark_unlearned),
            ("Pamiętam", lambda: self.on_review(True)),
            ("Nie pamiętam", lambda: self.on_review(False)),
            ("Usuń", self.on_remove),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        buttons.addStretch()
        close_button = QPushButton("Zamknij")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _filtered_entries(self):
        mode = self.filter_combo.currentData()
        query = self.search_edit.text().strip().lower()
        if mode == 'due':
            entries = self.store.due_reviews()
        else:
            entries = self.store.all_entries()
            if mode == 'learned':
                entries = [e for e in entries if e.get('status') == STATUS_LEARNED]
            elif mode == 'new':
                entries = [e for e in entries if e.get('status') != STATUS_LEARNED]
            entries.sort(key=lambda e: (e.get('status') == STATUS_LEARNED, -e.get('seen', 0), e['term'].lower()))
        if query:
            entries = [e for e in entries
                       if query in e['term'].lower() or query in (e.get('translation') or '').lower()]
        return entries

    def refresh(self, *_):
        stats = self.store.stats()
        self.stats_label.setText(
            f"Słów: {stats['total']} · nauczone: {stats['learned']} · do nauki: {stats['to_learn']} · "
            f"do powtórki teraz: {stats['due']}"
        )
        entries = self._filtered_entries()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            learned = entry.get('status') == STATUS_LEARNED
            next_review = ''
            if learned and entry.get('next_review'):
                try:
                    next_review = datetime.fromisoformat(entry['next_review']).strftime('%Y-%m-%d')
                except ValueError:
                    next_review = entry['next_review']
            values = [
                entry['term'], entry.get('translation', ''), entry.get('tip', ''),
                "nauczone" if learned else "do nauki", str(entry.get('seen', 0)), next_review,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, entry['term'])
                self.table.setItem(row, col, item)

    def _selected_terms(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        terms = []
        for row in rows:
            item = self.table.item(row, 0)
            if item is not None:
                terms.append(item.data(Qt.ItemDataRole.UserRole))
        return terms

    def on_mark_learned(self):
        for term in self._selected_terms():
            self.store.mark_learned(term)
        self.refresh()

    def on_mark_unlearned(self):
        for term in self._selected_terms():
            self.store.mark_unlearned(term)
        self.refresh()

    def on_review(self, remembered):
        for term in self._selected_terms():
            if self.store.is_learned(term):
                self.store.review(term, remembered)
        self.refresh()

    def on_remove(self):
        terms = self._selected_terms()
        if not terms:
            return
        answer = QMessageBox.question(self, "Usuń", f"Usunąć {len(terms)} słów ze słownika?")
        if answer == QMessageBox.StandardButton.Yes:
            for term in terms:
                self.store.remove(term)
            self.refresh()

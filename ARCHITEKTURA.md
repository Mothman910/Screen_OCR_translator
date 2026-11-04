# Architektura projektu ScreenOCR & Translator

## Stos technologiczny

### Język programowania i framework

- **Python 3.11+** - język główny
- **PyQt6** - framework do tworzenia interfejsu użytkownika i nakładki systemowej
- **Inno Setup** - narzędzie do tworzenia instalatora dla Windows

### Biblioteki główne

- **Tesseract OCR** - silnik OCR do rozpoznawania tekstu z obrazu
- **pytesseract** - wrapper Pythona dla Tesseract OCR
- **DeepL API** (domyślnie) / **Claude** / **Google Translate** / **MyMemory** - łańcuch silników tłumaczenia z automatycznym przełączaniem przy awarii
- **OpenCV-Python** - do przetwarzania obrazu przed OCR
- **pynput** - do obsługi globalnych skrótów klawiszowych
- **infi.systray** - do tworzenia ikony w zasobniku systemowym
- **pyinstaller** - do pakowania aplikacji do pliku .exe

## Funkcjonalności

1. **Przechwytywanie ekranu**

   - Nakładka do zaznaczania fragmentu ekranu aktywowana skrótem klawiszowym
   - Funkcjonalność półprzezroczystości umożliwiająca widoczność gry pod spodem
   - Możliwość dostosowania obszaru zaznaczenia

2. **OCR i przetwarzanie tekstu**

   - Rozpoznawanie tekstu z zaznaczonego obszaru
   - Optymalizacja obrazu przed OCR dla zwiększenia dokładności
   - Przetwarzanie tekstu (usuwanie niepotrzebnych znaków, formatowanie)

3. **Tłumaczenie**

   - Tłumaczenie rozpoznanego tekstu z angielskiego na polski
   - Optymalizacja wykorzystania API dla minimalizacji opóźnień

4. **Interfejs użytkownika**

   - Nowoczesny, elegancki pop-up z wynikiem tłumaczenia
   - Możliwość przeciągania i zmiany pozycji pop-upu
   - Różne opcje wyświetlania (przezroczystość, rozmiar, kolor)
   - Ikona w zasobniku systemowym z menu kontekstowym

5. **Konfiguracja**
   - Możliwość zmiany skrótu klawiszowego
   - Ustawienia stylów wyświetlania tłumaczenia
   - Konfiguracja dokładności OCR i silnika tłumaczenia
   - Zapisywanie i ładowanie konfiguracji użytkownika

## Architektura systemu

```
+-----------------------+
|    Zasobnik systemowy |
|     (Ikona tray)      |
+-----------+-----------+
            |
            v
+---------------------------+
|     Panel konfiguracji    |
+---------------------------+
            |
            v
+---------------------------+
|  Moduł obsługi skrótów    |
|      klawiszowych         |
+-----------+---------------+
            |
            v
+-----------+---------------+
|   Nakładka do zaznaczania |
|      fragmentu ekranu     |
+-----------+---------------+
            |
            v
+-----------+---------------+
| Moduł przetwarzania obrazu|
|     i ekstrakcji tekstu   |
+-----------+---------------+
            |
            v
+-----------+---------------+
|    Moduł tłumaczenia      |
+-----------+---------------+
            |
            v
+-----------+---------------+
|  Wyświetlanie tłumaczenia |
|       (Pop-up)            |
+-----------+---------------+
```

## Wymagania systemowe i uprawnienia

- Windows 11 (64-bit)
- Uprawnienia do przechwytywania ekranu
- Uprawnienia do działania w tle i globalnych skrótów klawiszowych
- Dostęp do internetu (dla API tłumaczenia)

## Proces instalacji

1. Instalator stworzony przy użyciu Inno Setup
2. Instalacja Tesseract OCR i wymaganych bibliotek
3. Konfiguracja uprawnień systemowych
4. Utworzenie skrótów w menu Start i pulpicie
5. Opcjonalny autostart z systemem

## Struktura projektu

```
ScreenOCR-Translator/
│
├── src/                      # Kod źródłowy
│   ├── main.py               # Punkt wejściowy aplikacji
│   ├── tray_icon.py          # Obsługa ikony w zasobniku
│   ├── screenshot.py         # Przechwytywanie ekranu
│   ├── ocr_engine.py         # Silnik OCR
│   ├── translator.py         # Moduł tłumaczenia
│   ├── popup.py              # Wyświetlanie pop-up
│   ├── settings.py           # Zarządzanie ustawieniami
│   └── utils/                # Narzędzia pomocnicze
│       ├── image_processing.py
│       └── hotkeys.py
│
├── resources/                # Zasoby aplikacji
│   ├── icons/                # Ikony
│   ├── styles/               # Style CSS dla UI
│   └── languages/            # Dane językowe
│
├── tests/                    # Testy
│
├── docs/                     # Dokumentacja
│
├── build_tools/              # Narzędzia do budowania
│   ├── installer.iss         # Skrypt Inno Setup
│   └── pyinstaller.spec      # Specyfikacja PyInstaller
│
└── requirements.txt          # Zależności Pythona
```

## Kolejne kroki implementacji

1. Konfiguracja środowiska projektowego
2. Implementacja podstawowego interfejsu użytkownika i ikony w zasobniku
3. Implementacja narzędzia do zaznaczania ekranu
4. Integracja OCR i przetwarzania obrazu
5. Implementacja modułu tłumaczenia
6. Utworzenie konfigurowalnego pop-up do wyświetlania tłumaczeń
7. Optymalizacja działania w tle
8. Konfiguracja uprawnień i integracja z systemem
9. Stworzenie paczki instalacyjnej

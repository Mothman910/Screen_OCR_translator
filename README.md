# Screen OCR Translator

Desktopowa aplikacja napisana w Pythonie dla systemu Windows. Pozwala na błyskawiczne zaznaczanie obszaru na ekranie w celu rozpoznania tekstu (OCR) i przetłumaczenia go w czasie rzeczywistym. Idealne narzędzie do gier, aplikacji bez natywnego wsparcia językowego oraz zablokowanych treści tekstowych (niemożliwych do skopiowania).

## 🚀 Główne funkcje
- **Globalne skróty klawiszowe** - Szybkie wywoływanie interfejsu zaznaczania obszaru (overlay) działające nad dowolną aplikacją.
- **Zaawansowany OCR** - Wykorzystanie precyzyjnego silnika Tesseract (wspieranego przez OpenCV do preprocessingu obrazu binarnego i odszumiania) zapewnia wysoką skuteczność odczytu.
- **Niezawodne Tłumaczenie** - Domyślnie DeepL API (najlepsza jakość EN→PL, darmowy plan 500 000 znaków/mies.), opcjonalnie Claude (AI rozumiejące kontekst i poprawiające błędy OCR). Gdy silnik zawiedzie, program sam przełącza się na kolejny: DeepL → Claude → Google → MyMemory.
- **Zgrabne UI** - Wyniki prezentowane są jako estetyczny, konfigurowalny pop-up okienkowy (PyQt6), który można swobodnie przesuwać.
- **Działanie w tle** - Aplikacja funkcjonuje prosto z zasobnika systemowego (System Tray) minimalizując użycie zasobów.

## 🛠️ Stos technologiczny
- **Język główny:** Python 3.11+
- **Interfejs Użytkownika:** PyQt6, infi.systray
- **Przetwarzanie Obrazu i OCR:** Tesseract OCR, Pytesseract, OpenCV-Python, Pillow
- **Silniki Tłumaczeń:** DeepL API, Claude (Anthropic SDK), Google Translate (fallback), MyMemory (fallback)
- **Narzędzia globalne:** pynput, keyboard, pyperclip
- **Pakowanie i release:** PyInstaller, Inno Setup (instalator .exe)

## ⚙️ Wymagania systemowe
- Operacyjny system Windows 11 / Windows 10 (64-bit)
- Silnik Tesseract OCR wgranym lokalnie
- Posiadanie odpowiednich uprawnień do "screenshot record"

## 💡 Jak uruchomić (dla deweloperów)
```bash
# Klonowanie repozytorium
git clone https://github.com/Mothman910/Screen_OCR_translator.git
cd Screen_OCR_translator

# Instalacja niezbędnych pakietów
pip install -r requirements.txt

# Uruchomienie aplikacji w środowisku
python src/main.py
```

## 🔑 Konfiguracja tłumaczenia
1. Załóż darmowe konto **DeepL API Free** na https://www.deepl.com/pro-api i skopiuj klucz (kończy się na `:fx`).
2. Wklej go w *Ustawienia → Tłumaczenie → Klucz API DeepL* i kliknij **Testuj tłumaczenie**.
3. (Opcjonalnie) Dodaj klucz Claude z https://platform.claude.com, aby mieć tłumaczenie AI jako drugi silnik lub wybrać je jako główne.

Klucze można też podać w pliku `.env` w katalogu programu (`DEEPL_API_KEY=...`, `ANTHROPIC_API_KEY=...`). Bez żadnego klucza program nadal działa przez Google i MyMemory.

## 🗂️ Architektura
Projekt pakowany jest z wykorzystaniem pyinstallera a następnie kompilowany gotowym Inno Setupem do pojedynczego okienka instalacyjnego. Szczegółowe diagramy powiązań i przebieg działania systemu dostępny jest do wglądu w pliku głównym `ARCHITEKTURA.md`.


# Screen OCR Translator

Desktopowa aplikacja napisana w Pythonie dla systemu Windows. Pozwala na błyskawiczne zaznaczanie obszaru na ekranie w celu rozpoznania tekstu (OCR) i przetłumaczenia go w czasie rzeczywistym. Idealne narzędzie do gier, aplikacji bez natywnego wsparcia językowego oraz zablokowanych treści tekstowych (niemożliwych do skopiowania).

## 🚀 Główne funkcje
- **Globalne skróty klawiszowe** - Szybkie wywoływanie interfejsu zaznaczania obszaru (overlay) działające nad dowolną aplikacją.
- **Zaawansowany OCR** - Wykorzystanie precyzyjnego silnika Tesseract (wspieranego przez OpenCV do preprocessingu obrazu binarnego i odszumiania) zapewnia wysoką skuteczność odczytu.
- **Niezawodne Tłumaczenie** - Domyślnie DeepL API (najlepsza jakość EN→PL, darmowy plan 500 000 znaków/mies.), opcjonalnie Claude (AI rozumiejące kontekst i poprawiające błędy OCR). Gdy silnik zawiedzie, program sam przełącza się na kolejny: DeepL → Claude → Google → MyMemory.
- **OCR przez AI** - Claude Haiku czyta tekst prosto z obrazu (także stylizowane czcionki z gier) za ułamek grosza; bez klucza działa lokalny Tesseract.
- **Nauka słówek** - Pop-up podpowiada kilka słów wartych nauki (z tłumaczeniem i krótką wskazówką), pomija to, co oznaczysz jako „✓ Znam”, i przypomina o powtórkach (1, 3, 7, 16, 35, 90 dni). Pełna lista w „Mój słownik” w menu ikony.
- **Wybór silnika w locie** - Pop-up pokazuje, który silnik przetłumaczył tekst, a przycisk „Inny silnik” tłumaczy go ponownie wybranym silnikiem.
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
3. (Opcjonalnie) Dodaj klucz Claude z https://platform.claude.com. Włącza OCR przez AI, wskazówki AI do nauki i Claude jako zapasowy silnik tłumaczenia. Domyślny model to najtańszy **Claude Haiku 5.5** (0,10 USD / 0,50 USD za milion tokenów): zrzut ekranu z OCR, tłumaczeniem i wskazówkami to ok. 0,1-0,3 grosza. Wystarczy doładować konto kwotą 5 USD.

### Ile to kosztuje
| Funkcja | Bez klucza Claude | Z kluczem Claude (Haiku 5.5) |
|---|---|---|
| OCR | Tesseract (darmowy) | Claude, ok. 0,1 gr za zrzut |
| Tłumaczenie | DeepL Free (500 000 znaków/mies.), Google, MyMemory | jak obok + Claude jako zapas |
| Wskazówki do nauki | darmowy tryb (rzadsze słowa + tłumaczenie) | AI: idiomy, phrasal verbs, wskazówki po polsku, ok. 0,1 gr |

Klucze można też podać w pliku `.env` w katalogu programu (`DEEPL_API_KEY=...`, `ANTHROPIC_API_KEY=...`). Bez żadnego klucza program nadal działa przez Google i MyMemory.

## 🗂️ Architektura
Projekt pakowany jest z wykorzystaniem pyinstallera a następnie kompilowany gotowym Inno Setupem do pojedynczego okienka instalacyjnego. Szczegółowe diagramy powiązań i przebieg działania systemu dostępny jest do wglądu w pliku głównym `ARCHITEKTURA.md`.


# Instrukcje projektu xmplayNVDA

- Zakres: `D:\Xmplay\xmplayNVDA`. Najpierw ustal właściwy moduł lub aplikację w tym katalogu; nie przenoś oryginalnych danych wejściowych, zapisów ani istniejących paczek na podstawie samej nazwy.
- Dokumentacja wewnętrzna: `D:\work\Forme\xmplayNVDA`; diagnostyka: `D:\work\Workspace\xmplayNVDA`; potwierdzone odpady: `D:\work\Trash\xmplayNVDA`. Aktualne wydania pozostają lokalnie w Installfiles/installfiles, z zachowaniem zastanej wielkości liter.


## Nawigacja i kontrole

- Stosuj [globalny indeks i właściwe moduły](<C:/Users/Pates/.codex/AGENTS.md>).
- Przed zmianą odczytaj istniejący audyt w [centralnym Forme](<D:/work/Forme/xmplayNVDA>). Bieżący zakres i pauzy mają pierwszeństwo przed dawnymi planami.
- Przed pracą: [README.md](<D:/Xmplay/xmplayNVDA/README.md>).
- Przed budowaniem lub zmianą ścieżek odczytaj właściwy skrypt: [build.ps1](<D:/Xmplay/xmplayNVDA/build.ps1>). Nie uruchamiaj buildu tylko z powodu porządkowania instrukcji.
- Przed zmianą kodu dobierz przypadki z [testów projektu](<D:/Xmplay/xmplayNVDA/tests>); polecenia i wymagania środowiska ustal z dokumentacji.
- Odnośniki nie wczytują treści automatycznie. Nie rozbijaj krótkiej, spójnej mapy projektu na dodatkowe pliki.

## Mapa i ograniczenia dodatku

- `addon/appModules/xmplay`: komunikacja z XMPlay, rozpoznawanie okien, komunikaty i dostępne dialogi. `addon/globalPlugins/xmplayAccessibility`: ustawienia NVDA, rejestrowanie poleceń i wybór języka.
- `translations_pl.json` jest źródłem polskich tłumaczeń; `tools/build_locale.py` generuje katalog. Zachowaj angielski i polski interfejs oraz dokumentację `addon/doc/en` i `addon/doc/pl`.
- Konfiguracja i gesty są zarządzane przez hosta NVDA zgodnie z wymaganiem panelu w ustawieniach NVDA. Nie przenoś profilu NVDA ani danych zewnętrznego XMPlay do repozytorium.
- Przechwytywanie natywnych skrótów dotyczy tylko głównego odtwarzacza i paneli ze skórką. Ustawienia, menu, edycja tekstu i okna plików zachowują zwykłą obsługę klawiatury. Nigdy nie odtwarzaj automatycznie skrótu po częściowym wykonaniu poleceń.
- Weryfikacja: `python -B -m unittest discover -s tests -p "test_*.py"`; build przez `build.ps1`; gotową paczkę sprawdza `tools/validate_addon.py`. Testy `live_*` mają jawne wymagania środowiska i nie oznaczają pełnej próby odsłuchowej w NVDA.
- Publikuj do zatwierdzonego publicznego repozytorium GitHub. Nie wysyłaj dodatku do sklepu NVDA. Nie podmieniaj po cichu zainstalowanego dodatku ani nie restartuj czytnika użytkownika.

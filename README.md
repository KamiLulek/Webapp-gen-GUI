# webapp-gen GUI 2.2

Graficzny menedżer osobnych aplikacji Chromium dla Linuksa/KDE, będący następcą
skryptu Bash webapp-gen 1.1.

Program korzysta z tych samych katalogów i formatu danych:

- ~/.config/webapp-gen/apps/*.cfg
- ~/.local/bin/webapp-list/*-app
- ~/.local/share/applications/*.desktop
- ~/.local/share/icons/webapp-ico/
- ~/.local/share/webapp-extensions/

Istniejące appki pojawią się w GUI bez migracji.

## Uruchomienie ze źródeł

Na Arch Linux:

    sudo pacman -S python-pyside6
    python -m webapp_gen

Albo w środowisku wirtualnym:

    python -m venv .venv
    .venv/bin/pip install -e .
    .venv/bin/webapp-gen

## Jednoplikowa binarka


    pip install -r requirements-build.txt
    ./build.sh

Powstanie wykonywalny plik webapp-gen. Pierwszy start binarki Nuitki może być
odrobinę wolniejszy, bo rozpakowuje ona komponenty Qt.

Instalacja dla bieżącego użytkownika i dodanie do launchera KDE:

    ./install.sh

Można też przekazać binarkę z innej ścieżki:

    ./install.sh /ścieżka/do/webapp-gen

## CLI

    webapp-gen --list
    webapp-gen --info APP

Uruchomienie bez argumentów otwiera GUI.

## Ważne zachowania

- Nazwa appki jest niezmienna po jej utworzeniu, żeby nie rozjechać profilu,
  wrappera, pliku desktop i reguł okna KDE.
- Usunięcie appki nie usuwa jej profilu Chromium ~/.config/NAZWA-app, więc dane
  nie giną przypadkiem.
- Pole Dodatkowe flagi jest przekazywane jako lista argumentów rozdzielonych
  spacjami, zgodnie z zachowaniem wersji Bash.

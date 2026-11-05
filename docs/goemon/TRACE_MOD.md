# Goemon-Laufzeit-Trace unter Windows

Du hast die fertige Goemon64Recompiled-Version bereits gestartet. Für unsere
Messdaten ist **kein vollständiger Goemon64Recomp-Build** nötig.
Wir bauen lediglich einen kleinen Diagnose-Mod mit dem offiziellen
[MNSGRecompModTemplate](https://github.com/klorfmorf/MNSGRecompModTemplate)
als .nrm-Datei.

## Einmalige Voraussetzungen

- Git und Python 3.11+ sind von der bisherigen ROM-Analyse vorhanden.
- LLVM/Clang mit MIPS-Target (das offizielle Mod-Template empfiehlt **18.1.8**,
  da 19.1.0 kein funktionierendes MIPS-Target bietet).
- ld.lld und make.
- RecompModTool.exe wird vom Buildskript automatisch aus dem offiziellen
  [N64Recomp-Release](https://github.com/N64Recomp/N64Recomp/releases/tag/mod-tool-release)
  heruntergeladen.

Mit Chocolatey, falls vorhanden:

~~~powershell
choco install llvm --version=18.1.8 make -y
clang --version
make --version
ld.lld --version
~~~

## Schritt 1 — Mod bauen

PowerShell aus deinem Shipwright-Verzeichnis:

~~~powershell
git pull --ff-only
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\goemon\diagnostic_mod\build_windows.ps1
~~~

Das Skript klont das offizielle Mod-Template mit seinen Submodulen in den
benachbarten Ordner GoemonTraceModBuild, ersetzt das Beispiel durch unseren
read-only Diagnose-Hook, kompiliert den MIPS-Code und erstellt über
RecompModTool.exe die Datei:

~~~text
..\GoemonTraceModBuild\build\goemon_original_trace.nrm
~~~

Es verändert den Goemon64Recomp-Quellcode nicht. Keine GitHub Actions.

## Schritt 2 — Mod installieren

Goemon64Recompiled.exe normal starten und im Mod-Menü über **Install Mods**
die erzeugte .nrm-Datei installieren. Sicherstellen, dass
**Goemon Original Reference Trace** aktiviert ist. Spiel beenden.

Die Mod ändert keinerlei Spielzustände, sondern verwendet ausschließlich
den offiziell unterstützten RECOMP_HOOK_RETURN-Hook am
Original-Handler func_80002040_2C40.

## Schritt 3 — Messdaten sammeln

Aus Shipwright:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\goemon\diagnostic_mod\capture_windows.ps1 -GameExe "D:\Spiele\Goemon64Recompiled\Goemon64Recompiled.exe"
~~~

Den EXE-Pfad an deine Installation anpassen. Das Skript startet
Goemon64Recompiled mit umgeleiteten Ausgabedateien. Verwende für diese
Aufzeichnung NICHT die Option --show-console: Sie ersetzt die umgeleiteten
Standardausgabe-Handles über freopen(CONOUT$).

Spiele 30–60 Sekunden **mit einem Charakter**: Stillstand, laufen,
loslassen, drehen, springen, landen und angreifen. Beende das Spiel normal.
Die Auswertung startet automatisch.

Das Ergebnis liegt außerhalb der Repositories:

~~~text
..\GoemonTraceRuns\run-JJJJMMTT-HHMMSS.zip
~~~

**Diese ZIP hier hochladen.** Sie enthält Logdateien und Spielerzustandsdaten,
keine ROM oder extrahierte Grafikdateien.

### Was aufgezeichnet wird

- GOEMON_REF: Original-Charakter-ID, action_id, Buttons, Sticks, gerenderte
  Position, Rotation und Animation.
- GOEMON_MEM: stichprobenartig bis zu 128 vollständige Kopien der
  originalen 448-Byte-Playerstruktur, ohne Assetdaten.
- GOEMON_TICK: Spielschleifen-, Frame- und Retrace-Zähler.

Die Aufnahme stoppt automatisch nach 2.400 gültigen Player-Frames.

## Technische Grenzen

Dieser .nrm-Mod ist neu und wurde noch nicht gegen deine konkrete
Windows-Installation getestet. Der Hook kommt aus dem offiziellen
Mod-Template, ist aber noch **nicht** als Physik-Tick bewiesen.
Der Output zeigt zunächst Original-Zustandsdaten, keine bereits
verifizierte Bewegungsgleichung.

Wenn Mod-Build oder Log-Aufnahme scheitern, sende das komplette
Fehlerprotokoll. Der Aufnahmestarter legt auch bei fehlenden GOEMON_REF
eine ZIP mit Diagnoseinformationen an.

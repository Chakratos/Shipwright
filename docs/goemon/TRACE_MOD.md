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

Es kopiert die fertige .nrm-Datei außerdem automatisch nach:

~~~text
C:\Users\Chakratos\AppData\Local\Goemon64Recompiled\mods
~~~

Es verändert den Goemon64Recomp-Quellcode nicht. Keine GitHub Actions.
Wenn du die Installation auslassen willst, nutze die Option -NoInstall.

## Schritt 2 — Aufnahme erst im Spiel aktivieren

Goemon64Recompiled.exe starten, sicherstellen, dass die Mod
**Goemon Original Reference Trace** im Mods-Menü aktiviert ist,
und zunächst einen Spielstand laden.

Die neue Mod-Konfigurationsoption **Original-Daten aufnehmen** ist
standardmäßig auf **Aus** gestellt. Öffne im laufenden Spiel
die Mod-Einstellungen und stelle sie auf **Aufnahme aktivieren**.
Danach das Mod-Menü verlassen und den Analogstick bewegen.

Der Mod wartet auf einen gültigen PlayerTask sowie eine
**aktive Analogstick-Bewegung**. Vorher werden **keine GOEMON_REF-
Messframes** aufgezeichnet — auch nicht im Titelmenü.
Die Mod protokolliert das Einschalten mit GOEMON_TRACE_ARMED,
den echten Start mit GOEMON_TRACE_BEGIN.

Zum Stoppen die Einstellung auf **Aus** zurücksetzen.
Alternativ endet die Aufnahme nach 2.400 Frames automatisch.
Pro Spielstart gibt es genau eine Aufnahme; für eine zweite Aufnahme
das Spiel neu starten.

## Schritt 3 — Messdaten sammeln

Aus Shipwright:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\goemon\diagnostic_mod\capture_windows.ps1
~~~

Der Launcher verwendet standardmäßig den von dir genannten Pfad
C:\Users\Chakratos\Desktop\Goemon64Recompiled\Goemon64Recompiled.exe.
Du kannst bei Bedarf weiterhin -GameExe mit einem anderen Pfad angeben.
Das Skript startet Goemon64Recompiled mit umgeleiteten Ausgabedateien.
Verwende für diese Aufzeichnung NICHT die Option --show-console:
Sie ersetzt die umgeleiteten Standardausgabe-Handles über freopen(CONOUT$).

Lade zuerst einen Spielstand, aktiviere die Aufnahme im Mod-Menü und
bewege danach den Analogstick. Spiele 30–60 Sekunden **mit einem Charakter**:
laufen, loslassen, stillstehen, drehen, springen, landen und angreifen.
Schalte die Aufzeichnung im Mod-Menü aus oder lass das Frame-Limit greifen,
und beende das Spiel danach normal. Die Auswertung startet automatisch.

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
Windows-Installation getestet. Die neue manuelle Start/Stop-Einstellung
verwendet das Mod-Konfigurations-API des offiziellen Templates.
Der Hook kommt aus dem offiziellen Mod-Template, ist aber noch
**nicht** als Physik-Tick bewiesen.
Der Output zeigt zunächst Original-Zustandsdaten, keine bereits
verifizierte Bewegungsgleichung.

Wenn Mod-Build oder Log-Aufnahme scheitern, sende das komplette
Fehlerprotokoll. Der Aufnahmestarter legt auch bei fehlenden GOEMON_REF
eine ZIP mit Diagnoseinformationen an.

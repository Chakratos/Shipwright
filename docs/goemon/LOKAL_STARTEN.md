# Einmalige lokale Goemon-Referenzanalyse (Windows)

Für den originalgetreuen Port brauchen wir **Daten aus der tatsächlich
vorhandenen NTSC-U-ROM**. Das Skript erstellt eine ZIP mit den für das
Reverse Engineering nötigen Analysen. Die ROM wird **nicht** in die ZIP
gepackt und **nicht** auf GitHub hochgeladen.

## 1. Beide Projekte einmalig herunterladen

Öffne PowerShell im gewünschten Entwicklungsverzeichnis:

```powershell
git clone --branch feature/goemon-original-controller --recurse-submodules https://github.com/Chakratos/Shipwright.git
git clone --branch dev --recurse-submodules https://github.com/klorfmorf/Goemon64Recomp.git
```

Benötigt: Git und Python **3.11 oder neuer**. Für die ersten ROM-Analysen
ist **kein Goemon64Recomp-Build** erforderlich. Die ROM muss die originale
US-Version von *Mystical Ninja Starring Goemon* (NG5E) sein, als
Big-Endian-`.z64`-Datei.

## 2. Einmaliger Analyse-Befehl

```powershell
cd Shipwright
py -3 tools\goemon\collect_reference.py --rom "D:\ROMs\Goemon.z64" --goemon "..\Goemon64Recomp"
```

Den Beispiel-ROM-Pfad durch den tatsächlichen Dateipfad ersetzen. Das
Skript akzeptiert sowohl die unveränderte **16-MiB-US-ROM** als auch die
bereits von Goemon64Recomp dekomprimierte ROM.

Die lokale Dekomprimierung läuft temporär; danach folgen automatisch:

- ROM-Version und Quellrevisionen erfassen;
- Overlay `.file_11` nach Original-Spielerfunktionen und Schreibzugriffen
  durchsuchen;
- den Aufrufgraphen der vier bekannten Original-Playerfunktionen ermitteln;
- die originalen Charaktergrafik-Datei-IDs und SHA-256-Manifeste ermitteln;
- die vorhandenen Python-Unit-Tests ausführen;
- **ausschließlich JSON/LOG-Dateien** in eine ZIP packen.

Für zusätzliche native C++20-Tests im gleichen Durchlauf kann
`--native` ergänzt werden. Dafür muss GCC, Clang oder MSVC im PATH liegen.

## 3. ZIP zurückgeben

Die ZIP liegt außerhalb der beiden Repositories, normalerweise:

```text
<Entwicklungsverzeichnis>\goemon-reference-reports\run-XXXXXX.zip
```

**Diese ZIP hier im Chat anhängen.** Sie enthält keine ROM, keine
Modelldateien, Texturen, Sounds oder ausführbare Original-Spielbinärdaten.
Bei Fehlern werden die jeweiligen Diagnose-Logs trotzdem mitgepackt.

Danach lassen sich die tatsächlichen Funktionsaufrufe und die vorhandenen
Charaktergrafikdateien anhand eines echten Originalspiels analysieren.

## Der nächste zusätzliche Schritt

Für echte Bewegungsdaten benötigen wir danach das Goemon-Spiel im
laufenden Goemon64Recomp-PC-Port. Die Installation des bereits vorhandenen
`tools/goemon/reference_probe/install_probe.py` und der Build sind in
[RE_TOOLCHAIN.md](RE_TOOLCHAIN.md) beschrieben. Dieser **zweite Schritt**
ist für die erste ZIP noch nicht erforderlich.

Ein GitHub Self-hosted Runner ist für spätere SoH- und Goemon-Builds
sinnvoll. Ein *GitHub Runner* verarbeitet allerdings technisch
**GitHub-Actions-Jobs**, nur eben auf dem eigenen Rechner. Wer GitHub
Actions grundsätzlich nicht nutzen möchte, braucht stattdessen einen
lokal betriebenen Build-Agenten oder einen direkt gestarteten Testprozess.

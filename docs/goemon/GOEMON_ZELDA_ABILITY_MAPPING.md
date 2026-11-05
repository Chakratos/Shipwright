# Goemon × Ocarina of Time – vereinbarte Fähigkeiten

**Status: Spiel- und Randomizer-Konzept, nicht implementiert.**
Diese Zuordnungen stammen ausschließlich aus den gemeinsam
erarbeiteten Nutzerideen vom 5. November 2026. Keine zusätzlichen
Originalfähigkeiten erfinden oder zwangsweise alle OoT-Items zuordnen.

## Gemeinsam vereinbarte Zuordnungen

| Originalfigur | Originalfähigkeit | OoT-Entsprechung | Stand |
|---|---|---|---|
| Goemon | Aufgeladener Ryu-Feuerball | Feuerpfeile und/oder Dins Feuer | Feuer-Interaktionen |
| Goemon | Chain Pipe | Enterhaken | Greif-/Enterhaken-Ziele |
| Goemon | Superkraft-Transformation („Super-Saiyajin“) | Goldene Handschuhe (Golden Gauntlets) | Schwere Objekte |
| Yae | Flöte | Okarina | Lied-/Musik-Ereignisse |
| Yae | Meerjungfrauenform | Eisenstiefel | Unterwasser-Bewegung |
| Yae | Meerjungfrauenform | Zora-Tunika | Unterwasser-Atmung |
| Yae | Bazooka | Bogen, eventuell Lichtpfeile | Licht-Aspekt noch offen |
| Sasuke | Eis-Kunais | Eispfeile | Eis-Interaktionen |
| Sasuke | Fliegen | Hover Boots / Schwebestiefel | Schweben und Abkürzungen |
| Ebisumaru | Kamera | Deku-Nüsse | Blend-/Betäubungsfunktion |
| Ebisumaru | Kamera/Licht | möglicherweise Mirror Shield / Spiegelschild | Weiterer offener Licht-Effekt |
| Ebisumaru | Kleinwerden | Crawl Spaces / Kriechgänge | Zugang im verkleinerten Zustand |
| Ebisumaru | Fleischhammer | Noch offen | Keine erzwungene Entsprechung |

## Verbindliche Designgrundsätze

1. Die vier Originalcharaktere behalten authentische Goemon-Mechanik,
   Waffen, Animationen, Interaktionen und Steuerung. Kein Link-Reskin.
2. OoT-Gegenstände werden funktional durch Goemon-Fähigkeiten
   ersetzt, nicht als bloßes Charaktermodell oder Textur ausgetauscht.
3. **Randomizer-Skips und alternative Progression sind erlaubt und
   erwünscht.** Es muss nicht jede Vanilla-Rätsellösung identisch
   funktionieren.
4. Konzept für später: spielmechanische Fähigkeiten von der
   OoT-/Randomizer-Logik entkoppeln. Mögliche technische
   Anforderungskategorien zu den obigen Zuordnungen sind
   Feuer, Eis, Greifen, Instrument, Unterwasser-Bewegung,
   Unterwasser-Atmung, Kraft, Schweben, Klein-/Kriechpassagen,
   Fernziel, Betäuben und eventuell Licht.
   Diese Kategorien sind **noch keine Projekt-APIs**.
5. **Offen lassen**: Fleischhammer, Bazooka-Lichtpfeile,
   Kamera/Spiegelschild. Ohne weitere Nutzerentscheidung keine
   genaue Spezialmechanik daraus behaupten.
6. Noch keine dieser Kampf-, Rätsel- und Randomizer-Funktionen ist
   im derzeitigen C++-Goemon-Bewegungskern implementiert.

Ziel: als klare, verlässliche Spezifikation für die spätere
Original-Goemon-zu-Zelda-Integrationsschicht dienen.

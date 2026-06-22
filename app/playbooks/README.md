# Troubleshooting-Playbooks

Strukturierte YAML-Dokumente für die ElevenLabs Knowledge Base. Jede Datei ist
eine YAML-**Liste** von Playbook-Einträgen.

## Pflichtfelder

| Feld           | Zweck                                                        |
|----------------|-------------------------------------------------------------|
| `id`           | eindeutiger Slug                                            |
| `title`        | sprechender Titel                                          |
| `area`         | FIBU \| ERP \| EVS \| HR \| IT \| Verwaltung                |
| `trigger`      | Symptom-Sprache des Anrufers (Erkennung, nicht Keywords)   |
| `diagnose`     | gezielte Rückfragen zur Eingrenzung                        |
| `loesung`      | sprechbare Lösungsschritte (kurz, gesprochen)              |
| `verifikation` | wie bestätigt wird, dass der Fall gelöst ist               |
| `eskalation`   | Liste aus `{bedingung, aktion}` — aktion: transfer \| ticket_hoch \| ticket |
| `handbuch_refs`| Querverweis auf KB-Handbuch für Faktenrückhalt            |

## WICHTIG
Die `loesung`-Schritte MÜSSEN aus echtem Fachwissen / den Handbüchern stammen.
Platzhalter `<<...>>` markieren ungefüllten Fachinhalt — vor Produktivnutzung ersetzen.
Ein selbstbewusst falsch antwortender Agent ist schlechter als ein Anrufbeantworter.

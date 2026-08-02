# Fonts

Cada font té un manifest JSON amb identificador estable, validable i ingerible.
Camps mínims:

```json
{
  "id": "yt_example",
  "kind": "video",
  "title": "Títol",
  "accessed_at": "2026-08-02",
  "source_level": "C_EXPLORATORY",
  "domain": "strategyquant",
  "rights_policy": "transformative_notes"
}
```

L'esquema complet és `manifests/source.schema.json`. Els fragments només contenen
notes transformadores amb localitzadors; mai una transcripció completa de tercers.

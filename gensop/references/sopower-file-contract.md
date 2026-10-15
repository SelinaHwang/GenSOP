# SOPower Share import contract

Verified read-only against the SOPower implementation on 2026-10-13. Recheck the current implementation if SOPower changes.

## Import envelope

The JSON document has exactly these top-level fields:

```json
{
  "kind": "soper-sop-share",
  "schemaVersion": 2,
  "exportedAt": 0,
  "payload": {
    "name": "SOP 名称",
    "steps": [
      {"name": "步骤名称", "duration": 60, "tags": []}
    ]
  }
}
```

- `exportedAt` is a non-negative safe integer in Unix epoch milliseconds.
- `payload` has exactly `name` and `steps`.
- Each step has exactly `name`, `duration`, and `tags`.
- The importer determines the format from JSON content; `.sop.json` is the current user-facing export suffix.
- The complete UTF-8 document must not exceed 1 MiB (1,048,576 bytes).

## SOPower hard constraints

- SOP name: trimmed non-empty string, at most 40 Unicode code points.
- Steps: at most 8. The current Share parser does not require at least one step, but GenSOP generation does.
- Step name: trimmed non-empty string, at most 60 Unicode code points.
- Step duration: safe integer from 1 through 86,400 seconds.
- Tags: array of at most 3 trimmed non-empty strings; each tag is at most 4 Unicode code points.
- Objects use exact key sets; unknown or missing keys are rejected.
- SOPower counts string length with JavaScript `Array.from(value).length`, which is Unicode code-point counting.
- SOPower calculates the file limit from the JSON text's UTF-8 byte length.

The app separately limits the user's live collection to 5 SOPs. That is an import-time collection-state limit, not a property that can be encoded or validated in one standalone Share file.

## GenSOP generation requirements

These are intentionally stricter than the importer:

- A generated response contains 1–8 steps.
- Every generated step is 60–86,400 seconds.
- Every generated step name is at most 8 Unicode code points.
- `preview` and `sopData` must be identical in title/name, step order, names, times, and tags; preview total time must equal the step sum.
- A refusal, failed validation, or unconfirmed preview cannot be exported.

The validator checks both layers and labels failures accordingly. It does not make semantic judgments about goals, order, granularity, label usefulness, factual grounding, or whether a refusal reason truly applies.

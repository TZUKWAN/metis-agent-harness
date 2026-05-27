# Custom Quality Gate Plugin

A Metis plugin that registers a `no_hardcoded_paths` quality gate.

## Gate Behavior

Scans all artifacts for hardcoded absolute paths such as:
- `/home/user/project/...`
- `C:\\Users\\name\\...`
- `/usr/local/...`

If any are found, the gate fails.

## Usage

Install the plugin and reference the gate in your eval suite:

```json
{
  "gates": ["no_hardcoded_paths"]
}
```

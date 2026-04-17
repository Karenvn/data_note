# Tests

This directory contains:

- small unit tests that run without external services
- fixture files for a lightweight smoke-test run
- representative output folders that show the expected shape of a generated genome-note folder

The fixture command is:

```bash
python -m data_note --template_file tests/fixtures/template.md tests/fixtures/bioprojects.txt
```

This is still a live run: it queries the configured public and optional local services and writes the generated species folder into the current working directory.

The sample folders in `tests/output/` are intentionally lightweight. They are included to show expected structure.

# Documentation claim auditor

An offline, deterministic Python 3.9+ CLI for checking whether documentation
claims about suffix stripping have matching Python call evidence. It uses only
the standard library, makes no network requests, sends no telemetry, and writes
no files. Version 0.1.0.

## Install and run

```sh
python3 -m pip install .
stemming-claim-audit --version
stemming-claim-audit audit .
python3 -m stemming_claim_audit audit . --json
stemming-claim-audit audit . --verbose --ignore vendor/ --ignore generated/ --fail-on medium
```

The directory defaults to the current directory. Exit 0 means no finding reaches
the chosen threshold; exit 2 means at least one does; exit 1 indicates a usage
or I/O error. The default threshold is high. Repeat the ignore option to skip
paths by relative prefix. Verbose decisions go to standard error, leaving JSON
output readable by other tools. Each JSON finding has verdict, message,
severity, and path fields. A clean JSON run returns an empty array.

## Scope and rules

The auditor reads the root README and Markdown below the docs directory.
Triple-backtick fenced blocks are excluded; inline code remains prose.
Matching uses case-insensitive exact substrings, longest first, without fuzzy
matching or hyphen conversion. Denials are removed before positive claims are
checked. Claims found only below a tests directory receive medium severity.
Python source is searched recursively, excluding Git metadata, bytecode caches,
and virtual environments. Evidence must occur in one module, with imports
resolved and local function or class shadowing respected.

The evidence routes are an imported suffix-chopping constructor paired with
an appropriate instance call, or one of the catalogued generic calls. An
unrelated attribute call with a shared generic name also qualifies. Imports
alone, string literals, comments, and external CLI invocation do not qualify.
Finding identifiers and examples follow:

```text
documented-stemming-claim-false          HIGH (MEDIUM for test-only claims)
documented-no-stemming-claim-false       HIGH
```

## Differentiation

The following neighboring tools check dictionary forms, text splitting,
per-token word-class labels, and typed entity spans, respectively:

```text
lemmatization-claim-audit
tokenization-claim-audit
part-of-speech-tagging-claim-audit
named-entity-recognition-claim-audit
```

Those operations do not establish suffix stripping. This auditor checks only
the checked feature; it does not assess the quality of language processing.

## Limitations

Static pattern matching is not semantic judgement. Exact phrases miss
paraphrases. Substring matching can produce false positives even for the
unrelated words shown below, because each contains a catalogued substring:

```text
system -> stem
systems -> stems
```

A shared method name on an unrelated object counts as generic evidence:

```python
unrelated.stem("value")
```

Evidence does not prove a call runs or returns correct output. Dynamic imports,
indirect call wrappers, and cross-module construction/use may be missed. Invalid
Python is ignored for evidence; unreadable scanned files cause an I/O error.
The tool reports contradictions and unsupported claims, not feature correctness.

## Development

```sh
python3 -m unittest discover
python3 -m build
```

MIT licensed.

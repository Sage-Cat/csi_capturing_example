# Local Experiments Directory

This directory stores raw captured experiment runs and metadata.

Expected layout:

```text
experiments/
  <exp_id>/
    meta.json
    <scenario>/
      run_<n>/
        distance_<X>m.jsonl
```

`experiments/` contents are intentionally git-ignored to prevent uploading raw runs.

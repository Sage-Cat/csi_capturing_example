# Local Experiments Directory

This directory stores raw captured experiment runs and metadata.

Legacy distance script layout (preserved):

```text
experiments/
  <exp_id>/
    meta.json
    <scenario>/
      run_<n>/
        distance_<X>m.jsonl
```

Unified config-driven runner layout:

```text
experiments/
  <exp_id>/
    <experiment_type>/
      run_<run_id>/
        manifest.json
        trial_<trial_id>/
          capture.jsonl
```

`experiments/` contents are intentionally git-ignored to prevent uploading raw runs.

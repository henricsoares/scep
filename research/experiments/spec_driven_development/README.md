# Spec-Driven Development Study

This directory contains the reproducible research artifacts for the SCEP case study on Spec-Driven Development with a generative AI coding agent.

## Files

- `methodology.md` — pre-analysis methodology, research questions, metrics, defect taxonomy and validity threats;
- `study_scope.md` — frozen Pull Request inclusion/exclusion rules and the primary quantitative sample;
- `collect_github_metrics.py` — collector for repository-observed GitHub metadata;
- `manual_classification.csv` — separate template for human semantic classification;
- `output/` — generated data; should not be treated as source-of-truth if it can be reproduced from GitHub.

## Primary sample

The main quantitative analysis uses 15 accepted functional increments:

```text
#1 #4 #9 #17 #19 #23 #26 #30 #36 #41 #45 #53 #55 #56 #58
```

All Pull Requests are still collected. Non-primary records are retained to avoid hiding documentation work, technical debt, test stabilization or superseded AI implementation attempts.

## Collect GitHub metadata

From the repository root:

```bash
python research/experiments/spec_driven_development/collect_github_metrics.py
```

For higher GitHub API rate limits, provide a token through the environment without committing it:

```bash
GITHUB_TOKEN=... python research/experiments/spec_driven_development/collect_github_metrics.py
```

The collector writes:

```text
research/experiments/spec_driven_development/output/pull_requests.csv
research/experiments/spec_driven_development/output/pull_requests.metadata.json
```

The CSV records GitHub-observed facts such as timestamps, commit counts, change size, comments, workflow results and explicit Issue traceability. It also applies the frozen study-scope labels defined in `study_scope.md`.

## Manual classification

Semantic judgments are intentionally kept separate from repository metadata.

Use `manual_classification.csv` to record whether an increment required a relevant correction, first-pass acceptance, correction severity, defect category, detection mechanism and supporting evidence.

Do not infer those fields automatically from commit messages alone.

## Interpretation

The collector measures elapsed repository-visible process intervals. In particular, `last_commit_at - first_commit_at` is only an observable agent iteration window proxy; it is not direct human effort, CPU time or uninterrupted agent execution time.

The study does not claim AI-versus-human productivity improvement because no equivalent manually implemented control group exists.

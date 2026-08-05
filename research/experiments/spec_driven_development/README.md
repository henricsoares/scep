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

## Commit timestamp semantics

Git preserves separate author and committer timestamps. The collector now records both:

```text
first_commit_author_at
last_commit_author_at
first_commit_committer_at
last_commit_committer_at
```

The study uses `committer.date` as the primary repository-visible timestamp basis. For compatibility with the analytical definitions, `first_commit_at` and `last_commit_at` are aliases of the first and last committer timestamps.

Author timestamps remain in the raw dataset so timestamp disagreements are observable rather than silently discarded.

The fact that a first commit can precede its associated Issue is preserved as a valid observation. Issue creation is therefore treated as task formalization time, not as a guaranteed start-of-work timestamp.

## CI history semantics

CI history is collected for every commit SHA observable in a Pull Request rather than only for the final PR head SHA.

For each PR, the collector queries GitHub Actions for `pull_request` workflow runs associated with every commit and deduplicates results by workflow-run id. The main fields are:

```text
workflow_commits_checked
observed_workflow_run_count
observed_failed_workflows_before_merge
observed_successful_workflows_before_merge
final_premerge_ci_result
```

The `observed_` prefix is intentional. GitHub may represent reruns as attempts of an existing workflow run, and historical representation is controlled by GitHub rather than by this study. These fields therefore describe the workflow history observable through the GitHub API at collection time; they must not be interpreted as a guaranteed exhaustive execution log.

`final_premerge_ci_result` describes the chronologically last observed Pull Request workflow run created before merge. A successful value supports the statement that a successful CI run was observed at the final integration stage; it does not imply that earlier commits never failed.

## Manual classification

Semantic judgments are intentionally kept separate from repository metadata.

Use `manual_classification.csv` to record whether an increment required a relevant correction, first-pass acceptance, correction severity, defect category, detection mechanism and supporting evidence.

Do not infer those fields automatically from commit messages alone.

## Interpretation

The collector measures elapsed repository-visible process intervals. In particular, `last_commit_at - first_commit_at` is only an observable agent iteration window proxy; it is not direct human effort, CPU time or uninterrupted agent execution time.

The study does not claim AI-versus-human productivity improvement because no equivalent manually implemented control group exists.

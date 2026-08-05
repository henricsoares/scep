# Methodology — Spec-Driven Development with Generative AI Agents

## 1. Study Overview

This study investigates the use of Spec-Driven Development combined with a generative AI coding agent during the development of the Smart Charging Experimentation Platform (SCEP).

The study focuses on the software development process rather than on the Smart Charging domain itself.

SCEP is used as a longitudinal case study because its development process includes:

- structured software specifications;
- Architecture Decision Records;
- GitHub Issues;
- Pull Requests;
- AI-assisted implementation;
- human review;
- automated testing;
- continuous integration;
- releases;
- an executable software artifact.

The objective is to analyze how structured specifications and software-engineering controls influenced the use of an AI coding agent, particularly regarding:

1. traceability;
2. delivery flow;
3. rework;
4. human supervision;
5. automated quality gates.

The study does not attempt to demonstrate that AI-assisted development is faster than conventional development, because no equivalent control group or manually implemented baseline exists.

## 2. Research Approach

The study follows an exploratory and descriptive case-study approach.

The primary unit of analysis is a functional software increment represented by a GitHub Pull Request associated with the implementation of a SCEP capability.

Whenever available, each increment is analyzed through the following traceability chain:

```text
Specification
    ↓
GitHub Issue
    ↓
AI-assisted implementation
    ↓
Pull Request
    ↓
Automated validation
    ↓
Human review
    ↓
Corrections
    ↓
Merge
    ↓
Release
```

Repository metadata is collected automatically when possible.

Qualitative attributes that cannot be reliably inferred from repository metadata are manually classified according to a predefined protocol.

## 3. Research Questions

### RQ1 — Traceability

To what extent did the adopted Spec-Driven Development process preserve traceability between software specifications and implemented increments?

### RQ2 — Delivery Flow

What delivery-cycle characteristics were observed for software increments implemented with the support of a generative AI coding agent?

### RQ3 — Rework

How frequently did initially generated implementations require relevant corrections before being accepted?

### RQ4 — Human Supervision

What categories of problems were identified through human review after the AI-generated implementation?

### RQ5 — Automated versus Human Detection

Which implementation problems were detected by automated quality gates, and which required human inspection or exploratory validation?

These questions are descriptive. No causal claim is made that the observed results are caused exclusively by the use of Spec-Driven Development or by the AI coding agent.

## 4. Study Object

The study object is the public SCEP Git repository.

SCEP was developed incrementally using:

- numbered software specifications;
- explicit architectural decisions;
- GitHub Issues for development scope;
- GitHub Pull Requests for implementation;
- a generative AI coding agent for implementation activities;
- automated tests and CI;
- human review before merge.

The implemented platform includes capabilities related to software architecture, identity and authorization, Smart Charging business operations, telemetry, domain events, analytics, dataset generation, external AI experimentation, occupancy predictions, digital-twin simulation and frontend visualization.

The diversity of these capabilities enables the study to observe AI-assisted development across different technical concerns instead of evaluating only homogeneous coding tasks.

## 5. Unit of Analysis

The primary unit of analysis is a **functional Pull Request**.

A Pull Request is preferred over an individual commit because it represents an identifiable development increment and aggregates:

- implementation changes;
- timestamps;
- commit history;
- changed files;
- code churn;
- automated checks;
- review activity;
- corrections;
- final merge status.

Specifications and Issues are treated as contextual and traceability artifacts associated with each Pull Request.

## 6. Inclusion Criteria

A Pull Request is included in the primary dataset when all of the following conditions are satisfied:

1. it contributes to the implementation of a functional SCEP capability;
2. it belongs to the development period considered by the study;
3. it contains implementation, testing, architectural, or functional integration work;
4. it can be associated with a software specification, functional requirement, or explicit project increment;
5. its repository metadata is available for analysis.

The primary analysis should prioritize functional increments related to the implementation of the SCEP specifications and the final MVP demonstration frontend.

Candidate categories include:

- domain capabilities;
- identity and authorization;
- telemetry;
- analytics;
- dataset export;
- predictions;
- simulation;
- external research integration;
- frontend demonstration.

## 7. Exclusion Criteria

Pull Requests are excluded from the primary quantitative analysis when their primary purpose is:

- documentation-only correction;
- repository housekeeping;
- formatting-only changes;
- dependency maintenance with no relevant functional impact;
- release metadata;
- administrative status updates;
- trivial configuration corrections unrelated to a functional increment.

Excluded Pull Requests may still be referenced qualitatively when they provide relevant context.

The inclusion/exclusion decision must be recorded explicitly to avoid retrospective selection based on observed outcomes.

## 8. Data Sources

### 8.1 Automatically collected data

The following data should be extracted through the GitHub API or equivalent repository tooling:

- Issue number;
- Issue creation timestamp;
- Pull Request number;
- Pull Request creation timestamp;
- Pull Request merge timestamp;
- commit count;
- commit timestamps;
- first commit timestamp;
- last commit timestamp;
- changed-file count;
- lines added;
- lines deleted;
- review comments;
- workflow runs;
- workflow results;
- workflow duration where available;
- merge status;
- associated Issue references;
- associated release information.

### 8.2 Manually classified data

The following attributes require human classification:

- associated specification;
- whether a functional correction was required;
- correction severity;
- defect category;
- defect detection mechanism;
- whether the first implementation was functionally acceptable;
- whether a relevant problem escaped automated validation;
- notes describing significant review episodes.

Manual classification must follow the definitions provided in this document.

## 9. Dataset Schema

The analytical dataset should use one row per included Pull Request.

Suggested fields:

```text
spec_id
issue_number
pr_number
issue_created_at
pr_created_at
first_commit_at
last_commit_at
merged_at

files_changed
additions
deletions
commit_count

workflow_run_count
failed_workflows_before_merge
successful_workflows_before_merge
review_comment_count

explicit_spec_traceability
explicit_issue_traceability
ci_before_merge

manual_correction_required
first_pass_accepted
correction_severity
defect_category
detection_mechanism
ci_green_when_human_defect_found

notes
```

Derived metrics should be computed from the raw fields rather than stored as primary observations whenever possible.

## 10. Quantitative Metrics

### 10.1 Traceability Coverage

Measures the proportion of analyzed increments with an identifiable chain between specification, Issue, and Pull Request.

```text
Traceability Coverage =
increments with SPEC → Issue → PR association
─────────────────────────────────────────────
total analyzed increments
```

Traceability may be classified as:

- explicit;
- reconstructed;
- unavailable.

An explicit association includes direct references such as `Closes #54`, `Fixes #54`, or `Resolves #54`.

A reconstructed association is one that can be reliably identified through repository history but is not explicitly encoded.

### 10.2 Issue-to-PR Time

```text
pr_created_at - issue_created_at
```

This metric represents the elapsed time between formalization of the development task and submission of the associated Pull Request. It must not be interpreted as direct human or machine working time.

### 10.3 Issue Lead Time

```text
merged_at - issue_created_at
```

This represents the total elapsed time between formalization of the task and integration into the main branch.

### 10.4 Pull Request Cycle Time

```text
merged_at - pr_created_at
```

This measures the elapsed review and integration period after the Pull Request becomes available.

## 11. AI Execution Window Metrics

Because the implementation workflow used an AI coding agent that continued working until the task requirements were satisfied, commit timestamps provide a partial observable approximation of agent iteration duration.

Two separate metrics are defined.

### 11.1 Time to First Observable Implementation

```text
first_commit_at - issue_created_at
```

This metric approximates the elapsed time between task formalization and the first repository-visible implementation artifact.

It includes unknown intervals and must not be interpreted as direct execution time.

### 11.2 Observed Agent Iteration Window

```text
last_commit_at - first_commit_at
```

This metric represents the observable time window during which implementation iterations were recorded through commits.

It is used as a **proxy for the observable AI-assisted implementation interval**.

The metric does not represent:

- CPU execution time;
- token-generation duration;
- exact human effort;
- uninterrupted coding time.

It may include:

- waiting for CI;
- pauses between interactions;
- human review time;
- delays before correction prompts;
- inactive periods.

It also excludes the implementation effort performed before the first commit.

For these reasons, the metric is treated only as an approximate process indicator.

## 12. Change Size Metrics

For each Pull Request, the following descriptive measures are collected:

- number of changed files;
- additions;
- deletions;
- total code churn;
- number of commits.

Total code churn may be expressed as:

```text
additions + deletions
```

These metrics are used as contextual variables and must not be interpreted directly as productivity or software quality indicators.

Possible exploratory analyses include:

- PR size versus review-cycle duration;
- PR size versus number of corrections;
- PR size versus CI failures.

## 13. Rework Metrics

### 13.1 First-Pass Acceptance

A Pull Request is considered first-pass accepted when its first submitted implementation does not require a relevant functional correction after human review.

```text
First-Pass Acceptance Rate =
PRs without relevant functional correction
──────────────────────────────────────────
analyzed PRs
```

The following do not invalidate first-pass acceptance:

- typo corrections;
- formatting;
- minor documentation edits;
- nonfunctional cosmetic adjustments.

The following do invalidate first-pass acceptance:

- functional bugs;
- authorization errors;
- incorrect contracts;
- race conditions;
- architectural violations;
- missing behavior required by the specification;
- significant missing tests;
- incorrect data or prediction behavior.

### 13.2 Manual Correction Rate

```text
Manual Correction Rate =
PRs requiring relevant correction
────────────────────────────────
analyzed PRs
```

This is the complement of first-pass acceptance when the classification is binary.

### 13.3 Additional Commits after Initial Implementation

The number of commits added after the first observable implementation is recorded as a repository-derived rework proxy.

This metric does not directly represent the number of defects. Additional commits may represent fixes, tests, refactoring, documentation or review adjustments.

Commit messages may be used as supporting qualitative evidence but not as the sole classification mechanism.

## 14. Correction Severity

Relevant corrections are classified into four levels.

### Level 0 — None

No relevant correction required.

### Level 1 — Minor

Small implementation adjustment with no material change in expected behavior.

Examples:

- minor UI state cleanup;
- additional defensive handling;
- small test adjustment.

### Level 2 — Functional

Correction required to satisfy expected behavior or acceptance criteria.

Examples:

- incorrect authorization order;
- invalid state transition;
- incorrect endpoint behavior;
- missing validation;
- stale frontend state causing invalid requests.

### Level 3 — Architectural or Scope-Level

Correction required because the implementation violated an architectural boundary, major requirement, or responsibility assignment.

Examples:

- model inference introduced into the Backend when it must remain external;
- Simulator directly accessing Backend persistence;
- incorrect module ownership;
- substantial deviation from an ADR.

Severity is assigned manually.

## 15. Defect Taxonomy

Relevant corrections are categorized according to the following predefined taxonomy.

### A. Requirements / Contract

Examples:

- incorrect interpretation of a specification;
- missing acceptance criterion;
- wrong endpoint semantics;
- contract mismatch.

### B. Security / Authorization

Examples:

- unauthorized behavior;
- incorrect authorization ordering;
- role or capability violation;
- data exposure.

### C. Architecture

Examples:

- responsibility assigned to the wrong component;
- violation of ADR;
- unintended coupling;
- module-boundary violation.

### D. Concurrency / State

Examples:

- stale state;
- race condition;
- inconsistent dependent selections;
- concurrent update issue.

### E. Data / Reproducibility

Examples:

- missing provenance;
- unreproducible experiment;
- inconsistent dataset handling;
- generated results without versioned process.

### F. Technical Quality

Examples:

- missing tests;
- error handling;
- type issues;
- build problems;
- validation gaps.

### G. Documentation

Examples:

- inaccurate README;
- stale project status;
- contract documentation mismatch.

If one correction belongs to multiple categories, a primary category should be assigned and secondary categories may be recorded separately.

## 16. Detection Mechanism

Each relevant problem is classified according to how it was discovered.

Allowed categories:

### AI Self-Correction

The coding agent identified and corrected the issue during implementation without external intervention.

### Automated Test

An automated test detected the defect.

### Continuous Integration

The defect was exposed by a CI quality gate such as test failure, type checking, lint, build, or security scan.

### Human Code Review

The problem was detected through manual inspection of implementation or architecture.

### Human Exploratory Testing

The problem was detected while manually exercising the running application.

This distinction allows comparison between automated and human defect detection.

## 17. CI Metrics

For each Pull Request, collect:

- number of workflow runs;
- number of failed runs before merge;
- number of successful runs;
- final pre-merge CI result.

A particularly relevant derived observation is:

```text
Human-found defect with CI green = true / false
```

This identifies cases where automated quality gates passed but a relevant semantic or behavioral defect still existed.

Such cases are especially important for evaluating the role of human supervision in AI-assisted development.

## 18. Automated versus Human Detection

The study compares the relative contribution of automated and human validation.

Problems are grouped into:

```text
Detected automatically
    - tests
    - CI
    - static analysis

Detected manually
    - code review
    - exploratory testing
```

The purpose is not to claim superiority of one mechanism. The goal is to identify which classes of defects were observable through each mechanism.

Special attention is given to cases where CI was successful but human review still discovered a relevant problem.

## 19. Descriptive Statistics

For temporal and size metrics, report:

- minimum;
- maximum;
- mean;
- median;
- standard deviation where useful.

Median should be emphasized for cycle-time measures because repository activity may include inactive periods and scheduling delays.

For categorical variables, report:

- absolute counts;
- percentages.

Because the expected number of analyzed increments is relatively small, inferential statistical claims should be avoided unless justified by the final dataset.

## 20. Exploratory Relationships

The following analyses may be performed descriptively:

- PR size versus correction severity;
- PR size versus review duration;
- agent iteration window versus correction requirement;
- CI failures versus manual correction requirement;
- specification complexity versus correction frequency;
- implementation domain versus defect category.

These analyses are exploratory and do not establish causality.

## 21. Optional Specification Complexity Analysis

A secondary exploratory analysis may characterize each specification through structural indicators such as:

- word count;
- number of acceptance criteria;
- number of explicit goals;
- number of non-goals;
- number of normative terms such as MUST or SHALL;
- number of API endpoints;
- number of referenced ADRs.

These measures may be compared descriptively with correction rate, cycle time, first-pass acceptance and PR size.

The number of specifications is expected to be small, so no strong statistical relationship should be inferred.

## 22. Metrics Explicitly Excluded

The following measures are intentionally excluded because the available evidence does not support reliable interpretation.

### Percentage of Code Written by AI

Repository history does not provide a reliable distinction between AI-generated and human-authored lines.

### Hours Saved by AI

No equivalent manually implemented control group exists.

### AI Productivity Gain

The study cannot reliably state that AI produced a specific percentage improvement over conventional development.

### Lines of Code per Hour

Lines of code are not treated as a meaningful productivity metric.

### Defects per Line of Code

The complete population of software defects is unknown.

### AI versus Human Speed

No equivalent set of tasks was implemented independently by both approaches.

## 23. Threats to Validity

### 23.1 Construct Validity

Commit timestamps are imperfect approximations of implementation activity.

The observed agent iteration window may include inactive periods and excludes work before the first commit.

Therefore, it must not be interpreted as exact implementation effort.

### 23.2 Internal Validity

The study is observational.

Multiple factors may influence delivery time and correction frequency, including:

- task complexity;
- specification quality;
- reviewer attention;
- project maturity;
- agent model behavior;
- available tests.

No causal inference should be made.

### 23.3 External Validity

The study analyzes one software project and one development workflow.

Results may not generalize directly to other programming languages, teams, AI agents, production-scale organizations or projects without structured specifications.

### 23.4 Researcher Bias

The project author also participated in specification definition, AI interaction, implementation review, exploratory testing and result interpretation.

To reduce retrospective bias:

- metrics are defined before final data collection;
- inclusion/exclusion criteria are predefined;
- defect categories are predefined;
- raw repository evidence is preserved;
- manual classifications should include explanatory notes.

### 23.5 Tool Evolution

AI coding agents may change over time.

Results should be interpreted in the context of the specific tool and development period used during the SCEP project.

## 24. Reproducibility

Repository-derived metrics should be collected automatically using a versioned script.

Suggested structure:

```text
research/
└── experiments/
    └── spec_driven_development/
        ├── methodology.md
        ├── collect_github_metrics.py
        ├── analyze_metrics.py
        ├── README.md
        └── output/
```

Generated analytical outputs should include, where appropriate:

```text
pull_requests.csv
issues.csv
workflows.csv
summary.json
```

The collection script should:

- use public GitHub repository metadata where possible;
- avoid embedded credentials;
- document the collection timestamp;
- preserve raw identifiers and timestamps;
- separate raw and derived data.

Generated outputs may remain unversioned if they are reproducible from the public repository.

## 25. Manual Review Dataset

Manual classifications should be stored separately from automatically collected metadata.

Suggested fields:

```text
pr_number
manual_correction_required
first_pass_accepted
correction_severity
defect_category
detection_mechanism
ci_green_when_human_defect_found
evidence
notes
```

This separation prevents subjective classification from being confused with repository-observed facts.

## 26. Ethical Considerations

The analysis should use only project information appropriate for academic publication.

The study must not expose:

- secrets;
- credentials;
- private user information;
- proprietary prompts from unrelated contexts;
- confidential external data.

Because the repository is public, source code and public development metadata may be analyzed, but the study should still distinguish public artifacts from private interaction history.

The role of the AI agent must be described transparently.

Human responsibility for final acceptance of generated software must also be acknowledged.

## 27. Interpretation Principles

The study should prioritize evidence-based claims.

Acceptable conclusions include:

> A defined proportion of analyzed increments required at least one relevant human-initiated correction.

> Certain categories of semantic defects were not detected by automated CI.

> The development process preserved explicit traceability between specifications, Issues and Pull Requests for a defined proportion of increments.

> The observed median Pull Request cycle time was X.

Claims that should not be made include:

> AI made development X% faster.

> AI replaced the software engineer.

> Spec-Driven Development caused the observed quality level.

> CI guarantees correctness of AI-generated software.

## 28. Expected Analytical Contribution

The expected contribution of the study is a practical characterization of an AI-assisted Spec-Driven Development workflow in which:

```text
Structured Specification
        +
Architectural Context
        +
Generative AI Agent
        +
Automated Quality Gates
        +
Human Review
        ↓
Traceable Software Increment
```

The study specifically examines where this process succeeds and where human engineering judgment remains necessary.

The resulting analysis is intended to contribute to discussions on:

- AI-assisted software engineering;
- specification-driven development;
- software project management;
- requirements traceability;
- human-in-the-loop development;
- quality assurance for AI-generated code.

## 29. Final Study Principle

The central methodological principle is:

> Repository metadata is treated as objective evidence of the development process, while semantic interpretation of implementation quality is explicitly separated into a documented human classification step.

This distinction should be preserved throughout data collection, analysis and reporting.

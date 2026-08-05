from __future__ import annotations

import argparse
import csv
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

DEFAULT_REPOSITORY = "henricsoares/scep"
PRIMARY_PRS = {1, 4, 9, 17, 19, 23, 26, 30, 36, 41, 45, 53, 55, 56, 58}
SUPERSEDED_BY = {2: 1, 8: 9, 16: 17, 40: 41}
SPEC_DOCUMENTATION_PRS = {14, 21, 24, 28, 34, 38, 43, 48, 50}
KNOWN_SECONDARY_PRS = SPEC_DOCUMENTATION_PRS | set(SUPERSEDED_BY)

ISSUE_CLOSE_RE = re.compile(
    r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)"
)


@dataclass(frozen=True)
class GitHubClient:
    repository: str
    token: str | None = None

    @property
    def api_root(self) -> str:
        return f"https://api.github.com/repos/{self.repository}"

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        request = urllib.request.Request(url)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "scep-spec-driven-development-study")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
                headers = {key.lower(): value for key, value in response.headers.items()}
                return payload, headers
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API request failed ({exc.code}): {url}\n{detail}") from exc

    def paginated(self, url: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        next_url: str | None = url
        while next_url:
            payload, headers = self.get(next_url)
            if not isinstance(payload, list):
                raise RuntimeError(f"Expected list response from {next_url}")
            records.extend(payload)
            next_url = _next_link(headers.get("link"))
        return records


def _next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue
        match = re.match(r"<([^>]+)>", section)
        if match:
            return match.group(1)
    return None


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat()


def _issue_reference(body: str | None) -> int | None:
    if not body:
        return None
    matches = ISSUE_CLOSE_RE.findall(body)
    return int(matches[0]) if matches else None


def _study_classification(pr_number: int, merged: bool) -> dict[str, Any]:
    if pr_number in PRIMARY_PRS:
        supersedes = next(
            (previous for previous, replacement in SUPERSEDED_BY.items() if replacement == pr_number),
            None,
        )
        return {
            "analysis_scope": "PRIMARY",
            "attempt_status": "ACCEPTED" if merged else "ABANDONED",
            "supersedes_pr": supersedes,
            "superseded_by_pr": None,
        }
    if pr_number in SUPERSEDED_BY:
        return {
            "analysis_scope": "SECONDARY",
            "attempt_status": "SUPERSEDED",
            "supersedes_pr": None,
            "superseded_by_pr": SUPERSEDED_BY[pr_number],
        }
    if pr_number in KNOWN_SECONDARY_PRS:
        return {
            "analysis_scope": "SECONDARY",
            "attempt_status": "NOT_APPLICABLE",
            "supersedes_pr": None,
            "superseded_by_pr": None,
        }
    return {
        "analysis_scope": "EXCLUDED",
        "attempt_status": "NOT_APPLICABLE",
        "supersedes_pr": None,
        "superseded_by_pr": None,
    }


def _commit_times(commits: list[dict[str, Any]]) -> dict[str, str | None]:
    author_times = sorted(
        timestamp
        for commit in commits
        if (timestamp := _iso(commit.get("commit", {}).get("author", {}).get("date")))
    )
    committer_times = sorted(
        timestamp
        for commit in commits
        if (timestamp := _iso(commit.get("commit", {}).get("committer", {}).get("date")))
    )

    return {
        "first_commit_author_at": author_times[0] if author_times else None,
        "last_commit_author_at": author_times[-1] if author_times else None,
        "first_commit_committer_at": committer_times[0] if committer_times else None,
        "last_commit_committer_at": committer_times[-1] if committer_times else None,
    }


def _workflow_runs_for_commits(
    client: GitHubClient, commits: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Collect PR-triggered workflow runs for every observable commit in the PR.

    GitHub Actions results are deduplicated by workflow-run id because the same run may be
    returned by more than one query in unusual histories. This remains an observed-history
    measure: GitHub may represent reruns as attempts of an existing run rather than as fully
    independent historical records.
    """

    runs_by_id: dict[int, dict[str, Any]] = {}
    checked_shas: set[str] = set()

    for commit in commits:
        sha = commit.get("sha")
        if not sha or sha in checked_shas:
            continue
        checked_shas.add(sha)
        encoded_sha = urllib.parse.quote(sha, safe="")
        payload, _ = client.get(
            f"{client.api_root}/actions/runs?head_sha={encoded_sha}&event=pull_request&per_page=100"
        )
        if not isinstance(payload, dict):
            continue
        for run in payload.get("workflow_runs", []):
            run_id = run.get("id")
            if isinstance(run_id, int):
                runs_by_id[run_id] = run

    return list(runs_by_id.values()), len(checked_shas)


def _workflow_summary(runs: list[dict[str, Any]], merged_at: str | None) -> dict[str, Any]:
    if not runs:
        return {
            "workflow_commits_checked": 0,
            "observed_workflow_run_count": 0,
            "observed_failed_workflows_before_merge": 0,
            "observed_successful_workflows_before_merge": 0,
            "final_premerge_ci_result": None,
        }

    merge_dt = datetime.fromisoformat(merged_at) if merged_at else None
    eligible: list[dict[str, Any]] = []
    for run in runs:
        created = _iso(run.get("created_at"))
        if created is None:
            continue
        if merge_dt is None or datetime.fromisoformat(created) <= merge_dt:
            eligible.append(run)

    eligible.sort(
        key=lambda item: (
            item.get("created_at") or "",
            int(item.get("run_attempt") or 0),
            int(item.get("id") or 0),
        )
    )
    failures = sum(1 for item in eligible if item.get("conclusion") == "failure")
    successes = sum(1 for item in eligible if item.get("conclusion") == "success")
    final = eligible[-1].get("conclusion") if eligible else None
    return {
        "observed_workflow_run_count": len(eligible),
        "observed_failed_workflows_before_merge": failures,
        "observed_successful_workflows_before_merge": successes,
        "final_premerge_ci_result": final,
    }


def _pull_request_row(client: GitHubClient, pr: dict[str, Any]) -> dict[str, Any]:
    number = int(pr["number"])
    detail, _ = client.get(f"{client.api_root}/pulls/{number}")
    commits = client.paginated(f"{client.api_root}/pulls/{number}/commits?per_page=100")
    reviews = client.paginated(f"{client.api_root}/pulls/{number}/reviews?per_page=100")
    issue_comments = client.paginated(f"{client.api_root}/issues/{number}/comments?per_page=100")
    review_comments = client.paginated(f"{client.api_root}/pulls/{number}/comments?per_page=100")

    commit_times = _commit_times(commits)
    workflow_runs, workflow_commits_checked = _workflow_runs_for_commits(client, commits)

    merged_at = _iso(detail.get("merged_at"))
    classification = _study_classification(number, bool(detail.get("merged")))
    workflow = _workflow_summary(workflow_runs, merged_at)
    workflow["workflow_commits_checked"] = workflow_commits_checked

    # Committer timestamps are the primary repository-visible timestamps used by the study.
    # Author timestamps are preserved independently because Git permits them to differ.
    first_commit_at = commit_times["first_commit_committer_at"]
    last_commit_at = commit_times["last_commit_committer_at"]

    return {
        "pr_number": number,
        "title": detail.get("title"),
        "state": detail.get("state"),
        "merged": bool(detail.get("merged")),
        "draft": bool(detail.get("draft")),
        "issue_number": _issue_reference(detail.get("body")),
        "pr_created_at": _iso(detail.get("created_at")),
        "first_commit_at": first_commit_at,
        "last_commit_at": last_commit_at,
        **commit_times,
        "merged_at": merged_at,
        "commit_count": len(commits),
        "files_changed": detail.get("changed_files"),
        "additions": detail.get("additions"),
        "deletions": detail.get("deletions"),
        "review_submission_count": len(reviews),
        "issue_comment_count": len(issue_comments),
        "review_comment_count": len(review_comments),
        "explicit_issue_traceability": _issue_reference(detail.get("body")) is not None,
        **workflow,
        **classification,
        "url": detail.get("html_url"),
    }


def _issue_created_at(client: GitHubClient, issue_number: int | None) -> str | None:
    if issue_number is None:
        return None
    payload, _ = client.get(f"{client.api_root}/issues/{issue_number}")
    return _iso(payload.get("created_at")) if isinstance(payload, dict) else None


def _all_pull_requests(client: GitHubClient) -> list[dict[str, Any]]:
    return client.paginated(f"{client.api_root}/pulls?state=all&sort=created&direction=asc&per_page=100")


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        raise RuntimeError("No Pull Requests were collected")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(materialized[0].keys()))
        writer.writeheader()
        writer.writerows(materialized)


def collect(repository: str, output: Path, token: str | None) -> None:
    client = GitHubClient(repository=repository, token=token)
    raw_prs = _all_pull_requests(client)
    rows: list[dict[str, Any]] = []

    for pr in raw_prs:
        row = _pull_request_row(client, pr)
        row["issue_created_at"] = _issue_created_at(client, row["issue_number"])
        rows.append(row)
        print(f"collected PR #{row['pr_number']}: {row['analysis_scope']} / {row['attempt_status']}")

    rows.sort(key=lambda item: int(item["pr_number"]))
    _write_csv(output, rows)

    metadata = {
        "repository": repository,
        "collected_at": datetime.now(UTC).isoformat(),
        "pull_request_count": len(rows),
        "primary_prs": sorted(PRIMARY_PRS),
        "primary_count": sum(1 for row in rows if row["analysis_scope"] == "PRIMARY"),
        "commit_timestamp_basis": "committer.date",
        "ci_collection": "pull_request workflow runs observed across every commit SHA in each PR, deduplicated by run id",
        "output": str(output),
    }
    metadata_path = output.with_suffix(".metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect reproducible GitHub metadata for the SCEP SDD case study")
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY, help="GitHub repository in owner/name form")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/experiments/spec_driven_development/output/pull_requests.csv"),
        help="CSV output path",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable containing an optional GitHub API token",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    collect(args.repository, args.output, os.getenv(args.token_env))


if __name__ == "__main__":
    main()

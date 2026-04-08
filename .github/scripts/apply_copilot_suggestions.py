#!/usr/bin/env python3
"""
Simple heuristic script to auto-apply GitHub Copilot "```suggestion```" review suggestions.
- Runs on the PR head branch and commits updates using the REST API.
- Safety: skips if the latest commit is authored by a GitHub Actions bot to avoid loops.
- Heuristic: uses the review comment's diff_hunk to find the original block to replace.
"""

import os
import re
import sys

from github import Github

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAME = os.environ.get("GITHUB_REPOSITORY")
PR_NUMBER = os.environ.get("PR_NUMBER")

if not (GITHUB_TOKEN and REPO_NAME and PR_NUMBER):
    print("Missing environment variables. Exiting.")
    sys.exit(1)

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)
pr = repo.get_pull(int(PR_NUMBER))
head_ref = pr.head.ref
head_sha = pr.head.sha

print(f"PR #{PR_NUMBER} on {REPO_NAME}, head ref {head_ref}, sha {head_sha}")

# Safety: skip if last commit author looks like a GitHub Actions bot and commit message indicates auto-apply
try:
    latest_commit = repo.get_commit(head_sha)
    author_login = None
    if latest_commit.author:
        author_login = latest_commit.author.login
    commit_msg = latest_commit.commit.message or ""
    print("Latest commit author:", author_login, "message:", commit_msg)
    if (
        author_login
        and "github-actions" in author_login
        and "Auto-applied Copilot" in commit_msg
    ):
        print("Latest commit is an auto-apply from Actions; skipping to avoid loop.")
        sys.exit(0)
except Exception as e:
    print("Could not inspect latest commit:", e)

# Collect review comments
comments = list(pr.get_review_comments())
print(f"Found {len(comments)} review comments")

suggestions_applied = []
suggestions_skipped = []

pattern = re.compile(r"```suggestion\n(?P<code>.*?)\n```", re.DOTALL)

for c in comments:
    try:
        author = c.user.login if c.user else ""
        body = c.body or ""
        if "suggestion" not in body:
            continue
        if "copilot" not in author.lower():
            # only auto-apply copilot authored suggestions by default
            continue
        m = pattern.search(body)
        if not m:
            suggestions_skipped.append((c.id, "no suggestion block"))
            continue
        suggestion_code = m.group("code")
        path = c.path
        diff_hunk = c.diff_hunk or ""
        if not path:
            suggestions_skipped.append((c.id, "no path"))
            continue
        print(f"Processing suggestion comment {c.id} on {path}")
        # derive old chunk from diff_hunk
        old_lines = []
        for line in diff_hunk.splitlines():
            if line.startswith("@@"):
                continue
            if line.startswith("-") or line.startswith(" "):
                # take removed lines and context
                if line.startswith("-"):
                    old_lines.append(line[1:])
                else:
                    old_lines.append(line[1:])
        old_chunk = "\n".join(old_lines).strip("\n")
        # fetch current file content on head ref
        try:
            contents = repo.get_contents(path, ref=head_ref)
            file_text = contents.decoded_content.decode("utf-8")
        except Exception as e:
            suggestions_skipped.append((c.id, f"could not load file: {e}"))
            continue
        applied = False
        # Try exact match replacement
        if old_chunk:
            idx = file_text.find(old_chunk)
            if idx != -1:
                new_text = file_text.replace(old_chunk, suggestion_code, 1)
                commit_message = (
                    f"Auto-applied Copilot suggestion from comment {c.id} (by {author})"
                )
                try:
                    repo.update_file(
                        path, commit_message, new_text, contents.sha, branch=head_ref
                    )
                    suggestions_applied.append((c.id, path))
                    print(f"Applied suggestion {c.id} to {path}")
                    applied = True
                except Exception as e:
                    suggestions_skipped.append((c.id, f"update failed: {e}"))
                    applied = False
        # Fallback: if suggestion_code already present skip, or try to append
        if not applied:
            if suggestion_code.strip() in file_text:
                suggestions_skipped.append((c.id, "suggestion already present"))
                continue
            # fallback: cannot confidently apply
            suggestions_skipped.append((c.id, "no matching hunk found"))

    except Exception as e:
        suggestions_skipped.append((getattr(c, "id", "unknown"), f"exception: {e}"))

# Post summary comment to PR
summary_lines = []
if suggestions_applied:
    summary_lines.append("Applied suggestions:")
    for cid, path in suggestions_applied:
        summary_lines.append(f"- Comment {cid} applied to {path}")
else:
    summary_lines.append("No suggestions were applied.")

if suggestions_skipped:
    summary_lines.append("\nSkipped/Failed suggestions:")
    for cid, reason in suggestions_skipped:
        summary_lines.append(f"- Comment {cid}: {reason}")

body = "\n".join(summary_lines)
try:
    pr.create_issue_comment(f":robot: Copilot auto-apply summary\n\n{body}")
except Exception as e:
    print("Failed to post summary comment:", e)

print("Done.")

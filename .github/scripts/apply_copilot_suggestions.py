#!/usr/bin/env python3
"""
Apply Copilot suggested changes from PR review comments where possible.

This script is intended to run inside a GitHub Action where the PR head branch
is checked out. It will:
 - Read the pull request number from GITHUB_EVENT_PATH
 - Fetch review comments authored by Copilot (or containing suggestion blocks)
 - For each suggestion, attempt to apply the suggested text to the target file
   by locating the original diff hunk in the checked-out file and replacing it
 - Commit and push changes back to the PR branch if any suggestions were applied
 - Post a PR comment summarizing applied/skipped suggestions

Exit codes:
 - 0: no suggestions found or all suggestions applied successfully
 - 2: some suggestions could not be applied (script will post a comment)

Requirements: PyGithub (pip install PyGithub)
"""

import os
import re
import json
import sys
import subprocess
from typing import List, Tuple

try:
    from github import Github
except Exception:
    print("PyGithub is required. Install with: pip install PyGithub", file=sys.stderr)
    sys.exit(1)


def load_event() -> dict:
    path = os.environ.get('GITHUB_EVENT_PATH')
    if not path or not os.path.exists(path):
        print('GITHUB_EVENT_PATH is not set or file not found; cannot determine PR number', file=sys.stderr)
        return {}
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def get_pr_number(event: dict) -> int:
    pr = event.get('pull_request')
    if pr and pr.get('number'):
        return int(pr.get('number'))
    env_pr = os.environ.get('PR_NUMBER')
    if env_pr:
        return int(env_pr)
    raise RuntimeError('Pull request number not found in event payload or PR_NUMBER env')


SUGGESTION_RE = re.compile(r'```suggestion\n([\s\S]*?)\n```')


def extract_suggestion(body: str) -> str:
    m = SUGGESTION_RE.search(body)
    return m.group(1) if m else None


def extract_original_from_diff(diff_hunk: str) -> str:
    # Keep context (' ') and removed ('-') lines as the original content
    lines: List[str] = []
    for ln in diff_hunk.splitlines():
        if not ln:
            continue
        if ln.startswith('@@'):
            continue
        if ln[0] in (' ', '-'):
            lines.append(ln[1:])
    return "\n".join(lines).strip()


def apply_suggestions_local(pr_comments, repo_root: str) -> Tuple[List[Tuple[int,str]], List[Tuple[int,str,str]]]:
    """Apply suggestions to files in the checked-out repository.

    Returns (applied, skipped) where applied is a list of (comment_id, path)
    and skipped is a list of (comment_id, path, reason).
    """
    applied = []
    skipped = []

    for c in pr_comments:
        body = c.body or ''
        author = (c.user.login or '').lower() if c.user else ''
        if 'copilot' not in author and '```suggestion' not in body:
            continue
        suggestion = extract_suggestion(body)
        if not suggestion:
            continue
        path = c.path
        diff_hunk = getattr(c, 'diff_hunk', '') or ''
        original = extract_original_from_diff(diff_hunk)
        full_path = os.path.join(repo_root, path)

        if not os.path.exists(full_path):
            skipped.append((c.id, path, 'file-not-found'))
            continue

        with open(full_path, 'r', encoding='utf-8') as fh:
            content = fh.read()

        applied_flag = False
        # First try exact original block replacement
        if original:
            idx = content.find(original)
            if idx != -1:
                new_content = content.replace(original, suggestion, 1)
                with open(full_path, 'w', encoding='utf-8') as fh:
                    fh.write(new_content)
                applied.append((c.id, path))
                applied_flag = True

        # If not applied, check if suggestion is already in file (already applied earlier)
        if not applied_flag and suggestion.strip() in content:
            applied.append((c.id, path))
            applied_flag = True

        # Fallback heuristics (do not modify if uncertain)
        if not applied_flag:
            # Try to find context-only match
            context_lines = '\n'.join([ln[1:] for ln in diff_hunk.splitlines() if ln.startswith(' ')]) if diff_hunk else ''
            if context_lines and context_lines.strip() in content:
                # Heuristic: replace the next few lines following context with suggestion
                pos = content.find(context_lines.strip())
                if pos != -1:
                    before = content[:pos + len(context_lines.strip())]
                    after = content[pos + len(context_lines.strip()):]
                    after_lines = after.splitlines()
                    new_after = '\n'.join(after_lines[20:]) if len(after_lines) > 20 else ''
                    new_content = before + '\n' + suggestion + (('\n' + new_after) if new_after else '')
                    with open(full_path, 'w', encoding='utf-8') as fh:
                        fh.write(new_content)
                    applied.append((c.id, path))
                    applied_flag = True
                else:
                    skipped.append((c.id, path, 'context-not-found'))
            else:
                skipped.append((c.id, path, 'no-match'))

    return applied, skipped


def git_has_changes() -> bool:
    res = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    return bool(res.stdout.strip())


def git_commit_and_push(pr_number: int, pr_head_ref: str) -> bool:
    try:
        if not git_has_changes():
            return False
        subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=True)
        subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', f'Apply Copilot suggestions for PR #{pr_number}'], check=True)
        subprocess.run(['git', 'push', 'origin', f'HEAD:{pr_head_ref}'], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print('git operation failed:', e, file=sys.stderr)
        return False


def main(argv: List[str]):
    verify_only = '--verify' in argv
    token = os.environ.get('GITHUB_TOKEN')
    repo_full = os.environ.get('GITHUB_REPOSITORY')
    if not token or not repo_full:
        print('GITHUB_TOKEN or GITHUB_REPOSITORY is not set', file=sys.stderr)
        sys.exit(1)

    event = load_event()
    try:
        pr_number = get_pr_number(event)
    except RuntimeError as e:
        print('Could not determine PR number:', e, file=sys.stderr)
        sys.exit(0)

    gh = Github(token)
    repo = gh.get_repo(repo_full)
    pr = repo.get_pull(pr_number)

    # Avoid running when the last commit is made by GitHub Actions to prevent loop
    try:
        last_author = subprocess.run(['git', 'log', '-1', '--pretty=format:%an'], capture_output=True, text=True).stdout.strip()
        if last_author in ('github-actions[bot]', 'github-actions'):
            print('Last commit authored by GitHub Actions; skipping to avoid loop')
            sys.exit(0)
    except Exception:
        pass

    pr_comments = list(pr.get_review_comments())
    # Filter for Copilot suggestions
    copilot_comments = [c for c in pr_comments if (c.user and 'copilot' in (c.user.login or '').lower()) or '```suggestion' in (c.body or '')]

    if not copilot_comments:
        print('No Copilot suggestions found')
        sys.exit(0)

    if verify_only:
        # Check whether all suggestions appear applied in files
        remaining = []
        repo_root = os.getcwd()
        for c in copilot_comments:
            suggestion = extract_suggestion(c.body or '')
            if not suggestion:
                continue
            path = c.path
            full_path = os.path.join(repo_root, path)
            if not os.path.exists(full_path):
                remaining.append((c.id, path, 'file-missing'))
                continue
            with open(full_path, 'r', encoding='utf-8') as fh:
                content = fh.read()
            if suggestion.strip() not in content:
                remaining.append((c.id, path, 'suggestion-not-present'))
        if remaining:
            msg = 'Some Copilot suggestions are not applied:\n' + '\n'.join([f'- Comment {cid} on {p}: {r}' for cid,p,r in remaining])
            try:
                pr.create_issue_comment(msg)
            except Exception:
                print('Failed to post PR comment')
            print(msg, file=sys.stderr)
            sys.exit(2)
        print('All Copilot suggestions appear applied')
        sys.exit(0)

    repo_root = os.getcwd()
    applied, skipped = apply_suggestions_local(copilot_comments, repo_root)

    changed = False
    if applied:
        changed = git_commit_and_push(pr_number, pr.head.ref)

    # Post summary comment
    lines = []
    if applied:
        lines.append(f'Applied {len(applied)} Copilot suggestion(s) automatically.')
    if skipped:
        lines.append(f'Could not apply {len(skipped)} suggestion(s):')
        for cid, path, reason in skipped:
            lines.append(f'- Comment {cid} on {path}: {reason}')
    if not lines:
        lines.append('No Copilot suggestions were found.')
    try:
        pr.create_issue_comment('\n'.join(lines))
    except Exception:
        print('Failed to post PR comment', file=sys.stderr)

    if skipped:
        sys.exit(2)
    sys.exit(0)

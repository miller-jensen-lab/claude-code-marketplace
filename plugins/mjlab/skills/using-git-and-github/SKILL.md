---
name: using-git-and-github
description: Agent behavior for git and GitHub in Miller-Jensen lab work — when to branch, what to commit, what to ignore, when to push back on big files, and how to handle the lab org `miller-jensen-lab`. TRIGGER when working in a git repository whose origin is under `miller-jensen-lab/*` OR a lab member's personal account doing lab-related work, when running `git`, `gh`, or any commit/branch/PR/repo-creation flow on lab code.
related:
  - coding-in-python
  - coding-in-r
  - starting-a-new-project
  - reproducible-envs
  - bio-data-hygiene
updated: 2026-05-13
---
# Using git and GitHub (Miller-Jensen lab)

This skill teaches the *agent* how to behave when handling git and GitHub for lab work. The user is a bench scientist, not a developer. They are not going to type "commit," ask for a branch, or notice when they're about to push a 4 GB FCS file. The agent does.

The lab's GitHub org is **`miller-jensen-lab`**. Default branch on every repo is `main`.

## First principles

- **The agent uses judgment about when to commit.** Don't wait for the word "commit." Commit when a logical task completes. Surface what you committed so the user can object.
- **Small data is fine in the repo.** Sample sheets, ≤~1 KB CSVs, metadata, lookup tables — track them. This is science, not a software project. Don't gitignore reflexively.
- **Big data never goes in git.** Bench data lives on the lab fileserver or Zenodo, not GitHub.
- **Never force-push a shared branch.** Propose a revert commit instead.
- **Never recommend Git LFS.** It costs more than it solves for this lab.

## Identity and auth

If the user has not authenticated `gh`, run:

```bash
gh auth login --hostname github.com --git-protocol https --web
```

This stores a token in the macOS Keychain (or system equivalent) and configures git to use `gh` as a credential helper. No SSH keys, no `~/.ssh/config`. SSH only as a fallback if the user already has it set up and prefers it.

Don't push 2FA or signed-commits configuration. Membership in `miller-jensen-lab` is gated by the admin (Kyle Jensen); attribution and key management are not a concern.

## Branch policy

Default: **commit on `main` and push.** PRs to yourself are theater.

Propose a branch only when:

1. The repo has **more than one recent committer** (last ~6 months). Check with `git log --since=6.months --format='%an' | sort -u`.
2. The change is **experimental** — the user wants to try something they may discard.
3. The user asks.

When you do branch on a solo repo, merge with `git merge --ff-only`, push, delete the branch. Don't open a PR to yourself.

When the repo is multi-author: open a PR with `gh pr create`, and request review from the other recent committer (`gh pr edit --add-reviewer <login>`).

## Commits

- Commit when a logical task completes. Don't ask permission. Don't commit mid-task.
- Message style: freeform present-tense imperative. First line ≤50 chars. Optional 1–3 line body. **No `feat:`/`fix:` Conventional Commits prefixes.**
- Surface what you committed in chat: file count, one-line summary, hash.
- The user can amend or revert if they object — make that easy.

Examples:

```
Add volcano plot to DE notebook
Rerun DESeq2 with corrected sample metadata
Drop wells D11–D12; contaminated per imaging
```

## What never goes in git

Drop a `.gitignore` like this on the first commit to any fresh lab repo:

```gitignore
# Data — fileserver or Zenodo, not git
data/raw/
data/derived/
*.h5ad
*.h5
*.fcs
*.fastq
*.fastq.gz
*.bam
*.bai
*.tiff
*.tif
*.czi
*.nd2

# Intermediate outputs
results/
figures/

# Notebook crud
.ipynb_checkpoints/
*.nbconvert.ipynb

# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/

# R
.Rhistory
.RData
.Rproj.user/
renv/library/
renv/local/
renv/staging/

# Env & secrets
.env
.env.local

# OS
.DS_Store
Thumbs.db
```

When manuscript figures need to be tracked, put them in an explicitly-tracked `manuscript/figures/` (not `results/` or `figures/`).

## Big-file pushback

Before any commit, check sizes of staged files.

- **>5 MB**: warn and propose moving to `data/raw/` (gitignored) with a `data.yml` entry.
- **>50 MB**: refuse to commit. No exceptions, no LFS suggestion.

The `data.yml` records what the file is and where it actually lives:

```yaml
- name: counts.h5ad
  sha256: e3b0c4...
  size_bytes: 1234567890
  location: /Volumes/MJ-lab/projects/2026-tnf-bursting/data/counts.h5ad
  # or: zenodo: https://doi.org/10.5281/zenodo.XXXXXXX
  description: TNF-α stimulated macrophage scRNA-seq, n=12k cells
```

Commit `data.yml`, not the data.

## Untracked files: report, propose, confirm

When `git status` shows untracked files, don't silently `.gitignore` or stage. Report what you see in one short block, propose a plan (track / ignore / refuse), and confirm with the user before acting.

Use judgment on ambiguous files. A 600-byte `samples.csv` is fine to track; a 4 GB `experiment.fcs` is not.

## Creating a new repo

When the user starts new analysis work, **ask once**: lab org or personal account?

Then **interview the user** before proposing a name. Ask:

- What's the experimental modality? (RNA-seq, flow, imaging, secretion, …)
- What biological system? (macrophages, T cells, wound healing, …)
- What perturbation or question? (IL-4 polarization, TNF bursting, …)
- What stage? (exploratory, paper draft, archival)
- First author, if known?

Propose 2–3 candidate names that follow these rules:

- lowercase kebab-case (`tnf-bursting`, not `TNF_bursting`)
- ≤4 words / ~30 chars
- self-contained — readable in `gh repo list miller-jensen-lab` six months later
- distinguishes from siblings (check `gh repo list miller-jensen-lab --limit 50` first)
- no dates unless the project is genuinely a one-shot timepoint
- no person names unless it's a paper archival (use `<firstauthor>etal-<topic>` then)
- never `test`, `scratch`, `new-project`, `untitled`

Create private by default:

```bash
gh repo create miller-jensen-lab/<name> --private --clone --description "<one sentence>"
```

## Personal → org migration

Softly prompt to move a personal repo to `miller-jensen-lab` when any of:

- A second collaborator is added.
- A preprint or paper figure is being prepared from it.
- Commits start referencing lab data paths (`/Volumes/MJ-lab/...`, fileserver mounts).

Accept "no" without nagging. Warn the user that transferring rewrites the URL and breaks any existing clones or bookmarks. Use:

```bash
gh repo transfer <repo> miller-jensen-lab
```

## Paper-replication archival

When the user says "we're submitting" or "this is going on bioRxiv," run through:

1. **Flip visibility** to public (confirm): `gh repo edit --visibility public`.
2. **README replication section**: paper title, authors, DOI/preprint, what's in the repo, exact reproduce commands.
3. **Lock the environment**: `uv sync` + commit `uv.lock`, or `renv::snapshot()` + commit `renv.lock`.
4. **Tag a release** so the at-submission state is recoverable (`git tag v1.0-preprint && git push --tags`). Brief — tags aren't central.
5. **Mention Zenodo**: one-time GitHub→Zenodo OAuth enable gives every future tag a citable DOI. The user does the OAuth step; the agent just points there.
6. **Offer to rename** to `<firstauthor>etal-<topic>` (e.g. `bridgesetal-ccc`). Don't enforce — URL changes break things.
7. **Add `CITATION.cff`** so GitHub's "Cite this repository" works.
8. **Pick a license** if none exists. Default to **MIT** unless the user has a reason otherwise.

## Other behaviors

- **Issues**: check `gh issue list --state all --limit 1` to see if the repo uses issues. If yes, file proactively when blocked. If no, ask the user once whether they want to start; don't impose.
- **Secrets**: before committing, look for obvious mistakes — `.env`, `credentials.json`, `*.pem`, and string patterns `AKIA[0-9A-Z]{16}`, `ghp_[A-Za-z0-9]{36}`, `sk-[A-Za-z0-9]{32,}`. Refuse the commit if found. For repos that legitimately handle sensitive code, suggest installing `gitleaks`, `detect-secrets`, `ripsecrets`, or `nosey-parker` as a pre-commit hook.
- **Force-push**: never on `main` or any branch that's been pushed. On a personal unpushed branch, OK with explicit user confirmation. Otherwise propose a revert commit.
- **CI / GitHub Actions**: don't propose unless the user asks.

## Remote sync

- On any multi-author repo, run `git fetch` before starting work. If `origin/main` is ahead, surface it.
- On pull conflicts: `git pull --rebase` on personal branches; stop and ask on `main`.
- At the start of a session in a known repo, run `git status` + `git fetch` and report anything unexpected (unpushed commits, divergent remote). Catches "I forgot to push from the other machine."

## Checklist before any push

- [ ] No data files >5 MB staged (warned) or >50 MB (refused)
- [ ] No `.env`, credentials, or obvious secrets staged
- [ ] No hardcoded user paths (`/Users/...`, `~/Dropbox/...`) introduced in this commit
- [ ] Commit message is imperative and ≤50 chars on the first line
- [ ] On `main` of a multi-author repo, you have a PR (not a direct push)

## Further reading

- [GitHub CLI manual](https://cli.github.com/manual/)
- [Pro Git book](https://git-scm.com/book/en/v2) — for users who want a deeper foundation
- [Zenodo + GitHub integration](https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content)
- [CITATION.cff format](https://citation-file-format.github.io/)
- [`gitleaks`](https://github.com/gitleaks/gitleaks), [`detect-secrets`](https://github.com/Yelp/detect-secrets), [`ripsecrets`](https://github.com/sirwart/ripsecrets), [`nosey-parker`](https://github.com/praetorian-inc/noseyparker)

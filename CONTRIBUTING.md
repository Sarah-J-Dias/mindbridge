# Contributing — a beginner's guide

Never used Git before? That's fine. Follow these steps every time you start a task.

## One-time setup

1. Make a free GitHub account and send your username to Sarah so she can add you to the repo.
2. Install Git: https://git-scm.com/downloads (or use Google Colab / GitHub Codespaces and skip installing).
3. Tell Git who you are:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@ucla.edu"
   ```
4. Clone the repo (see README → Quick start).

> Prefer clicking to typing? **GitHub Desktop** (https://desktop.github.com) does every step below with buttons.
> You can also edit and upload files directly on github.com — fine for docs and CSVs.

## Every task, the same 6 steps

```bash
# 1. Get the latest code
git checkout main
git pull

# 2. Make a branch named after you and the task
git checkout -b member4/crisis-keywords

# 3. Do your work (edit files in YOUR folder)

# 4. Save a snapshot
git add .
git commit -m "Add first 40 crisis keywords"

# 5. Upload your branch
git push -u origin member4/crisis-keywords

# 6. Open a Pull Request on github.com (a yellow "Compare & pull request" button appears)
```

Sarah reviews it, leaves comments if needed, and merges. Then start again at step 1 for your next task.

## Rules of the road

- **Stay in your folder** unless your task says otherwise — this avoids conflicts.
- **Never commit the API key** or a `.env` file. `.gitignore` blocks it, but double-check.
- **No real personal data** anywhere in this repo.
- Small commits with clear messages beat one giant commit.
- If Git shows a "merge conflict", don't panic — stop and ping Sarah.

## Branch names

`<member-or-name>/<short-task>` — e.g. `member1/anxiety-docs`, `member6/sidebar-disclaimer`.

## Pull request checklist

- [ ] Runs on my machine (or Colab)
- [ ] Only touches files for my task
- [ ] Includes a short note on how to use it
- [ ] No keys, passwords or personal data

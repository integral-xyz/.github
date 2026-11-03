# Alloy River organization profile

GitHub displays `profile/README.md` on the organization Overview after it reaches `main`.

Edit `profile/content.json` to change the description, links, and curated feature highlights. The numbers live in `profile/momentum.json`. Both are public; include only approved public content. Dates describe code merges, not verified deployment.

Render the README and all chart variants with Python 3.9 or newer:

```sh
python3 scripts/render_profile.py
```

Refresh counts using an authenticated GitHub CLI with read access to the three source repositories, then render:

```sh
python3 scripts/update_momentum.py
python3 scripts/render_profile.py
```

The updater counts all merged PR authors across `fms`, `fms-frontend`, and `integrations`. It uses the last twelve complete Monday–Sunday weeks in America/Toronto, including daylight saving transitions. It fetches aggregate counts and verifies source access before replacing the snapshot. It does not export PR titles, links, customer data, or code. Highlights remain manually curated.

The Codex recurring task runs Mondays at 9 a.m. America/Toronto after the initial profile PR has merged. It may update only the momentum JSON, generated README, and four momentum SVGs. It preserves content, layout, banners, and source scope. It pushes without force only if GitHub permits a direct update; otherwise it opens or updates a draft PR. No branch rules are changed.

Repository permissions report write access for the current account. The active organization ruleset, "Block Push to Main", requires one PR approval and resolved review threads on `main`, with no bypass actors. Direct pushes are currently blocked, so recurring updates use draft PRs. No branch rules are changed by this task.

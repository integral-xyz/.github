# Alloy River organization profile

GitHub displays `profile/README.md` on the organization Overview after it reaches `main`.

Edit `profile/content.json` to change the description, links, and footer. The numbers live in `profile/momentum.json`. Both are public; include only approved public content.

Render the README and all chart variants with Python 3.9 or newer:

```sh
python3 scripts/render_profile.py
```

Run the regression tests explicitly from the repository root:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Refresh counts using an authenticated GitHub CLI with read access to all organization repositories, then render:

```sh
python3 scripts/update_momentum.py
python3 scripts/render_profile.py
```

The updater counts merged PRs across all repositories owned by the `integral-xyz` organization, including private, archived, and forked repositories, with all PR authors included. Organization-wide queries automatically include new repositories. It uses the last twelve complete Monday–Sunday weeks in America/Toronto, including daylight saving transitions. It paginates the repository inventory and verifies access before replacing the snapshot. The authentication must retain access to every organization repository; GitHub can only return repositories visible to it. Public data contains aggregate counts and the inventory size, without repository names, PR titles, links, customer data, or code.

The Codex recurring task runs Mondays at 9 a.m. America/Toronto after the initial profile PR has merged. It may update only the momentum JSON, generated README, and four momentum SVGs. It preserves content, layout, banners, and source scope. It pushes without force only if GitHub permits a direct update; otherwise it opens or updates a draft PR. No branch rules are changed.

Recurring momentum updates are currently submitted as draft PRs for review.

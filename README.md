# Callback Wallboard

## Setup

1. Rename `github_workflows` folder to `.github/workflows`
2. Put your CSV in `data/callbacks.csv`
3. Push to GitHub — the Action will build `index.html` automatically
4. Connect Netlify to this repo — it will serve `index.html` as your live URL

## CSV column names expected
- `lead_id`
- `Agent Name`
- `CompanyName`
- `Call Back Stage`
- `callback_date`
- `last_call_date`
- `Callback Number`

## Power Automate flow
Trigger: When file is modified in OneDrive
Action 1: Delay 3 minutes (wait for export to finish)
Action 2: Get file content from OneDrive
Action 3: Update file in GitHub (path: data/callbacks.csv)
GitHub Action then rebuilds the HTML and Netlify deploys it.

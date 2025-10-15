# GitHub & PyPI Setup - Completed Steps & Next Actions

**Repository URL**: https://github.com/terrylica/exness-data-preprocess

---

## ✅ Completed Automatically

### 1. Code Changes
- ✅ Updated `pyproject.toml` URLs → `terrylica/exness-data-preprocess`
- ✅ Updated `CHANGELOG.md` comparison links
- ✅ Added 6 shields.io badges to `README.md`

### 2. GitHub Actions Workflows Created
- ✅ `.github/workflows/ci.yml` - Pre-commit CI + Python 3.9-3.13 testing
- ✅ `.github/workflows/publish.yml` - PyPI Trusted Publishing
- ✅ `.github/workflows/pre-commit-autoupdate.yml` - Weekly hook updates

### 3. Git Repository
- ✅ Initialized git repository
- ✅ Committed all files (75 files, 19,478 lines)
- ✅ Initial commit: `a982494`

### 4. GitHub Repository Created
- ✅ Repository: https://github.com/terrylica/exness-data-preprocess
- ✅ Public repository with description
- ✅ Code pushed to `main` branch
- ✅ 16 topics added (forex, duckdb, tick-data, financial-data, etc.)
- ✅ Issues enabled
- ✅ Wiki disabled

### 5. Repository Configuration
```json
{
  "name": "exness-data-preprocess",
  "description": "Professional forex tick data preprocessing with unified DuckDB storage, Phase7 OHLC schema, and sub-15ms query performance",
  "url": "https://github.com/terrylica/exness-data-preprocess",
  "isPrivate": false,
  "hasIssuesEnabled": true,
  "topics": ["backtesting", "data-engineering", "duckdb", "eurusd", "financial-data", "forex", "microstructure", "ohlc", "pandas", "parquet", "pyarrow", "python", "quantitative-finance", "tick-data", "time-series", "zstd"]
}
```

---

## 🔴 Critical: PyPI Trusted Publisher Setup (Must Do Before First Release)

**IMPORTANT**: This MUST be configured BEFORE creating your first release!

### Step 1: Go to PyPI Website

Open: https://pypi.org/manage/account/publishing/

### Step 2: Add Pending Publisher

Click **"Add a new pending publisher"** button

### Step 3: Fill in the Form

```
PyPI Project Name:    exness-data-preprocess
Owner:                terrylica
Repository name:      exness-data-preprocess
Workflow name:        publish.yml
Environment name:     release
```

### Step 4: Click "Add"

You should see a confirmation: "Pending publisher registered!"

### Step 5: Verify

You should see the pending publisher listed on the page:
- Project: `exness-data-preprocess`
- Status: Pending (will change to Active after first successful publish)

**What This Does:**
- Enables password-less publishing to PyPI via GitHub Actions
- Uses GitHub's OIDC tokens for authentication (no API tokens needed!)
- Automatically verifies your GitHub URLs with green checkmarks on PyPI
- Generates digital attestations (Sigstore) automatically

---

## ⚠️ Optional: Create GitHub Environment (Recommended)

This adds a manual approval gate before publishing to PyPI.

### Step 1: Go to Repository Settings

Open: https://github.com/terrylica/exness-data-preprocess/settings/environments

### Step 2: Create Environment

1. Click **"New environment"**
2. Name: `release`
3. Click **"Configure environment"**

### Step 3: Add Protection Rules (Optional)

**Required Reviewers** (recommended):
- Check "Required reviewers"
- Add yourself (`terrylica`)
- This will require you to manually approve each release

**Wait Timer** (optional):
- Set to 0 minutes (or add delay if wanted)

### Step 4: Save

Click **"Save protection rules"**

**What This Does:**
- Requires manual approval before publishing to PyPI
- Prevents accidental releases
- Adds extra safety layer

---

## 🎯 Optional: Branch Protection Rules (Best Practice)

Protects the `main` branch from direct pushes and requires CI to pass.

### Step 1: Go to Branch Settings

Open: https://github.com/terrylica/exness-data-preprocess/settings/branches

### Step 2: Add Rule

1. Click **"Add branch protection rule"**
2. Branch name pattern: `main`

### Step 3: Enable Protection

**Recommended settings:**
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
  - Search and add: `Pre-commit hooks`
  - Search and add: `Tests (Python 3.12)`
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings

### Step 4: Save Changes

Click **"Create"** or **"Save changes"**

---

## 🚀 Creating Your First Release (After PyPI Setup)

### Method 1: Using GitHub CLI (Recommended)

```bash
cd /Users/terryli/eon/exness-data-preprocess

# Update CHANGELOG.md date (change 2025-01-XX to today's date)
# Then commit
git add CHANGELOG.md
git commit -m "chore: prepare v0.1.0 release"
git push

# Create and push tag
git tag -a v0.1.0 -m "Release v0.1.0

Initial PyPI release with unified DuckDB architecture v2.0.0"
git push --tags

# Create GitHub release
gh release create v0.1.0 \
  --title "v0.1.0 - Initial Release" \
  --notes "## What's New

**Architecture v2.0.0:**
- Unified single-file DuckDB storage per instrument
- Phase7 13-column (v1.2.0) OHLC schema with dual-variant spreads and normalized metrics
- Sub-15ms query performance with date range filtering
- PRIMARY KEY constraints prevent duplicates
- Automatic gap detection for incremental updates
- DuckDB self-documentation with COMMENT ON statements

**Development:**
- GitHub Actions CI/CD with PyPI Trusted Publishing
- Pre-commit hooks (ruff, commitizen)
- Professional README with shields.io badges
- Python 3.9-3.13 support

**Full Changelog**: https://github.com/terrylica/exness-data-preprocess/blob/main/CHANGELOG.md"
```

### Method 2: Using GitHub Web Interface

1. Go to: https://github.com/terrylica/exness-data-preprocess/releases/new
2. Click "Choose a tag" → Type `v0.1.0` → Click "Create new tag: v0.1.0 on publish"
3. Release title: `v0.1.0 - Initial Release`
4. Description: Copy from CHANGELOG.md or use notes above
5. Click **"Publish release"**

### What Happens Next

1. **CI Workflow Runs** (~2-3 minutes)
   - Pre-commit hooks check
   - Tests on Python 3.9-3.13

2. **Publish Workflow Triggers** (~2-5 minutes)
   - Builds package
   - Publishes to PyPI via Trusted Publishing
   - Generates digital attestations automatically

3. **If Environment Protection Enabled:**
   - Go to: https://github.com/terrylica/exness-data-preprocess/actions
   - Find "Publish to PyPI" run
   - Click "Review deployments" → Approve

4. **Check PyPI:**
   - Package will be live at: https://pypi.org/project/exness-data-preprocess/
   - URLs will have green checkmarks (verified!)

5. **Update Repository Website:**
   - Go to: https://github.com/terrylica/exness-data-preprocess
   - Click ⚙️ (settings gear) next to "About"
   - Website: `https://pypi.org/project/exness-data-preprocess/`
   - Save

---

## 📊 Monitoring & Verification

### Check CI Status
```bash
gh run list --limit 5
```

Or visit: https://github.com/terrylica/exness-data-preprocess/actions

### Check Latest Release
```bash
gh release list
```

Or visit: https://github.com/terrylica/exness-data-preprocess/releases

### Test Package Installation (After First Release)
```bash
# Create clean environment
python -m venv /tmp/test-env
source /tmp/test-env/bin/activate

# Install from PyPI
pip install exness-data-preprocess

# Test import
python -c "import exness_data_preprocess as edp; print(edp.__version__)"
```

---

## 🔧 Common Commands

### Run Pre-commit Locally
```bash
pre-commit run --all-files
```

### Run Tests Locally
```bash
uv run pytest --cov
```

### Build Package Locally
```bash
uv build
```

### Check Package Metadata
```bash
uv run python -m build --outdir dist/
twine check dist/*
```

### Manual PyPI Upload (Not Recommended - Use Trusted Publishing Instead!)
```bash
# Only if Trusted Publishing fails
doppler run --project claude-config --config dev -- \
  uv publish --token "$PYPI_TOKEN"
```

---

## 📝 Post-Release Checklist

After your first successful release:

- [ ] Verify package on PyPI: https://pypi.org/project/exness-data-preprocess/
- [ ] Check that GitHub URLs have green checkmarks (verified)
- [ ] Update repository website field with PyPI URL
- [ ] Test installation: `pip install exness-data-preprocess`
- [ ] Share on social media / relevant communities
- [ ] Update project version in `pyproject.toml` to `0.2.0-dev` (prepare for next release)

---

## 🎉 What You Now Have (SOTA 2025)

✅ **Zero Secrets** - Trusted Publishing uses GitHub OIDC
✅ **Auto URL Verification** - Green checkmarks on PyPI
✅ **Digital Attestations** - Automatic Sigstore signing
✅ **Professional CI** - Pre-commit + Python 3.9-3.13 matrix
✅ **Auto-maintenance** - Weekly pre-commit hook updates
✅ **Professional Badges** - 6 shields.io badges in README
✅ **16 Topics** - Discoverable on GitHub
✅ **Branch Protection Ready** - Configurable via web UI
✅ **Environment Protection Ready** - Manual approval gate available

**Total Complexity:**
- Workflows: 3 files, ~120 lines YAML
- Secrets: 0 (Trusted Publishing!)
- Manual Token Management: None
- Maintenance: Automated

---

## 📚 Resources

- **Repository**: https://github.com/terrylica/exness-data-preprocess
- **Actions**: https://github.com/terrylica/exness-data-preprocess/actions
- **PyPI Trusted Publishers**: https://pypi.org/manage/account/publishing/
- **GitHub Environments**: https://github.com/terrylica/exness-data-preprocess/settings/environments
- **Branch Protection**: https://github.com/terrylica/exness-data-preprocess/settings/branches

---

**Last Updated**: 2025-10-12
**Status**: Repository created, PyPI setup pending
**Next Action**: Configure PyPI Trusted Publisher (see section above)

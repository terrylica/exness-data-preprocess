#!/bin/bash
# PyPI Publishing with Doppler Secret Management (Local-Only)
#
# WORKSPACE-WIDE POLICY: This script must ONLY run on local machines.
# CI/CD publishing is forbidden - see ADR-0027 for rationale.
#
# Prerequisites:
#   - Doppler CLI installed (brew install dopplerhq/cli/doppler)
#   - uv package manager installed (curl -LsSf https://astral.sh/uv/install.sh | sh)
#   - PYPI_TOKEN stored in Doppler (project: claude-config, config: prd)
#   - pyproject.toml with name and version fields
#
# Usage:
#   Copy this script to your project's scripts/ directory and run:
#     git pull origin main
#     ./scripts/publish-to-pypi.sh
#
# This script is project-agnostic and environment-agnostic.

set -euo pipefail

# ============================================================================
# CONFIGURATION (ADR: 2025-12-08-mise-env-centralized-config)
# ============================================================================
# Environment variables with defaults for backward compatibility.
# These can be pre-set via mise [env] or exported manually.
DOPPLER_PROJECT="${DOPPLER_PROJECT:-claude-config}"
DOPPLER_CONFIG="${DOPPLER_CONFIG:-prd}"
DOPPLER_PYPI_SECRET="${DOPPLER_PYPI_SECRET:-PYPI_TOKEN}"
PYPI_VERIFY_DELAY="${PYPI_VERIFY_DELAY:-3}"

# ============================================================================
# ENVIRONMENT DISCOVERY
# ============================================================================
# Discover how uv is installed before making assumptions.
# Supports: direct install, Homebrew, cargo, mise, asdf, or already in PATH.
#
# Non-interactive shells (like Claude Code) don't source shell configs,
# so we need to find tools explicitly.

discover_uv() {
    # Priority 1: Already in PATH (native install, Homebrew, or shell already configured)
    if command -v uv &> /dev/null; then
        echo "uv"
        return 0
    fi

    # Priority 2: Check common direct installation locations
    local uv_locations=(
        "$HOME/.local/bin/uv"             # Official curl installer
        "$HOME/.cargo/bin/uv"             # Cargo install
        "/opt/homebrew/bin/uv"            # macOS Homebrew (ARM)
        "/usr/local/bin/uv"               # macOS Homebrew (Intel) / Linux package manager
    )

    for uv_path in "${uv_locations[@]}"; do
        if [[ -x "$uv_path" ]]; then
            echo "$uv_path"
            return 0
        fi
    done

    # Priority 3: Try version managers (mise, asdf) as fallback
    # Only if uv not found directly - don't force any tool manager

    # Try mise
    local mise_locations=(
        "$HOME/.local/bin/mise"
        "/opt/homebrew/bin/mise"
        "/usr/local/bin/mise"
    )
    for mise_path in "${mise_locations[@]}"; do
        if [[ -x "$mise_path" ]]; then
            # Check if mise has uv available
            if "$mise_path" which uv &>/dev/null 2>&1; then
                echo "$mise_path exec -- uv"
                return 0
            fi
        fi
    done

    # Try asdf
    if [[ -f "$HOME/.asdf/asdf.sh" ]]; then
        # shellcheck source=/dev/null
        source "$HOME/.asdf/asdf.sh" 2>/dev/null || true
        if command -v uv &> /dev/null; then
            echo "uv"
            return 0
        fi
    fi

    # Not found
    return 1
}

# Discover uv installation method
UV_CMD=""
if UV_CMD=$(discover_uv); then
    : # Found
else
    echo ""
    echo "==============================================================="
    echo " ERROR: uv package manager not found"
    echo "==============================================================="
    echo ""
    echo "   Install uv using one of these methods:"
    echo ""
    echo "   # Official installer (recommended)"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "   # Homebrew"
    echo "   brew install uv"
    echo ""
    echo "   # Cargo"
    echo "   cargo install uv"
    echo ""
    echo "   # mise"
    echo "   mise use uv@latest"
    echo ""
    exit 1
fi

# ============================================================================
# CI DETECTION GUARDS
# ============================================================================
# This script must ONLY run on local machines, NEVER in CI/CD pipelines.
# Rationale (ADR-0027):
#   - Security: No long-lived PyPI tokens in GitHub secrets
#   - Speed: 30 seconds locally vs 3-5 minutes in CI
#   - Control: Manual approval step before production release

detect_ci_environment() {
    local ci_detected=false
    local detected_vars=""

    if [[ -n "${CI:-}" ]]; then
        ci_detected=true
        detected_vars="${detected_vars}\n   - CI: ${CI}"
    fi
    if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
        ci_detected=true
        detected_vars="${detected_vars}\n   - GITHUB_ACTIONS: ${GITHUB_ACTIONS}"
    fi
    if [[ -n "${GITLAB_CI:-}" ]]; then
        ci_detected=true
        detected_vars="${detected_vars}\n   - GITLAB_CI: ${GITLAB_CI}"
    fi
    if [[ -n "${JENKINS_URL:-}" ]]; then
        ci_detected=true
        detected_vars="${detected_vars}\n   - JENKINS_URL: ${JENKINS_URL}"
    fi
    if [[ -n "${CIRCLECI:-}" ]]; then
        ci_detected=true
        detected_vars="${detected_vars}\n   - CIRCLECI: ${CIRCLECI}"
    fi
    if [[ -n "${TRAVIS:-}" ]]; then
        ci_detected=true
        detected_vars="${detected_vars}\n   - TRAVIS: ${TRAVIS}"
    fi
    if [[ -n "${BUILDKITE:-}" ]]; then
        ci_detected=true
        detected_vars="${detected_vars}\n   - BUILDKITE: ${BUILDKITE}"
    fi

    if [[ "${ci_detected}" == "true" ]]; then
        echo ""
        echo "==============================================================="
        echo " ERROR: This script must ONLY be run on your LOCAL machine"
        echo "==============================================================="
        echo ""
        echo "   Detected CI environment variables:"
        echo -e "${detected_vars}"
        echo ""
        echo "   This project enforces LOCAL-ONLY PyPI publishing for:"
        echo "   - Security: No long-lived PyPI tokens in GitHub secrets"
        echo "   - Speed: 30 seconds locally vs 3-5 minutes in CI"
        echo "   - Control: Manual approval step before production release"
        echo ""
        echo "   See: docs/development/PUBLISHING.md (ADR-0027)"
        echo ""
        exit 1
    fi
}

# Run CI detection immediately
detect_ci_environment

# ============================================================================
# BRANCH VALIDATION GUARDS
# ============================================================================
# Publishing must only happen from main/master to ensure released code matches
# the version tagged by semantic-release.

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "${CURRENT_BRANCH}" != "main" && "${CURRENT_BRANCH}" != "master" ]]; then
    echo ""
    echo "==============================================================="
    echo " ERROR: This script must ONLY be run on main/master branch"
    echo "==============================================================="
    echo ""
    echo "   Current branch: ${CURRENT_BRANCH}"
    echo "   Required branch: main or master"
    echo ""
    echo "   To publish, switch to main and pull latest:"
    echo "     git checkout main"
    echo "     git pull origin main"
    echo "     ./scripts/publish-to-pypi.sh"
    echo ""
    exit 1
fi

# ============================================================================
# MAIN PUBLISHING WORKFLOW
# ============================================================================

echo ""
echo "Publishing to PyPI (Local Workflow)"
echo "======================================================"

# Step 0: Verify Doppler token is available
echo -e "\n Step 0: Verifying Doppler credentials..."

if ! command -v doppler &> /dev/null; then
    echo "   ERROR: Doppler CLI not installed"
    echo "   Install: brew install dopplerhq/cli/doppler"
    exit 1
fi

# Try to get PYPI_TOKEN from Doppler (configurable via env vars)
if ! PYPI_TOKEN=$(doppler secrets get "$DOPPLER_PYPI_SECRET" --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" --plain 2>/dev/null); then
    echo "   ERROR: $DOPPLER_PYPI_SECRET not found in Doppler"
    echo ""
    echo "   To fix, run:"
    echo "     doppler secrets set $DOPPLER_PYPI_SECRET='your-token' --project $DOPPLER_PROJECT --config $DOPPLER_CONFIG"
    echo ""
    echo "   Get token from: https://pypi.org/manage/account/token/"
    exit 1
fi
echo "   Doppler token verified"

# Step 1: Verify pyproject.toml exists
echo -e "\n Step 1: Reading package info from pyproject.toml..."

if [[ ! -f "pyproject.toml" ]]; then
    echo "   ERROR: pyproject.toml not found"
    echo "   This script must be run from the project root directory."
    exit 1
fi

# Extract package name and version from pyproject.toml
PACKAGE_NAME=$(grep '^name = ' pyproject.toml | sed 's/name = "\(.*\)"/\1/' | head -1)
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/' | head -1)

if [[ -z "${PACKAGE_NAME}" ]]; then
    echo "   ERROR: Could not extract package name from pyproject.toml"
    exit 1
fi

if [[ -z "${CURRENT_VERSION}" ]]; then
    echo "   ERROR: Could not extract version from pyproject.toml"
    exit 1
fi

echo "   Package: ${PACKAGE_NAME}"
echo "   Version: v${CURRENT_VERSION}"

# Step 2: Clean old builds - safe glob handling
# ADR: /docs/adr/2025-12-07-idempotency-backup-traceability.md
echo -e "\n Step 2: Cleaning old builds..."
rm -rf dist/ build/ 2>/dev/null || true
find . -maxdepth 1 -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
echo "   Cleaned"

# Step 3: Build package
echo -e "\n Step 3: Building package..."
echo "   Using: $UV_CMD"
$UV_CMD build 2>&1 | grep -E "(Building|Successfully built)" || $UV_CMD build
echo "   Built: dist/${PACKAGE_NAME}-${CURRENT_VERSION}*"

# Step 4: Publish to PyPI using Doppler token
echo -e "\n Step 4: Publishing to PyPI..."
echo "   Using $DOPPLER_PYPI_SECRET from Doppler ($DOPPLER_PROJECT/$DOPPLER_CONFIG)"

# Use UV_PUBLISH_TOKEN environment variable for security (no token in process list)
UV_PUBLISH_TOKEN="${PYPI_TOKEN}" $UV_CMD publish 2>&1 | grep -E "(Uploading|succeeded|Failed)" || \
    UV_PUBLISH_TOKEN="${PYPI_TOKEN}" $UV_CMD publish

echo "   Published to PyPI"

# Step 5: Verify publication on PyPI
echo -e "\n Step 5: Verifying on PyPI..."
sleep "$PYPI_VERIFY_DELAY"

# Check if package version is live on PyPI
if curl -s "https://pypi.org/pypi/${PACKAGE_NAME}/${CURRENT_VERSION}/json" | grep -q "\"version\":"; then
    echo "   Verified: https://pypi.org/project/${PACKAGE_NAME}/${CURRENT_VERSION}/"
else
    echo "   Still propagating (CDN caching)"
    echo "   Check manually in 30 seconds: https://pypi.org/project/${PACKAGE_NAME}/${CURRENT_VERSION}/"
fi

echo -e "\n Complete! Published ${PACKAGE_NAME} v${CURRENT_VERSION} to PyPI"
echo ""
echo "Next steps:"
echo "  - Verify package is installable: pip install ${PACKAGE_NAME}==${CURRENT_VERSION}"
echo "  - Check PyPI page: https://pypi.org/project/${PACKAGE_NAME}/"
echo "  - Monitor downloads: https://pypistats.org/packages/${PACKAGE_NAME}"

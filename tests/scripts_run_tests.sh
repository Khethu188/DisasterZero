
#!/bin/bash
# ─────────────────────────────────────────────────────────────
# scripts/run_tests.sh
# DisasterZero — Test Runner
# ─────────────────────────────────────────────────────────────
# Usage:
#   ./scripts/run_tests.sh              # Run all tests
#   ./scripts/run_tests.sh unit         # Unit tests only
#   ./scripts/run_tests.sh integration  # Integration tests only
#   ./scripts/run_tests.sh e2e          # End-to-end tests only
#   ./scripts/run_tests.sh coverage     # Full run with coverage report
#   ./scripts/run_tests.sh quick        # Fast subset for CI
# ─────────────────────────────────────────────────────────────

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

MODE="${1:-all}"

echo -e "${CYAN}"
echo "═══════════════════════════════════════════════════════"
echo "  🛡️  DisasterZero — Test Suite"
echo "  Mode: ${MODE}"
echo "  Date: $(date)"
echo "═══════════════════════════════════════════════════════"
echo -e "${NC}"

# Ensure we're in project root
cd "$(dirname "$0")/.."

# Install test dependencies
echo -e "${YELLOW}Installing test dependencies...${NC}"
pip install -q pytest pytest-cov pytest-mock pytest-xdist 2>/dev/null

case "$MODE" in
    unit)
        echo -e "${CYAN}Running unit tests...${NC}"
        pytest tests/unit/ -v --tb=short -m "not slow"
        ;;

    integration)
        echo -e "${CYAN}Running integration tests...${NC}"
        pytest tests/integration/ -v --tb=short
        ;;

    e2e)
        echo -e "${CYAN}Running end-to-end tests...${NC}"
        pytest tests/e2e/ -v --tb=long
        ;;

    coverage)
        echo -e "${CYAN}Running all tests with coverage...${NC}"
        pytest tests/ \
            -v \
            --tb=short \
            --cov=src \
            --cov-report=term-missing \
            --cov-report=html:reports/coverage \
            --cov-fail-under=80

        echo -e "\n${GREEN}Coverage report: reports/coverage/index.html${NC}"
        ;;

    quick)
        echo -e "${CYAN}Running quick tests (CI mode)...${NC}"
        pytest tests/unit/ -x -q --tb=line -m "not slow"
        ;;

    all)
        echo -e "${CYAN}Running ALL tests...${NC}"
        echo ""

        echo -e "${YELLOW}── Unit Tests ──${NC}"
        pytest tests/unit/ -v --tb=short
        echo ""

        echo -e "${YELLOW}── Integration Tests ──${NC}"
        pytest tests/integration/ -v --tb=short
        echo ""

        echo -e "${YELLOW}── End-to-End Tests ──${NC}"
        pytest tests/e2e/ -v --tb=short
        echo ""

        echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  ✅ All tests complete!${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
        ;;

    *)
        echo -e "${RED}Unknown mode: ${MODE}${NC}"
        echo "Usage: $0 {all|unit|integration|e2e|coverage|quick}"
        exit 1
        ;;
esac


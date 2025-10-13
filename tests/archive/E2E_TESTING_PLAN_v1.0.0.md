# End-to-End Testing Implementation Plan - v2.1.0

**Version**: 1.0.0
**Status**: In Progress
**Date**: 2025-10-12
**Objective**: True end-to-end testing with downloads from https://ticks.ex2archive.com/

---

## Architecture

**Data Source**: Exness public tick repository (https://ticks.ex2archive.com/)
**Download Method**: `ExnessDataProcessor.download_exness_zip()` (existing, battle-tested)
**Data Variants**: Raw_Spread (primary), Standard (secondary, availability varies)
**Test Month**: August 2024 (815,775 Raw_Spread ticks confirmed available)

---

## Service Level Objectives (SLOs)

### Availability
- **SLO-AV-1**: Fixture downloads complete or skip: 100% graceful handling
- **SLO-AV-2**: Network failures result in test skip: 0 test failures from network issues
- **SLO-AV-3**: Temp directories cleanup on all paths: 100% cleanup rate

### Correctness
- **SLO-CR-1**: Downloaded data matches Exness format: 100% schema compliance
- **SLO-CR-2**: Tests verify actual downloaded data: 0 hardcoded expectations
- **SLO-CR-3**: Skip logic prevents false failures: 100% skip accuracy when data unavailable
- **SLO-CR-4**: All passing tests use real downloads: 0 mocked data in passing tests

### Observability
- **SLO-OB-1**: Test skip messages identify missing data: 100% actionable skip reasons
- **SLO-OB-2**: Download progress visible in test output: 100% download transparency
- **SLO-OB-3**: Failures distinguish download vs processing errors: 100% error attribution

### Maintainability
- **SLO-MA-1**: Fixture logic reusable across tests: >80% fixture reuse
- **SLO-MA-2**: Skip decorators applied before test logic: 100% proper placement
- **SLO-MA-3**: Tests independent of data source changes: 0 hardcoded tick counts
- **SLO-MA-4**: Documentation reflects actual data availability: 100% accuracy

---

## Current State (2025-10-12 22:00)

### Working
- ✅ conftest.py downloads from Exness online source
- ✅ Raw_Spread variant downloads successfully (815,775 ticks, Aug 2024)
- ✅ 8/16 tests passing with real downloads
- ✅ Download errors result in test skip (pytest.skip)

### Issues
- ❌ Skip logic placed inside docstrings (syntax error)
- ❌ Standard variant unavailable for Aug/Sep 2024 (404 from source)
- ❌ 8/16 tests failing: attempt to load unavailable Standard variant
- ❌ Hardcoded tick count assertions (199, 276, 277) need dynamic values

---

## Implementation Plan

### Phase 1: Fix Skip Logic Placement ✅ NEXT
**Duration**: 15 minutes
**Blocker**: Tests attempting to load Standard variant when unavailable

**Tasks**:
1. Read test_functional_regression.py lines 60-260
2. Extract misplaced skip logic from docstrings
3. Place skip checks after docstring closing, before test logic
4. Pattern:
   ```python
   def test_name(self, processor_with_real_data):
       """Docstring here."""
       if not processor_with_real_data.has_standard_data:
           pytest.skip("Standard variant not available for this month")

       # Test logic starts here
   ```
5. Apply to tests at lines: 63, 110, 181, 217, 250
6. Remove hardcoded tick counts at lines: 276, 277

**Validation**:
- Run: `uv run pytest tests/test_functional_regression.py -v`
- Expected: 5 tests skip, 5 tests pass
- All passing tests use downloaded data

### Phase 2: Verify test_processor_pydantic.py
**Duration**: 10 minutes

**Tasks**:
1. Verify skip checks at lines 34, 119 are correctly placed
2. Run: `uv run pytest tests/test_processor_pydantic.py -v`
3. Expected: 2 tests skip, 4 tests pass

### Phase 3: Update Documentation
**Duration**: 20 minutes

**Tasks**:
1. Update PYDANTIC_REFACTORING_STATUS.md Phase 4E:
   - Note: True E2E with Exness downloads
   - Document: Standard variant limitation
   - Update: Test counts (10 pass, 6 skip when Standard unavailable)
2. Update test file docstrings:
   - Clarify: "Downloads from https://ticks.ex2archive.com/"
   - Note: "Standard variant may not be available for recent months"
3. Archive this plan to `tests/archive/E2E_TESTING_PLAN_v1.0.0.md`

### Phase 4: Explore Alternative Data Months (OPTIONAL)
**Duration**: 30 minutes (if needed)

**Fallback**: If Standard variant required for comprehensive testing

**Tasks**:
1. Test download availability for older months (2023-01 through 2024-06)
2. Identify month with both Raw_Spread AND Standard available
3. Update fixture to use that month
4. Re-run full suite

**Decision Criteria**:
- If 6 tests remain skipped: Document limitation, proceed to Phase 5
- If older month found with both variants: Update fixture, verify all 16 tests pass

### Phase 5: Final Validation
**Duration**: 10 minutes

**Tasks**:
1. Run full test suite: `uv run pytest --cov=exness_data_preprocess --cov-report=term-missing`
2. Verify coverage metrics
3. Update PYDANTIC_REFACTORING_STATUS.md with final counts
4. Mark Phase 4 as COMPLETE

---

## Error Handling Policy

**Fail-Fast**: All errors propagate immediately
- Network errors during download: pytest.skip with reason
- File not found after download: Test failure (indicates bug)
- Schema mismatch in downloaded data: Test failure (indicates data corruption)
- Database errors: Test failure (indicates processor bug)

**No Silent Failures**: Every error visible in test output

---

## Off-The-Shelf Components

- **Download**: `ExnessDataProcessor.download_exness_zip()` (existing)
- **Skip logic**: `pytest.skip()` (standard pytest)
- **Fixtures**: pytest fixtures (standard pattern)
- **Temp dirs**: `tempfile.mkdtemp()` (Python stdlib)
- **Cleanup**: pytest fixture teardown (standard pattern)

---

## References

**Active Documents**:
- Implementation: `/Users/terryli/eon/exness-data-preprocess/tests/conftest.py`
- Tests: `/Users/terryli/eon/exness-data-preprocess/tests/test_functional_regression.py`
- Tests: `/Users/terryli/eon/exness-data-preprocess/tests/test_processor_pydantic.py`
- Status: `/Users/terryli/eon/exness-data-preprocess/PYDANTIC_REFACTORING_STATUS.md`

**Data Source**:
- Repository: https://ticks.ex2archive.com/
- Format: `/ticks/{VARIANT}/{YEAR}/{MONTH}/Exness_{PAIR}_{VARIANT}_{YEAR}_{MONTH:02d}.zip`
- Known Available: Raw_Spread for EURUSD 2024-08 (815,775 ticks)
- Known Unavailable: Standard for EURUSD 2024-08, 2024-09 (404 error)

---

**Last Updated**: 2025-10-12 22:00
**Next Review**: After Phase 1 completion

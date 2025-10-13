"""Type safety tests for Literal types and helper functions (v2.1.0).

SLO Coverage:
- SLO-CR-3: Literal types enforce only valid values: 100% type constraint enforcement
- SLO-MA-2: Test names describe validation target: 100% naming consistency
"""

from typing import get_args

import exness_data_preprocess as edp
from exness_data_preprocess.models import PairType, TimeframeType, VariantType


class TestPairType:
    """Test PairType Literal type definition and helper functions."""

    def test_pair_type_valid_values(self):
        """Test PairType Literal contains all valid pairs.

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        valid_pairs = get_args(PairType)

        # Verify expected pairs are present
        assert "EURUSD" in valid_pairs
        assert "GBPUSD" in valid_pairs
        assert "XAUUSD" in valid_pairs
        assert "USDJPY" in valid_pairs
        assert "AUDUSD" in valid_pairs
        assert "USDCAD" in valid_pairs
        assert "NZDUSD" in valid_pairs
        assert "EURGBP" in valid_pairs
        assert "EURJPY" in valid_pairs
        assert "GBPJPY" in valid_pairs

        # Verify exact count (should be 10 pairs)
        assert len(valid_pairs) == 10

    def test_supported_pairs_helper(self):
        """Test supported_pairs() helper function.

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        pairs = edp.supported_pairs()

        # Verify return type is tuple
        assert isinstance(pairs, tuple)

        # Verify content matches PairType
        assert "EURUSD" in pairs
        assert "GBPUSD" in pairs
        assert "XAUUSD" in pairs
        assert "USDJPY" in pairs

        # Verify count
        assert len(pairs) == 10

    def test_supported_pairs_matches_pair_type(self):
        """Test supported_pairs() returns same values as PairType.

        SLO-CR-2: Field accuracy: 100%.
        """
        pairs_from_helper = edp.supported_pairs()
        pairs_from_literal = get_args(PairType)

        # Verify exact match
        assert pairs_from_helper == pairs_from_literal


class TestTimeframeType:
    """Test TimeframeType Literal type definition and helper functions."""

    def test_timeframe_type_valid_values(self):
        """Test TimeframeType Literal contains all valid timeframes.

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        valid_timeframes = get_args(TimeframeType)

        # Verify expected timeframes are present
        assert "1m" in valid_timeframes
        assert "5m" in valid_timeframes
        assert "15m" in valid_timeframes
        assert "30m" in valid_timeframes
        assert "1h" in valid_timeframes
        assert "4h" in valid_timeframes
        assert "1d" in valid_timeframes

        # Verify exact count (should be 7 timeframes)
        assert len(valid_timeframes) == 7

    def test_supported_timeframes_helper(self):
        """Test supported_timeframes() helper function.

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        timeframes = edp.supported_timeframes()

        # Verify return type is tuple
        assert isinstance(timeframes, tuple)

        # Verify content matches TimeframeType
        assert "1m" in timeframes
        assert "5m" in timeframes
        assert "15m" in timeframes
        assert "1h" in timeframes
        assert "1d" in timeframes

        # Verify count
        assert len(timeframes) == 7

    def test_supported_timeframes_matches_timeframe_type(self):
        """Test supported_timeframes() returns same values as TimeframeType.

        SLO-CR-2: Field accuracy: 100%.
        """
        timeframes_from_helper = edp.supported_timeframes()
        timeframes_from_literal = get_args(TimeframeType)

        # Verify exact match
        assert timeframes_from_helper == timeframes_from_literal

    def test_timeframe_ordering(self):
        """Test timeframes are ordered from shortest to longest.

        SLO-MA-2: Naming consistency: 100%.
        """
        timeframes = edp.supported_timeframes()

        # Verify ordering: 1m, 5m, 15m, 30m, 1h, 4h, 1d
        assert timeframes[0] == "1m"
        assert timeframes[1] == "5m"
        assert timeframes[2] == "15m"
        assert timeframes[3] == "30m"
        assert timeframes[4] == "1h"
        assert timeframes[5] == "4h"
        assert timeframes[6] == "1d"


class TestVariantType:
    """Test VariantType Literal type definition and helper functions."""

    def test_variant_type_valid_values(self):
        """Test VariantType Literal contains all valid variants.

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        valid_variants = get_args(VariantType)

        # Verify expected variants are present
        assert "raw_spread" in valid_variants
        assert "standard" in valid_variants

        # Verify exact count (should be 2 variants)
        assert len(valid_variants) == 2

    def test_supported_variants_helper(self):
        """Test supported_variants() helper function.

        SLO-CR-3: Type constraint enforcement: 100%.
        """
        variants = edp.supported_variants()

        # Verify return type is tuple
        assert isinstance(variants, tuple)

        # Verify content matches VariantType
        assert "raw_spread" in variants
        assert "standard" in variants

        # Verify count
        assert len(variants) == 2

    def test_supported_variants_matches_variant_type(self):
        """Test supported_variants() returns same values as VariantType.

        SLO-CR-2: Field accuracy: 100%.
        """
        variants_from_helper = edp.supported_variants()
        variants_from_literal = get_args(VariantType)

        # Verify exact match
        assert variants_from_helper == variants_from_literal

    def test_variant_ordering(self):
        """Test variants are ordered: raw_spread, standard.

        SLO-MA-2: Naming consistency: 100%.
        """
        variants = edp.supported_variants()

        # Verify ordering matches Exness source priority
        assert variants[0] == "raw_spread"  # Primary variant
        assert variants[1] == "standard"  # Reference variant


class TestTypeExports:
    """Test type definitions are properly exported from package."""

    def test_pair_type_accessible(self):
        """Test PairType is accessible from main package.

        SLO-OB-1: Actionable error messages: 100%.
        """
        assert hasattr(edp, "PairType")
        assert edp.PairType == PairType

    def test_timeframe_type_accessible(self):
        """Test TimeframeType is accessible from main package.

        SLO-OB-1: Actionable error messages: 100%.
        """
        assert hasattr(edp, "TimeframeType")
        assert edp.TimeframeType == TimeframeType

    def test_variant_type_accessible(self):
        """Test VariantType is accessible from main package.

        SLO-OB-1: Actionable error messages: 100%.
        """
        assert hasattr(edp, "VariantType")
        assert edp.VariantType == VariantType

    def test_helper_functions_accessible(self):
        """Test all helper functions are accessible from main package.

        SLO-OB-1: Actionable error messages: 100%.
        """
        assert hasattr(edp, "supported_pairs")
        assert hasattr(edp, "supported_timeframes")
        assert hasattr(edp, "supported_variants")

        # Verify they are callable
        assert callable(edp.supported_pairs)
        assert callable(edp.supported_timeframes)
        assert callable(edp.supported_variants)

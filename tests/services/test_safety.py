"""
Tests for safety filter service
"""
import pytest
from kidsearch.api.services.safety import SafetyFilter
from kidsearch.api.models import SearchResult, SearchSource


@pytest.mark.unit
class TestSafetyFilter:
    """Test cases for SafetyFilter"""

    def test_safety_filter_initialization(self):
        """Test safety filter initialization"""
        filter_obj = SafetyFilter()

        assert filter_obj.blocked_domains is not None
        assert filter_obj.allowed_domains is not None
        assert filter_obj.blocked_keywords is not None

    def test_result_safety_check_safe(self):
        """Test that safe results pass"""
        filter_obj = SafetyFilter()

        result = SearchResult(
            id="1",
            title="Dinosaures",
            url="https://safe.com/page",
            excerpt="Information about dinosaurs",
            source=SearchSource.TYPESENSE,
            score=0.9
        )

        is_safe, reason = filter_obj.is_safe(result)
        assert is_safe is True
        assert reason is None

    def test_result_safety_check_unsafe_keyword(self):
        """Test that unsafe results are blocked"""
        filter_obj = SafetyFilter()
        filter_obj.blocked_keywords = ["violence", "adult", "casino"]

        result = SearchResult(
            id="1",
            title="Violence content",
            url="https://example.com/page",
            excerpt="This contains violence",
            source=SearchSource.TYPESENSE,
            score=0.9
        )

        is_safe, reason = filter_obj.is_safe(result)
        assert is_safe is False
        assert reason is not None
        assert "violence" in reason.lower()

    def test_result_safety_case_insensitive(self):
        """Test that safety check is case insensitive"""
        filter_obj = SafetyFilter()
        filter_obj.blocked_keywords = ["blocked"]

        result = SearchResult(
            id="1",
            title="BLOCKED content",
            url="https://example.com/page",
            excerpt="Test",
            source=SearchSource.TYPESENSE,
            score=0.9
        )

        is_safe, reason = filter_obj.is_safe(result)
        assert is_safe is False

    def test_filter_results_by_domain(self):
        """Test filtering results by blocked domain"""
        filter_obj = SafetyFilter()
        filter_obj.blocked_domains = {"blocked.com"}

        results = [
            SearchResult(
                id="1",
                title="Safe Result",
                url="https://safe.com/page",
                excerpt="Safe",
                source=SearchSource.TYPESENSE,
                score=0.9
            ),
            SearchResult(
                id="2",
                title="Blocked Result",
                url="https://blocked.com/page",
                excerpt="Blocked",
                source=SearchSource.TYPESENSE,
                score=0.8
            )
        ]

        filtered = filter_obj.filter_results(results)

        assert len(filtered) == 1
        assert filtered[0].id == "1"

    def test_filter_results_allowed_domains_only(self):
        """Test filtering to allow only specific domains"""
        filter_obj = SafetyFilter()
        filter_obj.allowed_domains = {"allowed.com"}

        results = [
            SearchResult(
                id="1",
                title="Allowed Result",
                url="https://allowed.com/page",
                excerpt="Allowed",
                source=SearchSource.TYPESENSE,
                score=0.9
            ),
            SearchResult(
                id="2",
                title="Other Result",
                url="https://other.com/page",
                excerpt="Other",
                source=SearchSource.TYPESENSE,
                score=0.8
            )
        ]

        filtered = filter_obj.filter_results(results)

        # If allowed_domains is set, only those should pass
        assert len(filtered) == 1
        assert filtered[0].id == "1"

    def test_filter_results_empty_list(self):
        """Test filtering empty result list"""
        filter_obj = SafetyFilter()

        filtered = filter_obj.filter_results([])

        assert filtered == []

    def test_extract_domain_removes_www(self):
        """Test that domain extraction removes www prefix"""
        filter_obj = SafetyFilter()

        domain1 = filter_obj._extract_domain("https://www.example.com/page")
        domain2 = filter_obj._extract_domain("https://example.com/page")

        assert domain1 == domain2
        assert domain1 == "example.com"

    def test_add_blocked_domain(self):
        """Test adding a domain to blocklist"""
        filter_obj = SafetyFilter()

        test_domain = "badsite.com"  # Test literal, not a URL to parse
        filter_obj.add_blocked_domain(test_domain)

        # Verify exact match in set (not substring search)
        assert test_domain in filter_obj.blocked_domains

    def test_add_blocked_keyword(self):
        """Test adding a keyword to blocklist"""
        filter_obj = SafetyFilter()

        filter_obj.add_blocked_keyword("inappropriate")

        assert "inappropriate" in filter_obj.blocked_keywords

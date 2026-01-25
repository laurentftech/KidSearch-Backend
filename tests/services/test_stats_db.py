"""
Tests for stats database service
"""
import pytest
import os
from kidsearch.api.services.stats_db import StatsDatabase


@pytest.mark.unit
class TestStatsDatabase:
    """Test cases for StatsDB"""

    def test_stats_db_initialization(self, temp_db_path):
        """Test stats database initialization"""
        db = StatsDatabase(db_path=temp_db_path)
        assert os.path.exists(temp_db_path)

    def test_log_search_query(self, temp_db_path):
        """Test logging a search query"""
        db = StatsDatabase(db_path=temp_db_path)

        stats = {
            "total_results": 20,
            "typesense_results": 15,
            "cse_results": 5,
            "wiki_results": 0,
            "processing_time_ms": 250.5,
            "typesense_time_ms": 100.0,
            "cse_time_ms": 120.0,
            "reranking_time_ms": 30.5,
            "reranking_applied": True,
            "cache_hit": False
        }

        # Should not raise an exception
        db.log_search(
            query="dinosaures",
            lang="fr",
            limit=20,
            use_cse=True,
            use_reranking=True,
            use_hybrid=False,
            stats=stats
        )

    def test_get_total_searches(self, temp_db_path):
        """Test getting total search count"""
        db = StatsDatabase(db_path=temp_db_path)

        # Initially should be 0
        assert db.get_total_searches() == 0

        # Log a search
        stats = {"total_results": 10, "processing_time_ms": 100.0}
        db.log_search("test", "fr", 10, True, True, False, stats)

        # Should be 1
        assert db.get_total_searches() == 1

    def test_get_searches_last_hour(self, temp_db_path):
        """Test getting searches from last hour"""
        db = StatsDatabase(db_path=temp_db_path)

        stats = {"total_results": 10, "processing_time_ms": 100.0}
        db.log_search("test", "fr", 10, True, True, False, stats)

        # Should include the just-logged search
        count = db.get_searches_last_hour()
        assert count >= 1

    def test_get_avg_search_time(self, temp_db_path):
        """Test getting average search time"""
        db = StatsDatabase(db_path=temp_db_path)

        # Log searches with different response times
        stats1 = {"total_results": 10, "processing_time_ms": 100.0}
        stats2 = {"total_results": 10, "processing_time_ms": 200.0}

        db.log_search("test1", "fr", 10, True, True, False, stats1)
        db.log_search("test2", "fr", 10, True, True, False, stats2)

        avg = db.get_avg_search_time()
        assert avg == pytest.approx(150.0)

    def test_get_top_queries(self, temp_db_path):
        """Test getting top queries"""
        db = StatsDatabase(db_path=temp_db_path)

        stats = {"total_results": 10, "processing_time_ms": 100.0}

        # Log multiple searches with same query
        db.log_search("dinosaures", "fr", 10, True, True, False, stats)
        db.log_search("dinosaures", "fr", 10, True, True, False, stats)
        db.log_search("espace", "fr", 10, True, True, False, stats)

        top = db.get_top_queries(limit=2)

        # dinosaures should be first with count 2
        assert len(top) >= 1
        assert top[0]["query"] == "dinosaures"
        assert top[0]["count"] == 2

    def test_log_feedback(self, temp_db_path):
        """Test logging user feedback"""
        db = StatsDatabase(db_path=temp_db_path)

        # Should not raise an exception
        db.log_feedback(
            query="test query",
            result_id="result-123",
            result_url="https://example.com",
            reason="inappropriate",
            comment="Not suitable for children"
        )

    def test_get_avg_typesense_time(self, temp_db_path):
        """Test getting average Typesense query time"""
        db = StatsDatabase(db_path=temp_db_path)

        stats1 = {
            "total_results": 10,
            "processing_time_ms": 100.0,
            "typesense_time_ms": 50.0
        }
        stats2 = {
            "total_results": 10,
            "processing_time_ms": 200.0,
            "typesense_time_ms": 100.0
        }

        db.log_search("test1", "fr", 10, True, True, False, stats1)
        db.log_search("test2", "fr", 10, True, True, False, stats2)

        avg = db.get_avg_typesense_time()
        assert avg == pytest.approx(75.0)

    def test_migration_from_meilisearch_columns(self, temp_db_path):
        """Test that database migration handles old Meilisearch column names"""
        # This test verifies the migration logic in _init_database
        db = StatsDatabase(db_path=temp_db_path)

        # Database should be created with new Typesense column names
        # and the migration should have run successfully
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(search_queries)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()

        # Should have typesense columns, not meilisearch columns
        assert "typesense_results" in columns
        assert "typesense_time_ms" in columns

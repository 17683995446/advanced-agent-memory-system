"""Unit tests for the session manager module."""
import pytest
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.core.session_context_manager import SessionManager, SessionContext


class TestSessionContext:
    def test_create_default(self):
        ctx = SessionContext()
        assert ctx.session_id is not None
        assert ctx.message_count == 0
        assert ctx.working_memory == []

    def test_age_seconds(self):
        ctx = SessionContext(created_at=time.time() - 100)
        assert ctx.age_seconds >= 100

    def test_add_message(self):
        ctx = SessionContext()
        ctx.add_message("user", "Hello")
        assert ctx.message_count == 1
        assert len(ctx.working_memory) == 1
        assert ctx.working_memory[0]["role"] == "user"

    def test_get_recent_messages(self):
        ctx = SessionContext()
        for i in range(10):
            ctx.add_message("user", f"msg {i}")
        recent = ctx.get_recent_messages(3)
        assert len(recent) == 3
        assert recent[0]["content"] == "msg 7"

    def test_variables(self):
        ctx = SessionContext()
        ctx.set_variable("theme", "dark")
        assert ctx.get_variable("theme") == "dark"
        assert ctx.get_variable("missing", "default") == "default"

    def test_to_dict(self):
        ctx = SessionContext(user_id="u1")
        ctx.add_message("user", "test")
        d = ctx.to_dict()
        assert d["user_id"] == "u1"
        assert d["message_count"] == 1

    def test_touch(self):
        ctx = SessionContext()
        old = ctx.last_active
        time.sleep(0.01)
        ctx.touch()
        assert ctx.last_active > old


class TestSessionManager:
    def setup_method(self):
        self.sm = SessionManager()

    def test_create_session(self):
        ctx = self.sm.create_session(user_id="u1")
        assert ctx.session_id is not None
        assert ctx.user_id == "u1"

    def test_create_with_custom_id(self):
        ctx = self.sm.create_session(session_id="custom-id")
        assert ctx.session_id == "custom-id"

    def test_get_session(self):
        ctx = self.sm.create_session()
        retrieved = self.sm.get_session(ctx.session_id)
        assert retrieved is not None
        assert retrieved.session_id == ctx.session_id

    def test_get_nonexistent_session(self):
        assert self.sm.get_session("nonexistent") is None

    def test_get_current_session(self):
        assert self.sm.get_current_session() is None
        ctx = self.sm.create_session()
        current = self.sm.get_current_session()
        assert current is not None
        assert current.session_id == ctx.session_id

    def test_switch_session(self):
        ctx1 = self.sm.create_session(user_id="u1")
        ctx2 = self.sm.create_session(user_id="u2")
        assert self.sm.get_current_session().session_id == ctx2.session_id
        self.sm.switch_session(ctx1.session_id)
        assert self.sm.get_current_session().session_id == ctx1.session_id

    def test_switch_nonexistent(self):
        assert self.sm.switch_session("nonexistent") is False

    def test_destroy_session(self):
        ctx = self.sm.create_session()
        result = self.sm.destroy_session(ctx.session_id)
        assert result is True
        assert self.sm.get_session(ctx.session_id) is None

    def test_destroy_nonexistent(self):
        assert self.sm.destroy_session("nonexistent") is False

    def test_destroy_current_clears(self):
        ctx = self.sm.create_session()
        self.sm.destroy_session(ctx.session_id)
        assert self.sm.get_current_session() is None

    def test_list_sessions(self):
        self.sm.create_session(user_id="u1")
        self.sm.create_session(user_id="u2")
        self.sm.create_session(user_id="u1")
        all_sessions = self.sm.list_sessions()
        assert len(all_sessions) == 3
        u1_sessions = self.sm.list_sessions(user_id="u1")
        assert len(u1_sessions) == 2

    def test_max_sessions_eviction(self):
        sm = SessionManager(max_sessions=3)
        s1 = sm.create_session()
        s2 = sm.create_session()
        s3 = sm.create_session()
        s4 = sm.create_session()  # Should evict s1
        assert sm.get_session(s1.session_id) is None
        assert sm.get_session(s4.session_id) is not None

    def test_session_timeout(self):
        sm = SessionManager(session_timeout=0.1)  # 100ms
        ctx = sm.create_session()
        time.sleep(0.15)
        assert sm.get_session(ctx.session_id) is None

    def test_cleanup_expired(self):
        sm = SessionManager(session_timeout=0.1)
        sm.create_session()
        time.sleep(0.15)
        sm.create_session()  # This one is still fresh
        cleaned = sm.cleanup_expired()
        assert cleaned == 1

    def test_get_stats(self):
        self.sm.create_session()
        stats = self.sm.get_stats()
        assert stats["total_sessions"] == 1
        assert stats["max_sessions"] == 1000

    def test_get_all_user_ids(self):
        self.sm.create_session(user_id="u1")
        self.sm.create_session(user_id="u2")
        self.sm.create_session(user_id="u1")
        user_ids = self.sm.get_all_user_ids()
        assert set(user_ids) == {"u1", "u2"}

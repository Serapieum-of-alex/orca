from __future__ import annotations
from orca.core.errors import ErrorPolicy, HumanInputRequired, OrcaError, ValidationError


class TestOrcaError:
    def test_orca_error_is_base_exception(self) -> None:
        """No inputs. Verifies that OrcaError subclasses Exception and can be caught as such."""
        try:
            raise OrcaError("boom")
        except Exception as e:
            assert isinstance(e, OrcaError)


class TestValidationError:
    def test_validation_error_is_subclass(self) -> None:
        """No inputs. Confirms ValidationError inherits from OrcaError for unified catching."""
        try:
            raise ValidationError("invalid graph")
        except OrcaError as e:
            assert isinstance(e, ValidationError)


class TestHumanInputRequired:
    def test_defaults_and_str(self) -> None:
        """Construct with run_id/gate_id only; expect default message and formatted __str__."""
        err = HumanInputRequired(run_id="r1", gate_id="g1")
        assert err.run_id == "r1"
        assert err.gate_id == "g1"
        assert err.message == "Human input required"
        s = str(err)
        assert "run_id=r1" in s and "gate_id=g1" in s and "Human input required" in s

    def test_custom_message(self) -> None:
        """Provide a custom message; ensure it's used and preserved in __str__."""
        err = HumanInputRequired(run_id="r1", gate_id="g1", message="Please approve")
        assert err.message == "Please approve"
        assert "Please approve" in str(err)

    def test_catch_as_base(self) -> None:
        """No inputs. Verify HumanInputRequired is catchable as OrcaError (subclass)."""
        try:
            raise HumanInputRequired("rid", "gid")
        except OrcaError as e:
            assert isinstance(e, HumanInputRequired)


class TestErrorPolicy:
    def test_defaults(self) -> None:
        """Construct with no args; verify default retry/backoff/jitter/flags are set."""
        ep = ErrorPolicy()
        assert ep.max_retries == 0
        assert ep.base_backoff_seconds == 0.5
        assert ep.max_backoff_seconds == 5.0
        assert ep.jitter == 0.1
        assert ep.fallback_node is None
        assert ep.escalate_to_human is False

    def test_custom_values(self) -> None:
        """Set all attributes; verify they are stored exactly as given."""
        ep = ErrorPolicy(max_retries=3, base_backoff_seconds=1.0, max_backoff_seconds=10.0, jitter=0.2, fallback_node="fb", escalate_to_human=True)
        assert (ep.max_retries, ep.base_backoff_seconds, ep.max_backoff_seconds, ep.jitter) == (3, 1.0, 10.0, 0.2)
        assert ep.fallback_node == "fb"
        assert ep.escalate_to_human is True

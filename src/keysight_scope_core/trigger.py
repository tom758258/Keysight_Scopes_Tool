"""Trigger controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import math
import time

from .capabilities import ScopeCapabilities
from .channel import validate_analog_channel
from .errors import ParameterValidationError, TriggerResponseError
from .scpi import SCPIClient


_SLOPE_COMMANDS = {
    "positive": "POSitive",
    "pos": "POSitive",
    "rising": "POSitive",
    "negative": "NEGative",
    "neg": "NEGative",
    "falling": "NEGative",
    "either": "EITHer",
    "eith": "EITHer",
    "alternate": "ALTernate",
    "alt": "ALTernate",
}

_SLOPE_READBACKS = {
    "POS": "positive",
    "POSITIVE": "positive",
    "NEG": "negative",
    "NEGATIVE": "negative",
    "EITH": "either",
    "EITHER": "either",
    "ALT": "alternate",
    "ALTERNATE": "alternate",
}

OPERATION_CONDITION_RUN_MASK = 1 << 3
OPERATION_CONDITION_RUI_ENAB_MASK = 1 << 4
OPERATION_CONDITION_WAIT_TRIG_MASK = 1 << 5


@dataclass(frozen=True)
class EdgeTriggerState:
    """Readback state for analog edge trigger settings."""

    source_channel: int
    level_volts: float
    slope: str


@dataclass(frozen=True)
class TriggerWaitConfig:
    """Controls for explicit triggered capture waiting."""

    timeout_ms: int
    poll_interval_ms: int = 100
    force_on_timeout: bool = False
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


@dataclass(frozen=True)
class TriggerWaitResult:
    """Structured result from a finite trigger wait."""

    outcome: str
    forced: bool
    timed_out: bool
    poll_count: int
    elapsed_ms: float
    condition_values: tuple[int, ...] = field(default_factory=tuple)
    raw_values: tuple[str, ...] = field(default_factory=tuple)
    capture_allowed: bool = False
    capture_block_reason: str | None = None
    error: str | None = None

    def to_json(self, config: TriggerWaitConfig) -> dict[str, object]:
        return {
            "wait_enabled": True,
            "arm_command": single_command(),
            "poll_source": "operation_condition",
            "poll_command": operation_condition_query(),
            "timeout_ms": config.timeout_ms,
            "poll_interval_ms": config.poll_interval_ms,
            "force_on_timeout": config.force_on_timeout,
            "force_command": force_trigger_command(),
            "outcome": self.outcome,
            "forced": self.forced,
            "timed_out": self.timed_out,
            "poll_count": self.poll_count,
            "elapsed_ms": self.elapsed_ms,
            "condition_values": list(self.condition_values),
            "raw_values": list(self.raw_values),
            "capture_allowed": self.capture_allowed,
            "capture_block_reason": self.capture_block_reason,
            "error": self.error,
        }


class EdgeTriggerController:
    """Controls for analog edge trigger settings."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def configure(self, source_channel: int, level_volts: float, slope: str) -> None:
        """Configure analog edge trigger source, level, and slope."""

        source_channel = validate_analog_channel(source_channel, self.capabilities)
        level_volts = validate_trigger_level(level_volts)
        slope_command = normalize_edge_slope(slope)
        self.scpi.write(trigger_mode_edge_command())
        self.scpi.write(edge_trigger_source_command(source_channel))
        self.scpi.write(edge_trigger_level_command(level_volts))
        self.scpi.write(edge_trigger_slope_command(slope_command))

    def query(self) -> EdgeTriggerState:
        """Query analog edge trigger source, level, and slope."""

        source_channel = parse_edge_trigger_source(self.scpi.query(edge_trigger_source_query()))
        validate_analog_channel(source_channel, self.capabilities)
        level_volts = parse_trigger_float(self.scpi.query(edge_trigger_level_query()), "level")
        slope = parse_edge_slope(self.scpi.query(edge_trigger_slope_query()))
        return EdgeTriggerState(source_channel=source_channel, level_volts=level_volts, slope=slope)


def validate_trigger_level(level_volts: float) -> float:
    """Validate a trigger level before sending it to the instrument."""

    try:
        value = float(level_volts)
    except (TypeError, ValueError) as exc:
        raise ParameterValidationError("trigger level must be a number.") from exc
    if not math.isfinite(value):
        raise ParameterValidationError("trigger level must be a finite number.")
    return value


def normalize_edge_slope(slope: str) -> str:
    """Normalize a user-facing edge slope into a SCPI argument."""

    normalized = slope.strip().lower()
    try:
        return _SLOPE_COMMANDS[normalized]
    except KeyError as exc:
        raise ParameterValidationError(
            "edge trigger slope must be one of: positive, negative, either, alternate."
        ) from exc


def trigger_mode_edge_command() -> str:
    """Build the SCPI command that selects edge trigger mode."""

    return ":TRIGger:MODE EDGE"


def single_command() -> str:
    """Return the SCPI command that arms one single acquisition."""

    return ":SINGle"


def operation_condition_query() -> str:
    """Return the operation condition status query used by trigger waits."""

    return ":OPERegister:CONDition?"


def edge_trigger_source_command(channel: int) -> str:
    """Build the SCPI command for analog edge trigger source."""

    return f":TRIGger:EDGE:SOURce CHANnel{channel}"


def edge_trigger_source_query() -> str:
    """Build the SCPI query for edge trigger source."""

    return ":TRIGger:EDGE:SOURce?"


def edge_trigger_level_command(level_volts: float) -> str:
    """Build the SCPI command for edge trigger level."""

    return f":TRIGger:EDGE:LEVel {_format_scpi_float(level_volts)}"


def edge_trigger_level_query() -> str:
    """Build the SCPI query for edge trigger level."""

    return ":TRIGger:EDGE:LEVel?"


def edge_trigger_slope_command(slope_command: str) -> str:
    """Build the SCPI command for edge trigger slope."""

    return f":TRIGger:EDGE:SLOPe {slope_command}"


def edge_trigger_slope_query() -> str:
    """Build the SCPI query for edge trigger slope."""

    return ":TRIGger:EDGE:SLOPe?"


def parse_edge_trigger_source(raw: str) -> int:
    """Parse an edge trigger source readback into an analog channel number."""

    normalized = raw.strip().upper()
    if normalized.startswith("CHANNEL"):
        suffix = normalized.removeprefix("CHANNEL")
    elif normalized.startswith("CHAN"):
        suffix = normalized.removeprefix("CHAN")
    else:
        raise TriggerResponseError(f"Could not parse edge trigger source response: {raw!r}")

    try:
        channel = int(suffix)
    except ValueError as exc:
        raise TriggerResponseError(f"Could not parse edge trigger source response: {raw!r}") from exc
    if channel < 1:
        raise TriggerResponseError(f"Could not parse edge trigger source response: {raw!r}")
    return channel


def parse_edge_slope(raw: str) -> str:
    """Parse an edge trigger slope readback."""

    normalized = raw.strip().upper()
    try:
        return _SLOPE_READBACKS[normalized]
    except KeyError as exc:
        raise TriggerResponseError(f"Could not parse edge trigger slope response: {raw!r}") from exc


def parse_trigger_float(raw: str, setting_name: str) -> float:
    """Parse a numeric trigger query response."""

    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise TriggerResponseError(
            f"Could not parse trigger {setting_name} response: {raw!r}"
        ) from exc
    if not math.isfinite(value):
        raise TriggerResponseError(f"Could not parse trigger {setting_name} response: {raw!r}")
    return value


def _format_scpi_float(value: float) -> str:
    return f"{value:.12g}"


def force_trigger_command() -> str:
    """Return the SCPI command that forces one trigger event.

    The command is a state-changing write. High-level workflows must keep force
    behavior explicit and opt-in.
    """

    return ":TRIGger:FORCe"


def classify_operation_condition(value: int, *, profile: str = "live") -> str:
    """Classify one operation-condition value for trigger waiting.

    DSO-X 2000X/3000X/4000X and simulator waits use the Operation Status
    Condition Run bit: set means acquisition is still pending, clear means the
    wait completed. Other live profiles remain conservative until separately
    validated.
    """

    if profile in {"2000x", "3000x", "4000x", "simulator"}:
        if value & OPERATION_CONDITION_RUN_MASK:
            return "pending"
        return "complete"
    return "unknown"


def parse_operation_condition(raw: str) -> int:
    """Parse an operation-condition response into an integer value."""

    text = raw.strip()
    try:
        return int(text, 0)
    except ValueError:
        try:
            value = float(text)
        except ValueError as exc:
            raise TriggerResponseError(
                f"Could not parse operation condition response: {raw!r}"
            ) from exc
    if not math.isfinite(value) or not value.is_integer():
        raise TriggerResponseError(f"Could not parse operation condition response: {raw!r}")
    return int(value)


def validate_trigger_wait_config(config: TriggerWaitConfig) -> TriggerWaitConfig:
    """Validate finite trigger wait settings."""

    if config.timeout_ms < 1:
        raise ParameterValidationError("trigger timeout must be at least 1 ms.")
    if config.poll_interval_ms < 1:
        raise ParameterValidationError("trigger poll interval must be at least 1 ms.")
    if config.poll_interval_ms > config.timeout_ms:
        raise ParameterValidationError(
            "trigger poll interval must be less than or equal to trigger timeout."
        )
    return config


def wait_for_trigger_completion(
    scpi: SCPIClient,
    config: TriggerWaitConfig,
    *,
    classifier_profile: str = "live",
) -> TriggerWaitResult:
    """Arm a single acquisition and wait finitely for trigger completion."""

    config = validate_trigger_wait_config(config)
    raw_values: list[str] = []
    condition_values: list[int] = []
    start = config.clock()
    scpi.write(single_command())

    outcome, error = _poll_operation_condition(
        scpi,
        config,
        deadline=start + config.timeout_ms / 1000.0,
        raw_values=raw_values,
        condition_values=condition_values,
        classifier_profile=classifier_profile,
    )
    if outcome == "complete":
        return _trigger_wait_result(
            "natural", False, False, start, config, raw_values, condition_values
        )
    if outcome == "unknown":
        return _trigger_wait_result(
            "unknown", False, False, start, config, raw_values, condition_values, error=error
        )
    if not config.force_on_timeout:
        return _trigger_wait_result(
            "timeout", False, True, start, config, raw_values, condition_values
        )

    scpi.write(force_trigger_command())
    force_start = config.clock()
    outcome, error = _poll_operation_condition(
        scpi,
        config,
        deadline=force_start + config.timeout_ms / 1000.0,
        raw_values=raw_values,
        condition_values=condition_values,
        classifier_profile=classifier_profile,
    )
    if outcome == "complete":
        return _trigger_wait_result(
            "forced", True, False, start, config, raw_values, condition_values
        )
    if outcome == "unknown":
        return _trigger_wait_result(
            "unknown", True, False, start, config, raw_values, condition_values, error=error
        )
    return _trigger_wait_result(
        "timeout", True, True, start, config, raw_values, condition_values
    )


def _poll_operation_condition(
    scpi: SCPIClient,
    config: TriggerWaitConfig,
    *,
    deadline: float,
    raw_values: list[str],
    condition_values: list[int],
    classifier_profile: str,
) -> tuple[str, str | None]:
    while True:
        try:
            raw = scpi.query(operation_condition_query())
            value = parse_operation_condition(raw)
        except Exception as exc:
            return "unknown", str(exc)
        raw_values.append(raw)
        condition_values.append(value)
        classification = classify_operation_condition(value, profile=classifier_profile)
        if classification == "complete":
            return "complete", None
        if classification == "unknown":
            return "unknown", f"unclassified operation condition value: {value}"
        now = config.clock()
        if now >= deadline:
            return "timeout", None
        sleep_s = min(config.poll_interval_ms / 1000.0, max(0.0, deadline - now))
        if sleep_s > 0:
            config.sleep(sleep_s)


def _trigger_wait_result(
    outcome: str,
    forced: bool,
    timed_out: bool,
    start: float,
    config: TriggerWaitConfig,
    raw_values: list[str],
    condition_values: list[int],
    *,
    error: str | None = None,
) -> TriggerWaitResult:
    capture_allowed = outcome in {"natural", "forced"}
    block_reason = None if capture_allowed else outcome
    return TriggerWaitResult(
        outcome=outcome,
        forced=forced,
        timed_out=timed_out,
        poll_count=len(raw_values),
        elapsed_ms=max(0.0, (config.clock() - start) * 1000.0),
        condition_values=tuple(condition_values),
        raw_values=tuple(raw_values),
        capture_allowed=capture_allowed,
        capture_block_reason=block_reason,
        error=error,
    )

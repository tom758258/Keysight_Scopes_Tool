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

_GLITCH_POLARITY_COMMANDS = {
    "positive": "POSitive",
    "pos": "POSitive",
    "negative": "NEGative",
    "neg": "NEGative",
}

_GLITCH_POLARITY_READBACKS = {
    "POS": "positive",
    "POSITIVE": "positive",
    "NEG": "negative",
    "NEGATIVE": "negative",
}

_GLITCH_QUALIFIER_COMMANDS = {
    "greater-than": "GREaterthan",
    "greater_than": "GREaterthan",
    "greaterthan": "GREaterthan",
    "gre": "GREaterthan",
    "less-than": "LESSthan",
    "less_than": "LESSthan",
    "lessthan": "LESSthan",
    "less": "LESSthan",
    "range": "RANGe",
    "rang": "RANGe",
}

_GLITCH_QUALIFIER_READBACKS = {
    "GRE": "greater-than",
    "GREATERTHAN": "greater-than",
    "LESS": "less-than",
    "LESSTHAN": "less-than",
    "RANG": "range",
    "RANGE": "range",
}

_RUNT_POLARITY_COMMANDS = {
    "positive": "POSitive",
    "negative": "NEGative",
    "either": "EITHer",
}

_RUNT_POLARITY_READBACKS = {
    "POS": "positive",
    "POSITIVE": "positive",
    "NEG": "negative",
    "NEGATIVE": "negative",
    "EITH": "either",
    "EITHER": "either",
}

_RUNT_QUALIFIER_COMMANDS = {
    "greater-than": "GREaterthan",
    "less-than": "LESSthan",
    "none": "NONE",
}

_RUNT_QUALIFIER_READBACKS = {
    "GRE": "greater-than",
    "GREATERTHAN": "greater-than",
    "LESS": "less-than",
    "LESSTHAN": "less-than",
    "NONE": "none",
}

_TRANSITION_SLOPE_COMMANDS = {
    "positive": "POSitive",
    "negative": "NEGative",
}

_TRANSITION_SLOPE_READBACKS = {
    "POS": "positive",
    "POSITIVE": "positive",
    "NEG": "negative",
    "NEGATIVE": "negative",
}

_TRANSITION_QUALIFIER_COMMANDS = {
    "greater-than": "GREaterthan",
    "less-than": "LESSthan",
}

_TRANSITION_QUALIFIER_READBACKS = {
    "GRE": "greater-than",
    "GREATERTHAN": "greater-than",
    "LESS": "less-than",
    "LESSTHAN": "less-than",
}

_PATTERN_FORMAT_READBACKS = {
    "ASC": "ascii",
    "ASCII": "ascii",
    "HEX": "hex",
}

_PATTERN_QUALIFIER_READBACKS = {
    "ENT": "entered",
    "ENTERED": "entered",
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
class GlitchTriggerState:
    """Readback state for pulse-width trigger settings."""

    mode: str | None
    source: str
    source_kind: str | None
    channel: int | None
    digital: int | None
    polarity: str | None
    qualifier: str | None
    greater_than_seconds: float | None
    less_than_seconds: float | None
    range_min_seconds: float | None
    range_max_seconds: float | None
    level_volts: float | None
    raw: dict[str, str]

    def to_json(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "source": self.source,
            "source_kind": self.source_kind,
            "channel": self.channel,
            "digital": self.digital,
            "polarity": self.polarity,
            "qualifier": self.qualifier,
            "greater_than_seconds": self.greater_than_seconds,
            "less_than_seconds": self.less_than_seconds,
            "range_min_seconds": self.range_min_seconds,
            "range_max_seconds": self.range_max_seconds,
            "level_volts": self.level_volts,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class RuntTriggerState:
    """Readback state for runt trigger settings."""

    mode: str | None
    source: str
    source_kind: str | None
    channel: int | None
    polarity: str | None
    qualifier: str | None
    time_seconds: float | None
    low_level_volts: float | None
    high_level_volts: float | None
    raw: dict[str, str]

    def to_json(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "source": self.source,
            "source_kind": self.source_kind,
            "channel": self.channel,
            "polarity": self.polarity,
            "qualifier": self.qualifier,
            "time_seconds": self.time_seconds,
            "low_level_volts": self.low_level_volts,
            "high_level_volts": self.high_level_volts,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class TransitionTriggerState:
    """Readback state for transition trigger settings."""

    mode: str | None
    source: str
    source_kind: str | None
    channel: int | None
    slope: str | None
    qualifier: str | None
    time_seconds: float | None
    low_level_volts: float | None
    high_level_volts: float | None
    raw: dict[str, str]

    def to_json(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "source": self.source,
            "source_kind": self.source_kind,
            "channel": self.channel,
            "slope": self.slope,
            "qualifier": self.qualifier,
            "time_seconds": self.time_seconds,
            "low_level_volts": self.low_level_volts,
            "high_level_volts": self.high_level_volts,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class PatternTriggerState:
    """Readback state for pattern trigger settings."""

    mode: str | None
    format: str | None
    pattern: str | None
    qualifier: str | None
    edge_source_raw: str | None
    edge_raw: str | None
    raw_pattern_response: str | None
    raw: dict[str, str]

    def to_json(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "format": self.format,
            "pattern": self.pattern,
            "qualifier": self.qualifier,
            "edge_source_raw": self.edge_source_raw,
            "edge_raw": self.edge_raw,
            "raw_pattern_response": self.raw_pattern_response,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class OrTriggerState:
    """Readback state for DSO analog OR trigger settings."""

    mode: str | None
    raw_mode: str
    pattern: str | None
    raw_pattern: str
    raw: dict[str, str]

    def to_json(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "raw_mode": self.raw_mode,
            "pattern": self.pattern,
            "raw_pattern": self.raw_pattern,
            "raw": dict(self.raw),
        }


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


class GlitchTriggerController:
    """Controls for analog pulse-width trigger settings."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def configure(
        self,
        *,
        channel: int,
        polarity: str,
        qualifier: str,
        time_seconds: float | None = None,
        min_time_seconds: float | None = None,
        max_time_seconds: float | None = None,
        level_volts: float | None = None,
    ) -> None:
        """Configure analog-channel pulse-width trigger settings."""

        commands = glitch_trigger_configure_commands(
            channel=channel,
            polarity=polarity,
            qualifier=qualifier,
            capabilities=self.capabilities,
            time_seconds=time_seconds,
            min_time_seconds=min_time_seconds,
            max_time_seconds=max_time_seconds,
            level_volts=level_volts,
        )
        for command in commands:
            self.scpi.write(command)

    def query(self) -> GlitchTriggerState:
        """Query pulse-width trigger state without changing acquisition state."""

        raw = {
            "mode": self.scpi.query(trigger_mode_query()),
            "source": self.scpi.query(glitch_trigger_source_query()),
            "polarity": self.scpi.query(glitch_trigger_polarity_query()),
            "qualifier": self.scpi.query(glitch_trigger_qualifier_query()),
            "greater_than": self.scpi.query(glitch_trigger_greater_than_query()),
            "less_than": self.scpi.query(glitch_trigger_less_than_query()),
            "range": self.scpi.query(glitch_trigger_range_query()),
            "level": self.scpi.query(glitch_trigger_level_query()),
        }
        source_kind, channel, digital = parse_glitch_source(raw["source"])
        range_min, range_max = parse_glitch_range(raw["range"])
        return GlitchTriggerState(
            mode=parse_trigger_mode(raw["mode"]),
            source=raw["source"].strip(),
            source_kind=source_kind,
            channel=channel,
            digital=digital,
            polarity=parse_glitch_polarity_readback(raw["polarity"]),
            qualifier=parse_glitch_qualifier_readback(raw["qualifier"]),
            greater_than_seconds=parse_optional_trigger_float(
                raw["greater_than"], "glitch greater-than"
            ),
            less_than_seconds=parse_optional_trigger_float(raw["less_than"], "glitch less-than"),
            range_min_seconds=range_min,
            range_max_seconds=range_max,
            level_volts=parse_glitch_level(raw["level"]),
            raw=raw,
        )


class RuntTriggerController:
    """Controls for analog runt trigger settings."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def configure(
        self,
        *,
        channel: int,
        polarity: str,
        qualifier: str,
        low_level_volts: float,
        high_level_volts: float,
        time_seconds: float | None = None,
    ) -> None:
        """Configure analog-channel runt trigger settings."""

        commands = runt_trigger_configure_commands(
            channel=channel,
            polarity=polarity,
            qualifier=qualifier,
            low_level_volts=low_level_volts,
            high_level_volts=high_level_volts,
            capabilities=self.capabilities,
            time_seconds=time_seconds,
        )
        for command in commands:
            self.scpi.write(command)

    def query(self) -> RuntTriggerState:
        """Query runt trigger state without changing acquisition state."""

        raw = {
            "mode": self.scpi.query(trigger_mode_query()),
            "source": self.scpi.query(runt_trigger_source_query()),
            "polarity": self.scpi.query(runt_trigger_polarity_query()),
            "qualifier": self.scpi.query(runt_trigger_qualifier_query()),
            "time": self.scpi.query(runt_trigger_time_query()),
        }
        source_kind, channel = parse_runt_source(raw["source"])
        low_level = None
        high_level = None
        if channel is not None:
            raw["low_level"] = self.scpi.query(runt_trigger_low_level_query(channel))
            raw["high_level"] = self.scpi.query(runt_trigger_high_level_query(channel))
            low_level = parse_trigger_float(raw["low_level"], "runt low level")
            high_level = parse_trigger_float(raw["high_level"], "runt high level")
        return RuntTriggerState(
            mode=parse_trigger_mode(raw["mode"]),
            source=raw["source"].strip(),
            source_kind=source_kind,
            channel=channel,
            polarity=parse_runt_polarity_readback(raw["polarity"]),
            qualifier=parse_runt_qualifier_readback(raw["qualifier"]),
            time_seconds=parse_optional_trigger_float(raw["time"], "runt time"),
            low_level_volts=low_level,
            high_level_volts=high_level,
            raw=raw,
        )


class TransitionTriggerController:
    """Controls for analog transition trigger settings."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def configure(
        self,
        *,
        channel: int,
        slope: str,
        qualifier: str,
        low_level_volts: float,
        high_level_volts: float,
        time_seconds: float,
    ) -> None:
        """Configure analog-channel transition trigger settings."""

        commands = transition_trigger_configure_commands(
            channel=channel,
            slope=slope,
            qualifier=qualifier,
            low_level_volts=low_level_volts,
            high_level_volts=high_level_volts,
            capabilities=self.capabilities,
            time_seconds=time_seconds,
        )
        for command in commands:
            self.scpi.write(command)

    def query(self) -> TransitionTriggerState:
        """Query transition trigger state without changing acquisition state."""

        raw = {
            "mode": self.scpi.query(trigger_mode_query()),
            "source": self.scpi.query(transition_trigger_source_query()),
            "slope": self.scpi.query(transition_trigger_slope_query()),
            "qualifier": self.scpi.query(transition_trigger_qualifier_query()),
            "time": self.scpi.query(transition_trigger_time_query()),
        }
        source_kind, channel = parse_transition_source(raw["source"])
        low_level = None
        high_level = None
        if channel is not None:
            raw["low_level"] = self.scpi.query(trigger_low_level_query(channel))
            raw["high_level"] = self.scpi.query(trigger_high_level_query(channel))
            low_level = parse_trigger_float(raw["low_level"], "transition low level")
            high_level = parse_trigger_float(raw["high_level"], "transition high level")
        return TransitionTriggerState(
            mode=parse_trigger_mode(raw["mode"]),
            source=raw["source"].strip(),
            source_kind=source_kind,
            channel=channel,
            slope=parse_transition_slope_readback(raw["slope"]),
            qualifier=parse_transition_qualifier_readback(raw["qualifier"]),
            time_seconds=parse_optional_trigger_float(raw["time"], "transition time"),
            low_level_volts=low_level,
            high_level_volts=high_level,
            raw=raw,
        )


class PatternTriggerController:
    """Controls for DSO ASCII pattern trigger settings."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def configure(self, pattern: str) -> PatternTriggerState:
        """Configure DSO ASCII entered-pattern trigger settings."""

        commands = pattern_trigger_configure_commands(
            pattern=pattern,
            capabilities=self.capabilities,
        )
        for command in commands:
            self.scpi.write(command)
        normalized = validate_pattern_trigger_pattern(pattern, self.capabilities)
        return PatternTriggerState(
            mode="pattern",
            format="ascii",
            pattern=normalized,
            qualifier="entered",
            edge_source_raw=None,
            edge_raw=None,
            raw_pattern_response=None,
            raw={
                "mode": "PATTern",
                "format": "ASCii",
                "pattern": normalized,
                "qualifier": "ENTered",
            },
        )

    def query(self) -> PatternTriggerState:
        """Query pattern trigger state without changing acquisition state."""

        raw = {
            "mode": self.scpi.query(trigger_mode_query()),
            "format": self.scpi.query(pattern_trigger_format_query()),
            "pattern": self.scpi.query(pattern_trigger_pattern_query()),
            "qualifier": self.scpi.query(pattern_trigger_qualifier_query()),
        }
        pattern, edge_source, edge = parse_pattern_trigger_response(raw["pattern"])
        return PatternTriggerState(
            mode=parse_trigger_mode(raw["mode"]),
            format=parse_pattern_format_readback(raw["format"]),
            pattern=pattern,
            qualifier=parse_pattern_qualifier_readback(raw["qualifier"]),
            edge_source_raw=edge_source,
            edge_raw=edge,
            raw_pattern_response=raw["pattern"],
            raw=raw,
        )


class OrTriggerController:
    """Controls for DSO analog OR trigger settings."""

    def __init__(self, scpi: SCPIClient, capabilities: ScopeCapabilities) -> None:
        self.scpi = scpi
        self.capabilities = capabilities

    def configure(self, pattern: str) -> OrTriggerState:
        """Configure DSO analog OR trigger settings."""

        commands = or_trigger_configure_commands(
            pattern=pattern,
            capabilities=self.capabilities,
        )
        for command in commands:
            self.scpi.write(command)
        normalized = validate_or_trigger_pattern(pattern, self.capabilities)
        return OrTriggerState(
            mode="or",
            raw_mode="OR",
            pattern=normalized,
            raw_pattern=normalized,
            raw={"mode": "OR", "pattern": normalized},
        )

    def query(self) -> OrTriggerState:
        """Query OR trigger state without changing acquisition state."""

        raw = {
            "mode": self.scpi.query(trigger_mode_query()),
            "pattern": self.scpi.query(or_trigger_pattern_query()),
        }
        return OrTriggerState(
            mode=parse_trigger_mode(raw["mode"]),
            raw_mode=raw["mode"],
            pattern=parse_or_trigger_pattern_response(raw["pattern"]),
            raw_pattern=raw["pattern"],
            raw=raw,
        )


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


def normalize_glitch_polarity(polarity: str) -> str:
    """Normalize a user-facing glitch polarity into a SCPI argument."""

    normalized = polarity.strip().lower()
    try:
        return _GLITCH_POLARITY_COMMANDS[normalized]
    except KeyError as exc:
        raise ParameterValidationError(
            "pulse-width trigger polarity must be one of: positive, negative."
        ) from exc


def normalize_glitch_qualifier(qualifier: str) -> str:
    """Normalize a user-facing glitch qualifier into a SCPI argument."""

    normalized = qualifier.strip().lower()
    try:
        return _GLITCH_QUALIFIER_COMMANDS[normalized]
    except KeyError as exc:
        raise ParameterValidationError(
            "pulse-width trigger qualifier must be one of: greater-than, less-than, range."
        ) from exc


def normalize_runt_polarity(polarity: str) -> str:
    """Normalize a user-facing runt polarity into a SCPI argument."""

    normalized = polarity.strip().lower()
    try:
        return _RUNT_POLARITY_COMMANDS[normalized]
    except KeyError as exc:
        raise ParameterValidationError(
            "runt trigger polarity must be one of: positive, negative, either."
        ) from exc


def normalize_runt_qualifier(qualifier: str) -> str:
    """Normalize a user-facing runt qualifier into a SCPI argument."""

    normalized = qualifier.strip().lower()
    try:
        return _RUNT_QUALIFIER_COMMANDS[normalized]
    except KeyError as exc:
        raise ParameterValidationError(
            "runt trigger qualifier must be one of: greater-than, less-than, none."
        ) from exc


def normalize_transition_slope(slope: str) -> str:
    """Normalize a user-facing transition slope into a SCPI argument."""

    normalized = slope.strip().lower()
    try:
        return _TRANSITION_SLOPE_COMMANDS[normalized]
    except KeyError as exc:
        raise ParameterValidationError(
            "transition trigger slope must be one of: positive, negative."
        ) from exc


def normalize_transition_qualifier(qualifier: str) -> str:
    """Normalize a user-facing transition qualifier into a SCPI argument."""

    normalized = qualifier.strip().lower()
    try:
        return _TRANSITION_QUALIFIER_COMMANDS[normalized]
    except KeyError as exc:
        raise ParameterValidationError(
            "transition trigger qualifier must be one of: greater-than, less-than."
        ) from exc


def trigger_mode_edge_command() -> str:
    """Build the SCPI command that selects edge trigger mode."""

    return ":TRIGger:MODE EDGE"


def trigger_mode_glitch_command() -> str:
    """Build the SCPI command that selects glitch trigger mode."""

    return ":TRIGger:MODE GLITch"


def trigger_mode_runt_command() -> str:
    """Build the SCPI command that selects runt trigger mode."""

    return ":TRIGger:MODE RUNT"


def trigger_mode_transition_command() -> str:
    """Build the SCPI command that selects transition trigger mode."""

    return ":TRIGger:MODE TRANsition"


def trigger_mode_pattern_command() -> str:
    """Build the SCPI command that selects pattern trigger mode."""

    return ":TRIGger:MODE PATTern"


def trigger_mode_or_command() -> str:
    """Build the SCPI command that selects OR trigger mode."""

    return ":TRIGger:MODE OR"


def trigger_mode_query() -> str:
    """Build the SCPI query for trigger mode."""

    return ":TRIGger:MODE?"


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


def glitch_trigger_source_command(channel: int) -> str:
    """Build the SCPI command for analog GLITch source."""

    return f":TRIGger:GLITch:SOURce CHANnel{channel}"


def glitch_trigger_source_query() -> str:
    """Build the SCPI query for GLITch source."""

    return ":TRIGger:GLITch:SOURce?"


def glitch_trigger_level_command(level_volts: float, channel: int) -> str:
    """Build the SCPI command for analog glitch trigger level."""

    return f":TRIGger:GLITch:LEVel {_format_scpi_float(level_volts)},CHANnel{channel}"


def glitch_trigger_level_query() -> str:
    """Build the SCPI query for glitch trigger level."""

    return ":TRIGger:GLITch:LEVel?"


def glitch_trigger_polarity_command(polarity_command: str) -> str:
    """Build the SCPI command for glitch trigger polarity."""

    return f":TRIGger:GLITch:POLarity {polarity_command}"


def glitch_trigger_polarity_query() -> str:
    """Build the SCPI query for glitch trigger polarity."""

    return ":TRIGger:GLITch:POLarity?"


def glitch_trigger_qualifier_command(qualifier_command: str) -> str:
    """Build the SCPI command for glitch trigger qualifier."""

    return f":TRIGger:GLITch:QUALifier {qualifier_command}"


def glitch_trigger_qualifier_query() -> str:
    """Build the SCPI query for glitch trigger qualifier."""

    return ":TRIGger:GLITch:QUALifier?"


def glitch_trigger_greater_than_command(time_seconds: float) -> str:
    """Build the SCPI command for glitch greater-than timing."""

    return f":TRIGger:GLITch:GREaterthan {_format_scpi_float(time_seconds)}"


def glitch_trigger_greater_than_query() -> str:
    """Build the SCPI query for glitch greater-than timing."""

    return ":TRIGger:GLITch:GREaterthan?"


def glitch_trigger_less_than_command(time_seconds: float) -> str:
    """Build the SCPI command for glitch less-than timing."""

    return f":TRIGger:GLITch:LESSthan {_format_scpi_float(time_seconds)}"


def glitch_trigger_less_than_query() -> str:
    """Build the SCPI query for glitch less-than timing."""

    return ":TRIGger:GLITch:LESSthan?"


def glitch_trigger_range_command(max_time_seconds: float, min_time_seconds: float) -> str:
    """Build the SCPI command for glitch range timing."""

    return (
        ":TRIGger:GLITch:RANGe "
        f"{_format_scpi_float(max_time_seconds)},{_format_scpi_float(min_time_seconds)}"
    )


def glitch_trigger_range_query() -> str:
    """Build the SCPI query for glitch range timing."""

    return ":TRIGger:GLITch:RANGe?"


def glitch_trigger_query_commands() -> list[str]:
    """Return the glitch trigger query SCPI sequence."""

    return [
        trigger_mode_query(),
        glitch_trigger_source_query(),
        glitch_trigger_polarity_query(),
        glitch_trigger_qualifier_query(),
        glitch_trigger_greater_than_query(),
        glitch_trigger_less_than_query(),
        glitch_trigger_range_query(),
        glitch_trigger_level_query(),
    ]


def glitch_trigger_configure_commands(
    *,
    channel: int,
    polarity: str,
    qualifier: str,
    capabilities: ScopeCapabilities,
    time_seconds: float | None = None,
    min_time_seconds: float | None = None,
    max_time_seconds: float | None = None,
    level_volts: float | None = None,
) -> list[str]:
    """Return the analog glitch trigger configure SCPI sequence."""

    channel = validate_analog_channel(channel, capabilities)
    polarity_command = normalize_glitch_polarity(polarity)
    qualifier_command = normalize_glitch_qualifier(qualifier)
    level = validate_trigger_level(level_volts) if level_volts is not None else None

    commands = [
        trigger_mode_glitch_command(),
        glitch_trigger_source_command(channel),
    ]
    if level is not None:
        commands.append(glitch_trigger_level_command(level, channel))
    commands.append(glitch_trigger_polarity_command(polarity_command))

    if qualifier_command == "GREaterthan":
        if time_seconds is None:
            raise ParameterValidationError(
                "pulse-width trigger greater-than requires time_seconds."
            )
        if min_time_seconds is not None or max_time_seconds is not None:
            raise ParameterValidationError(
                "pulse-width trigger greater-than does not accept range timing."
            )
        commands.append(glitch_trigger_greater_than_command(validate_trigger_time(time_seconds)))
    elif qualifier_command == "LESSthan":
        if time_seconds is None:
            raise ParameterValidationError("pulse-width trigger less-than requires time_seconds.")
        if min_time_seconds is not None or max_time_seconds is not None:
            raise ParameterValidationError("pulse-width trigger less-than does not accept range timing.")
        commands.append(glitch_trigger_less_than_command(validate_trigger_time(time_seconds)))
    else:
        if time_seconds is not None:
            raise ParameterValidationError("pulse-width trigger range does not accept time_seconds.")
        if min_time_seconds is None or max_time_seconds is None:
            raise ParameterValidationError(
                "pulse-width trigger range requires min_time_seconds and max_time_seconds."
            )
        min_time = validate_trigger_time(min_time_seconds)
        max_time = validate_trigger_time(max_time_seconds)
        if min_time >= max_time:
            raise ParameterValidationError(
                "pulse-width trigger min_time_seconds must be less than max_time_seconds."
            )
        commands.append(glitch_trigger_range_command(max_time, min_time))

    commands.append(glitch_trigger_qualifier_command(qualifier_command))
    return commands


def runt_trigger_source_command(channel: int) -> str:
    """Build the SCPI command for analog RUNT source."""

    return f":TRIGger:RUNT:SOURce CHANnel{channel}"


def runt_trigger_source_query() -> str:
    """Build the SCPI query for RUNT source."""

    return ":TRIGger:RUNT:SOURce?"


def trigger_low_level_command(level_volts: float, channel: int) -> str:
    """Build the SCPI command for analog trigger low threshold."""

    return f":TRIGger:LEVel:LOW {_format_scpi_float(level_volts)},CHANnel{channel}"


def trigger_low_level_query(channel: int) -> str:
    """Build the SCPI query for analog trigger low threshold."""

    return f":TRIGger:LEVel:LOW? CHANnel{channel}"


def trigger_high_level_command(level_volts: float, channel: int) -> str:
    """Build the SCPI command for analog trigger high threshold."""

    return f":TRIGger:LEVel:HIGH {_format_scpi_float(level_volts)},CHANnel{channel}"


def trigger_high_level_query(channel: int) -> str:
    """Build the SCPI query for analog trigger high threshold."""

    return f":TRIGger:LEVel:HIGH? CHANnel{channel}"


def runt_trigger_low_level_command(level_volts: float, channel: int) -> str:
    """Build the SCPI command for analog runt low level."""

    return trigger_low_level_command(level_volts, channel)


def runt_trigger_low_level_query(channel: int) -> str:
    """Build the SCPI query for analog runt low level."""

    return trigger_low_level_query(channel)


def runt_trigger_high_level_command(level_volts: float, channel: int) -> str:
    """Build the SCPI command for analog runt high level."""

    return trigger_high_level_command(level_volts, channel)


def runt_trigger_high_level_query(channel: int) -> str:
    """Build the SCPI query for analog runt high level."""

    return trigger_high_level_query(channel)


def runt_trigger_polarity_command(polarity_command: str) -> str:
    """Build the SCPI command for runt trigger polarity."""

    return f":TRIGger:RUNT:POLarity {polarity_command}"


def runt_trigger_polarity_query() -> str:
    """Build the SCPI query for runt trigger polarity."""

    return ":TRIGger:RUNT:POLarity?"


def runt_trigger_time_command(time_seconds: float) -> str:
    """Build the SCPI command for runt timing."""

    return f":TRIGger:RUNT:TIME {_format_scpi_float(time_seconds)}"


def runt_trigger_time_query() -> str:
    """Build the SCPI query for runt timing."""

    return ":TRIGger:RUNT:TIME?"


def runt_trigger_qualifier_command(qualifier_command: str) -> str:
    """Build the SCPI command for runt trigger qualifier."""

    return f":TRIGger:RUNT:QUALifier {qualifier_command}"


def runt_trigger_qualifier_query() -> str:
    """Build the SCPI query for runt trigger qualifier."""

    return ":TRIGger:RUNT:QUALifier?"


def runt_trigger_query_commands() -> list[str]:
    """Return the unconditional runt trigger query SCPI sequence."""

    return [
        trigger_mode_query(),
        runt_trigger_source_query(),
        runt_trigger_polarity_query(),
        runt_trigger_qualifier_query(),
        runt_trigger_time_query(),
    ]


def runt_trigger_configure_commands(
    *,
    channel: int,
    polarity: str,
    qualifier: str,
    low_level_volts: float,
    high_level_volts: float,
    capabilities: ScopeCapabilities,
    time_seconds: float | None = None,
) -> list[str]:
    """Return the analog runt trigger configure SCPI sequence."""

    channel = validate_analog_channel(channel, capabilities)
    polarity_command = normalize_runt_polarity(polarity)
    qualifier_command = normalize_runt_qualifier(qualifier)
    low_level = validate_trigger_level(low_level_volts)
    high_level = validate_trigger_level(high_level_volts)
    if low_level >= high_level:
        raise ParameterValidationError(
            "runt trigger low_level_volts must be less than high_level_volts."
        )

    commands = [
        trigger_mode_runt_command(),
        runt_trigger_source_command(channel),
        runt_trigger_low_level_command(low_level, channel),
        runt_trigger_high_level_command(high_level, channel),
        runt_trigger_polarity_command(polarity_command),
    ]

    if qualifier_command in {"GREaterthan", "LESSthan"}:
        if time_seconds is None:
            raise ParameterValidationError(
                "runt trigger greater-than and less-than require time_seconds."
            )
        commands.append(runt_trigger_time_command(validate_trigger_time(time_seconds)))
    elif time_seconds is not None:
        raise ParameterValidationError("runt trigger qualifier none rejects time_seconds.")

    commands.append(runt_trigger_qualifier_command(qualifier_command))
    return commands


def transition_trigger_source_command(channel: int) -> str:
    """Build the SCPI command for analog TRANsition source."""

    return f":TRIGger:TRANsition:SOURce CHANnel{channel}"


def transition_trigger_source_query() -> str:
    """Build the SCPI query for TRANsition source."""

    return ":TRIGger:TRANsition:SOURce?"


def transition_trigger_slope_command(slope_command: str) -> str:
    """Build the SCPI command for transition trigger slope."""

    return f":TRIGger:TRANsition:SLOPe {slope_command}"


def transition_trigger_slope_query() -> str:
    """Build the SCPI query for transition trigger slope."""

    return ":TRIGger:TRANsition:SLOPe?"


def transition_trigger_time_command(time_seconds: float) -> str:
    """Build the SCPI command for transition timing."""

    return f":TRIGger:TRANsition:TIME {_format_scpi_float(time_seconds)}"


def transition_trigger_time_query() -> str:
    """Build the SCPI query for transition timing."""

    return ":TRIGger:TRANsition:TIME?"


def transition_trigger_qualifier_command(qualifier_command: str) -> str:
    """Build the SCPI command for transition trigger qualifier."""

    return f":TRIGger:TRANsition:QUALifier {qualifier_command}"


def transition_trigger_qualifier_query() -> str:
    """Build the SCPI query for transition trigger qualifier."""

    return ":TRIGger:TRANsition:QUALifier?"


def transition_trigger_query_commands() -> list[str]:
    """Return the unconditional transition trigger query SCPI sequence."""

    return [
        trigger_mode_query(),
        transition_trigger_source_query(),
        transition_trigger_slope_query(),
        transition_trigger_qualifier_query(),
        transition_trigger_time_query(),
    ]


def transition_trigger_configure_commands(
    *,
    channel: int,
    slope: str,
    qualifier: str,
    low_level_volts: float,
    high_level_volts: float,
    capabilities: ScopeCapabilities,
    time_seconds: float,
) -> list[str]:
    """Return the analog transition trigger configure SCPI sequence."""

    channel = validate_analog_channel(channel, capabilities)
    slope_command = normalize_transition_slope(slope)
    qualifier_command = normalize_transition_qualifier(qualifier)
    low_level = validate_trigger_level(low_level_volts)
    high_level = validate_trigger_level(high_level_volts)
    trigger_time = validate_trigger_time(time_seconds)
    if low_level >= high_level:
        raise ParameterValidationError(
            "transition trigger low_level_volts must be less than high_level_volts."
        )

    return [
        trigger_mode_transition_command(),
        transition_trigger_source_command(channel),
        trigger_low_level_command(low_level, channel),
        trigger_high_level_command(high_level, channel),
        transition_trigger_slope_command(slope_command),
        transition_trigger_time_command(trigger_time),
        transition_trigger_qualifier_command(qualifier_command),
    ]


def pattern_trigger_format_command() -> str:
    """Build the SCPI command for ASCII pattern format."""

    return ":TRIGger:PATTern:FORMat ASCii"


def pattern_trigger_format_query() -> str:
    """Build the SCPI query for pattern format."""

    return ":TRIGger:PATTern:FORMat?"


def pattern_trigger_pattern_command(pattern: str) -> str:
    """Build the SCPI command for the raw ASCII pattern string."""

    return f':TRIGger:PATTern "{pattern}"'


def pattern_trigger_pattern_query() -> str:
    """Build the SCPI query for pattern state."""

    return ":TRIGger:PATTern?"


def pattern_trigger_qualifier_command() -> str:
    """Build the SCPI command for entered pattern qualifier."""

    return ":TRIGger:PATTern:QUALifier ENTered"


def pattern_trigger_qualifier_query() -> str:
    """Build the SCPI query for pattern qualifier."""

    return ":TRIGger:PATTern:QUALifier?"


def pattern_trigger_query_commands() -> list[str]:
    """Return the pattern trigger query SCPI sequence."""

    return [
        trigger_mode_query(),
        pattern_trigger_format_query(),
        pattern_trigger_pattern_query(),
        pattern_trigger_qualifier_query(),
    ]


def pattern_trigger_configure_commands(
    *,
    pattern: str,
    capabilities: ScopeCapabilities,
) -> list[str]:
    """Return the DSO ASCII pattern trigger configure SCPI sequence."""

    normalized = validate_pattern_trigger_pattern(pattern, capabilities)
    return [
        trigger_mode_pattern_command(),
        pattern_trigger_format_command(),
        pattern_trigger_pattern_command(normalized),
        pattern_trigger_qualifier_command(),
    ]


def validate_pattern_trigger_pattern(pattern: str, capabilities: ScopeCapabilities) -> str:
    """Validate and normalize a v1 DSO ASCII pattern string."""

    if not isinstance(pattern, str):
        raise ParameterValidationError("pattern trigger pattern must be a string.")
    if pattern.lower().startswith("0x"):
        raise ParameterValidationError("pattern trigger pattern does not accept hex strings.")
    normalized = pattern.upper()
    if not normalized:
        raise ParameterValidationError("pattern trigger pattern must not be empty.")
    if any(char not in {"0", "1", "X"} for char in normalized):
        raise ParameterValidationError("pattern trigger pattern may contain only 0, 1, and X.")
    if len(normalized) != capabilities.analog_channels:
        raise ParameterValidationError(
            "pattern trigger pattern length must match the model analog channel count "
            f"({capabilities.analog_channels})."
        )
    return normalized


def or_trigger_pattern_command(pattern: str) -> str:
    """Build the SCPI command for the raw OR trigger edge mask."""

    return f':TRIGger:OR "{pattern}"'


def or_trigger_pattern_query() -> str:
    """Build the SCPI query for OR trigger state."""

    return ":TRIGger:OR?"


def or_trigger_query_commands() -> list[str]:
    """Return the OR trigger query SCPI sequence."""

    return [
        trigger_mode_query(),
        or_trigger_pattern_query(),
    ]


def or_trigger_configure_commands(
    *,
    pattern: str,
    capabilities: ScopeCapabilities,
) -> list[str]:
    """Return the DSO analog OR trigger configure SCPI sequence."""

    normalized = validate_or_trigger_pattern(pattern, capabilities)
    return [
        trigger_mode_or_command(),
        or_trigger_pattern_command(normalized),
    ]


def validate_or_trigger_pattern(pattern: str, capabilities: ScopeCapabilities) -> str:
    """Validate and normalize a v1 DSO analog OR trigger edge mask."""

    if not isinstance(pattern, str):
        raise ParameterValidationError("OR trigger pattern must be a string.")
    if pattern.lower().startswith("0x"):
        raise ParameterValidationError("OR trigger pattern does not accept hex strings.")
    normalized = pattern.upper()
    if not normalized:
        raise ParameterValidationError("OR trigger pattern must not be empty.")
    if any(char not in {"R", "F", "E", "X"} for char in normalized):
        raise ParameterValidationError("OR trigger pattern may contain only R, F, E, and X.")
    if len(normalized) != capabilities.analog_channels:
        raise ParameterValidationError(
            "OR trigger pattern length must match the model analog channel count "
            f"({capabilities.analog_channels})."
        )
    return normalized


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


def parse_trigger_mode(raw: str) -> str | None:
    """Parse a trigger mode readback when recognized."""

    normalized = raw.strip().upper()
    if normalized in {"GLIT", "GLITCH"}:
        return "glitch"
    if normalized in {"RUNT"}:
        return "runt"
    if normalized in {"TRAN", "TRANSITION"}:
        return "transition"
    if normalized in {"PATT", "PATTERN"}:
        return "pattern"
    if normalized in {"OR"}:
        return "or"
    if normalized in {"EDGE"}:
        return "edge"
    return None


def parse_glitch_source(raw: str) -> tuple[str | None, int | None, int | None]:
    """Parse a glitch source readback without assuming analog-only state."""

    normalized = raw.strip().upper()
    if normalized in {"", "NONE"}:
        return "none", None, None
    if normalized.startswith("CHANNEL"):
        suffix = normalized.removeprefix("CHANNEL")
        return _parse_channel_source(suffix), _parse_channel_suffix(suffix), None
    if normalized.startswith("CHAN"):
        suffix = normalized.removeprefix("CHAN")
        return _parse_channel_source(suffix), _parse_channel_suffix(suffix), None
    if normalized.startswith("DIGITAL"):
        suffix = normalized.removeprefix("DIGITAL")
        return _parse_digital_source(suffix), None, _parse_digital_suffix(suffix)
    if normalized.startswith("DIG"):
        suffix = normalized.removeprefix("DIG")
        return _parse_digital_source(suffix), None, _parse_digital_suffix(suffix)
    if normalized.startswith("EXT"):
        return "external", None, None
    return None, None, None


def parse_glitch_polarity_readback(raw: str) -> str | None:
    """Parse a glitch polarity readback when recognized."""

    return _GLITCH_POLARITY_READBACKS.get(raw.strip().upper())


def parse_glitch_qualifier_readback(raw: str) -> str | None:
    """Parse a glitch qualifier readback when recognized."""

    return _GLITCH_QUALIFIER_READBACKS.get(raw.strip().upper())


def parse_runt_source(raw: str) -> tuple[str | None, int | None]:
    """Parse a runt source readback, preserving unsafe non-analog sources."""

    normalized = raw.strip().upper()
    if normalized.startswith("CHANNEL"):
        suffix = normalized.removeprefix("CHANNEL")
        return _parse_channel_source(suffix), _parse_channel_suffix(suffix)
    if normalized.startswith("CHAN"):
        suffix = normalized.removeprefix("CHAN")
        return _parse_channel_source(suffix), _parse_channel_suffix(suffix)
    return None, None


def parse_runt_polarity_readback(raw: str) -> str | None:
    """Parse a runt polarity readback when recognized."""

    return _RUNT_POLARITY_READBACKS.get(raw.strip().upper())


def parse_runt_qualifier_readback(raw: str) -> str | None:
    """Parse a runt qualifier readback when recognized."""

    return _RUNT_QUALIFIER_READBACKS.get(raw.strip().upper())


def parse_transition_source(raw: str) -> tuple[str | None, int | None]:
    """Parse a transition source readback, preserving unsafe non-analog sources."""

    normalized = raw.strip().upper()
    if normalized.startswith("CHANNEL"):
        suffix = normalized.removeprefix("CHANNEL")
        return _parse_channel_source(suffix), _parse_channel_suffix(suffix)
    if normalized.startswith("CHAN"):
        suffix = normalized.removeprefix("CHAN")
        return _parse_channel_source(suffix), _parse_channel_suffix(suffix)
    return None, None


def parse_transition_slope_readback(raw: str) -> str | None:
    """Parse a transition slope readback when recognized."""

    return _TRANSITION_SLOPE_READBACKS.get(raw.strip().upper())


def parse_transition_qualifier_readback(raw: str) -> str | None:
    """Parse a transition qualifier readback when recognized."""

    return _TRANSITION_QUALIFIER_READBACKS.get(raw.strip().upper())


def parse_pattern_format_readback(raw: str) -> str | None:
    """Parse a pattern format readback when recognized."""

    return _PATTERN_FORMAT_READBACKS.get(raw.strip().upper())


def parse_pattern_qualifier_readback(raw: str) -> str | None:
    """Parse a pattern qualifier readback when recognized."""

    return _PATTERN_QUALIFIER_READBACKS.get(raw.strip().upper())


def parse_pattern_trigger_response(raw: str) -> tuple[str | None, str | None, str | None]:
    """Parse :TRIGger:PATTern? as string plus optional edge fields."""

    parts = _split_pattern_response(raw)
    if not parts:
        return None, None, None
    pattern = _strip_optional_quotes(parts[0])
    edge_source = parts[1].strip() if len(parts) > 1 else None
    edge = parts[2].strip() if len(parts) > 2 else None
    return pattern, edge_source, edge


def parse_or_trigger_pattern_response(raw: str) -> str | None:
    """Parse common OR trigger pattern readbacks without destroying unusual values."""

    pattern = _strip_optional_quotes(raw.strip()).upper()
    if pattern and all(char in {"R", "F", "E", "X"} for char in pattern):
        return pattern
    return None


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


def parse_optional_trigger_float(raw: str, setting_name: str) -> float | None:
    """Parse a numeric trigger response, preserving explicit NONE as absent."""

    if raw.strip().upper() == "NONE":
        return None
    return parse_trigger_float(raw, setting_name)


def parse_glitch_level(raw: str) -> float | None:
    """Parse a glitch trigger level readback."""

    text = raw.strip()
    if text.upper() == "NONE":
        return None
    return parse_trigger_float(text.split(",", 1)[0], "glitch level")


def parse_glitch_range(raw: str) -> tuple[float | None, float | None]:
    """Parse glitch range as CLI min/max from SCPI max,min readback."""

    text = raw.strip()
    if text.upper() == "NONE":
        return None, None
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        raise TriggerResponseError(f"Could not parse trigger glitch range response: {raw!r}")
    max_time = parse_trigger_float(parts[0], "glitch range max")
    min_time = parse_trigger_float(parts[1], "glitch range min")
    return min_time, max_time


def validate_trigger_time(seconds: float) -> float:
    """Validate a positive trigger timing value in seconds."""

    try:
        value = float(seconds)
    except (TypeError, ValueError) as exc:
        raise ParameterValidationError("trigger time must be a number of seconds.") from exc
    if not math.isfinite(value) or value <= 0:
        raise ParameterValidationError("trigger time must be a positive finite number of seconds.")
    return value


def _format_scpi_float(value: float) -> str:
    return f"{value:.12g}"


def _parse_channel_suffix(suffix: str) -> int | None:
    try:
        value = int(suffix)
    except ValueError:
        return None
    return value if value >= 1 else None


def _parse_digital_suffix(suffix: str) -> int | None:
    try:
        value = int(suffix)
    except ValueError:
        return None
    return value if value >= 0 else None


def _parse_channel_source(suffix: str) -> str | None:
    return "channel" if _parse_channel_suffix(suffix) is not None else None


def _parse_digital_source(suffix: str) -> str | None:
    return "digital" if _parse_digital_suffix(suffix) is not None else None


def _split_pattern_response(raw: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    for char in raw.strip():
        if char == '"':
            in_quotes = not in_quotes
            current.append(char)
        elif char == "," and not in_quotes:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current or raw.strip():
        parts.append("".join(current).strip())
    return parts


def _strip_optional_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


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

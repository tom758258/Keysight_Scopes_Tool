import pytest

from keysight_scope_core.capabilities import capabilities_for_model
from keysight_scope_core.errors import ParameterValidationError, TriggerResponseError
from keysight_scope_core.fake_backend import FakeBackend
from keysight_scope_core.scpi import SCPIClient
from keysight_scope_core.trigger import (
    EdgeTriggerController,
    OPERATION_CONDITION_RUI_ENAB_MASK,
    OPERATION_CONDITION_RUN_MASK,
    OPERATION_CONDITION_WAIT_TRIG_MASK,
    TriggerWaitConfig,
    classify_operation_condition,
    edge_trigger_level_command,
    edge_trigger_level_query,
    edge_trigger_slope_command,
    edge_trigger_slope_query,
    edge_trigger_source_command,
    force_trigger_command,
    edge_trigger_source_query,
    normalize_edge_slope,
    parse_edge_slope,
    parse_edge_trigger_source,
    parse_operation_condition,
    parse_trigger_float,
    wait_for_trigger_completion,
    trigger_mode_edge_command,
    validate_trigger_level,
)


class _StepClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _SequenceBackend:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0
        self.history = []

    def write(self, command):
        self.history.append(command)

    def query(self, command):
        self.history.append(command)
        index = min(self.index, len(self.values) - 1)
        value = self.values[index]
        if self.index < len(self.values) - 1:
            self.index += 1
        if isinstance(value, Exception):
            raise value
        return value

def test_edge_trigger_commands_use_keysight_syntax():
    assert trigger_mode_edge_command() == ":TRIGger:MODE EDGE"
    assert edge_trigger_source_command(1) == ":TRIGger:EDGE:SOURce CHANnel1"
    assert edge_trigger_source_query() == ":TRIGger:EDGE:SOURce?"
    assert edge_trigger_level_command(0.25) == ":TRIGger:EDGE:LEVel 0.25"
    assert edge_trigger_level_query() == ":TRIGger:EDGE:LEVel?"
    assert edge_trigger_slope_command("POSitive") == ":TRIGger:EDGE:SLOPe POSitive"
    assert edge_trigger_slope_query() == ":TRIGger:EDGE:SLOPe?"

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("CHAN1", 1),
        ("CHANnel2", 2),
        (" channel4 ", 4),
    ],
)


def test_parse_edge_trigger_source(raw, expected):
    assert parse_edge_trigger_source(raw) == expected

@pytest.mark.parametrize("raw", ["NONE", "EXT", "CHANX", "CHAN0"])


def test_parse_edge_trigger_source_rejects_non_analog_channel(raw):
    with pytest.raises(TriggerResponseError):
        parse_edge_trigger_source(raw)

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("POS", "positive"),
        ("POSitive", "positive"),
        ("NEG", "negative"),
        ("EITH", "either"),
        ("ALT", "alternate"),
    ],
)


def test_parse_edge_slope(raw, expected):
    assert parse_edge_slope(raw) == expected

def test_parse_edge_slope_rejects_unexpected_response():
    with pytest.raises(TriggerResponseError):
        parse_edge_slope("MAYBE")

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("positive", "POSitive"),
        ("rising", "POSitive"),
        ("negative", "NEGative"),
        ("falling", "NEGative"),
        ("either", "EITHer"),
        ("alternate", "ALTernate"),
    ],
)


def test_normalize_edge_slope(raw, expected):
    assert normalize_edge_slope(raw) == expected

def test_normalize_edge_slope_rejects_unknown_slope():
    with pytest.raises(ParameterValidationError):
        normalize_edge_slope("sideways")

@pytest.mark.parametrize("raw, expected", [("2.5E-1", 0.25), (" -1.0 ", -1.0)])


def test_parse_trigger_float(raw, expected):
    assert parse_trigger_float(raw, "level") == expected

@pytest.mark.parametrize("raw", ["MAYBE", "NaN", "INF"])


def test_parse_trigger_float_rejects_unexpected_response(raw):
    with pytest.raises(TriggerResponseError):
        parse_trigger_float(raw, "level")

@pytest.mark.parametrize("value", [0.0, -1.0, "0.25"])


def test_validate_trigger_level_accepts_finite_values(value):
    assert validate_trigger_level(value) == float(value)

@pytest.mark.parametrize("value", [float("inf"), float("nan"), "abc"])


def test_validate_trigger_level_rejects_non_finite_values(value):
    with pytest.raises(ParameterValidationError):
        validate_trigger_level(value)

def test_edge_trigger_controller_configures_and_reads_back_state():
    backend = FakeBackend(
        responses={
            ":TRIGger:EDGE:SOURce?": "CHAN1",
            ":TRIGger:EDGE:LEVel?": "2.5E-1",
            ":TRIGger:EDGE:SLOPe?": "POS",
        }
    )
    controller = EdgeTriggerController(SCPIClient(backend), capabilities_for_model("DSOX4024A"))

    controller.configure(source_channel=1, level_volts=0.25, slope="positive")
    state = controller.query()

    assert state.source_channel == 1
    assert state.level_volts == 0.25
    assert state.slope == "positive"
    assert backend.history == [
        ":TRIGger:MODE EDGE",
        ":TRIGger:EDGE:SOURce CHANnel1",
        ":TRIGger:EDGE:LEVel 0.25",
        ":TRIGger:EDGE:SLOPe POSitive",
        ":TRIGger:EDGE:SOURce?",
        ":TRIGger:EDGE:LEVel?",
        ":TRIGger:EDGE:SLOPe?",
    ]

def test_edge_trigger_controller_rejects_invalid_channel_before_scpi():
    backend = FakeBackend()
    controller = EdgeTriggerController(SCPIClient(backend), capabilities_for_model("DSOX4022A"))

    with pytest.raises(ParameterValidationError):
        controller.configure(source_channel=3, level_volts=0.0, slope="positive")

    assert backend.history == []


def test_force_trigger_command_returns_expected_scpi():
    assert force_trigger_command() == ":TRIGger:FORCe"


def test_force_trigger_command_writes_only_force_trigger_scpi():
    backend = FakeBackend()
    client = SCPIClient(backend)

    client.write(force_trigger_command())

    assert backend.history == [":TRIGger:FORCe"]


def test_operation_condition_classifier_is_conservative_for_live_values():
    assert parse_operation_condition("+1") == 1
    assert classify_operation_condition(0, profile="live") == "unknown"
    assert classify_operation_condition(1, profile="live") == "unknown"
    assert classify_operation_condition(24, profile="live") == "unknown"


def test_operation_condition_masks_match_x_series_register_bits():
    assert OPERATION_CONDITION_RUN_MASK == 8
    assert OPERATION_CONDITION_RUI_ENAB_MASK == 16
    assert OPERATION_CONDITION_WAIT_TRIG_MASK == 32


@pytest.mark.parametrize("profile", ["2000x", "3000x", "4000x", "simulator"])
@pytest.mark.parametrize("value", [8, 24, 40, 56])
def test_operation_condition_classifier_x_series_run_bit_set_is_pending(profile, value):
    assert classify_operation_condition(value, profile=profile) == "pending"


@pytest.mark.parametrize("profile", ["2000x", "3000x", "4000x", "simulator"])
@pytest.mark.parametrize("value", [0, 16, 32, 48])
def test_operation_condition_classifier_x_series_run_bit_clear_is_complete(profile, value):
    assert classify_operation_condition(value, profile=profile) == "complete"


@pytest.mark.parametrize("value", [56, 40, 32, 24, 48, 16, 8, 0])
def test_operation_condition_classifier_unsupported_live_values_remain_unknown(value):
    assert classify_operation_condition(value, profile="live") == "unknown"


def test_wait_for_trigger_completion_natural_path_uses_single_and_poll():
    clock = _StepClock()
    backend = FakeBackend(responses={":OPERegister:CONDition?": "48"})

    result = wait_for_trigger_completion(
        SCPIClient(backend),
        TriggerWaitConfig(100, clock=clock, sleep=clock.sleep),
        classifier_profile="simulator",
    )

    assert result.outcome == "natural"
    assert result.capture_allowed is True
    assert result.condition_values == (48,)
    assert backend.history == [":SINGle", ":OPERegister:CONDition?"]


def test_wait_for_trigger_completion_timeout_without_real_sleep():
    clock = _StepClock()
    backend = FakeBackend(responses={":OPERegister:CONDition?": "56"})

    result = wait_for_trigger_completion(
        SCPIClient(backend),
        TriggerWaitConfig(2, poll_interval_ms=1, clock=clock, sleep=clock.sleep),
        classifier_profile="simulator",
    )

    assert result.outcome == "timeout"
    assert result.capture_allowed is False
    assert result.timed_out is True
    assert result.poll_count == 3


@pytest.mark.parametrize("profile", ["2000x", "3000x", "4000x"])
def test_wait_for_trigger_completion_x_series_polls_until_run_bit_clears(profile):
    clock = _StepClock()
    backend = _SequenceBackend(["40", "40", "32"])

    result = wait_for_trigger_completion(
        SCPIClient(backend),
        TriggerWaitConfig(10, poll_interval_ms=1, clock=clock, sleep=clock.sleep),
        classifier_profile=profile,
    )

    assert result.outcome == "natural"
    assert result.capture_allowed is True
    assert result.raw_values == ("40", "40", "32")
    assert result.condition_values == (40, 40, 32)
    assert backend.history == [
        ":SINGle",
        ":OPERegister:CONDition?",
        ":OPERegister:CONDition?",
        ":OPERegister:CONDition?",
    ]


def test_wait_for_trigger_completion_4000x_force_after_timeout_then_completes():
    clock = _StepClock()
    backend = _SequenceBackend(["56", "56", "56", "56", "48"])

    result = wait_for_trigger_completion(
        SCPIClient(backend),
        TriggerWaitConfig(
            2,
            poll_interval_ms=1,
            force_on_timeout=True,
            clock=clock,
            sleep=clock.sleep,
        ),
        classifier_profile="4000x",
    )

    assert result.outcome == "forced"
    assert result.forced is True
    assert result.capture_allowed is True
    assert result.raw_values == ("56", "56", "56", "56", "48")
    assert backend.history == [
        ":SINGle",
        ":OPERegister:CONDition?",
        ":OPERegister:CONDition?",
        ":OPERegister:CONDition?",
        ":TRIGger:FORCe",
        ":OPERegister:CONDition?",
        ":OPERegister:CONDition?",
    ]


def test_wait_for_trigger_completion_unknown_blocks_capture():
    clock = _StepClock()
    backend = FakeBackend(responses={":OPERegister:CONDition?": "+24"})

    result = wait_for_trigger_completion(
        SCPIClient(backend),
        TriggerWaitConfig(100, clock=clock, sleep=clock.sleep),
        classifier_profile="live",
    )

    assert result.outcome == "unknown"
    assert result.capture_allowed is False
    assert result.raw_values == ("+24",)
    assert result.condition_values == (24,)


def test_wait_for_trigger_completion_query_failure_is_unknown_without_force():
    clock = _StepClock()
    backend = _SequenceBackend([RuntimeError("configured query failure")])

    result = wait_for_trigger_completion(
        SCPIClient(backend),
        TriggerWaitConfig(
            100,
            force_on_timeout=True,
            clock=clock,
            sleep=clock.sleep,
        ),
        classifier_profile="4000x",
    )

    assert result.outcome == "unknown"
    assert result.forced is False
    assert result.capture_allowed is False
    assert result.raw_values == ()
    assert result.condition_values == ()
    assert "configured query failure" in result.error
    assert backend.history == [":SINGle", ":OPERegister:CONDition?"]

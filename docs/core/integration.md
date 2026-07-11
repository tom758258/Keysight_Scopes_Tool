# Core Integration

Import the Core runtime with:

```python
import keysight_scope_core
```

The public import surface is defined by `keysight_scope_core.__all__`. These
names are intended for package consumers and tests:

- `ChannelController`
- `DisplayController`
- `AnnotationState`
- `DisplayPersistence`
- `DVM_MODES`
- `DvmAutoRangeState`
- `DvmBooleanState`
- `DvmController`
- `DvmModeState`
- `DvmReading`
- `DvmSourceState`
- `DvmState`
- `DelayTriggerController`
- `DelayTriggerState`
- `EdgeBurstTriggerController`
- `EdgeBurstTriggerState`
- `EdgeTriggerController`
- `EdgeTriggerState`
- `EdgeTriggerExternalLevelController`
- `EdgeTriggerExternalLevelState`
- `EdgeTriggerSourceController`
- `EdgeTriggerSourceState`
- `GlitchTriggerController`
- `EdgeTriggerCouplingController`
- `EdgeTriggerCouplingState`
- `EdgeTriggerLevelController`
- `EdgeTriggerLevelState`
- `EdgeTriggerRejectController`
- `EdgeTriggerRejectState`
- `EdgeTriggerSlopeController`
- `EdgeTriggerSlopeState`
- `ExternalTriggerRangeController`
- `ExternalTriggerRangeState`
- `ExternalTriggerProbeController`
- `ExternalTriggerProbeState`
- `ExternalTriggerSettingsController`
- `ExternalTriggerSettingsState`
- `ExternalTriggerUnitsController`
- `ExternalTriggerUnitsState`
- `GlitchTriggerState`
- `OrTriggerController`
- `OrTriggerState`
- `PatternTriggerController`
- `PatternTriggerState`
- `RuntTriggerController`
- `RuntTriggerState`
- `SetupHoldTriggerController`
- `SetupHoldTriggerState`
- `TransitionTriggerController`
- `TransitionTriggerState`
- `TriggerHfRejectController`
- `TriggerNoiseRejectController`
- `TriggerRejectState`
- `TriggerSweepController`
- `TriggerSweepState`
- `IDN`
- `KeysightScope`
- `MeasurementController`
- `MeasurementResult`
- `MeasurementShowState`
- `MeasurementSourceState`
- `MeasurementWindowState`
- `ReferenceWaveformController`
- `ReferenceWaveformState`
- `SEARCH_MODES`
- `SearchController`
- `SearchCountState`
- `SearchModeState`
- `SearchState`
- `MultiChannelWaveformCapture`
- `OperationCompleteState`
- `OperationPlan`
- `OperationResult`
- `ResolvedRunConfig`
- `RunModeOptions`
- `CaptureRequest`
- `MeasureLogRequest`
- `MeasureRequest`
- `MeasureSweepRequest`
- `SmokeRequest`
- `AcquisitionCheckRequest`
- `ScreenshotCapture`
- `ScreenshotController`
- `ScopeCapabilities`
- `SystemErrorEntry`
- `StatusController`
- `StatusRegisterState`
- `SystemOptionsState`
- `TimebaseController`
- `TriggerWaitConfig`
- `TriggerWaitResult`
- `TvTriggerController`
- `TvTriggerState`
- `WaveformCapture`
- `WaveformPreamble`
- `capabilities_for_model`
- `detect_series`
- `parse_channel_display`
- `parse_channel_coupling`
- `parse_channel_impedance`
- `parse_channel_units`
- `parse_display_label`
- `parse_idn`
- `parse_operation_complete`
- `parse_status_register`
- `parse_system_error`
- `parse_system_options`
- `resolve_run_mode`
- `resolve_resource`
- `require_resource`
- `open_scope_for_run`
- `plan_capture`
- `plan_doctor`
- `plan_measure`
- `plan_measure_sweep`
- `plan_smoke`
- `plan_acquisition_check`
- `run_capture`
- `run_doctor`
- `run_measure_log`
- `run_measure`
- `run_measure_sweep`
- `run_smoke`
- `run_acquisition_check`

## Runtime Guidance

Use `resolve_run_mode`, `resolve_resource`, `require_resource`, and
`open_scope_for_run` to centralize live, simulated, and dry-run behavior.
Operation planning helpers return planned SCPI and artifact paths without
opening VISA. Operation runners execute against the selected backend.

Core should remain independent from command-line parser types and WebUI
controller concepts. Package adapters may call Core, but Core should not import
from adapter packages.

System/Status Pack v1 is available through `KeysightScope.clear_status()`,
`query_operation_complete()`, `query_status_byte()`,
`query_standard_event_status()`, `query_operation_status()`, and
`query_system_options()`. These methods do not require an IDN or capability
profile. `query_standard_event_status()` performs the destructive `*ESR?`
event-register read. `query_operation_status()` uses
`:OPERegister:CONDition?`; it does not introduce the intentionally unsupported
`:RSTate?` query. Existing `query_system_error()` and `drain_system_errors()`
remain the APIs for `:SYSTem:ERRor?`.

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
- `EdgeTriggerController`
- `EdgeTriggerState`
- `GlitchTriggerController`
- `GlitchTriggerState`
- `RuntTriggerController`
- `RuntTriggerState`
- `TransitionTriggerController`
- `TransitionTriggerState`
- `IDN`
- `KeysightScope`
- `MeasurementController`
- `MeasurementResult`
- `MultiChannelWaveformCapture`
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
- `TimebaseController`
- `TriggerWaitConfig`
- `TriggerWaitResult`
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
- `parse_system_error`
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

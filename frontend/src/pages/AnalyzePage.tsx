import { useState } from "react";
import type { ReactElement } from "react";
import { PageLayout } from "./components/PageLayout";
import { PageHeader } from "./components/PageHeader";
import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { InfoNote } from "./components/InfoNote";
import { StatusBadge } from "./components/StatusBadge";
import type { StatusTone } from "./components/StatusBadge";
import { FileDropzone } from "../shared/components";
import { NAVIGATION_ITEMS } from "../app/navigation/navigationModel";
import {
  toAnalysisInput,
  validateAnalysisInput,
  describeRejection,
} from "./analyze/analysisInput";
import type { AnalysisInput } from "./analyze/analysisInput";
import { isNativeFileSelectionSupported, pickNativeReportFile } from "./analyze/nativeFileSelection";
import { describeExecutionError } from "./analyze/analysisExecutionError";
import {
  beginValidating,
  DEFAULT_ANALYSIS_OPTIONS,
  initialAnalysisWorkflowState,
  markInvalid,
  markReady,
  selectInput,
  updateOptions,
} from "./analyze/analysisWorkflowState";
import type { AnalysisWorkflowState } from "./analyze/analysisWorkflowState";
import type { AnalysisOptions } from "../shared/api/types";
import { useAnalysisExecution } from "./analyze/useAnalysisExecution";
import { AnalysisResultSummary } from "./analyze/AnalysisResultSummary";
import { AnalysisOptionsControls } from "./analyze/AnalysisOptionsControls";
import "./AnalyzePage.css";

/** The Investigations destination's route, from the single
 * navigation source of truth (`NAVIGATION_ITEMS`) rather than a
 * hardcoded string — §9: "The destination must use the existing
 * route definition. Do NOT invent a new route." A plain hash-link
 * (not `useNavigate`/`Link`) is used at the call site so this page
 * keeps rendering standalone, outside a Router, exactly as
 * `pages.test.tsx` (Phase 4G-2, frozen) already exercises it. */
const INVESTIGATIONS_PATH =
  NAVIGATION_ITEMS.find((item) => item.id === "investigations")?.path ?? "/investigations";

const STATUS_LABEL: Record<AnalysisWorkflowState["status"], string> = {
  idle: "No file selected",
  inputSelected: "Checking file…",
  validating: "Checking file…",
  ready: "Ready to analyze",
  invalid: "Invalid file",
  analyzing: "Analyzing…",
  completed: "Analysis complete",
  failed: "Analysis failed",
};

const STATUS_TONE: Record<AnalysisWorkflowState["status"], StatusTone> = {
  idle: "neutral",
  inputSelected: "info",
  validating: "info",
  ready: "success",
  invalid: "error",
  analyzing: "info",
  completed: "success",
  failed: "error",
};

/**
 * Analyze page — Phase 4I-1A (foundation) through 4I-2 (result/handoff).
 *
 * A person can select or drop a file, see it validated, run the real
 * `analyze_report` execution, and reach a `completed` or `failed`
 * outcome. `completed` renders `AnalysisResultSummary` (risk score,
 * severity, status, investigation handoff — §4/§7/§8); `failed`
 * offers a real retry against the same input (§10). This page itself
 * does not render IOC or Threat Intel detail inline — those remain
 * the Investigation Workspace's job (reached via the handoff link) —
 * the `InfoNote` below says so explicitly rather than the page
 * silently implying more capability than it has.
 */
export function AnalyzePage(): ReactElement {
  const [state, setState] = useState<AnalysisWorkflowState>(
    initialAnalysisWorkflowState,
  );
  const [dropRejection, setDropRejection] = useState<string | null>(null);
  const { canStart, blockedReason, start, canRetry, retry } = useAnalysisExecution(state, setState);

  // Validation is driven imperatively from the selection handler
  // (not a `useEffect` keyed off `state`) so a second file selected
  // while the first is still validating can't have the first
  // validation's *cleanup* race the second's *start* — the async
  // work and the "is this result still current" check both live in
  // one place, keyed on the actual `AnalysisInput` object identity.
  async function handleInputSelected(input: AnalysisInput): Promise<void> {
    setDropRejection(null);
    const selected = selectInput(input);
    setState(selected);

    const validating = beginValidating(selected);
    setState(validating);

    const result = await validateAnalysisInput(input);

    setState((current) => {
      // A newer selection has since taken over — this result is stale.
      // Split into two checks (rather than one `||`) so the
      // narrowing that gives `current.input` below doesn't depend on
      // control-flow inference through a compound condition.
      if (current.status === "idle") {
        return current;
      }
      if (current.input !== input) {
        return current;
      }
      return result.ok ? markReady(validating) : markInvalid(validating, result.rejection);
    });
  }

  async function handleFileSelected(file: File): Promise<void> {
    await handleInputSelected(toAnalysisInput(file));
  }

  /**
   * Blocker A: the native desktop picker (`tauri-plugin-dialog`) is
   * the one supported way to get a real, backend-readable
   * `report_path` — see `nativeFileSelection.ts`/`analysisReportPath.ts`.
   * A cancelled dialog is a normal, silent no-op (matches native OS
   * picker convention); a genuine read failure surfaces through the
   * same `dropRejection` message slot `FileDropzone`'s own rejection
   * path already uses, rather than a second, parallel error UI.
   */
  async function handleNativeBrowse(): Promise<void> {
    setDropRejection(null);
    const result = await pickNativeReportFile();
    if (result.ok) {
      await handleInputSelected(result.input);
      return;
    }
    if (result.reason === "cancelled") {
      return;
    }
    if (result.reason === "unsupported") {
      setDropRejection("Native file selection isn't available in this environment.");
      return;
    }
    setDropRejection("Couldn't read the selected file. Check that it's still available and try again.");
  }

  const selectedFileName = state.status !== "idle" ? state.input.fileName : undefined;
  const isDropzoneDisabled = state.status === "analyzing";

  /**
   * What the three stage controls show right now — Part 3 §4/§5/§8.
   * `ready`/`analyzing`/`failed` show the *requested* selection
   * (`state.options`, carried by the state machine itself); a
   * `completed` run shows the *applied* selection the backend
   * actually echoed back (`state.result.options`), which is what
   * makes a disabled stage's absence from the results honest rather
   * than merely inferred from a request that might not have been
   * fully honored. Every other state (no file selected/validating/
   * invalid yet) has no real selection to show, so the controls fall
   * back to the same all-selected default a fresh `ready` state
   * starts with.
   */
  const displayedOptions: AnalysisOptions =
    state.status === "ready" || state.status === "analyzing" || state.status === "failed"
      ? state.options
      : state.status === "completed"
        ? state.result.options
        : DEFAULT_ANALYSIS_OPTIONS;

  // Only editable from `ready` — before a run has started and after
  // any previous run's outcome is showing, not mid-run or on a
  // result/error the options no longer describe an editable choice
  // for.
  function handleOptionsChange(options: AnalysisOptions): void {
    setState((current) => (current.status === "ready" ? updateOptions(current, options) : current));
  }

  return (
    <PageLayout label="Analyze page">
      <PageHeader
        title="Analyze"
        description="Submit a file or report for analysis. This entry point establishes the future analysis workflow surface."
      />

      <section className="page-layout__section">
        <Card title="New Analysis">
          <FileDropzone
            id="analysis-file-input"
            label="Select a report file to analyze"
            selectedFileName={selectedFileName}
            disabled={isDropzoneDisabled}
            onFileSelected={(file) => {
              void handleFileSelected(file);
            }}
            onRejected={setDropRejection}
          />

          {isNativeFileSelectionSupported() ? (
            <Button
              variant="secondary"
              className="analyze-page__native-browse-button"
              onClick={() => {
                void handleNativeBrowse();
              }}
              disabled={isDropzoneDisabled}
            >
              Browse for Analysis
            </Button>
          ) : null}

          <AnalysisOptionsControls
            options={displayedOptions}
            disabled={state.status !== "ready"}
            onChange={handleOptionsChange}
          />

          <div className="analyze-page__status" aria-live="polite">
            <StatusBadge label={STATUS_LABEL[state.status]} tone={STATUS_TONE[state.status]} />
          </div>

          {dropRejection ? (
            <p className="analyze-page__validation-message" role="alert">
              {dropRejection}
            </p>
          ) : null}

          {state.status === "invalid" ? (
            <p className="analyze-page__validation-message" role="alert">
              {describeRejection(state.rejection)}
            </p>
          ) : null}

          {state.status === "ready" || state.status === "analyzing" ? (
            <div className="analyze-page__execution transition-fade">
              <Button
                variant="secondary"
                className="analyze-page__start-button analyze-page__accent-button"
                onClick={start}
                disabled={!canStart || state.status === "analyzing"}
                aria-busy={state.status === "analyzing"}
              >
                {state.status === "analyzing" ? "Analyzing…" : "Start Analysis"}
              </Button>

              {blockedReason ? (
                <p className="analyze-page__validation-message">{blockedReason}</p>
              ) : null}

              {state.status === "analyzing" ? (
                <div className="analyze-page__progress" role="status" aria-live="polite">
                  {state.progress ? (
                    <>
                      <progress
                        className="analyze-page__progress-bar"
                        value={state.progress.percent}
                        max={100}
                        aria-label="Analysis progress"
                      />
                      <p className="analyze-page__progress-message">{state.progress.message}</p>
                    </>
                  ) : (
                    <>
                      <progress className="analyze-page__progress-bar" aria-label="Analysis progress" />
                      <p className="analyze-page__progress-message">Analysis is running…</p>
                    </>
                  )}
                </div>
              ) : null}
            </div>
          ) : null}

          {state.status === "completed" ? (
            <AnalysisResultSummary result={state.result} investigationsPath={INVESTIGATIONS_PATH} />
          ) : null}

          {state.status === "failed" ? (
            <div className="analyze-page__execution transition-fade">
              <p className="analyze-page__validation-message" role="alert">
                {describeExecutionError(state.error)}
              </p>
              <Button
                variant="secondary"
                className="analyze-page__retry-button analyze-page__accent-button"
                onClick={retry}
                disabled={!canRetry}
              >
                Try Again
              </Button>
              {!canRetry && blockedReason ? (
                <p className="analyze-page__validation-message">{blockedReason}</p>
              ) : null}
            </div>
          ) : null}

          <InfoNote>
            {state.status === "analyzing" ||
            state.status === "completed" ||
            state.status === "failed" ||
            state.status === "ready"
              ? "File selection, validation, and execution are functional against the real analysis service. A completed run shows risk score, severity, status, and an investigation handoff link; IOC and threat-intelligence detail views are available from the Investigation Workspace, not shown inline here."
              : "File selection, validation, and execution are functional against the real analysis service. Select or drop a report to begin."}
          </InfoNote>
        </Card>
      </section>
    </PageLayout>
  );
}

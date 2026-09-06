import type { ReactElement } from "react";
import type { AnalysisOptions } from "../../shared/api/types";
import "./AnalysisOptionsControls.css";

export interface AnalysisOptionsControlsProps {
  /** The selection to display — see `AnalyzePage.tsx`'s
   * `displayedOptions` for how this is chosen per workflow state. */
  readonly options: AnalysisOptions;
  /** Whether the controls can currently be changed — true only while
   * the workflow is `ready` (Part 3 §5: options are a pre-execution
   * choice). Disabled elsewhere, but never hidden: the selection
   * they reflect (requested or applied) stays visible throughout the
   * run and its outcome. */
  readonly disabled: boolean;
  readonly onChange: (options: AnalysisOptions) => void;
}

/**
 * The three Phase 4I stage controls — Part 3 §4. Each maps 1:1 to a
 * field of `AnalysisOptions` (`shared/api/types.ts`, mirroring
 * `app/application/dto.py`), which is in turn exactly the payload
 * `analysisExecution.ts::executeAnalysis` sends to the real
 * `analyze_report` command — no control here is decorative or
 * unwired (§4: "There must be no dead controls").
 *
 * Plain, accessible checkboxes rather than a bespoke toggle
 * component: this project has no existing checkbox/switch primitive
 * to reuse (`pages/components` has none), and introducing one here
 * would be new design-system surface this checkpoint's own brief
 * rules out ("Do NOT redesign the Analysis page"). Native
 * `<input type="checkbox">` + `<label>` already satisfies §14's
 * accessibility requirements (keyboard, focus, accessible name) for
 * free.
 */
export function AnalysisOptionsControls({
  options,
  disabled,
  onChange,
}: AnalysisOptionsControlsProps): ReactElement {
  function toggle(key: keyof AnalysisOptions): void {
    onChange({ ...options, [key]: !options[key] });
  }

  // `disabled` is set on the `<fieldset>` (the semantically correct
  // place — a single disabled ancestor communicating "this whole
  // group is inactive" to assistive tech) *and* individually on each
  // `<input>`. Real browsers propagate a disabled fieldset to its
  // descendant controls automatically per the HTML spec; the
  // explicit per-input attribute is defense-in-depth for
  // environments (including this project's own jsdom-based test
  // suite) that don't implement that propagation, so "disabled"
  // means the same, verifiable thing everywhere this renders.
  return (
    <fieldset className="analysis-options-controls" disabled={disabled}>
      <legend className="analysis-options-controls__legend">Analysis stages</legend>

      <label className="analysis-options-controls__option" htmlFor="analysis-option-extract-iocs">
        <input
          id="analysis-option-extract-iocs"
          type="checkbox"
          checked={options.extract_iocs}
          disabled={disabled}
          onChange={() => toggle("extract_iocs")}
        />
        Extract IOCs
      </label>

      <label className="analysis-options-controls__option" htmlFor="analysis-option-enrich-ti">
        <input
          id="analysis-option-enrich-ti"
          type="checkbox"
          checked={options.enrich_ti}
          disabled={disabled}
          onChange={() => toggle("enrich_ti")}
        />
        Enrich Threat Intelligence
      </label>

      <label className="analysis-options-controls__option" htmlFor="analysis-option-score-risk">
        <input
          id="analysis-option-score-risk"
          type="checkbox"
          checked={options.score_risk}
          disabled={disabled}
          onChange={() => toggle("score_risk")}
        />
        Calculate Risk
      </label>
    </fieldset>
  );
}

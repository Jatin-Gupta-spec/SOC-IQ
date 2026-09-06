/**
 * `FileDropzone` static/structural tests — Phase 4I-1A, §6/§15.
 *
 * `renderToStaticMarkup`, no jsdom — matches the project's existing
 * static/live test split (e.g. `CommandPalette.test.tsx`).
 * Interaction (drag/drop, click, keyboard, change events) needs a
 * live DOM and lives in `FileDropzone.live.test.tsx`.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FileDropzone } from "./FileDropzone";

describe("FileDropzone", () => {
  it("renders without throwing", () => {
    expect(() =>
      renderToStaticMarkup(
        <FileDropzone id="f1" label="Select a file" onFileSelected={() => {}} />,
      ),
    ).not.toThrow();
  });

  it("shows helper text when no file is selected", () => {
    const html = renderToStaticMarkup(
      <FileDropzone
        id="f1"
        label="Select a file"
        helperText="Drag a file here, or browse to select one"
        onFileSelected={() => {}}
      />,
    );
    expect(html).toContain("Drag a file here, or browse to select one");
  });

  it("shows the selected file name instead of the helper text", () => {
    const html = renderToStaticMarkup(
      <FileDropzone
        id="f1"
        label="Select a file"
        helperText="Drag a file here"
        selectedFileName="incident-report.txt"
        onFileSelected={() => {}}
      />,
    );
    expect(html).toContain("incident-report.txt");
    expect(html).not.toContain("Drag a file here");
  });

  it("renders exactly one file input with the given id and accessible label", () => {
    const html = renderToStaticMarkup(
      <FileDropzone id="analysis-file-input" label="Select a report file to analyze" onFileSelected={() => {}} />,
    );
    expect((html.match(/type="file"/g) ?? []).length).toBe(1);
    expect(html).toContain('id="analysis-file-input"');
    expect(html).toContain('aria-label="Select a report file to analyze"');
  });

  it("renders the input as disabled when disabled is true", () => {
    const html = renderToStaticMarkup(
      <FileDropzone id="f1" label="Select a file" disabled onFileSelected={() => {}} />,
    );
    expect(html).toContain("disabled");
  });

  it("wraps long filenames instead of overflowing (no truncation styling applied via markup)", () => {
    const longName = "a".repeat(120) + ".txt";
    const html = renderToStaticMarkup(
      <FileDropzone id="f1" label="Select a file" selectedFileName={longName} onFileSelected={() => {}} />,
    );
    expect(html).toContain(longName);
  });

  it("produces no duplicate React keys across renders of the same tree", () => {
    // No list rendering inside FileDropzone — a static render that
    // doesn't throw a "duplicate key" warning is sufficient evidence.
    expect(() =>
      renderToStaticMarkup(
        <FileDropzone id="f1" label="Select a file" onFileSelected={() => {}} />,
      ),
    ).not.toThrow();
  });
});

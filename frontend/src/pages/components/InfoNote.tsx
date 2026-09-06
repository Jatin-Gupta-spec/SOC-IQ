import type { ReactElement } from "react";
import "./InfoNote.css";

export interface InfoNoteProps {
  readonly children: string;
}

/**
 * Explicit "this is not functional yet" note (Phase 4G-2 Part 3, §14).
 *
 * §14 requires that a non-functional control's state be made clear
 * "rather than creating fake persistence". This is that explicit
 * marker — used on Settings (controls that don't persist) and
 * Analyze (an entry point with no real backend execution yet) so the
 * mock surfaces don't quietly imply capability they don't have.
 */
export function InfoNote({ children }: InfoNoteProps): ReactElement {
  return (
    <p className="info-note" role="note">
      {children}
    </p>
  );
}

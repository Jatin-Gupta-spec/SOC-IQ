import { lazy, Suspense, type ReactElement } from "react";
import { useParams } from "react-router-dom";
import { PageLayout } from "../pages/components/PageLayout";
import { PageHeader } from "../pages/components/PageHeader";
import { InfoNote } from "../pages/components/InfoNote";
import { parseInvestigationId } from "./investigationRouteParams";
import { RouteLoadingFallback } from "./RouteLoadingFallback";

/**
 * MAX-8 Phase 2A (MAX8-F-01): lazy rather than static, matching
 * `router.tsx`'s five navigation-item routes. `InvestigationIocWorkspace.tsx`
 * (665 lines) and `InvestigationWorkspacePage.tsx` (497 lines) are the
 * two largest non-test source files in the project (MAX8-F-04), so
 * this is the single highest-value split available under F-01 --
 * an analyst who never opens an investigation never pays for either
 * file's JS.
 */
const InvestigationWorkspacePage = lazy(() =>
  import("../pages/investigation/InvestigationWorkspacePage").then((m) => ({
    default: m.InvestigationWorkspacePage,
  })),
);

/**
 * Route target for `/investigations/:investigationId` (Phase 4J-3,
 * scope step 7).
 *
 * Still deliberately minimal at the route-parameter layer, per 4J-3's
 * original scope ("create only the minimal route target required to
 * prove routing works"). It:
 *
 * 1. reads the raw `:investigationId` route parameter via
 *    `useParams()`,
 * 2. validates it with `parseInvestigationId()`, and
 * 3. renders one of exactly two route-level states -- "invalid route
 *    parameter" (unchanged from 4J-3: a plain inline message, never
 *    routed further) or "valid investigation ID".
 *
 * Phase 4J-6 Part 1A: a *valid* ID now hands off to the real
 * `InvestigationWorkspacePage` (`pages/investigation/`), which owns
 * everything downstream of that hand-off -- data fetching via
 * `useInvestigation()`, the not-found/error/partial/success states,
 * and the workspace shell itself. This route component's own job
 * stays exactly what it was: validate the route parameter and decide
 * whether there is a numeric ID worth handing off at all. It still
 * never claims an investigation exists just because its ID is
 * well-formed -- that distinction belongs entirely to the workspace
 * page now, not to this route target.
 */
export function InvestigationRoute(): ReactElement {
  const { investigationId: rawInvestigationId } = useParams<{
    investigationId: string;
  }>();

  const result = parseInvestigationId(rawInvestigationId);

  if (!result.valid) {
    return (
      <PageLayout label="Investigation page">
        <PageHeader
          title="Investigation"
          description="This investigation link is invalid."
        />
        <section className="page-layout__section">
          <InfoNote>
            {`"${rawInvestigationId ?? ""}" is not a valid investigation ID.`}
          </InfoNote>
        </section>
      </PageLayout>
    );
  }

  return (
    <Suspense fallback={<RouteLoadingFallback label="Investigation Workspace" />}>
      <InvestigationWorkspacePage investigationId={result.investigationId} />
    </Suspense>
  );
}

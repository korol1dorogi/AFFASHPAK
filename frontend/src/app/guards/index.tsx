import { Navigate, Outlet, useLocation } from "react-router";

import { homeFor, routes } from "@/app/routes";
import { useMe } from "@/app/session";
import { ErrorState, PageSkeleton } from "@/components/States";

function Loading() {
  return (
    <div className="mx-auto max-w-[1120px] p-6">
      <PageSkeleton />
    </div>
  );
}

/** No session → /login?next=<current path>. */
export function RequireAuth() {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <Loading />;
  if (me.isError) return <ErrorState error={me.error} onRetry={() => me.refetch()} />;
  if (!me.data) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`${routes.login}?next=${next}`} replace />;
  }
  return <Outlet />;
}

/** Wrong side (client on /bank or bank on /app) → own home. */
export function RequireKind({ kind }: { kind: "client" | "bank" }) {
  const me = useMe();
  if (!me.data) return null;
  if (me.data.kind !== kind) return <Navigate to={homeFor(me.data.kind)} replace />;
  return <Outlet />;
}

/** A client without a company goes to create one first. */
export function RequireCompany() {
  const me = useMe();
  if (me.data && me.data.kind === "client" && me.data.company_id === null) {
    return <Navigate to={routes.companyNew} replace />;
  }
  return <Outlet />;
}

/** /login and /register for someone already signed in → own home. */
export function RedirectIfAuthed() {
  const me = useMe();
  if (me.isPending) return <Loading />;
  if (me.data) return <Navigate to={homeFor(me.data.kind)} replace />;
  return <Outlet />;
}

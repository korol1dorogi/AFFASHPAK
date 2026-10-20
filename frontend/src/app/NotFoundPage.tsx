import { SearchX } from "lucide-react";
import { Link } from "react-router";

import { homeFor, routes } from "@/app/routes";
import { useMe } from "@/app/session";
import { EmptyState } from "@/components/States";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  const me = useMe();
  const home = me.data ? homeFor(me.data.kind) : routes.landing;
  return (
    <div className="mx-auto max-w-[640px] p-6">
      <EmptyState
        icon={<SearchX className="size-6" aria-hidden="true" />}
        title="Страница не найдена"
        text="Возможно, ссылка устарела или в адресе опечатка."
        action={
          <Button asChild>
            <Link to={home}>На главную</Link>
          </Button>
        }
      />
    </div>
  );
}

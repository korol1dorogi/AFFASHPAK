import { Link } from "react-router";

import { routes } from "@/app/routes";
import { Button } from "@/components/ui/button";
import { PRODUCT_NAME } from "@/texts";

/** One-screen landing, first version (B9 polishes it). */
export function LandingPage() {
  return (
    <section className="flex flex-col gap-6 py-12">
      <h1 className="m-0 max-w-[18ch] font-display text-[40px] leading-[44px] font-extrabold tracking-[-0.02em]">
        Деньги для бизнеса — под вашу задачу
      </h1>
      <p className="m-0 max-w-[60ch] text-lg leading-7 text-ink-muted">
        {PRODUCT_NAME} спросит, зачем нужны деньги, подберёт продукт и сумму по обороту на счёте и
        объяснит каждую цифру. Заявка, проверка и подписание — в одном кабинете.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button asChild size="lg">
          <Link to={routes.login}>Войти</Link>
        </Button>
        <Button asChild size="lg" variant="secondary">
          <Link to={routes.register}>Зарегистрироваться</Link>
        </Button>
      </div>
      <p className="m-0 text-sm text-ink-muted">
        Прототип для хакатона: все компании и данные синтетические, внешние сервисы — симуляторы.
      </p>
    </section>
  );
}

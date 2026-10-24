import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { routes } from "@/app/routes";
import { Field } from "@/components/Field";
import { DemoBadge, PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDemoLogin, useDemoPersonas, useLogin } from "@/features/auth/api";
import { ApiError, errorMessage } from "@/lib/errors";

const schema = z.object({
  username: z.string().trim().min(1, "Введите логин"),
  password: z.string().min(1, "Введите пароль"),
});
type Values = z.infer<typeof schema>;

function loginError(error: unknown): string {
  if (error instanceof ApiError && (error.status === 401 || error.status === 400)) {
    return "Неверный логин или пароль.";
  }
  if (error instanceof ApiError && error.status === 429) {
    return "Слишком много попыток. Подождите минуту и попробуйте снова.";
  }
  return errorMessage(error);
}

function DemoPersonas() {
  const personas = useDemoPersonas();
  const demoLogin = useDemoLogin();
  if (!personas.data?.length) return null;
  return (
    <Card className="gap-3">
      <div className="flex items-center gap-2">
        <h2 className="m-0 text-lg font-semibold">Быстрый вход за демо-компанию</h2>
        <DemoBadge />
      </div>
      <p className="m-0 text-sm text-ink-muted">
        Вымышленные компании, на которых можно проверить сценарии.
      </p>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {personas.data.map((persona) => (
          <li
            key={persona.code}
            className="flex items-center gap-3 rounded-md border border-line p-3"
          >
            <span className="min-w-0 flex-1">
              <span className="block font-medium">{persona.title}</span>
              <span className="text-sm text-ink-muted">
                {persona.kind === "bank" ? "Рабочее место банка" : `Сценарий ${persona.scenario}`}
              </span>
            </span>
            <Button
              variant="secondary"
              size="sm"
              loading={demoLogin.isPending && demoLogin.variables === persona.code}
              onClick={() => demoLogin.mutate(persona.code)}
            >
              Войти
            </Button>
          </li>
        ))}
      </ul>
      {demoLogin.isError ? (
        <p className="m-0 text-sm text-status-danger">{errorMessage(demoLogin.error)}</p>
      ) : null}
    </Card>
  );
}

export function LoginPage() {
  const login = useLogin();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { username: "", password: "" },
  });
  const { errors } = form.formState;

  return (
    <div className="mx-auto flex w-full max-w-[480px] flex-col gap-6">
      <PageHeader title="Вход" subtitle="Кредитный кабинет для малого бизнеса." />
      <Card>
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={form.handleSubmit((values) => login.mutate(values))}
        >
          <Field label="Логин" error={errors.username?.message}>
            <Input autoComplete="username" {...form.register("username")} />
          </Field>
          <Field label="Пароль" error={errors.password?.message}>
            <Input type="password" autoComplete="current-password" {...form.register("password")} />
          </Field>
          {login.isError ? (
            <p role="alert" className="m-0 text-sm text-status-danger">
              {loginError(login.error)}
            </p>
          ) : null}
          <Button type="submit" size="lg" loading={login.isPending}>
            Войти
          </Button>
        </form>
        <p className="m-0 text-sm text-ink-muted">
          Нет учётной записи? <Link to={routes.register}>Зарегистрироваться</Link>
        </p>
      </Card>
      <DemoPersonas />
    </div>
  );
}

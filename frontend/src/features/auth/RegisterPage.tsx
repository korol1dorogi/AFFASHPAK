import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { routes } from "@/app/routes";
import { Field } from "@/components/Field";
import { PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useRegister } from "@/features/auth/api";
import { applyFieldErrors } from "@/lib/errors";

const FIELDS = ["username", "password", "full_name"] as const;

const PASSWORD_HINT =
  "От 8 символов, не только цифры, не простой вроде qwerty123 и не похожий на логин";

// Limits mirror RegisterRequest in docs/openapi.yaml. One message per field, the first check
// that fails; the server adds «распространённый» and «похож на логин» the same way. The repeat
// of the password is checked here only and never sent.
const schema = z
  .object({
    full_name: z.string().trim().min(1, "Как к вам обращаться").max(200),
    username: z
      .string()
      .trim()
      .min(3, "Логин — от 3 символов")
      .max(150)
      .regex(/^[\w.@+-]+$/, "Только буквы, цифры и . @ + - _"),
    password: z
      .string()
      .min(8, "Пароль — от 8 символов")
      .max(128)
      .refine((value) => !/^\d+$/.test(value), "Пароль не может состоять только из цифр"),
    password_repeat: z.string().min(1, "Повторите пароль"),
  })
  .refine((values) => values.password === values.password_repeat, {
    message: "Пароли не совпадают",
    path: ["password_repeat"],
  });
type Values = z.infer<typeof schema>;

export function RegisterPage() {
  const register = useRegister();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", username: "", password: "", password_repeat: "" },
  });
  const { errors } = form.formState;
  const [rest, setRest] = useState<string | null>(null);

  return (
    <div className="mx-auto flex w-full max-w-[480px] flex-col gap-6">
      <PageHeader
        title="Регистрация"
        subtitle="Без почты и телефона: логин и пароль. Компанию добавите следующим шагом по ИНН."
      />
      <Card>
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={form.handleSubmit(({ password_repeat: _, ...values }) => {
            setRest(null);
            register.mutate(values, {
              onError: (error) => setRest(applyFieldErrors(error, form.setError, FIELDS)),
            });
          })}
        >
          <Field label="Имя и фамилия" error={errors.full_name?.message}>
            <Input autoComplete="name" {...form.register("full_name")} />
          </Field>
          <Field label="Логин" error={errors.username?.message}>
            <Input autoComplete="username" {...form.register("username")} />
          </Field>
          <Field label="Пароль" hint={PASSWORD_HINT} error={errors.password?.message}>
            <Input type="password" autoComplete="new-password" {...form.register("password")} />
          </Field>
          <Field label="Повторите пароль" error={errors.password_repeat?.message}>
            <Input
              type="password"
              autoComplete="new-password"
              {...form.register("password_repeat")}
            />
          </Field>
          {rest ? (
            <p role="alert" className="m-0 text-sm text-status-danger">
              {rest}
            </p>
          ) : null}
          <Button type="submit" size="lg" loading={register.isPending}>
            Создать учётную запись
          </Button>
        </form>
        <p className="m-0 text-sm text-ink-muted">
          Уже есть учётная запись?{" "}
          <Link to={routes.login} className="link">
            Войти
          </Link>
        </p>
      </Card>
    </div>
  );
}

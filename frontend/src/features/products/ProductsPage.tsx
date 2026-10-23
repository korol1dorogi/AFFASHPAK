import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link } from "react-router";

import { api, type Schemas } from "@/api/client";
import { routes } from "@/app/routes";
import { Field } from "@/components/Field";
import { MoneyText, RateText } from "@/components/Money";
import { MoneyInput } from "@/components/MoneyInput";
import { ErrorState, PageHeader, PageSkeleton } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { useProducts } from "@/features/applications/api";
import { errorMessage, unwrap } from "@/lib/errors";
import { formatDecimal, formatMoney, percentToFraction } from "@/lib/format";
import { DOCUMENT_KIND, PRODUCT_KIND, PRODUCTS as T } from "@/texts";

type Product = Schemas["Product"];

/** C4: the catalog with conditions and a payment calculator (POST /api/calculators/annuity). */
export function ProductsPage() {
  const products = useProducts();
  const [chosen, setChosen] = useState<string | null>(null);
  if (products.isPending) return <PageSkeleton />;
  if (products.isError)
    return (
      <ErrorState
        title={T.loadError}
        error={products.error}
        onRetry={() => void products.refetch()}
      />
    );
  const list = products.data;
  const product = list.find((item) => item.code === chosen) ?? list.find((p) => !p.is_revolving);
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={T.title}
        subtitle={T.subtitle}
        actions={
          <Button asChild>
            <Link to={routes.match}>{T.match}</Link>
          </Button>
        }
      />
      <ul aria-label={T.title} className="m-0 grid list-none gap-4 p-0 md:grid-cols-2">
        {list.map((item) => (
          <li key={item.code}>
            <ProductCard product={item} onCalculate={() => setChosen(item.code)} />
          </li>
        ))}
      </ul>
      {product ? (
        <Calculator
          key={product.code}
          products={list.filter((p) => !p.is_revolving)}
          product={product}
          onProduct={setChosen}
        />
      ) : null}
    </div>
  );
}

function ProductCard({ product, onCalculate }: { product: Product; onCalculate: () => void }) {
  return (
    <Card className="h-full">
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle className="m-0">{product.name}</CardTitle>
        <Badge variant="neutral">{PRODUCT_KIND[product.kind]}</Badge>
      </div>
      <p className="m-0 text-sm text-ink-muted">{product.description}</p>
      <dl className="m-0 grid grid-cols-3 gap-3 text-sm">
        <div>
          <dt className="text-ink-muted">{T.rate}</dt>
          <dd className="m-0 font-semibold">
            <RateText value={product.rate_min} /> – <RateText value={product.rate_max} />
          </dd>
        </div>
        <div>
          <dt className="text-ink-muted">{T.term}</dt>
          <dd className="m-0 font-semibold">
            {T.months(product.term_min_months, product.term_max_months)}
          </dd>
        </div>
        <div>
          <dt className="text-ink-muted">{T.amount}</dt>
          <dd className="m-0 font-semibold">
            {formatMoney(product.amount_min)} – {formatMoney(product.amount_max)}
          </dd>
        </div>
      </dl>
      <p className="m-0 text-sm">
        {product.collateral_required ? T.collateralNeeded : T.noCollateral}
        {" · "}
        {product.is_revolving ? T.revolving : T.annuity}
      </p>
      <p className="m-0 text-sm text-ink-muted">
        {T.documents}:{" "}
        {product.required_documents.length
          ? product.required_documents.map((kind) => DOCUMENT_KIND[kind]).join(", ")
          : T.noDocuments}
      </p>
      {product.is_revolving ? null : (
        <Button variant="secondary" size="sm" className="self-start" onClick={onCalculate}>
          {T.calculate}
        </Button>
      )}
    </Card>
  );
}

function Calculator({
  products,
  product,
  onProduct,
}: {
  products: Product[];
  product: Product;
  onProduct: (code: string) => void;
}) {
  const middle = (Number(product.rate_min) + Number(product.rate_max)) / 2;
  const [amount, setAmount] = useState<string | null>(product.amount_min);
  const [term, setTerm] = useState(String(Math.min(12, product.term_max_months)));
  const [rate, setRate] = useState(formatDecimal(String(Math.round(middle * 1000) / 10)));
  const calculate = useMutation({
    mutationFn: async (body: Schemas["AnnuityRequest"]) =>
      unwrap(await api.POST("/api/calculators/annuity", { body })),
  });
  const fraction = percentToFraction(rate);
  const months = Number.parseInt(term, 10);
  const valid = Boolean(amount && fraction && months >= 1 && months <= 360);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || !amount || !fraction) return;
    calculate.mutate({ principal: amount, annual_rate: fraction, term_months: months });
  };
  const result = calculate.data;
  return (
    <Card>
      <CardTitle className="m-0">{T.calculatorTitle}</CardTitle>
      <p className="m-0 text-sm text-ink-muted">{T.calculatorHint}</p>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
        <Field label={T.product} className="min-w-56 flex-1">
          <NativeSelect value={product.code} onChange={(event) => onProduct(event.target.value)}>
            {products.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label={T.amount} className="min-w-44">
          <MoneyInput value={amount ?? ""} onValueChange={setAmount} />
        </Field>
        <Field label={T.termMonths} className="w-28">
          <Input
            inputMode="numeric"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
          />
        </Field>
        <Field label={T.ratePercent} className="w-32">
          <Input
            inputMode="decimal"
            value={rate}
            onChange={(event) => setRate(event.target.value)}
          />
        </Field>
        <Button type="submit" disabled={!valid} loading={calculate.isPending}>
          {T.calculate}
        </Button>
      </form>
      {calculate.isError ? (
        <p role="alert" className="m-0 text-status-danger">
          {errorMessage(calculate.error)}
        </p>
      ) : null}
      {result ? (
        <div className="flex flex-col gap-4">
          <dl className="m-0 grid grid-cols-3 gap-3">
            <div>
              <dt className="text-sm text-ink-muted">{T.payment}</dt>
              <dd className="m-0">
                <MoneyText value={result.payment} size="md" />
              </dd>
            </div>
            <div>
              <dt className="text-sm text-ink-muted">{T.totalPaid}</dt>
              <dd className="m-0">
                <MoneyText value={result.total_paid} size="md" />
              </dd>
            </div>
            <div>
              <dt className="text-sm text-ink-muted">{T.overpayment}</dt>
              <dd className="m-0">
                <MoneyText value={result.overpayment} size="md" />
              </dd>
            </div>
          </dl>
          <p className="m-0 text-sm text-ink-muted">{T.notAnOffer}</p>
          <details>
            <summary className="cursor-pointer text-sm font-medium">{T.schedule}</summary>
            <div className="mt-2 max-h-80 overflow-auto rounded-md border border-line">
              <table className="w-full border-collapse text-sm">
                <thead className="bg-sunken text-left text-xs text-ink-muted uppercase">
                  <tr>
                    <th className="px-3 py-2">№</th>
                    <th className="px-3 py-2 text-right">{T.payment}</th>
                    <th className="px-3 py-2 text-right">{T.interest}</th>
                    <th className="px-3 py-2 text-right">{T.principal}</th>
                    <th className="px-3 py-2 text-right">{T.balance}</th>
                  </tr>
                </thead>
                <tbody className="tabular">
                  {result.schedule.map((row) => (
                    <tr key={row.number} className="border-t border-line">
                      <td className="px-3 py-1.5">{row.number}</td>
                      <td className="px-3 py-1.5 text-right">{formatMoney(row.payment)}</td>
                      <td className="px-3 py-1.5 text-right">{formatMoney(row.interest)}</td>
                      <td className="px-3 py-1.5 text-right">{formatMoney(row.principal)}</td>
                      <td className="px-3 py-1.5 text-right">{formatMoney(row.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      ) : null}
    </Card>
  );
}

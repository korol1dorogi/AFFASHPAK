import { createBrowserRouter, Navigate } from "react-router";

import { RedirectIfAuthed, RequireAuth, RequireCompany, RequireKind } from "@/app/guards";
import { BankLayout, ClientLayout, PublicLayout } from "@/app/layouts";
import { NotFoundPage } from "@/app/NotFoundPage";
import { routes } from "@/app/routes";
import { NewApplicationPage } from "@/features/application-wizard/NewApplicationPage";
import { WizardPage } from "@/features/application-wizard/WizardPage";
import { ApplicationPage } from "@/features/applications/ApplicationPage";
import { ApplicationsPage } from "@/features/applications/ApplicationsPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { BankApplicationPage } from "@/features/bank-application/BankApplicationPage";
import { BankDashboardPage } from "@/features/bank-dashboard/BankDashboardPage";
import { BankDemoPage } from "@/features/bank-demo/BankDemoPage";
import { BankPolicyPage } from "@/features/bank-policy/BankPolicyPage";
import { BankQueuePage } from "@/features/bank-queue/BankQueuePage";
import { CompanyNewPage } from "@/features/company/CompanyNewPage";
import { CompanyPage } from "@/features/company/CompanyPage";
import { HealthPage } from "@/features/health/HealthPage";
import { HomePage } from "@/features/home/HomePage";
import { LandingPage } from "@/features/landing/LandingPage";
import { MatchPage } from "@/features/match/MatchPage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";
import { ProductsPage } from "@/features/products/ProductsPage";
import { SignPage } from "@/features/signing/SignPage";
import { StyleguidePage } from "@/features/styleguide/StyleguidePage";

/**
 * The route tree (docs/frontend.md §2–3). Each task replaces only its own page component;
 * adding or moving a route is the lead's change.
 */
export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { path: routes.landing, element: <LandingPage /> },
      { path: routes.status, element: <HealthPage /> },
      {
        element: <RedirectIfAuthed />,
        children: [
          { path: routes.login, element: <LoginPage /> },
          { path: routes.register, element: <RegisterPage /> },
        ],
      },
      ...(import.meta.env.DEV ? [{ path: routes.devUi, element: <StyleguidePage /> }] : []),
    ],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <RequireKind kind="client" />,
        children: [
          {
            element: <ClientLayout />,
            children: [
              { path: routes.companyNew, element: <CompanyNewPage /> },
              {
                element: <RequireCompany />,
                children: [
                  { path: routes.home, element: <HomePage /> },
                  { path: routes.company, element: <CompanyPage /> },
                  { path: routes.match, element: <MatchPage /> },
                  { path: routes.products, element: <ProductsPage /> },
                  { path: routes.applications, element: <ApplicationsPage /> },
                  { path: routes.applicationNew, element: <NewApplicationPage /> },
                  { path: "/app/applications/:id", element: <ApplicationPage /> },
                  { path: "/app/applications/:id/edit", element: <Navigate to="params" replace /> },
                  { path: "/app/applications/:id/edit/:step", element: <WizardPage /> },
                  { path: "/app/applications/:id/sign", element: <SignPage /> },
                  { path: routes.notifications, element: <NotificationsPage /> },
                ],
              },
            ],
          },
        ],
      },
      {
        element: <RequireKind kind="bank" />,
        children: [
          {
            element: <BankLayout />,
            children: [
              { path: routes.bank, element: <BankQueuePage /> },
              { path: "/bank/applications/:id", element: <BankApplicationPage /> },
              { path: routes.bankDashboard, element: <BankDashboardPage /> },
              { path: routes.bankDemo, element: <BankDemoPage /> },
              { path: routes.bankPolicy, element: <BankPolicyPage /> },
            ],
          },
        ],
      },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);

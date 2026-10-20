import { test } from "@playwright/test";

// Client and bank journeys = the 7 scenarios from docs/plan.md (personas: docs/demo.md,
// statuses: docs/state-machine.md). Each test becomes real when its task is done
// (docs/tasks.md "Готово, когда"); until then it stays fixme.
test.describe("scenario 1: coffee shop — overdraft, auto offer, signing, disbursement", () => {
  test.fixme("client logs in as the persona and sees the dashboard (C2, C8)", async () => {});
  test.fixme("match recommends an overdraft of 900 000 ₽ with reasons (C4)", async () => {});
  test.fixme("wizard prefills the application; director submits (C5)", async () => {});
  test.fixme("auto offer → accept → sign with the on-screen code → issued (C6, C7)", async () => {});
});

test.describe("scenario 2: supplier — factoring for a shipment", () => {
  test.fixme("factoring offer of 4 500 000 ₽ for the UPD amount → issued (C4, C7)", async () => {});
});

test.describe("scenario 3: seasonal store — counteroffer by DSCR", () => {
  test.fixme("asks 5.3 mln → counteroffer 2 009 314 ₽ with reasons → accepts → issued (C7)", async () => {});
});

test.describe("scenario 4: manufacturer — manual review and info request", () => {
  test.fixme("grade C → manual review; bank requests a document (B4, B5)", async () => {});
  test.fixme("client uploads the document and responds; bank approves (C6, B5)", async () => {});
});

test.describe("scenario 5: dependent supplier — decline with improvements", () => {
  test.fixme("decline shows reasons and what to improve (C6)", async () => {});
});

test.describe("scenario 6: company in liquidation — stop factor", () => {
  test.fixme("instant decline with the stop factor (L4, C6)", async () => {});
});

test.describe("scenario 7: BKI outage — manual review", () => {
  test.fixme("demo panel turns BKI off → application lands in manual review with a note (B7, L4)", async () => {});
});

test.describe("scenario 8: equipment without collateral — alternative product", () => {
  test.fixme("investment loan without collateral → leasing offer → issued (S6, D15)", async () => {});
});

test.describe("access", () => {
  test.fixme("another client cannot open this application (404) (L3)", async () => {});
});

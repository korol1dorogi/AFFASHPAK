import { test } from "@playwright/test";

// End-to-end client journey (docs/demo.md, docs/case.md F1…Fn).
// Each step becomes a real test when its task is done (docs/tasks.md: "Готово, когда" = this step).
// Steps are refined in phase 2 after the case text arrives.
test.describe("client journey", () => {
  test.fixme("1. client logs in and sees the dashboard with demo data", async () => {});
  test.fixme("2. assistant identifies the need and recommends a product with reasons", async () => {});
  test.fixme("3. recommendation prefills an application; the client confirms and submits", async () => {});
  test.fixme("4. client sees the preliminary evaluation with reasons", async () => {});
  test.fixme("5. bank officer sees the same application in the back office", async () => {});
  test.fixme("6. another user cannot open this application (404)", async () => {});
});

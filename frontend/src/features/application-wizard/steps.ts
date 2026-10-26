import type { WizardStep } from "@/app/routes";

export const STEP_LABEL: Record<WizardStep, string> = {
  params: "Параметры",
  business: "Сведения о компании",
  documents: "Документы",
  review: "Проверка и отправка",
};

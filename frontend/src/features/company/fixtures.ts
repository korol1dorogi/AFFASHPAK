import type { Schemas } from "@/api/client";

/** Synthetic ЕГРЮЛ record (демо), shaped like persona 4's company. */
export function registryRecord(
  changes: Partial<Schemas["RegistryRecord"]> = {},
): Schemas["RegistryRecord"] {
  return {
    inn: "0001000042",
    ogrn: "1260000000042",
    legal_form: "ooo",
    name: "ООО «Дубрава Мебель» (демо)",
    okved: "31.09",
    okved_name: "Производство прочей мебели",
    registered_at: "2014-10-01",
    region: "Демо-область",
    address: "г. Демо, ул. Примерная, 4",
    registry_status: "active",
    director_name: "Пётр Демо",
    ...changes,
  };
}

export function company(changes: Partial<Schemas["Company"]> = {}): Schemas["Company"] {
  return { ...registryRecord(), id: 4, is_demo: true, my_role: "signatory", ...changes };
}

export function me(changes: Partial<Schemas["Me"]> = {}): Schemas["Me"] {
  return {
    id: 10,
    username: "demo_furniture_maker",
    full_name: "Пётр Демо",
    kind: "client",
    company_id: 4,
    company_role: "signatory",
    is_demo: true,
    ...changes,
  };
}

export const members: Schemas["Member"][] = [
  {
    id: 1,
    user: { id: 10, full_name: "Пётр Демо" },
    role: "signatory",
    position: "Генеральный директор",
  },
  {
    id: 2,
    user: { id: 11, full_name: "Ольга Демо" },
    role: "preparer",
    position: "Главный бухгалтер",
  },
];

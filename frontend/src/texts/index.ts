/**
 * All interface texts (docs/frontend.md §5, task D8 owns the wording).
 * Keyed by enum values from the contract: a new status or action in docs/openapi.yaml fails
 * the type check here until it gets its text.
 */
import type { Schemas } from "@/api/client";
import type { operations } from "@/api/schema";
import type { BankTab } from "@/app/routes";

export const PRODUCT_NAME = "Оборот";

export type StatusGroup = "action" | "progress" | "success" | "danger" | "neutral";

export interface StatusText {
  label: string;
  group: StatusGroup;
  /** «Что это значит» — для клиента. */
  meaning: string;
  /** «Что дальше» — для клиента. */
  next: string;
}

export const STATUS: Record<Schemas["ApplicationStatus"], StatusText> = {
  draft: {
    label: "Черновик",
    group: "action",
    meaning: "Заявка ещё не отправлена в банк.",
    next: "Проверьте данные и отправьте заявку — черновик сохраняется сам.",
  },
  submitted: {
    label: "Отправлена",
    group: "progress",
    meaning: "Заявка в банке, скоро начнётся проверка.",
    // TODO(L4): until the pipeline runs, nothing moves the status on by itself; once L4 is
    // merged, return to «Ничего делать не нужно — обновим статус сами.»
    next: "Заявка в банке. Проверка запускается — статус обновится здесь.",
  },
  processing: {
    label: "Проверяем",
    group: "progress",
    meaning: "Проверяем данные в реестрах, кредитной истории и по счёту.",
    next: "Обычно это занимает до минуты.",
  },
  manual_review: {
    label: "У сотрудника банка",
    group: "progress",
    meaning: "Заявку смотрит сотрудник банка.",
    next: "Обычно это занимает до одного дня. Если понадобятся документы, пришлём уведомление.",
  },
  info_requested: {
    label: "Нужны уточнения",
    group: "action",
    meaning: "Банку не хватает данных или документа.",
    next: "Ответьте на запрос ниже — без этого проверка не продолжится.",
  },
  offer: {
    label: "Есть предложение",
    group: "action",
    meaning: "Банк готов дать деньги на условиях ниже.",
    next: "Примите предложение, чтобы перейти к подписанию, или откажитесь.",
  },
  signing: {
    label: "Подписание",
    group: "action",
    meaning: "Предложение принято, осталось подписать договор.",
    next: "Подпишите договор кодом, который покажем на экране.",
  },
  signed: {
    label: "Договор подписан",
    group: "success",
    meaning: "Договор подписан, деньги отправляем на счёт.",
    next: "Обычно деньги приходят в течение нескольких минут.",
  },
  issued: {
    label: "Деньги выданы",
    group: "success",
    meaning: "Деньги поступили на счёт.",
    next: "Готово. График платежей — в разделе заявки.",
  },
  declined: {
    label: "Отказ",
    group: "danger",
    meaning: "Сейчас банк не может дать деньги.",
    next: "Посмотрите причины и что можно улучшить — затем подайте заявку снова.",
  },
  cancelled: {
    label: "Отозвана",
    group: "neutral",
    meaning: "Заявка отозвана.",
    next: "Чтобы получить деньги, подберите финансирование заново.",
  },
};

export const ACTION: Record<Schemas["ApplicationAction"], string> = {
  edit: "Изменить заявку",
  upload_document: "Загрузить документ",
  submit: "Отправить в банк",
  cancel: "Отозвать заявку",
  respond_info: "Ответить банку",
  accept_offer: "Принять и подписать",
  decline_offer: "Отказаться",
  sign: "Подписать договор",
  assign: "Взять в работу",
  approve: "Одобрить",
  counteroffer: "Иные условия",
  request_info: "Запросить информацию",
  decline: "Отказать",
};

export interface NeedText {
  title: string;
  hint: string;
}

export const NEED: Record<Schemas["NeedType"], NeedText> = {
  cash_gap: {
    title: "Не хватает денег до поступлений",
    hint: "Зарплата 5-го, а клиенты платят позже",
  },
  receivable_delay: {
    title: "Отгрузили, а покупатель платит позже",
    hint: "Есть УПД, оплата через 30–90 дней",
  },
  working_capital: { title: "Нужно закупиться к сезону", hint: "Товар, сырьё, запасы" },
  capex: { title: "Покупаю оборудование или транспорт", hint: "Станок, машина, помещение" },
};

export const PRODUCT_KIND: Record<Schemas["ProductKind"], string> = {
  overdraft: "Овердрафт",
  factoring: "Факторинг",
  working_capital_loan: "Кредит на пополнение оборотных средств",
  investment_loan: "Инвестиционный кредит",
  leasing: "Лизинг",
};

export const DOCUMENT_KIND: Record<Schemas["DocumentKind"], string> = {
  bank_statement: "Выписка по счёту",
  financial_report: "Бухгалтерская отчётность",
  tax_return: "Налоговая декларация",
  contract: "Договор",
  invoice: "Счёт",
  shipment_document: "Документ отгрузки (УПД)",
  other: "Другой документ",
};

export const DECISION_OUTCOME: Record<Schemas["DecisionOutcome"], string> = {
  offer: "Одобрено",
  counteroffer: "Иные условия",
  alternative_product: "Другой продукт",
  manual_review: "Нужен сотрудник банка",
  info_requested: "Нужны уточнения",
  declined: "Отказ",
};

export interface MetricText {
  /** Понятное название для клиента. */
  title: string;
  /** Пояснение «что это» — без терминов. */
  hint: string;
  /** Как показывать значение. */
  format: "money" | "decimal" | "percent" | "months" | "days" | "points" | "text";
}

/**
 * Reason.metric → text: every metric apps/scoring and apps/recommendations can return
 * (the list is pinned in texts.test.ts). An unknown metric gets UNKNOWN_METRIC_TITLE, never its code.
 */
export const METRIC: Record<string, MetricText> = {
  overdraft_limit: {
    title: "Лимит от оборота",
    hint: "Доля от среднего месячного поступления на счёт без своих переводов и возвратов.",
    format: "money",
  },
  factoring_advance: {
    title: "Финансирование под отгрузку",
    hint: "Доля от суммы отгрузки по документу ЭДО.",
    format: "money",
  },
  factoring_commission: {
    title: "Комиссия за факторинг",
    hint: "Сколько стоит получить деньги раньше покупателя.",
    format: "money",
  },
  working_capital_need: {
    title: "Потребность в оборотных средствах",
    hint: "Запасы и долги покупателей минус долги поставщикам — столько денег сейчас в обороте.",
    format: "money",
  },
  max_loan_by_dscr: {
    title: "Сумма, которую выдержит денежный поток",
    hint: "Больше этой суммы платёж не потянуть: поток должен покрывать платежи хотя бы в 1,25 раза.",
    format: "money",
  },
  dscr: {
    title: "Покрытие платежей потоком (DSCR)",
    hint: "Во сколько раз денежный поток больше платежей по долгам.",
    format: "decimal",
  },
  dscr_after: {
    title: "Покрытие платежей с новым кредитом",
    hint: "Во сколько раз денежный поток больше всех платежей — уже с новым кредитом.",
    format: "decimal",
  },
  debt_to_ebitda: {
    title: "Долговая нагрузка (Долг / EBITDA)",
    hint: "Сколько лет операционной прибыли нужно, чтобы отдать долги.",
    format: "decimal",
  },
  revenue_trend: {
    title: "Выручка год к году",
    hint: "Последние три месяца против тех же месяцев прошлого года.",
    format: "percent",
  },
  counterparty_concentration: {
    title: "Доля крупнейшего покупателя",
    hint: "Какая часть поступлений приходит от одного плательщика.",
    format: "percent",
  },
  business_age_months: {
    title: "Возраст бизнеса",
    hint: "Сколько месяцев прошло с регистрации.",
    format: "months",
  },
  bki_history: {
    title: "Кредитная история",
    hint: "Были ли просрочки по кредитам.",
    format: "text",
  },
  transparent_business: {
    title: "Проверка ФНС",
    hint: "Массовый адрес или руководитель, долги по налогам.",
    format: "text",
  },
  score_total: { title: "Оценка риска", hint: "Сумма баллов балльной карты.", format: "points" },
  // Stop factors (apps/scoring/stop_factors.py)
  registry_status: {
    title: "Статус в реестре",
    hint: "Действует компания, ликвидируется или уже ликвидирована — по ЕГРЮЛ/ЕГРИП.",
    format: "text",
  },
  egrul_found: {
    title: "Запись в реестре",
    hint: "Есть ли компания в ЕГРЮЛ/ЕГРИП.",
    format: "text",
  },
  ebitda: {
    title: "Операционная прибыль (EBITDA)",
    hint: "Прибыль до процентов, налогов и амортизации.",
    format: "money",
  },
  bki_current_overdue_days: {
    title: "Текущая просрочка",
    hint: "Сколько дней сейчас просрочен платёж по кредиту.",
    format: "days",
  },
  // Product fit in the match (apps/recommendations/service.py)
  product_requirements: {
    title: "Требования продукта",
    hint: "Правовая форма, возраст бизнеса и залог.",
    format: "text",
  },
  term_months: {
    title: "Срок",
    hint: "Какой срок допускает продукт.",
    format: "months",
  },
  amount_min: {
    title: "Минимальная сумма продукта",
    hint: "Меньше этой суммы продукт не выдаётся.",
    format: "money",
  },
  amount_max: {
    title: "Максимальная сумма продукта",
    hint: "Больше этой суммы продукт не выдаётся.",
    format: "money",
  },
};

export const UNKNOWN_METRIC_TITLE = "Дополнительная проверка";

/** Title of a reason for the client; a metric code never reaches the screen. */
export function metricTitle(metric: string): string {
  return METRIC[metric]?.title ?? UNKNOWN_METRIC_TITLE;
}

// ── Bank queue (B3) ──

export type QueueOrdering = NonNullable<
  NonNullable<operations["listBankApplications"]["parameters"]["query"]>["ordering"]
>;

export const QUEUE_ORDERING: Record<QueueOrdering, string> = {
  status_changed_at: "Дольше всего в статусе",
  "-status_changed_at": "Недавно сменили статус",
  requested_amount: "Сумма: по возрастанию",
  "-requested_amount": "Сумма: по убыванию",
  "-created_at": "Сначала новые",
  created_at: "Сначала старые",
};

export const BANK_QUEUE = {
  title: "Очередь заявок",
  subtitle: "Заявки клиентов по статусам. Список обновляется сам раз в 15 секунд.",
  statusFilter: "Фильтр по статусу",
  allStatuses: "Все",
  statusChip: (label: string, count: number) => `${label}: ${count}`,
  filters: "Фильтры очереди",
  search: "Поиск",
  searchPlaceholder: "ИНН или название",
  product: "Продукт",
  allProducts: "Все продукты",
  grade: "Грейд",
  anyGrade: "Любой грейд",
  assignee: "Исполнитель",
  assigneeAll: "Все",
  assigneeMe: "Мои",
  assigneeNone: "Не назначены",
  assigneeId: (id: string) => `Сотрудник №${id}`,
  minHours: "В статусе",
  anyHours: "Сколько угодно",
  moreThanHours: (hours: number) => `Больше ${hours} ч`,
  ordering: "Сортировка",
  resetFilters: "Сбросить фильтры",
  table: "Заявки в очереди",
  columns: {
    id: "№",
    company: "Компания",
    product: "Продукт",
    amount: "Сумма",
    status: "Статус",
    grade: "Грейд",
    assignee: "Исполнитель",
    inStatus: "В статусе",
  },
  openApplication: (id: number) => `Заявка №${id}`,
  inn: (inn: string) => `ИНН ${inn}`,
  hoursInStatus: (hours: number) => `${hours} ч`,
  overdue: "дольше суток",
  sourceUnavailable: "Источник недоступен",
  unassigned: "Не назначен",
  noValue: "—",
  pagination: "Страницы очереди",
  previous: "Назад",
  next: "Вперёд",
  pageOf: (page: number, pages: number) => `Страница ${page} из ${pages}`,
  total: (count: number) => `всего ${count}`,
  refreshing: "Обновляем…",
  loading: "Загружаем очередь",
  empty: "Заявок с такими фильтрами нет",
  emptyText: "Измените условия или сбросьте фильтры.",
  emptyQueue: "В очереди пока нет заявок",
  error: "Не получилось загрузить очередь",
} as const;

// ── Bank application card (B4) ──

export const BANK_TAB: Record<BankTab, string> = {
  application: "Заявка",
  client: "Клиент",
  checks: "Проверки",
  scoring: "Скоринг",
  documents: "Документы",
  journal: "Журнал",
};

export const CHECK_SOURCE: Record<Schemas["CheckSource"], string> = {
  egrul: "ЕГРЮЛ / ЕГРИП",
  transparent_business: "«Прозрачный бизнес» ФНС",
  bki: "Бюро кредитных историй",
  bank_account: "Расчётный счёт",
};

export const CHECK_STATUS: Record<Schemas["Check"]["status"], string> = {
  ok: "В порядке",
  warning: "Есть замечания",
  failed: "Не пройдена",
  unavailable: "Источник не ответил",
};

export const DECIDED_BY: Record<Schemas["Decision"]["decided_by"], string> = {
  auto: "Система",
  officer: "Сотрудник банка",
};

export const OFFER_STATUS: Record<Schemas["Offer"]["status"], string> = {
  active: "Действует",
  accepted: "Принят клиентом",
  declined: "Клиент отказался",
  superseded: "Заменён новым",
};

export const INFO_REQUEST_ORIGIN: Record<Schemas["InfoRequest"]["origin"], string> = {
  validation: "Автоматическая проверка полноты",
  officer: "Запрос сотрудника",
};

export const INFO_REQUEST_STATUS: Record<Schemas["InfoRequest"]["status"], string> = {
  open: "Ждёт ответа",
  answered: "Клиент ответил",
};

export const LEGAL_FORM: Record<Schemas["LegalForm"], string> = {
  ip: "ИП",
  ooo: "ООО",
};

export const REGISTRY_STATUS: Record<Schemas["RegistryStatus"], string> = {
  active: "Действует",
  liquidating: "В процессе ликвидации",
  liquidated: "Ликвидирована",
};

export const SNAPSHOT_SOURCE: Record<Schemas["SnapshotSource"], string> = {
  case: "Данные кейса",
  demo: "Демо-данные",
  simulator: "Симулятор счёта",
  manual: "Введено вручную",
};

type SnapshotMetric = Exclude<keyof Schemas["FinancialSnapshot"], "id" | "period" | "source">;

/** Snapshot metrics in display order: money, then ratios shown as they are. */
export const SNAPSHOT_FIELD: Record<SnapshotMetric, { title: string; format: "money" | "ratio" }> =
  {
    cleaned_credit_turnover: {
      title: "Очищенный кредитовый оборот, в месяц",
      format: "money",
    },
    cfads: { title: "Денежный поток на обслуживание долга (CFADS), в месяц", format: "money" },
    debt_service: { title: "Платежи по текущим долгам, в месяц", format: "money" },
    revenue: { title: "Выручка за 12 мес", format: "money" },
    cogs: { title: "Себестоимость за 12 мес", format: "money" },
    ebitda: { title: "EBITDA за 12 мес", format: "money" },
    debt: { title: "Долг", format: "money" },
    cash: { title: "Деньги на счетах", format: "money" },
    receivables: { title: "Дебиторская задолженность", format: "money" },
    inventory: { title: "Запасы", format: "money" },
    payables: { title: "Кредиторская задолженность", format: "money" },
    revenue_trend: { title: "Выручка год к году (коэффициент)", format: "ratio" },
    counterparty_concentration: {
      title: "Доля крупнейшего покупателя (коэффициент)",
      format: "ratio",
    },
  };

export const BANK_CARD = {
  notFoundTitle: "Заявка не найдена",
  notFoundText: "Возможно, ссылка устарела. Вернитесь к очереди и откройте заявку оттуда.",
  forbiddenTitle: "Нет доступа",
  forbiddenText: "Карточку заявки видят только сотрудники банка.",
  backToQueue: "К очереди",
  title: (id: number) => `Заявка № ${id}`,
  tabsLabel: "Разделы карточки",
  actionsLabel: "Действия сотрудника",
  noValue: "нет данных",
  noProduct: "Продукт не выбран",
  noGrade: "нет",
  noAssignee: "Не назначен",
  sourceUnavailable:
    "Один из источников не ответил — данные проверки неполные. Это не отказ: проверьте вручную.",
  header: {
    amount: "Сумма",
    product: "Продукт",
    grade: "Грейд",
    assignee: "Исполнитель",
  },
  application: {
    params: "Параметры заявки",
    need: "Потребность",
    purpose: "Цель",
    requested: "Запрошено",
    term: "Срок",
    invoice: "Сумма отгрузки",
    collateral: "Залог",
    noCollateral: "Без залога",
    created: "Создана",
    submitted: "Отправлена",
    statusChanged: "Статус изменён",
    notSubmitted: "Ещё не отправлена",
    offer: "Оффер",
    offerRequested: "Клиент просил",
    rate: "Ставка",
    payment: "Платёж в месяц",
    revolvingPayment: "Зависит от использования",
    expires: "Действует до",
    counteroffer: "Иные условия",
    productChanged: "Другой продукт",
    infoRequests: "Запросы информации",
    documentsNeeded: "Документы",
    clientAnswer: "Ответ клиента",
    decisions: "История решений",
    noDecisions: "Решений пока нет",
    noDecisionsText: "Решение появится после автоматической проверки или действия сотрудника.",
    decidedBy: "Кто решил",
    preliminary: "предварительная оценка",
    policy: "Версия правил",
    comment: "Комментарий клиенту",
    reasons: "Причины решения",
    offerReasons: "Почему такие условия",
    months: (n: number) => `${n} мес`,
  },
  client: {
    requisites: "Реквизиты",
    requisitesNote: "из ЕГРЮЛ",
    inn: "ИНН",
    ogrn: "ОГРН",
    legalForm: "Форма",
    name: "Название",
    okved: "ОКВЭД",
    registered: "Дата регистрации",
    region: "Регион",
    address: "Адрес",
    registryStatus: "Статус в реестре",
    director: "Руководитель",
    members: "Сотрудники и роли",
    noMembers: "Сотрудников нет",
    snapshot: "Финансовый снимок",
    period: "Период",
    source: "Источник",
    noSnapshot: "Снимка нет",
    noSnapshotText: "Клиент не подключил счёт — метрики посчитать не из чего.",
  },
  checks: {
    empty: "Проверки ещё не запускались",
    emptyText:
      "Реестры, «Прозрачный бизнес», БКИ и счёт проверяются автоматически после отправки заявки.",
    missing: "Нет результата",
    checkedAt: "Проверено",
    list: "Проверки по источникам",
  },
  scoring: {
    title: "Разложение скоринга",
    note: "Скоринг — оценка риска заёмщика, а не решение по заявке.",
    empty: "Скоринг ещё не считали",
    emptyText: "Балльная карта считается после проверок источников.",
    total: "Итого",
    grade: "Грейд",
    model: "Версия модели",
    factors: "Факторы скоринга",
    points: (points: number, max?: number) =>
      max === undefined ? `${points} б.` : `${points} из ${max}`,
    outOf: (total: number) => `${total} из 100`,
  },
  documents: {
    empty: "Документов нет",
    emptyText: "Клиент ещё не загрузил документы к заявке.",
    download: (filename: string) => `Скачать ${filename}`,
    downloadShort: "Скачать",
  },
  journal: {
    title: "Журнал",
    commentLabel: "Внутренний комментарий",
    commentHint: "Клиент его не увидит.",
    commentRequired: "Напишите комментарий",
    commentTooLong: "Не длиннее 2000 символов",
    send: "Добавить в журнал",
    sent: "Комментарий добавлен",
  },
} as const;

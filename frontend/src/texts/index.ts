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
    next: "Ничего делать не нужно — обновим статус сами.",
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
    meaning:
      "Банк сделал предложение — условия ниже. Это ещё не договор: условия закрепятся, когда вы его подпишете.",
    next: "Примите предложение, чтобы перейти к подписанию, или откажитесь.",
  },
  signing: {
    label: "Подписание",
    group: "action",
    meaning: "Предложение принято, осталось подписать договор.",
    next: "Подпишите договор кодом с экрана. Подписать может только подписант компании.",
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
    next: "Готово. Условия финансирования — на странице заявки.",
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
    meaning: "Заявка закрыта: вы отозвали её или отказались от предложения.",
    next: "Чтобы получить деньги, подберите финансирование заново.",
  },
};

export const ACTION: Record<Schemas["ApplicationAction"], string> = {
  edit: "Изменить заявку",
  upload_document: "Загрузить документ",
  submit: "Отправить в банк",
  hand_off: "Передать директору",
  cancel: "Отозвать заявку",
  respond_info: "Ответить банку",
  accept_offer: "Принять и подписать",
  decline_offer: "Отказаться от предложения",
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
  capex: { title: "Нужно купить оборудование или транспорт", hint: "Станок, машина, помещение" },
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

/** 1 балл, 2 балла, 5 баллов, 11 баллов, 21 балл. */
function pointsWord(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return "балл";
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return "балла";
  return "баллов";
}

/** XP2: «как получить одобрение» при отказе по грейду. */
export const APPROVAL_PLAN = {
  title: "Как получить одобрение",
  summary: (current: number, grade: string, target: number, targetGrade: string) =>
    `Сейчас ${current} ${pointsWord(current)} из 100 — грейд ${grade}. Эти шаги дают ${target} — ` +
    `грейд ${targetGrade}: ${
      targetGrade === "C"
        ? "с ним заявку рассмотрит сотрудник банка."
        : "с ним банк сможет одобрить заявку."
    }`,
  points: (n: number) => `+${n} ${pointsWord(n)}`,
  note: "Предварительная оценка по данным вашего счёта, не решение банка.",
} as const;

function daysWord(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return "день";
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return "дня";
  return "дней";
}

/**
 * BKI1: «Кредитная история понятным языком». From the live interview L01 (docs/research.md):
 * «отказали по кредитной истории — что и откуда, никто не знает; как исправить, никто не знает».
 * Facts about the bureau report follow 218-FZ «О кредитных историях».
 */
export const CREDIT_HISTORY = {
  title: "Кредитная история: что увидел банк",
  days: (n: number) => `${n} ${daysWord(n)}`,
  currentStop: (days: number, limit: number) =>
    `Сейчас есть просрочка ${days} ${daysWord(days)}. Пока она больше ${limit} ${daysWord(limit)}, ` +
    "банк не может выдать деньги — это не зависит от остальных показателей.",
  /** The backend's own sentence («Сейчас есть просрочка по кредиту: 12 дней») + why it matters. */
  current: (message: string) => `${message}. Это сильнее всего снижает оценку кредитной истории.`,
  pastOver: (days: number, limit: number) =>
    `В истории была просрочка ${days} ${daysWord(days)} — больше порога банка ` +
    `${limit} ${daysWord(limit)}, поэтому оценка кредитной истории низкая.`,
  pastWithin: (days: number, limit: number) =>
    `В истории была просрочка ${days} ${daysWord(days)} — в пределах порога банка ` +
    `${limit} ${daysWord(limit)}. Это не причина отказа, но чистая история дала бы больше баллов.`,
  source:
    "Откуда это: сведения из бюро кредитных историй, которые банк запросил с вашего согласия при " +
    "отправке заявки. Банк их не меняет — исправить ошибку можно только через бюро.",
  stepsTitle: "Что можно сделать",
  payCurrent: "Погасите текущую просрочку — после этого заявку можно подать снова.",
  steps: [
    "Узнайте, в каких бюро хранится история (для ИП — ваша, для ООО — компании): бесплатный запрос на Госуслугах «Сведения о бюро кредитных историй».",
    "Закажите отчёт в каждом из этих бюро: дважды в год — бесплатно. В отчёте видно, у какого кредитора и когда была просрочка.",
    "Нашли ошибку или погашенная просрочка числится открытой — подайте в бюро заявление об исправлении. Бюро проверит сведения у кредитора и ответит в течение 20 рабочих дней.",
  ],
  attach: (finished: boolean) =>
    finished
      ? "К новой заявке приложите справку кредитора о погашении (тип документа «Другой документ») — сотрудник банка её учтёт."
      : "Приложите к заявке справку кредитора о погашении (тип документа «Другой документ») — сотрудник банка её учтёт.",
} as const;

/** UX1: landing — the jury understands the product in 30 seconds and signs in as a persona. */
export const LANDING = {
  eyebrow: "Кредитный кабинет для малого бизнеса",
  title: "Деньги для бизнеса — под вашу задачу",
  lead:
    "Расскажите, зачем нужны деньги. Кабинет подберёт инструмент — овердрафт, факторинг, кредит на " +
    "пополнение оборотных средств, инвестиционный кредит или лизинг — посчитает сумму по обороту " +
    "на счёте и объяснит каждую цифру. Заявка, проверки, предложение и подписание — в одном месте, без визита в банк.",
  tryPersona: "Войти за демо-компанию",
  signIn: "Войти по логину",
  ownCompany: "Своя компания?",
  register: "Зарегистрируйтесь — нужен только ИНН",
  example: {
    title: "Пример: кофейня, кассовый разрыв",
    product: "Овердрафт",
    amount: "900000.00",
    caption: "Лимит по обороту на счёте — и почему именно столько",
    note: "Предварительная оценка, не решение банка",
  },
  clientTitle: "Путь клиента — три шага",
  clientSteps: [
    {
      title: "Скажите, что случилось",
      text: "«Зарплата 5-го, а покупатели платят 10-го» — кабинет или ассистент переведут это в инструмент: кассовый разрыв → овердрафт, отсрочка оплаты → факторинг, оборудование → кредит или лизинг.",
    },
    {
      title: "Получите сумму с объяснением",
      text: "Сумма, ставка и платёж — по данным счёта и реестров, с показателями и порогами. Заявка заполняется сама: реквизиты из ЕГРЮЛ, ничего не вводите дважды.",
    },
    {
      title: "Следите за заявкой и подпишите",
      text: "Статус и «что дальше» на каждом шаге. Предложение, иные условия или отказ — всегда с причинами и планом, как получить одобрение. Подпись кодом с экрана.",
    },
  ],
  bankTitle: "Путь банка — та же заявка",
  bankSteps: [
    {
      title: "Очередь со сроками",
      text: "Фильтры по статусу, продукту и грейду, срок реакции по каждой заявке.",
    },
    {
      title: "Карточка с проверками",
      text: "ЕГРЮЛ, ФНС, БКИ и счёт, скоринг по факторам, кредитное заключение.",
    },
    {
      title: "Решение сотрудника",
      text: "Одобрить, предложить иные условия, запросить документ или отказать с причинами.",
    },
    {
      title: "Дашборд конвейера",
      text: "Воронка, время в статусах, доля автоматических решений.",
    },
  ],
  whyTitle: "Чем отличается",
  quote:
    "«Отказали по причине плохой кредитной истории. Что и откуда — никто не знает. Как исправить — никто не знает»",
  quoteSource: "Предприниматель, живое интервью",
  why: [
    {
      title: "Каждая цифра объяснена",
      text: "Причина — это показатель, значение и порог. При отказе — план «как получить одобрение», при проблеме с кредитной историей — что увидел банк и что делать.",
    },
    {
      title: "Ассистент помогает, но не решает",
      text: "Модель с открытыми весами работает только через инструменты кабинета от вашего имени. Заявку отправляете вы сами.",
    },
    {
      title: "Без звонков, SMS и навязанных услуг",
      text: "Всё в кабинете: уведомления внутри, подпись кодом с экрана, условия без скрытых платежей видны до подписания.",
    },
  ],
  personasTitle: "Попробуйте за демо-компанию",
  personasLead:
    "Синтетические компании: у каждой свой сценарий. Вход в один клик, пароль не нужен.",
  personaClient: (scenario: number) => `Сценарий ${scenario}`,
  personaBank: "Рабочее место банка",
  personaSignIn: "Войти",
  personasOff: "Демо-компании выключены на этом стенде. Войдите по логину или зарегистрируйтесь.",
  links: { swagger: "Контракт API (Swagger)", status: "Состояние системы" },
  disclaimer:
    "Прототип для хакатона: все компании и данные синтетические и помечены «демо», внешние источники — симуляторы.",
} as const;

/** What the jury sees for each demo persona (docs/demo.md); unknown codes show only the title. */
export const PERSONA_STORY: Record<string, string> = {
  coffee_shop: "Кассовый разрыв → овердрафт 900 000 ₽ → предложение сразу → подпись → деньги",
  retail_supplier: "Покупатель платит через 60 дней → факторинг под УПД",
  garden_store: "Просит 5,3 млн на сезон → иные условия с причинами и «Что если»",
  furniture_maker: "Станок, просрочка в БКИ → сотрудник банка → запрос документа → одобрение",
  accountant: "Бухгалтер готовит заявку мебельной фабрики, а подписывает директор",
  dependent_supplier: "Один крупный покупатель, выручка падает → отказ с планом одобрения",
  liquidating_company: "Компания в ликвидации → мгновенный отказ по стоп-фактору",
  bki_outage: "БКИ не отвечает → ручное рассмотрение, а не отказ",
  equipment_no_collateral: "Оборудование без залога → вместо кредита лизинг",
  bank: "Очередь, карточка заявки, решения, дашборд и демо-панель сбоев",
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
    hint: "Доля от суммы отгрузки по УПД.",
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
    hint: "Больше этой суммы платёж не потянуть: денежного потока должно хватать на все платежи с запасом.",
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
    hint: "Нет ли долгов по налогам и не зарегистрировано ли на тот же адрес или руководителя много других компаний — по данным ФНС.",
    format: "text",
  },
  score_total: {
    title: "Оценка риска",
    hint: "Сумма баллов по всем показателям: чем больше, тем лучше.",
    format: "points",
  },
  // Automatic check (apps/pipeline): a source did not answer or the check could not finish
  source_egrul: {
    title: "ЕГРЮЛ / ЕГРИП",
    hint: "Источник не ответил — заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  source_transparent_business: {
    title: "«Прозрачный бизнес» (ФНС)",
    hint: "Источник не ответил — заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  source_bki: {
    title: "Бюро кредитных историй",
    hint: "Источник не ответил — заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  source_bank_account: {
    title: "Выписка по счёту",
    hint: "Счёт не подключён или выписка не пришла — заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  missing_key_metrics: {
    title: "Данные для автоматической оценки",
    hint: "Не хватает данных по счёту для автоматической оценки — заявку посмотрит сотрудник банка. Это не отказ.",
    format: "decimal",
  },
  automatic_check: {
    title: "Автоматическая проверка",
    hint: "Проверка не завершилась — заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
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
    title: "Операционная прибыль",
    hint: "Прибыль от основной работы за год — до процентов, налогов и износа оборудования.",
    format: "money",
  },
  bki_current_overdue_days: {
    title: "Текущая просрочка",
    hint: "Сколько дней сейчас просрочен платёж по кредиту.",
    format: "days",
  },
  accounts_suspended: {
    title: "Операции по счетам",
    hint: "Не приостановила ли налоговая операции по счетам компании — с такими счетами кредит не выдать.",
    format: "text",
  },
  // ЕГРЮЛ marks that send the application to an officer (apps/scoring/review.py, SRC5)
  egrul_unreliable_address: {
    title: "Достоверность адреса",
    hint: "Есть ли в ЕГРЮЛ отметка, что адрес компании недостоверен. Это не отказ: проверит сотрудник.",
    format: "text",
  },
  egrul_unreliable_director: {
    title: "Достоверность сведений о руководителе",
    hint: "Есть ли в ЕГРЮЛ отметка, что сведения о руководителе недостоверны. Это не отказ: проверит сотрудник.",
    format: "text",
  },
  egrul_pending_exclusion: {
    title: "Исключение из реестра",
    hint: "Не готовит ли налоговая исключение компании из ЕГРЮЛ. Это не отказ: проверит сотрудник.",
    format: "text",
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
  /** Past the status norm (XP4): shown as text next to the icon, not by colour alone. */
  overdue: (hours: number) => (hours > 0 ? `просрочено на ${hours} ч` : "просрочено, меньше часа"),
  overdueOnly: "Только просроченные",
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
  transparent_business: "«Прозрачный бизнес» (ФНС)",
  bki: "Бюро кредитных историй",
  bank_account: "Выписка по счёту",
};

export const CHECK_STATUS: Record<Schemas["Check"]["status"], string> = {
  ok: "В порядке",
  warning: "Есть замечания",
  failed: "Не пройдена",
  unavailable: "Источник не ответил",
  not_found: "Нет в реестре",
  restricted: "Сведения скрыты",
  consent_missing: "Не запрашивали — нет согласия",
};

type CheckStatus = Schemas["Check"]["status"];

/**
 * «Что это значит» под статусом проверки (SRC6) — по docs/decision-model.md: стоп-факторы (§2),
 * П3 и «Нет данных — не отказ» (§5). Текст для пары «источник + статус», иначе — для статуса.
 */
export const CHECK_MEANING: {
  status: Record<CheckStatus, string>;
  bySource: Partial<Record<Schemas["CheckSource"], Partial<Record<CheckStatus, string>>>>;
  notConnected: string;
} = {
  status: {
    ok: "Источник ответил, замечаний нет.",
    warning: "Источник ответил и нашёл замечания — они ниже.",
    failed: "Проверка не пройдена — это отказ (стоп-фактор).",
    unavailable:
      "Источник не ответил. Это не отказ: заявку рассматривает сотрудник — проверьте вручную.",
    not_found: "Компании нет в реестре — это отказ (стоп-фактор): её не проверить.",
    restricted:
      "Источник ответил, но сведения скрыты. Это не отказ: заявку рассматривает сотрудник.",
    consent_missing:
      "Клиент не дал согласие на запрос в БКИ, поэтому бюро не спрашивали (218-ФЗ). Это не отказ: заявку рассматривает сотрудник.",
  },
  bySource: {
    egrul: {
      ok: "Компания действует, отметок о недостоверности и предстоящем исключении нет.",
      warning:
        "Компания ликвидируется — это отказ (стоп-фактор). Или в реестре есть отметка о недостоверности либо предстоящем исключении — тогда заявку проверяет сотрудник.",
      // Before SRC2 «no such INN» was stored as failed.
      failed: "Компании нет в реестре — это отказ (стоп-фактор): её не проверить.",
    },
    transparent_business: {
      ok: "Массового адреса и руководителя, налогового долга и приостановки операций по счетам нет.",
      warning:
        "Есть массовый адрес или руководитель либо налоговый долг — это снижает баллы. Приостановка операций по счетам — отказ (стоп-фактор).",
    },
    bki: {
      ok: "Текущей просрочки нет, прошлая — не больше 30 дней.",
      warning: "Прошлая просрочка больше 30 дней или текущая до 30 дней — это снижает баллы.",
      failed: "Текущая просрочка больше 30 дней — это отказ (стоп-фактор).",
    },
    bank_account: {
      ok: "Выписка получена — показатели снимка посчитаны по ней.",
    },
  },
  notConnected:
    "Клиент не подключил счёт — выписки нет. Это не отказ: заявку рассматривает сотрудник.",
};

/** Ключи ответов источников (docs/external/*.yaml) → подпись поля во вкладке «Проверки». */
export const CHECK_FIELD: Record<string, string> = {
  registry_status: "Статус в реестре",
  registered_at: "Дата регистрации",
  okved: "Вид деятельности (ОКВЭД)",
  address: "Адрес",
  director_name: "Руководитель",
  founders: "Учредители",
  kpp: "КПП",
  unreliable_address: "Отметка о недостоверности адреса",
  unreliable_director: "Отметка о недостоверности сведений о руководителе",
  pending_exclusion: "Предстоящее исключение из реестра",
  mass_address: "Массовый адрес регистрации",
  mass_director: "Массовый руководитель",
  tax_arrears: "Налоговая задолженность",
  accounts_suspended: "Приостановка операций по счетам",
  employees: "Численность сотрудников",
  tax_regime: "Налоговый режим",
  msp_category: "Категория МСП",
  taxes_paid: "Уплачено налогов за год",
  current_overdue_days: "Текущая просрочка",
  past_overdue_max_days: "Самая долгая прошлая просрочка",
  obligations: "Действующие кредиты и лизинг",
  months: "Выписка",
  period: "Последний месяц выписки",
  account_masked: "Счёт",
};

/** Значения полей проверок, которые приходят кодами. */
export const CHECK_VALUE = {
  yes: "да",
  no: "нет",
  noKpp: "нет — у ИП КПП не бывает",
  days: (n: number) => `${n} дн.`,
  months: (n: number) => `${n} мес`,
  people: (n: number) => `${n} чел.`,
  founder: (name: string, inn: string, share: string) => `${name} — ИНН ${inn}, доля ${share}`,
  obligation: (kind: string, payment: string, balance: string, opened: string) =>
    `${kind}: платёж ${payment} в месяц, остаток ${balance}, с ${opened}`,
  taxRegime: {
    psn: "Патент (ПСН)",
    usn_income: "УСН «доходы»",
    usn_income_minus_expenses: "УСН «доходы минус расходы»",
    osn: "Общая система (ОСН)",
  } as Record<string, string>,
  mspCategory: {
    micro: "Микропредприятие",
    small: "Малое предприятие",
    medium: "Среднее предприятие",
    not_msp: "Не входит в реестр МСП",
  } as Record<string, string>,
  obligationKind: { loan: "Кредит", leasing: "Лизинг" } as Record<string, string>,
} as const;

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

/**
 * Where an amount comes from (SRC7, docs/products.md «Входные данные»): the label next to it and
 * a hint on hover. `officer` — the amount a bank officer set in a decision.
 */
export const AMOUNT_SOURCE = {
  client: { label: "со слов клиента", hint: "Сумму указал клиент" },
  statement: { label: "по выписке", hint: "Посчитано по выписке с расчётного счёта" },
  calc: {
    label: "расчёт",
    hint: "Рассчитано по формулам банка из данных выписки и условий продукта",
  },
  officer: { label: "решение банка", hint: "Сумму установил сотрудник банка" },
} as const;

type SnapshotMetric = Exclude<keyof Schemas["FinancialSnapshot"], "id" | "period" | "source">;

/** Snapshot metrics in display order: money, then ratios shown as they are. */
export const SNAPSHOT_FIELD: Record<SnapshotMetric, { title: string; format: "money" | "ratio" }> =
  {
    cleaned_credit_turnover: {
      title: "Очищенный кредитовый оборот, в месяц",
      format: "money",
    },
    cfads: { title: "Денежный поток на обслуживание долга (CFADS), в месяц", format: "money" },
    debt_service: { title: "Платежи по долгу, в месяц", format: "money" },
    revenue: { title: "Выручка за 12 мес", format: "money" },
    cogs: { title: "Себестоимость за 12 мес", format: "money" },
    ebitda: { title: "EBITDA за 12 мес", format: "money" },
    debt: { title: "Долг", format: "money" },
    cash: { title: "Денежные средства", format: "money" },
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
    shortName: "Короткое название (от клиента)",
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
    noSnapshotText: "Клиент не подключил счёт — показатели посчитать не из чего.",
  },
  checks: {
    empty: "Проверки ещё не запускались",
    emptyText:
      "Реестры, «Прозрачный бизнес», БКИ и счёт проверяются автоматически после отправки заявки.",
    missing: "Нет результата",
    checkedAt: "Проверено",
    list: "Проверки по источникам",
    facts: "Сведения источника",
    risk: "признак риска",
    provenance: {
      title: "Происхождение",
      receivedAt: "Ответ получен",
      version: "Версия симулятора",
      sha256: "SHA-256 ответа",
      none: "Источник не ответил — происхождения нет",
    },
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
  /** XP3: the printable credit conclusion of the card. */
  conclusion: {
    open: "Кредитное заключение",
    print: "Сохранить в PDF",
    close: "Закрыть",
    previewLabel: "Предпросмотр кредитного заключения",
    previewHint: "В окне печати выберите «Сохранить как PDF».",
    title: "Кредитное заключение",
    number: (id: number) => `по заявке № ${id}`,
    generatedAt: "Сформировано",
    assignee: "Исполнитель",
    status: "Статус заявки",
    client: "Клиент",
    application: "Заявка",
    product: "Продукт",
    checks: "Проверки источников",
    noChecks: "Проверки ещё не проводились: реестры, БКИ и счёт проверяются после отправки заявки.",
    checkMissing: "Нет результата",
    scoring: "Скоринг",
    noScore: "Скоринг ещё не считали: балльная карта считается после проверок источников.",
    factor: "Фактор",
    value: "Значение",
    points: "Баллы",
    comment: "Пояснение",
    scoreTotal: (total: number, grade: string) => `Итого ${total} из 100 · грейд ${grade}`,
    scoreModel: (version: string, at: string) => `Модель ${version} · ${at}`,
    decisions: "Решения и история",
    noDecisions: "Решений пока нет: заявка ещё не прошла автоматическую проверку.",
    officer: "Сотрудник банка",
    reasons: "Причины",
    passed: "пройдено",
    failed: "не пройдено",
    threshold: "порог",
    improvements: "Что улучшить",
    officerComment: "Комментарий сотрудника",
    handoff: (cause: string, outcome: string) =>
      `Решение принял сотрудник: система передала заявку на ручное рассмотрение (${cause}) → сотрудник: ${outcome}`,
    handoffNoCause: "причина не указана",
    override: "Сотрудник изменил предварительную оценку",
    overrideOutcome: (auto: string, officer: string) =>
      `Система: «${auto}» → сотрудник: «${officer}»`,
    overrideAmount: (amount: string, limit: string, metric: string) =>
      `Сотрудник одобрил ${amount} — больше допустимой суммы системы ${limit} (${metric})`,
    overrideWho: (who: string, at: string) => `Кто и когда: ${who}, ${at}`,
    overrideWhy: "Почему",
    noReason: "обоснование не указано",
    infoRequests: "Запросы информации",
    clientAnswer: "Ответ клиента",
    noAnswer: "клиент ещё не ответил",
    offer: "Текущее предложение",
    noOffer: "Предложения нет.",
    footerDemo: "Синтетические данные, демо. Документ сформирован в рабочем месте банка.",
    signature: "Сотрудник банка",
    signatureLine: "подпись",
    signatureDate: "дата",
  },
} as const;

/** C3: company screens. */
export const COMPANY = {
  fromRegistry: "из ЕГРЮЛ",
  record: {
    name: "Название",
    legalForm: "Форма",
    inn: "ИНН",
    ogrn: "ОГРН",
    okved: "Основной вид деятельности (ОКВЭД)",
    registered: "Дата регистрации",
    region: "Регион",
    address: "Адрес",
    director: "Руководитель",
    status: "Статус в реестре",
  },
  notActive:
    "Компания в процессе ликвидации или уже ликвидирована: кредит не выдадут. Подключить её можно, но заявку банк отклонит.",
  create: {
    title: "Подключите компанию",
    subtitle: "Введите ИНН — реквизиты подтянем из ЕГРЮЛ/ЕГРИП, вводить их вручную не нужно.",
    inn: "ИНН компании или ИП",
    innHint: "10 цифр у компании, 12 — у ИП",
    find: "Найти в реестре",
    retry: "Повторить",
    found: "Нашли в реестре",
    confirm: "Это моя компания",
    other: "Другой ИНН",
    done: "Компания подключена",
  },
  profile: {
    requisites: "Реквизиты",
    requisitesNote: "Реквизиты взяты из ЕГРЮЛ/ЕГРИП и меняются только там.",
    shortName: "Короткое название",
    shortNameHint:
      "Так компания называется в кабинете. Юридическое название из реестра не меняется — банк видит его в реквизитах.",
    shortNameClear: "Оставьте пустым, чтобы показывать название из реестра.",
    save: "Сохранить",
    saved: "Название сохранено",
  },
  members: {
    title: "Сотрудники и роли",
    you: "вы",
    rolesHint:
      "Подписант отправляет заявки, принимает предложения и подписывает. Готовит заявки — заполняет черновики, загружает документы, отвечает банку.",
    readOnly: "Приглашать и убирать сотрудников может подписант.",
    empty: "Сотрудников пока нет",
    loading: "Загружаем сотрудников",
    invite: "Пригласить сотрудника",
    inviteHint:
      "Сотрудник регистрируется сам, а вы приглашаете его по логину. В компании он появится, когда примет приглашение в своём кабинете.",
    username: "Логин сотрудника",
    position: "Должность",
    positionPlaceholder: "Например, главный бухгалтер",
    role: "Роль",
    invited: "Приглашение создано — сотрудник увидит его, когда войдёт в кабинет",
    pending: "Ждут ответа",
    pendingLoading: "Загружаем приглашения",
    invitedAs: (role: string, position: string) => `${role} · ${position}`,
    cancel: (username: string) => `Отозвать приглашение для ${username}`,
    cancelShort: "Отозвать",
    cancelled: "Приглашение отозвано",
    remove: (name: string) => `Убрать ${name}`,
    removeShort: "Убрать",
    removeTitle: "Убрать сотрудника?",
    removeText: (name: string) =>
      `${name} больше не увидит заявки компании и не сможет с ними работать.`,
    removed: "Сотрудник убран",
  },
  invitations: {
    title: "Вас пригласили в компанию",
    hint: "Примите приглашение — и сразу начнёте работать в компании. Подключать свою компанию тогда не нужно.",
    list: "Приглашения в компании",
    loading: "Загружаем приглашения",
    invitedBy: (name: string) => `Пригласил: ${name}`,
    accept: "Принять",
    acceptLabel: (company: string) => `Принять приглашение от ${company}`,
    decline: "Отклонить",
    declineLabel: (company: string) => `Отклонить приглашение от ${company}`,
    accepted: "Вы в компании",
    declined: "Приглашение отклонено",
    orOwn: "Или подключите свою компанию по ИНН",
  },
  integrations: {
    title: "Источники данных",
    hint: "Подключите счёт — предварительная оценка посчитает показатели по выписке. ЭДО (электронный документооборот) — документы отгрузки для факторинга.",
    sources: {
      bank_account: "Выписка по расчётному счёту",
      edo: "ЭДО: документы отгрузки (УПД)",
    },
    connect: "Подключить",
    connected: (when: string) => `Подключено ${when}`,
    done: "Источник подключён — показатели обновлены",
  },
  metrics: {
    title: "Показатели по счёту",
    period: (period: string) => `Снимок за ${period}. Так их видит предварительная оценка.`,
    empty: "Подключите выписку по счёту — показатели появятся здесь.",
  },
  errors: {
    inn: "ИНН — 10 цифр у компании или 12 у ИП",
    innChecksum: "В ИНН ошибка: не сходятся контрольные цифры. Проверьте номер.",
    name: "Напишите название",
    tooLong: (max: number) => `Не длиннее ${max} символов`,
    username: "Напишите логин",
    usernameFormat: "В логине — только буквы, цифры и символы . @ + - _, без пробелов",
    position: "Напишите должность",
  },
} as const;

/** B5: officer actions on the bank card. */
export const BANK_ACTIONS = {
  none: "Сейчас по заявке нет действий для сотрудника.",
  productChange: "Другой продукт",
  cancel: "Отмена",
  assigned: "Заявка у вас в работе",
  conflictHint: "Карточку обновили — проверьте данные и повторите.",
  unavailable: "Это действие больше недоступно: статус заявки изменился. Закройте окно.",
  fields: {
    amount: "Сумма",
    amountHint: (max: string) => `По денежному потоку клиента допустимо до ${max}`,
    term: "Срок, месяцев",
    rate: "Ставка, % годовых",
    rateHint: (min: string, max: string) => `Ставка продукта: от ${min} до ${max}`,
    product: "Продукт",
    chooseProduct: "Выберите продукт",
    comment: "Комментарий клиенту",
    commentHint: "Клиент увидит его в заявке.",
    commentOptional: "Необязательно. Клиент увидит его в заявке.",
  },
  approve: {
    title: "Одобрить заявку",
    text: (amount: string, months: number) =>
      `Клиент получит предложение на запрошенных условиях: ${amount} на ${months} мес.`,
    confirm: "Одобрить",
    done: "Заявка одобрена — клиент получил предложение",
  },
  counteroffer: {
    title: "Предложить иные условия",
    text: "Клиент получит предложение с новыми условиями и вашим комментарием.",
    confirm: "Предложить условия",
    done: "Иные условия отправлены клиенту",
  },
  product: {
    title: "Предложить другой продукт",
    text: "Клиент получит предложение по другому продукту и ваш комментарий — почему он подходит лучше.",
    confirm: "Предложить продукт",
    done: "Предложение по другому продукту отправлено клиенту",
  },
  requestInfo: {
    title: "Запросить информацию",
    text: "Заявка перейдёт к клиенту и вернётся к вам, когда он ответит.",
    message: "Что нужно от клиента",
    messageHint: "Клиент увидит этот текст.",
    documents: "Какие документы загрузить",
    documentsHint:
      "Клиенту предложим загрузить именно их. Можно не отмечать, если нужен только ответ.",
    confirm: "Отправить запрос",
    done: "Запрос отправлен клиенту",
  },
  decline: {
    title: "Отказать по заявке",
    text: "Это окончательное решение. Клиент увидит причины и советы, что улучшить.",
    reasons: "Почему отказ — простым языком",
    improvement: (n: number) => `Что улучшить, пункт ${n}`,
    addImprovement: "Добавить пункт",
    removeImprovement: (n: number) => `Убрать пункт ${n}`,
    confirm: "Отказать",
    done: "Отказ оформлен",
  },
  errors: {
    amount: "Укажите сумму больше нуля",
    term: "Срок — целое число от 1 до 360 месяцев",
    rate: "Укажите ставку больше нуля, например 21,5",
    product: "Выберите продукт",
    comment: "Напишите комментарий для клиента",
    message: "Напишите, что нужно от клиента",
    reasons: "Напишите причину отказа",
    improvement: "Заполните пункт или уберите его",
    tooLong: (max: number) => `Не длиннее ${max} символов`,
  },
} as const;

/** C4: catalog and calculator. */
export const PRODUCTS = {
  title: "Продукты",
  subtitle: "Условия банка (демо). Не знаете, что выбрать, — подберём по задаче.",
  loadError: "Не получилось загрузить продукты",
  match: "Подобрать по задаче",
  rate: "Ставка",
  term: "Срок",
  amount: "Сумма",
  months: (min: number, max: number) => (min === max ? `${min} мес` : `${min}–${max} мес`),
  collateralNeeded: "Нужен залог",
  noCollateral: "Без залога",
  revolving: "возобновляемый лимит",
  annuity: "равные платежи",
  documents: "Документы",
  noDocuments: "не нужны",
  calculate: "Рассчитать платёж",
  calculatorTitle: "Калькулятор платежа",
  calculatorHint:
    "Равные платежи: платёж одинаковый каждый месяц. У овердрафта и факторинга платёж зависит от того, сколько денег вы возьмёте.",
  product: "Продукт",
  termMonths: "Срок, мес",
  ratePercent: "Ставка, %",
  payment: "Платёж в месяц",
  totalPaid: "Всего выплатите",
  overpayment: "Переплата",
  notAnOffer: "Это расчёт, а не предложение банка: ставку и сумму определит оценка заявки.",
  schedule: "График платежей",
  interest: "Проценты",
  principal: "Основной долг",
  balance: "Остаток",
} as const;

/** C8: notification centre. */
export const NOTIFICATIONS = {
  title: "Уведомления",
  loadError: "Не получилось загрузить уведомления",
  unread: (count: number) => `Непрочитанных: ${count}`,
  allRead: "Всё прочитано",
  readAll: "Отметить все прочитанными",
  emptyTitle: "Уведомлений пока нет",
  emptyText: "Здесь появится каждое изменение по вашим заявкам — без почты и SMS.",
  new: "Новое",
  open: "Открыть заявку",
  markRead: "Прочитано",
} as const;

/**
 * SRC1: consent to the credit bureau request (218-FZ, art. 6), ticked on the last wizard step.
 * `version` must match BKI_CONSENT_VERSION in backend/apps/applications/models.py: a new wording
 * means a new version on both sides, and the API rejects the old one.
 */
export const BKI_CONSENT = {
  version: "bki-2026-10",
  label: "Согласен на запрос кредитной истории в бюро кредитных историй",
  text:
    "Банк запросит кредитную историю компании и её руководителя в бюро кредитных историй — " +
    "только для рассмотрения этой заявки (ст. 6 Федерального закона № 218-ФЗ «О кредитных " +
    "историях»). Согласие действует 6 месяцев, а если договор будет заключён — весь срок " +
    "договора. Без согласия банк не может проверить кредитную историю, поэтому отправить " +
    "заявку нельзя.",
  required: "Поставьте галочку согласия — без неё заявку не отправить.",
} as const;

/** B6: bank dashboard. */
export const BANK_DASHBOARD = {
  title: "Дашборд",
  subtitle: "Как заявки проходят конвейер: этапы, время в статусах и доля автоматических решений.",
  loadError: "Не получилось загрузить дашборд",
  period: "Период",
  days: (count: number) => `${count} дней`,
  total: "Заявок за период",
  autoShare: "Решено автоматически",
  autoShareHint:
    "Доля итоговых решений (предложение, иные условия, другой продукт, отказ) без сотрудника",
  issued: "Деньги выданы",
  funnel: "Воронка: сколько заявок дошло до этапа",
  hours: "Среднее время в статусе",
  hoursValue: (value: string) => `${value} ч`,
  noData: "Данных пока нет.",
  overdue: "Просрочено по нормативу",
  overdueValue: (count: number, total: number) => `${count} из ${total}`,
  overdueNone: "Сейчас нет заявок, которые ждут банк",
  norms: "Нормативы",
  normValue: (status: string, hours: number) => `${status} — ${hours} ч`,
  overdueLink: "Показать просроченные в очереди",
} as const;

/** B7: demo panel. */
export const BANK_DEMO = {
  title: "Демо-панель",
  subtitle: "Только на стенде: сбои источников, быстрый вход за персону и сброс данных.",
  loadError: "Не получилось загрузить флаги сбоев",
  outagesTitle: "Сбои источников (сценарий 7)",
  outagesHint:
    "Включите сбой — следующие заявки уйдут сотруднику с пометкой «источник не ответил». Это не отказ.",
  sources: {
    egrul: "ЕГРЮЛ / ЕГРИП",
    transparent_business: "«Прозрачный бизнес» (ФНС)",
    bki: "Бюро кредитных историй",
    bank_account: "Выписка по счёту",
  } as Record<"egrul" | "transparent_business" | "bki" | "bank_account", string>,
  up: "Работает",
  down: "Сбой",
  personasTitle: "Быстрый вход за персону",
  personasHint: "Сессия сотрудника банка завершится, откроется кабинет персоны.",
  bankPlace: "Рабочее место банка",
  scenario: (number: number) => `Сценарий ${number}`,
  signInAs: "Войти",
  resetTitle: "Сброс демо-данных",
  resetHint:
    "Удалит заявки демо-персон и демо-очереди с их уведомлениями, выключит сбои и заново засеет очередь. Учётные записи и заявки компаний, которые подключили сами посетители, останутся.",
  reset: "Сбросить",
  resetConfirmTitle: "Сбросить демо-данные?",
  resetConfirmText:
    "Заявки демо-персон и демо-очереди и уведомления по ним будут удалены. Это нельзя отменить.",
  resetDone: "Демо-данные сброшены",
} as const;

/** XP1: «что если» под предложением банка — расчёт, предложение не меняется. */
export const WHAT_IF = {
  title: "Что если",
  subtitle: "Подвиньте сумму и срок — посчитаем платёж и покажем, пройдут ли такие условия.",
  amount: "Сумма",
  amountExact: "Сумма точно, ₽",
  term: "Срок",
  months: (n: number) => `${n} мес`,
  payment: "Платёж в месяц",
  maxAmount: (term: number) => `Допустимо на ${term} мес`,
  noMaxAmount: "Посчитать нельзя",
  coverage: "Покрытие платежей",
  coverageValue: (value: string, norm: string) => `${value} при норме от ${norm}`,
  fits: "Такие условия прошли бы",
  notFits: "Такие условия не пройдут",
  why: "Почему",
  counting: "Считаем…",
  note: "Это расчёт: предложение банка от него не меняется. Предварительная оценка, не решение банка.",
} as const;

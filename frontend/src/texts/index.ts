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
    next: "Проверьте данные и отправьте заявку. Черновик сохраняется сам.",
  },
  submitted: {
    label: "Отправлена",
    group: "progress",
    meaning: "Заявка в банке, скоро начнётся проверка.",
    next: "Ничего делать не нужно: статус обновится сам.",
  },
  processing: {
    label: "Проверяем",
    group: "progress",
    meaning: "Проверяем компанию по реестрам, смотрим кредитную историю и обороты по счёту.",
    next: "Обычно это занимает меньше минуты.",
  },
  manual_review: {
    label: "У сотрудника банка",
    group: "progress",
    meaning: "Заявку смотрит сотрудник банка.",
    next: "Обычно это занимает не больше дня. Если понадобятся документы, пришлём уведомление.",
  },
  info_requested: {
    label: "Нужны уточнения",
    group: "action",
    meaning: "Банку не хватает данных или документа.",
    next: "Ответьте на запрос ниже, и проверка продолжится.",
  },
  offer: {
    label: "Есть предложение",
    group: "action",
    meaning:
      "Банк готов дать деньги на условиях ниже. Это ещё не договор: условия закрепятся, когда вы его подпишете.",
    next: "Если условия подходят, примите предложение, и останется подписать договор. Если нет, откажитесь.",
  },
  signing: {
    label: "Подписание",
    group: "action",
    meaning: "Предложение принято, осталось подписать договор.",
    next: "Подпишите договор кодом с экрана. Это может сделать только сотрудник с ролью «Подписант».",
  },
  signed: {
    label: "Договор подписан",
    group: "success",
    meaning: "Договор подписан, деньги отправляем на счёт.",
    next: "Обычно деньги приходят за несколько минут.",
  },
  issued: {
    label: "Деньги выданы",
    group: "success",
    meaning: "Деньги пришли на счёт.",
    next: "Готово. Все условия есть на странице заявки.",
  },
  declined: {
    label: "Отказ",
    group: "danger",
    meaning: "Сейчас банк не может дать деньги.",
    next: "Посмотрите, почему так вышло и что можно улучшить, а потом подайте заявку снова.",
  },
  cancelled: {
    label: "Отозвана",
    group: "neutral",
    meaning: "Заявка закрыта: вы отозвали её или отказались от предложения.",
    next: "Если деньги всё ещё нужны, начните подбор заново.",
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
  counteroffer: "Другие условия",
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
  counteroffer: "Другие условия",
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
    `Сейчас у заявки ${current} ${pointsWord(current)} из 100, оценка риска — ${grade}. ` +
    `Если выполнить шаги ниже, наберётся ${target} ${pointsWord(target)} и оценка станет ` +
    `${targetGrade}. ${
      targetGrade === "C"
        ? "Тогда заявку рассмотрит сотрудник банка."
        : "Тогда банк сможет её одобрить."
    }`,
  points: (n: number) => `+${n} ${pointsWord(n)}`,
  gradeHint:
    "Оценка риска — буква от A до E по сумме баллов из 100, A — лучше всего. " +
    "При A или B банк может одобрить сразу, при C заявку смотрит сотрудник банка.",
  note: "Это предварительная оценка по данным вашего счёта, а не решение банка.",
} as const;

/** 1 месяц, 3 месяца, 12 месяцев: a term in a sentence, «на 36 месяцев». */
function monthsWord(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return "месяц";
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return "месяца";
  return "месяцев";
}

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
    "банк не может выдать деньги, какими бы хорошими ни были остальные показатели.",
  /** The backend's own sentence («Сейчас есть просрочка по кредиту: 12 дней») + why it matters. */
  current: (message: string) => `${message}. Это сильнее всего снижает оценку кредитной истории.`,
  pastOver: (days: number, limit: number) =>
    `В истории была просрочка ${days} ${daysWord(days)}, а банк допускает не больше ` +
    `${limit} ${daysWord(limit)}, поэтому кредитную историю оценили низко.`,
  pastWithin: (days: number, limit: number) =>
    `В истории была просрочка ${days} ${daysWord(days)}, а банк допускает до ` +
    `${limit} ${daysWord(limit)}. Отказывать из-за неё не будут, но без просрочек баллов было бы ` +
    "больше.",
  source:
    "Откуда это: когда вы отправили заявку, банк с вашего согласия запросил сведения в бюро " +
    "кредитных историй. Банк их не меняет, исправить ошибку можно только через бюро.",
  stepsTitle: "Что можно сделать",
  payCurrent: "Погасите текущую просрочку, после этого заявку можно подать снова.",
  steps: [
    "Узнайте, в каких бюро хранится история: у ИП — личная, у ООО — история компании. Запрос бесплатный, на Госуслугах он называется «Сведения о бюро кредитных историй».",
    "Закажите отчёт в каждом из этих бюро, дважды в год это бесплатно. В отчёте видно, у какого кредитора и когда была просрочка.",
    "Если нашли ошибку или погашенная просрочка всё ещё числится открытой, подайте в бюро заявление об исправлении. Бюро проверит сведения у кредитора и ответит в течение 20 рабочих дней.",
  ],
  attach: (finished: boolean) =>
    finished
      ? "К новой заявке приложите справку от кредитора о том, что долг погашен (тип документа — «Другой документ»). Сотрудник банка её учтёт."
      : "Приложите к заявке справку от кредитора о том, что долг погашен (тип документа — «Другой документ»). Сотрудник банка её учтёт.",
} as const;

/** UX1: landing — the jury understands the product in 30 seconds and signs in as a persona. */
export const LANDING = {
  eyebrow: "Кредитный кабинет для малого бизнеса",
  title: "Деньги для бизнеса — под вашу задачу",
  lead:
    "Скажите, на что нужны деньги — закрыть кассовый разрыв, закупить товар или купить " +
    "оборудование. Мы подберём подходящий вариант, посчитаем сумму по оборотам на вашем счёте " +
    "и объясним, откуда она взялась. Заявка, ответ банка и подписание договора — здесь же, " +
    "в отделение идти не нужно.",
  tryPersona: "Войти за демо-компанию",
  signIn: "Войти по логину",
  ownCompany: "Своя компания?",
  register: "Зарегистрируйтесь — логин и пароль, компанию добавите по ИНН",
  example: {
    title: "Пример: кофейня, кассовый разрыв",
    product: "Овердрафт",
    amount: "900000.00",
    caption: "Сколько можно взять по оборотам на счёте и почему именно столько",
    note: "Предварительная оценка, не решение банка",
  },
  clientTitle: "Как получить деньги: три шага",
  clientSteps: [
    {
      title: "Скажите, что случилось",
      text: "Например: «Зарплата 5-го, а покупатели платят 10-го». Кабинет или ассистент сами поймут, что подойдёт: при кассовом разрыве — овердрафт, если покупатель платит с отсрочкой — факторинг, для покупки оборудования — кредит или лизинг.",
    },
    {
      title: "Получите сумму с объяснением",
      text: "Сумму, ставку и платёж считаем по данным вашего счёта и реестров, а потом показываем, из чего они сложились. Заявка заполняется сама: реквизиты подтянутся из ЕГРЮЛ, вводить их не нужно.",
    },
    {
      title: "Следите за заявкой и подпишите договор",
      text: "На каждом шаге видно, что с заявкой и что будет дальше. Если банк предложит другие условия или откажет, вы увидите причины и план, как получить одобрение. Договор подписывается кодом с экрана.",
    },
  ],
  bankTitle: "Банк работает с той же заявкой",
  bankSteps: [
    {
      title: "Очередь со сроками",
      text: "Заявки можно отобрать по статусу, продукту и оценке риска. У каждой видно, сколько времени осталось на ответ.",
    },
    {
      title: "Карточка с проверками",
      text: "В одной карточке — проверки по ЕГРЮЛ, ФНС, бюро кредитных историй и счёту, баллы по каждому показателю и кредитное заключение.",
    },
    {
      title: "Решение сотрудника",
      text: "Сотрудник одобряет заявку, предлагает другие условия, запрашивает документ или отказывает и объясняет почему.",
    },
    {
      title: "Дашборд",
      text: "Сколько заявок на каждом этапе, сколько времени они там проводят и какую часть решений система принимает сама.",
    },
  ],
  whyTitle: "Чем мы отличаемся",
  quote:
    "«Отказали по причине плохой кредитной истории. Что и откуда — никто не знает. Как исправить — никто не знает»",
  quoteSource: "Предприниматель, живое интервью",
  why: [
    {
      title: "Каждая цифра с объяснением",
      text: "За каждой причиной стоят показатель, его значение и порог банка. Если банк откажет, вы получите план, как добиться одобрения, а если дело в кредитной истории — узнаете, что увидел банк и что с этим делать.",
    },
    {
      title: "Ассистент помогает, но не решает",
      text: "Ассистент работает на модели с открытыми весами и действует в кабинете только от вашего имени и в пределах ваших прав. Отправить заявку без вас он не может.",
    },
    {
      title: "Без звонков, SMS и навязанных услуг",
      text: "Всё происходит в кабинете: уведомления приходят сюда же, договор подписывается кодом с экрана, а все условия и платежи видны ещё до подписания.",
    },
  ],
  personasTitle: "Попробуйте от имени демо-компании",
  personasLead: "Компании вымышленные, у каждой свой сценарий. Вход в один клик, пароль не нужен.",
  personaClient: (scenario: number) => `Сценарий ${scenario}`,
  personaBank: "Рабочее место банка",
  personaSignIn: "Войти",
  personasOff: "Демо-компании выключены на этом стенде. Войдите по логину или зарегистрируйтесь.",
  links: { swagger: "Контракт API (Swagger)", status: "Состояние системы" },
  disclaimer:
    "Это прототип для хакатона. Все компании и данные вымышленные и помечены «демо», а внешние источники заменены симуляторами.",
} as const;

/** What the jury sees for each demo persona (docs/demo.md); unknown codes show only the title. */
export const PERSONA_STORY: Record<string, string> = {
  coffee_shop:
    "Кассовый разрыв. Овердрафт на 900 000 ₽ одобряют сразу, дальше — подпись и деньги на счёте.",
  retail_supplier:
    "Покупатель платит через 60 дней. Деньги за отгрузку можно получить сразу — через факторинг.",
  garden_store:
    "Просит 5,3 млн ₽ на сезон. Банк предлагает другие условия и объясняет почему, а в «Что если» можно прикинуть свои.",
  furniture_maker:
    "Нужен станок, но в кредитной истории есть просрочка. Сотрудник банка запрашивает документ и одобряет заявку.",
  accountant: "Бухгалтер готовит заявку мебельной фабрики, а подписывает директор",
  dependent_supplier:
    "Почти все деньги приносит один покупатель, выручка падает. Банк отказывает, но показывает, как добиться одобрения.",
  liquidating_company: "Компания ликвидируется, поэтому отказ приходит сразу.",
  bki_outage: "Бюро кредитных историй не отвечает. Заявку смотрит сотрудник банка, отказа нет.",
  equipment_no_collateral:
    "Нужно оборудование, а залога нет, поэтому вместо кредита предлагают лизинг.",
  bank: "Очередь заявок, карточка заявки, решения, дашборд и демо-панель сбоев.",
};

/** AI5, AI6, AI9: the assistant panels of the client and of the bank officer. */
export const ASSISTANT = {
  open: "Ассистент",
  title: "Ассистент",
  subtitle: "Подберёт финансирование, посчитает платёж и объяснит решение. Решения принимает банк.",
  aboutApplication: (id: number) => `Говорим о заявке № ${id}`,
  general: "Общий вопрос",
  placeholder: "Например: зарплата 5-го, а клиенты платят 10-го",
  send: "Отправить",
  sending: "Ассистент думает…",
  empty: "Спросите, зачем бизнесу деньги, сколько платить или что значит решение по заявке.",
  examples: [
    "Зарплата 5-го, а клиенты платят 10-го",
    "Сколько платить, если взять 1 000 000 под 24% на 12 месяцев?",
    "Что такое овердрафт?",
  ],
  loadError: "Не получилось загрузить историю",
  throttled: "Слишком много сообщений — подождите минуту.",
  you: "Вы",
  assistant: "Ассистент",
  toolsTitle: "Что сделал ассистент",
  toolError: "не получилось",
  pendingTitle: "Ассистент предлагает",
  confirm: "Подтвердить",
  cancel: "Отмена",
  confirmed: "Черновик создан",
  openDraft: "Открыть черновик",
  cancelled: "Предложение отменено — ничего не создано.",
  apply: "Оформить",
  applying: "Оформляем…",
  fits: "подходит",
  notFits: "не проходит",
  payment: "Платёж в месяц",
  totalPaid: "Всего выплат",
  overpayment: "Переплата",
  revolving: "Зависит от использования",
  preliminary: "Предварительная оценка, не решение банка.",
  close: "Закрыть",
  tools: {
    recommend_products: "Подобрал продукты",
    calc_payment: "Посчитал платёж",
    explain_status: "Посмотрел статус заявки",
    explain_decision: "Посмотрел решение",
    create_draft: "Подготовил черновик заявки",
    what_if: "Пересчитал условия",
    approval_plan: "Посмотрел план одобрения",
    explain_check_status: "Посмотрел проверки",
    company_metrics: "Посмотрел показатели компании",
    required_documents: "Посмотрел документы",
    explain_term: "Нашёл термин в словаре",
    application_summary: "Собрал картину по заявке",
    checks_with_provenance: "Посмотрел проверки и источники",
    score_breakdown: "Разобрал скоринг",
    dscr_and_limits: "Посмотрел платёжеспособность и лимиты",
    policy_compare: "Сверил с кредитной политикой",
    missing_documents: "Проверил, чего не хватает",
    draft_officer_comment: "Подготовил черновик комментария",
  } as Record<string, string>,
  // AI6: the questions the context buttons ask.
  ask: {
    whyDecision: "Почему такое решение?",
    howToApprove: "Как получить одобрение?",
    whatIfLonger: (amount: string, months: number) =>
      `Что если взять ${amount} на ${months} месяцев?`,
    whatIsStatus: "Что значит этот статус?",
  },
  bank: {
    title: "Ассистент сотрудника",
    subtitle: "Собирает факты по заявке и готовит черновик. Решение и комментарий — за вами.",
    summary: "Сводка для решения",
    summaryLoading: "Собираем сводку…",
    risks: "Риски",
    toVerify: "Что перепроверить",
    draft: "Черновик комментария",
    sources: "Источники",
    noRisks: "Существенных рисков по фактам заявки нет.",
    nothingToVerify: "Перепроверять нечего.",
    insert: "Вставить в комментарий",
    inserted: "Текст в поле комментария — проверьте и сохраните сами.",
    placeholder: "Например: почему грейд C?",
    empty: "Спросите про грейд, проверки, платёжеспособность или что запросить у клиента.",
    error: "Не получилось собрать сводку",
  },
} as const;

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
    title: "Лимит по оборотам",
    hint: "Часть от того, сколько в среднем приходит на счёт за месяц. Свои переводы и возвраты не считаются.",
    format: "money",
  },
  factoring_advance: {
    title: "Деньги под отгрузку",
    hint: "Часть суммы отгрузки по УПД, которую можно получить сразу.",
    format: "money",
  },
  factoring_commission: {
    title: "Комиссия за факторинг",
    hint: "Сколько стоит получить деньги, не дожидаясь оплаты от покупателя.",
    format: "money",
  },
  working_capital_need: {
    title: "Деньги в обороте",
    hint: "Запасы и долги покупателей за вычетом долгов поставщикам. Столько денег сейчас заморожено в товаре и отсрочках покупателям.",
    format: "money",
  },
  max_loan_by_dscr: {
    title: "Сумма, которую потянет бизнес",
    hint: "Если взять больше, платёж будет не по силам: свободных денег должно хватать на все платежи и ещё оставаться запас.",
    format: "money",
  },
  dscr: {
    title: "Запас на платежи по долгам (DSCR)",
    hint: "Во сколько раз свободных денег больше, чем нужно на платежи по долгам.",
    format: "decimal",
  },
  dscr_after: {
    title: "Запас на платежи с новым кредитом",
    hint: "Во сколько раз свободных денег больше, чем нужно на все платежи вместе с новым кредитом.",
    format: "decimal",
  },
  debt_to_ebitda: {
    title: "Долговая нагрузка (долг к EBITDA)",
    hint: "За сколько лет бизнес смог бы отдать долги из операционной прибыли.",
    format: "decimal",
  },
  revenue_trend: {
    title: "Выручка к прошлому году",
    hint: "Выручка за последние три месяца в сравнении с теми же месяцами прошлого года.",
    format: "percent",
  },
  counterparty_concentration: {
    title: "Доля крупнейшего покупателя",
    hint: "Какую часть денег на счёт приносит самый крупный покупатель.",
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
    hint: "По данным ФНС: нет ли долгов по налогам и не зарегистрировано ли много других компаний на тот же адрес или того же руководителя.",
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
    hint: "Источник не ответил, поэтому заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  source_transparent_business: {
    title: "«Прозрачный бизнес» (ФНС)",
    hint: "Источник не ответил, поэтому заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  source_bki: {
    title: "Бюро кредитных историй",
    hint: "Источник не ответил, поэтому заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  source_bank_account: {
    title: "Выписка по счёту",
    hint: "Счёт не подключён или выписка не пришла, поэтому заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  missing_key_metrics: {
    title: "Данные для автоматической оценки",
    hint: "По счёту не хватает данных для автоматической оценки, поэтому заявку посмотрит сотрудник банка. Это не отказ.",
    format: "decimal",
  },
  automatic_check: {
    title: "Автоматическая проверка",
    hint: "Проверка не завершилась, поэтому заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  // Stop factors (apps/scoring/stop_factors.py)
  registry_status: {
    title: "Статус в реестре",
    hint: "По ЕГРЮЛ или ЕГРИП: работает компания, ликвидируется или уже ликвидирована.",
    format: "text",
  },
  egrul_found: {
    title: "Запись в реестре",
    hint: "Есть ли компания в ЕГРЮЛ/ЕГРИП.",
    format: "text",
  },
  ebitda: {
    title: "Операционная прибыль",
    hint: "Прибыль от основной работы за год без учёта процентов, налогов и износа оборудования.",
    format: "money",
  },
  bki_current_overdue_days: {
    title: "Текущая просрочка",
    hint: "Сколько дней сейчас просрочен платёж по кредиту.",
    format: "days",
  },
  accounts_suspended: {
    title: "Операции по счетам",
    hint: "Не приостановила ли налоговая операции по счетам компании. Если приостановила, кредит выдать нельзя.",
    format: "text",
  },
  // ЕГРЮЛ marks that send the application to an officer (apps/scoring/review.py, SRC5)
  egrul_unreliable_address: {
    title: "Достоверность адреса",
    hint: "Есть ли в ЕГРЮЛ отметка, что адрес компании недостоверен. Если есть, заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  egrul_unreliable_director: {
    title: "Достоверность сведений о руководителе",
    hint: "Есть ли в ЕГРЮЛ отметка, что сведения о руководителе недостоверны. Если есть, заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  egrul_pending_exclusion: {
    title: "Исключение из реестра",
    hint: "Не собирается ли налоговая исключить компанию из ЕГРЮЛ. Если собирается, заявку проверит сотрудник банка. Это не отказ.",
    format: "text",
  },
  // Product fit in the match (apps/recommendations/service.py)
  product_requirements: {
    title: "Требования продукта",
    hint: "Подходят ли правовая форма, возраст бизнеса и залог.",
    format: "text",
  },
  term_months: {
    title: "Срок",
    hint: "На какой срок выдают этот продукт.",
    format: "months",
  },
  amount_min: {
    title: "Минимальная сумма",
    hint: "Меньше этой суммы не выдают.",
    format: "money",
  },
  amount_max: {
    title: "Максимальная сумма",
    hint: "Больше этой суммы не выдают.",
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
  assigneeId: (id: string) => `Сотрудник № ${id}`,
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
  openApplication: (id: number) => `Заявка № ${id}`,
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
  assistant: "Ассистент",
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
        "Либо компания ликвидируется — это отказ (стоп-фактор), либо в реестре есть отметка о недостоверности или предстоящем исключении — тогда заявку проверяет сотрудник.",
      // Before SRC2 «no such INN» was stored as failed.
      failed: "Компании нет в реестре — это отказ (стоп-фактор): её не проверить.",
    },
    transparent_business: {
      ok: "Массового адреса и руководителя, налогового долга и приостановки операций по счетам нет.",
      warning:
        "Есть массовый адрес или руководитель либо налоговый долг — это снижает баллы. Если операции по счетам приостановлены, это отказ (стоп-фактор).",
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
    "Клиент не подключил счёт, поэтому выписки нет. Это не отказ: заявку рассматривает сотрудник.",
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
  liquidating: "Ликвидируется",
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
  /** The same amount in the client's own cabinet: «со слов клиента» about oneself reads odd. */
  you: { label: "вы указали", hint: "Эту сумму вы указали в заявке" },
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
    "Один из источников не ответил, поэтому данные проверки неполные. Это не отказ: проверьте заявку вручную.",
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
    offer: "Предложение",
    offerRequested: "Клиент просил",
    rate: "Ставка",
    payment: "Платёж в месяц",
    revolvingPayment: "Зависит от того, сколько клиент возьмёт",
    expires: "Действует до",
    counteroffer: "Другие условия",
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
    noSnapshotText: "Клиент не подключил счёт, поэтому показатели посчитать не из чего.",
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
      none: "Источник не ответил, поэтому сведений о происхождении нет",
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
      `Система передала заявку на ручное рассмотрение (${cause}), решение принял сотрудник: ${outcome}`,
    handoffNoCause: "причина не указана",
    override: "Сотрудник изменил предварительную оценку",
    overrideOutcome: (auto: string, officer: string) =>
      `Система предлагала «${auto}», сотрудник решил «${officer}»`,
    overrideAmount: (amount: string, limit: string, metric: string) =>
      `Сотрудник одобрил ${amount}, а система допускала не больше ${limit} (${metric})`,
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
    "Компания ликвидируется или уже ликвидирована, поэтому кредит ей не выдадут. Подключить её можно, но банк отклонит заявку.",
  create: {
    title: "Подключите компанию",
    subtitle:
      "Введите ИНН, и мы подтянем реквизиты из ЕГРЮЛ или ЕГРИП — вручную вводить ничего не нужно.",
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
      "Подписант отправляет заявки, принимает предложения банка и подписывает договор. Сотрудник с ролью «Готовит заявки» заполняет черновики, загружает документы и отвечает банку.",
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
    invited: "Приглашение создано: сотрудник увидит его, когда войдёт в кабинет",
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
    hint: "Примите приглашение, и сразу сможете работать в компании. Подключать свою компанию тогда не нужно.",
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
    hint: "Подключите счёт, и показатели для предварительной оценки посчитаются по выписке. Через ЭДО (электронный документооборот) приходят документы отгрузки, они нужны для факторинга.",
    sources: {
      bank_account: "Выписка по расчётному счёту",
      edo: "ЭДО: документы отгрузки (УПД)",
    },
    connect: "Подключить",
    connected: (when: string) => `Подключено ${when}`,
    done: "Источник подключён, показатели обновлены",
  },
  metrics: {
    title: "Показатели по счёту",
    period: (period: string) => `Данные за ${period}. По ним считается предварительная оценка.`,
    empty: "Подключите выписку по счёту, и показатели появятся здесь.",
  },
  errors: {
    inn: "В ИНН должно быть 10 цифр у компании или 12 у ИП",
    innChecksum: "В ИНН ошибка: не сходятся контрольные цифры. Проверьте номер.",
    name: "Напишите название",
    tooLong: (max: number) => `Не длиннее ${max} символов`,
    username: "Напишите логин",
    usernameFormat: "В логине могут быть только буквы, цифры и символы . @ + - _, без пробелов",
    position: "Напишите должность",
  },
} as const;

/** B5: officer actions on the bank card. */
export const BANK_ACTIONS = {
  none: "Сейчас по заявке нет действий для сотрудника.",
  productChange: "Другой продукт",
  cancel: "Отмена",
  assigned: "Заявка у вас в работе",
  conflictHint: "Карточку уже обновили: проверьте данные и повторите действие.",
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
      `Клиент получит предложение на запрошенных условиях: ${amount} на ${months} ${monthsWord(months)}.`,
    confirm: "Одобрить",
    done: "Заявка одобрена, клиент получил предложение",
  },
  counteroffer: {
    title: "Предложить другие условия",
    text: "Клиент получит предложение с новыми условиями и вашим комментарием.",
    confirm: "Предложить условия",
    done: "Другие условия отправлены клиенту",
  },
  product: {
    title: "Предложить другой продукт",
    text: "Клиент получит предложение по другому продукту и ваш комментарий о том, почему он подходит лучше.",
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
    reasons: "Причина отказа простыми словами",
    improvement: (n: number) => `Что улучшить, пункт ${n}`,
    addImprovement: "Добавить пункт",
    removeImprovement: (n: number) => `Убрать пункт ${n}`,
    confirm: "Отказать",
    done: "Отказ оформлен",
  },
  errors: {
    amount: "Укажите сумму больше нуля",
    term: "Укажите срок целым числом от 1 до 360 месяцев",
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
  subtitle: "Условия банка (демо). Если не знаете, что выбрать, подберём по вашей задаче.",
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
  notAnOffer:
    "Это расчёт, а не предложение банка: ставку и сумму банк назовёт, когда оценит заявку.",
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
  emptyText:
    "Здесь будут все изменения по вашим заявкам. На почту и по SMS мы ничего не присылаем.",
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
    "Какую часть итоговых решений (предложение, другие условия, другой продукт, отказ) система приняла без сотрудника",
  issued: "Деньги выданы",
  funnel: "Воронка: сколько заявок дошло до каждого этапа",
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
/** «нашли 1 вариант», «3 варианта», «5 вариантов». */
export function variantsWord(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return "вариант";
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return "варианта";
  return "вариантов";
}

/** «1 ошибка», «3 ошибки», «5 ошибок». */
export function errorsWord(n: number): string {
  const last = n % 10;
  const tens = n % 100;
  if (last === 1 && tens !== 11) return "ошибка";
  if (last >= 2 && last <= 4 && (tens < 12 || tens > 14)) return "ошибки";
  return "ошибок";
}

export const BANK_DEMO = {
  title: "Демо-панель",
  subtitle: "Только на стенде: сбои источников, быстрый вход за персону и сброс данных.",
  loadError: "Не получилось загрузить флаги сбоев",
  outagesTitle: "Сбои источников (сценарий 7)",
  outagesHint:
    "Если включить сбой, следующие заявки уйдут сотруднику с пометкой «источник не ответил». Это не отказ. Сбой выключится сам через 15 минут, чтобы не мешать следующим проверяющим.",
  sources: {
    egrul: "ЕГРЮЛ / ЕГРИП",
    transparent_business: "«Прозрачный бизнес» (ФНС)",
    bki: "Бюро кредитных историй",
    bank_account: "Выписка по счёту",
  } as Record<"egrul" | "transparent_business" | "bki" | "bank_account", string>,
  up: "Работает",
  down: "Сбой",
  twoClicks:
    "Сценарий 7 в два клика: выключите «Бюро кредитных историй» и нажмите «Войти» у персоны сценария 7. Когда её заявка встретит сбой, предохранитель (circuit breaker) этого источника здесь сработает.",
  // XP6: the circuit breaker of each source, live (GET /api/demo/sources).
  breaker: {
    closed: "Предохранитель в норме",
    open: "Предохранитель сработал",
    half_open: "Предохранитель: пробный вызов",
    calls: "вызовы идут",
    streak: (n: number) => `${n} ${errorsWord(n)} подряд`,
    of: (n: number, threshold: number) => `ошибок подряд: ${n} из ${threshold}`,
    retryIn: (seconds: number) => `повтор через ${seconds} с`,
    trial: "следующий вызов пробный",
    offIn: (minutes: number) => `сбой выключится сам через ${minutes} мин`,
  },
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
    "Удалим заявки демо-персон и демо-очереди вместе с уведомлениями. Отменить это нельзя.",
  resetDone: "Демо-данные сброшены",
} as const;

/** XP1: «что если» под предложением банка — расчёт, предложение не меняется. */
export const WHAT_IF = {
  title: "Что если",
  subtitle:
    "Подвигайте сумму и срок: мы посчитаем платёж и покажем, подойдут ли банку такие условия.",
  amount: "Сумма",
  amountExact: "Сумма точно, ₽",
  term: "Срок",
  months: (n: number) => `${n} мес`,
  payment: "Платёж в месяц",
  maxAmount: (term: number) => `Можно взять на ${term} мес`,
  noMaxAmount: "Не получается посчитать",
  coverage: "Запас на платежи",
  coverageHint:
    "Во сколько раз свободных денег больше, чем нужно на все платежи по долгам вместе с этим кредитом. " +
    "Если меньше нужного, платёж будет не по силам.",
  coverageValue: (value: string, norm: string) => `${value}, нужно не меньше ${norm}`,
  fits: "Такие условия прошли бы",
  notFits: "Такие условия не пройдут",
  why: "Почему",
  counting: "Считаем…",
  note: "Это только расчёт: предложение банка от него не меняется. Оценка предварительная, решение принимает банк.",
} as const;

/** UX2: loading, empty and error states of blocks inside a screen (documents, history, metrics). */
export const BLOCK_STATE = {
  retry: "Повторить",
  documentsLoading: "Загружаем документы",
  documentsEmpty: "Документов пока нет.",
  documentsError: "Не получилось загрузить документы.",
  historyLoading: "Загружаем историю",
  historyEmpty: "Событий пока нет: здесь появится каждый шаг по заявке.",
  historyError: "Не получилось загрузить историю.",
  companyLoading: "Загружаем данные компании",
  companyError: "Не получилось загрузить данные компании.",
  metricsLoading: "Загружаем показатели по счёту",
  metricsError: "Не получилось загрузить показатели по счёту.",
} as const;

/** UX2: /status — what the check found and what to do. */
export const HEALTH = {
  title: "Состояние системы",
  subtitle: "Проверка связи кабинета с API (GET /api/health)",
  checking: "Проверяем…",
  ok: "Бэкенд работает",
  degraded: "База данных недоступна",
  unavailable: "API недоступен",
} as const;

/** UX2: what screen readers hear when something changes without a click (aria-live, toasts). */
export const LIVE = {
  statusChanged: (label: string) => `Статус заявки изменился: ${label}`,
  openApplication: (id: number) => `Открыть заявку № ${id}`,
  matchFound: (count: number) => `Нашли ${count} ${variantsWord(count)}`,
  matchNone: "Подходящих вариантов нет",
} as const;

/** UX2: empty states — what is (not) here and what to do next. */
export const EMPTY = {
  filteredApplicationsTitle: "В этом разделе заявок нет",
  filteredApplicationsText: "Остальные заявки — в других разделах.",
  showAll: "Показать все заявки",
  productsTitle: "Каталог продуктов пуст",
  productsText:
    "Банк ещё не выложил условия. Подберите кредит по задаче — покажем, что можно взять сейчас.",
  dashboardTitle: "Заявок за период нет",
  dashboardText: "Выберите период подлиннее или откройте очередь заявок.",
  dashboardLonger: "Показать за 90 дней",
  toQueue: "Открыть очередь",
  personasLoading: "Загружаем демо-персон",
  personasError: "Не получилось загрузить демо-персон.",
  personasEmptyTitle: "Демо-персон нет",
  personasEmptyText:
    "Они появятся после сброса демо-данных: нажмите «Сбросить» ниже и проверьте ещё раз.",
  refresh: "Проверить ещё раз",
} as const;

/** UX2: the payment calculator says what is wrong instead of a grey button. */
export const CALCULATOR_ERRORS = {
  amount: "Укажите сумму",
  term: "Укажите срок целым числом от 1 до 360 месяцев",
  rate: "Укажите ставку больше нуля, например 24,5",
} as const;

/** UX4: the living styleguide /dev/ui (dev only) — every design-system component on one page. */
export const STYLEGUIDE = {
  title: "Стайлгайд «Оборот»",
  subtitle:
    "Все компоненты дизайн-системы на одной странице: токены, типографика, кнопки, статусы, деньги, причины, оффер, скоринг. Данные — демо.",
  sections: {
    colors: "Цвета (токены)",
    type: "Типографика",
    buttons: "Кнопки",
    badges: "Бейджи и статусы",
    money: "Деньги и источник суммы",
    inputs: "Поля ввода",
    nextStep: "Что дальше",
    stepper: "Шаги мастера",
    timeline: "Лента событий",
    reasons: "Причины и что улучшить",
    offer: "Предложение банка",
    score: "Разложение скоринга",
    facts: "Факты",
    states: "Пустое состояние, ошибка, загрузка",
    dialog: "Диалог подтверждения",
  },
  type: {
    display: "Заголовок страницы",
    title: "Заголовок карточки",
    body: "Основной текст: простым языком, без банковского жаргона.",
    muted: "Подпись, подсказка или дата",
  },
  buttons: {
    primary: "Отправить в банк",
    secondary: "Сохранить черновик",
    ghost: "Отмена",
    danger: "Отказаться",
    link: "Подробнее",
    loading: "Отправляем…",
  },
  badges: { brand: "демо", neutral: "черновик" },
  inputLabel: "Сумма",
  inputHint: "Сколько нужно бизнесу",
  inputError: "Укажите сумму от 300 000 ₽",
  nextStepExtra: "Предложение действует до 13 ноября.",
  emptyTitle: "Заявок пока нет",
  emptyText: "Начните с подбора: расскажите, зачем бизнесу деньги.",
  errorTitle: "Не получилось загрузить",
  openDialog: "Открыть диалог",
  dialogTitle: "Отказаться от предложения?",
  dialogText: "Заявка закроется, а банк перестанет её рассматривать.",
  dialogConfirm: "Отказаться",
  improvements: [
    "Снизьте долю крупнейшего покупателя до 50 % и меньше",
    "Верните выручку хотя бы к уровню прошлого года",
  ],
} as const;

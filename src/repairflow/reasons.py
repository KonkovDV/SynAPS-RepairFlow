"""Stable human-readable reason codes for RepairFlow v1."""

from __future__ import annotations

from enum import StrEnum

REASON_CODES = (
    "MISSING_SETUP",
    "CREW_UNBOUND",
    "CREW_OVERLAP",
    "AUX_OVERLAP",
    "SKILL_MISMATCH",
    "CENTER_OVERLAP",
    "PRECEDENCE_BROKEN",
    "WINDOW_BROKEN",
    "DUE_MISSED",
    "DEADLINE_MISSED",
    "FROZEN_MOVED",
    "SPARE_UNAVAILABLE",
    "UNKNOWN_OPERATION",
    "UNKNOWN_RESOURCE",
    "DAG_UNSUPPORTED",
    "PARTIAL_COVERAGE",
    "KERNEL_STATUS_MISSING",
    "DUPLICATE_ASSIGNMENT",
    "INVALID_DURATION",
    "HORIZON_VIOLATION",
    "RELEASE_VIOLATION",
    "ELIGIBLE_CENTER_MISMATCH",
    "SETUP_MISMATCH",
    "CALENDAR_BROKEN",
    "INVALID_PROBLEM",
    "INVALID_ID_MAP",
    "KERNEL_STATUS_UNKNOWN",
    "DAG_FIXPOINT_NOT_CONVERGED",
    "EXCHANGE_POOL_STOCKOUT",
    "NERVOUSNESS_HIGH",
    "KERNEL_CALENDAR_UNSUPPORTED",
    "CPSAT_OPS_CAP",
)


class ReasonCode(StrEnum):
    MISSING_SETUP = "MISSING_SETUP"
    CREW_UNBOUND = "CREW_UNBOUND"
    CREW_OVERLAP = "CREW_OVERLAP"
    AUX_OVERLAP = "AUX_OVERLAP"
    SKILL_MISMATCH = "SKILL_MISMATCH"
    CENTER_OVERLAP = "CENTER_OVERLAP"
    PRECEDENCE_BROKEN = "PRECEDENCE_BROKEN"
    WINDOW_BROKEN = "WINDOW_BROKEN"
    DUE_MISSED = "DUE_MISSED"
    DEADLINE_MISSED = "DEADLINE_MISSED"
    FROZEN_MOVED = "FROZEN_MOVED"
    SPARE_UNAVAILABLE = "SPARE_UNAVAILABLE"
    UNKNOWN_OPERATION = "UNKNOWN_OPERATION"
    UNKNOWN_RESOURCE = "UNKNOWN_RESOURCE"
    DAG_UNSUPPORTED = "DAG_UNSUPPORTED"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    KERNEL_STATUS_MISSING = "KERNEL_STATUS_MISSING"
    DUPLICATE_ASSIGNMENT = "DUPLICATE_ASSIGNMENT"
    INVALID_DURATION = "INVALID_DURATION"
    HORIZON_VIOLATION = "HORIZON_VIOLATION"
    RELEASE_VIOLATION = "RELEASE_VIOLATION"
    ELIGIBLE_CENTER_MISMATCH = "ELIGIBLE_CENTER_MISMATCH"
    SETUP_MISMATCH = "SETUP_MISMATCH"
    CALENDAR_BROKEN = "CALENDAR_BROKEN"
    INVALID_PROBLEM = "INVALID_PROBLEM"
    INVALID_ID_MAP = "INVALID_ID_MAP"
    KERNEL_STATUS_UNKNOWN = "KERNEL_STATUS_UNKNOWN"
    DAG_FIXPOINT_NOT_CONVERGED = "DAG_FIXPOINT_NOT_CONVERGED"
    EXCHANGE_POOL_STOCKOUT = "EXCHANGE_POOL_STOCKOUT"
    NERVOUSNESS_HIGH = "NERVOUSNESS_HIGH"
    KERNEL_CALENDAR_UNSUPPORTED = "KERNEL_CALENDAR_UNSUPPORTED"
    CPSAT_OPS_CAP = "CPSAT_OPS_CAP"


REASON_RU: dict[str, str] = {
    ReasonCode.MISSING_SETUP: "нет записи переналадки в матрице",
    ReasonCode.CREW_UNBOUND: "операции с требуемыми навыками не назначена бригада",
    ReasonCode.CREW_OVERLAP: "бригада назначена на пересекающиеся интервалы",
    ReasonCode.AUX_OVERLAP: "оснастка занята другим назначением",
    ReasonCode.SKILL_MISMATCH: "бригада без требуемой квалификации",
    ReasonCode.CENTER_OVERLAP: "пост занят другим назначением",
    ReasonCode.PRECEDENCE_BROKEN: "нарушена технологическая последовательность",
    ReasonCode.WINDOW_BROKEN: "работа вне допустимого окна",
    ReasonCode.DUE_MISSED: "заказ не уложился в срок готовности",
    ReasonCode.DEADLINE_MISSED: "заказ вышел за жёсткий deadline",
    ReasonCode.FROZEN_MOVED: "сдвинуто замороженное назначение",
    ReasonCode.SPARE_UNAVAILABLE: "ЗИП недоступен к старту операции",
    ReasonCode.UNKNOWN_OPERATION: "назначение ссылается на неизвестную операцию",
    ReasonCode.UNKNOWN_RESOURCE: "назначение ссылается на неизвестный ресурс",
    ReasonCode.DAG_UNSUPPORTED: "ветвящийся DAG не поддержан и не линеаризуется",
    ReasonCode.PARTIAL_COVERAGE: "не все операции покрыты планом",
    ReasonCode.KERNEL_STATUS_MISSING: "в результате нет статуса ядра",
    ReasonCode.DUPLICATE_ASSIGNMENT: "операция назначена более одного раза",
    ReasonCode.INVALID_DURATION: "нулевая или отрицательная длительность слота",
    ReasonCode.HORIZON_VIOLATION: "назначение выходит за горизонт планирования",
    ReasonCode.RELEASE_VIOLATION: "старт раньше даты выпуска заказа",
    ReasonCode.ELIGIBLE_CENTER_MISMATCH: "пост не входит в список допущенных",
    ReasonCode.SETUP_MISMATCH: "длительность переналадки не совпадает с матрицей",
    ReasonCode.CALENDAR_BROKEN: "слот не лежит внутри одной календарной смены",
    ReasonCode.INVALID_PROBLEM: "вход не проходит доменную валидацию",
    ReasonCode.INVALID_ID_MAP: "карта идентификаторов неполная или неоднозначная",
    ReasonCode.KERNEL_STATUS_UNKNOWN: "неизвестный статус ядра",
    ReasonCode.DAG_FIXPOINT_NOT_CONVERGED: ("окна межсегментных связей не сошлись за лимит итераций"),
    ReasonCode.EXCHANGE_POOL_STOCKOUT: "обменный фонд ушёл в минус",
    ReasonCode.NERVOUSNESS_HIGH: "перепланирование сдвинуло слишком большую долю работ",
    ReasonCode.KERNEL_CALENDAR_UNSUPPORTED: (
        "календарь бригады или оснастки нельзя передать в закреплённое ядро"
    ),
    ReasonCode.CPSAT_OPS_CAP: "экземпляр больше лабораторного предела CP-SAT",
}


SUGGESTIONS: dict[str, str] = {
    ReasonCode.MISSING_SETUP: "добавить ячейку setup_matrix для пары состояний на посту",
    ReasonCode.CREW_UNBOUND: "явно назначить квалифицированную crew_id до проверки",
    ReasonCode.CREW_OVERLAP: "сдвинуть одну из работ или добавить смену бригады",
    ReasonCode.AUX_OVERLAP: "развести работы по времени или добавить единицу оснастки",
    ReasonCode.SKILL_MISMATCH: "назначить бригаду с требуемой квалификацией",
    ReasonCode.CENTER_OVERLAP: "выбрать альтернативный пост или сдвинуть слот",
    ReasonCode.PRECEDENCE_BROKEN: "начать операцию не раньше окончания предшественника",
    ReasonCode.WINDOW_BROKEN: "уложить работу в одно согласованное окно",
    ReasonCode.DUE_MISSED: "сдвинуть предшественников, добавить ресурс или согласовать новый срок",
    ReasonCode.DEADLINE_MISSED: "уложить последнюю операцию до deadline или сдвинуть deadline",
    ReasonCode.FROZEN_MOVED: "оставить замороженный слот без изменений",
    ReasonCode.SPARE_UNAVAILABLE: "отложить старт до available_from или заменить артикул",
    ReasonCode.PARTIAL_COVERAGE: "увеличить горизонт, ресурсы или разрешить частичный план явно",
    ReasonCode.DAG_UNSUPPORTED: "разбить ветвление на линейные техкарты или расширить ядро",
    ReasonCode.DAG_FIXPOINT_NOT_CONVERGED: (
        "повторить со стратегией serialize или увеличить max_fixpoint_iter"
    ),
    ReasonCode.EXCHANGE_POOL_STOCKOUT: "сдвинуть выдачу, пополнить фонд или снять hard",
    ReasonCode.NERVOUSNESS_HIGH: "сузить окрестность перепланирования или поднять порог",
    ReasonCode.KERNEL_CALENDAR_UNSUPPORTED: (
        "считать этот экземпляр domain GREED/EDD или снять календарь ресурса, которого нет в ядре"
    ),
    ReasonCode.CPSAT_OPS_CAP: (
        "считать экземпляр domain GREED/EDD/ATC; CP-SAT в этой сборке не вызывается выше 80 операций"
    ),
}

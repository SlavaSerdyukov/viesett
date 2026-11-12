import hashlib
from datetime import date

from viesett.coownership.context import Document, Fact, fact_date, ids, money
from viesett.document_intelligence.association import normalize
from viesett.domain.coownership import (
    CapitalCall,
    Decision,
    DecisionStatus,
    Meeting,
    PlannedWork,
    WorkCategory,
)
from viesett.domain.intelligence import AnalysisKind


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def projects(
    documents: list[Document], when: date
) -> tuple[list[Meeting], list[PlannedWork], list[CapitalCall]]:
    meetings: dict[str, Meeting] = {}
    candidates: dict[str, list[tuple[Decision, list[Fact]]]] = {}
    calls: dict[str, CapitalCall] = {}
    for doc in documents:
        meeting_date = fact_date(doc.one("meeting_date"))
        if meeting_date and meeting_date > when:
            continue
        meeting_type = (
            "EXTRAORDINARY" if doc.kind == AnalysisKind.EXTRAORDINARY_AGM_MINUTES else "ORDINARY"
        )
        meeting_key = digest(
            str(doc.value("enterprise_number"))
            + normalize(str(doc.value("address")))
            + str(meeting_date)
            + meeting_type
        )
        if doc.kind in {AnalysisKind.AGM_MINUTES, AnalysisKind.EXTRAORDINARY_AGM_MINUTES}:
            meetings.setdefault(
                meeting_key,
                Meeting(
                    key=meeting_key,
                    meeting_date=meeting_date,
                    meeting_type=meeting_type,
                    decisions=[],
                    source_document_ids=[],
                ),
            )
            meetings[meeting_key].source_document_ids.append(doc.id)
        groups = sorted({f.field.group for f in doc.fields if f.field.group.startswith("work_")})
        for group in groups:
            fields = [f for f in doc.fields if f.field.group == group]
            reference = doc.value("project_reference", group)
            category = WorkCategory(str(doc.value("category", group) or "OTHER"))
            decision = Decision(
                reference=str(reference) if reference else None,
                category=category,
                decision_status=DecisionStatus(
                    str(doc.value("decision_status", group) or "UNKNOWN")
                ),
                meeting_date=meeting_date,
                topic=category.value,
                budget=money(doc.one("budget", group)),
                estimated_budget=money(doc.one("estimated_budget", group)),
                agenda_item_number=group.removeprefix("work_"),
                normalized_decision=category.value
                + ": "
                + str(doc.value("decision_status", group) or "UNKNOWN"),
                reserve_allocation=money(doc.one("reserve_allocation", group)),
                capital_call_total=money(doc.one("call_total", group)),
                funding_source=str(doc.value("funding_source", group))
                if doc.value("funding_source", group)
                else None,
                expected_start=fact_date(doc.one("expected_start", group)),
                vote_result=str(doc.value("vote_result", group))
                if doc.value("vote_result", group)
                else None,
                evidence_ids=ids(fields + doc.all("meeting_date")),
            )
            key = (
                digest(
                    "project:"
                    + str(doc.value("enterprise_number"))
                    + ":"
                    + str(reference).casefold()
                    + ":"
                    + category.value
                )
                if reference
                else digest(meeting_key + ":" + doc.source_sha256 + ":" + group)
            )
            candidates.setdefault(key, []).append((decision, fields))
            if doc.kind in {AnalysisKind.AGM_MINUTES, AnalysisKind.EXTRAORDINARY_AGM_MINUTES}:
                canonical = decision.model_dump(exclude={"evidence_ids"})
                existing = next(
                    (
                        d
                        for d in meetings[meeting_key].decisions
                        if d.model_dump(exclude={"evidence_ids"}) == canonical
                    ),
                    None,
                )
                if existing:
                    existing.evidence_ids = sorted(
                        set(existing.evidence_ids + decision.evidence_ids)
                    )
                else:
                    meetings[meeting_key].decisions.append(decision)
        call_groups = {f.field.group for f in doc.fields if f.field.group.startswith("call_")}
        if doc.kind == AnalysisKind.CAPITAL_CALL:
            call_groups.add("root")
        for group in sorted(call_groups):
            fields = [f for f in doc.fields if f.field.group in {group, "root"}]
            reference = doc.value("call_reference", group)
            project_ref = doc.value("project_reference", group)
            if not any(
                doc.one(name, group) for name in ("call_reference", "call_total", "lot_amount")
            ):
                continue
            result = CapitalCall(
                reference=str(reference) if reference else None,
                project_reference=str(project_ref) if project_ref else None,
                total=money(doc.one("call_total", group)),
                lot_specific_amount=money(doc.one("lot_amount", group)),
                lot=str(doc.value("lot")) if doc.value("lot") else None,
                due_date=fact_date(doc.one("due_date", group)),
                effective_date=fact_date(doc.one("as_of")),
                purpose=str(doc.value("category", group)) if doc.value("category", group) else None,
                fund_type=str(doc.value("fund_type", group) or "UNKNOWN"),
                covers_full_project=doc.value("full_project_call", group) is True,
                evidence_ids=ids(fields),
            )
            key = digest(str(result.model_dump(exclude={"evidence_ids"})))
            if key in calls:
                calls[key].evidence_ids = sorted(set(calls[key].evidence_ids + result.evidence_ids))
            else:
                calls[key] = result
    works = []
    for key, rows in sorted(candidates.items()):
        newest = max((d.meeting_date or date.min) for d, _ in rows)
        current = [d for d, _ in rows if (d.meeting_date or date.min) == newest]
        observations = {str(d.model_dump(exclude={"evidence_ids"})) for d in current}
        # Same-reference same-date disagreements remain distinct candidates.
        selected = [current[0]] if len(observations) == 1 else current
        for index, decision in enumerate(selected):
            status = decision.decision_status
            works.append(
                PlannedWork(
                    key=key if len(selected) == 1 else key + "-" + str(index),
                    reference=decision.reference,
                    category=decision.category,
                    description=decision.topic,
                    decision_status=status,
                    decision_date=decision.meeting_date,
                    approved_total_cost=decision.budget
                    if status == DecisionStatus.APPROVED
                    else None,
                    estimated_total_cost=decision.estimated_budget
                    or (decision.budget if status != DecisionStatus.APPROVED else None),
                    funding_source=decision.funding_source,
                    reserve_fund_allocation=decision.reserve_allocation,
                    capital_call_total=decision.capital_call_total,
                    expected_start=decision.expected_start,
                    evidence_ids=sorted({eid for d, _ in rows for eid in d.evidence_ids}),
                )
            )
    return list(meetings.values()), works, list(calls.values())

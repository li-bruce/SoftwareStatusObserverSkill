"""Direct-folder policy and real deterministic checks for this project."""
import hashlib
import uuid
from .ports import TracePort


def is_direct_manager(project_id: str, operator_id: str, folder_id: str,
                      assignments: list[dict], trace: TracePort | None = None,
                      basis: dict | None = None, parent: str | None = None) -> bool:
    trace = trace or TracePort()
    allowed = any(a["project_id"] == project_id and a["operator_id"] == operator_id
                  and a["folder_id"] == folder_id for a in assignments)
    trace.bo_record("scope_check", "decision", basis or {}, lambda: {
        "inputs": {"project_id": project_id, "operator_id": operator_id,
                   "folder_id": folder_id, "assignments": assignments},
        "outputs": {"allowed": allowed, "inherit_ancestors": False}},
        call_id=uuid.uuid4().hex, parent_call_id=parent)
    return allowed


def candidate_allowed(grant: dict, request: dict, now: float, reviewers: list[str],
                      trace: TracePort | None = None, basis: dict | None = None,
                      parent: str | None = None) -> dict:
    trace = trace or TracePort()
    # Each condition is evaluated in this call, including rejected candidates.
    result = {
        "project_ok": grant["project_id"] == request["project_id"],
        "operator_ok": grant["operator_id"] == request["operator_id"],
        "document_ok": grant["document_id"] == request["document_id"],
        "version_ok": grant["content_version"] == request["content_version"],
        "reviewer_ok": grant["reviewer_id"] in reviewers,
        "different_actor": grant["reviewer_id"] != request["operator_id"],
        "not_revoked": not bool(grant["revoked"]),
        "time_ok": now < grant["deadline"],
    }
    result["target_matches"] = all(result[k] for k in
        ("project_ok", "operator_ok", "document_ok", "version_ok"))
    result["allowed"] = all(result.values())
    trace.bo_record("approval_candidate", "decision", basis or {}, lambda: {
        "inputs": {**grant, "request_project": request["project_id"],
                   "request_operator": request["operator_id"],
                   "request_document": request["document_id"],
                   "request_version": request["content_version"], "clock": now},
        "outputs": result}, call_id=uuid.uuid4().hex, parent_call_id=parent)
    return result


def evaluate_approvals(project_id: str, operator_id: str, document_id: str,
                       content_version: int, approvals: list[dict], reviewers: list[str],
                       now: float, trace: TracePort, basis: dict, parent: str) -> dict:
    call = uuid.uuid4().hex
    request = dict(project_id=project_id, operator_id=operator_id,
                   document_id=document_id, content_version=content_version)
    candidates = [{"id": g["id"], **candidate_allowed(g, request, now, reviewers,
                  trace, basis, call)} for g in approvals]
    allowed = any(c["allowed"] for c in candidates)
    trace.bo_record("approval_check", "decision", basis, lambda: {
        "inputs": {**request, "clock": now, "candidate_count": len(candidates)},
        "outputs": {"allowed": allowed, "candidates": candidates}},
        call_id=call, parent_call_id=parent)
    return {"allowed": allowed, "candidates": candidates}


def check_size(content: str, limit_bytes: int, project_id: str, limit_revision: int,
               trace: TracePort | None = None, basis: dict | None = None,
               parent: str | None = None, source_event: str | None = None) -> dict:
    trace = trace or TracePort()
    content_bytes = len(content.encode("utf-8"))
    result = {"content_bytes":content_bytes,"limit_bytes":limit_bytes,
              "limit_revision":limit_revision,"allowed":content_bytes <= limit_bytes,
              "excess_bytes":max(0,content_bytes-limit_bytes)}
    trace.bo_record("size_guard","decision",basis or {},lambda:{
        "inputs":{"project_id":project_id,"content_bytes":content_bytes,
                  "limit_bytes":limit_bytes,"limit_revision":limit_revision},
        "outputs":result},call_id=uuid.uuid4().hex,parent_call_id=parent,
        depends=[(source_event,"data")] if source_event else [])
    return result


def check_content(content: str, trace: TracePort | None = None,
                  basis: dict | None = None, call_id: str | None = None) -> dict:
    trace = trace or TracePort()
    result = {"passed": "SECRET:" not in content, "marker_present": "SECRET:" in content}
    trace.bo_record("content_check", "return", basis or {}, lambda: {
        "inputs": {"content_length": len(content),
                   "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                   "forbidden_marker": "SECRET:"},
        "outputs": result}, call_id=call_id or uuid.uuid4().hex)
    return result


def check_index(title: str, project_id: str, document_number: str,
                trace: TracePort | None = None, basis: dict | None = None,
                call_id: str | None = None) -> dict:
    trace = trace or TracePort()
    result = {"title_present": bool(title.strip()),
              "project_present": bool(project_id.strip()),
              "number_present": bool(document_number.strip())}
    result["passed"] = all(result.values())
    trace.bo_record("index_check", "return", basis or {}, lambda: {
        "inputs": {"title_length": len(title), "project_id": project_id,
                   "document_number": document_number}, "outputs": result},
        call_id=call_id or uuid.uuid4().hex)
    return result

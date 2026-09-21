from ss_seo.contracts import Audit, AuditMode, AuditStatus, Project


def test_quick_audit_defaults_are_safe():
    project = Project(id="p1", name="Example", base_url="https://example.com")
    audit = Audit(id="a1", project_id=project.id, mode=AuditMode.QUICK)

    assert audit.status is AuditStatus.QUEUED
    assert audit.max_urls == 100
    assert audit.max_depth == 10


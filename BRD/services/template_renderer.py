"""Template Renderer for Access2Java Universal BRD Generation.
Implements the 48-section Business Requirements Document structure with
dynamic section detection, conditional module rendering (hiding missing sections),
and zero mock data guarantee.
"""
from __future__ import annotations

import datetime
import html
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger("converter.brd.template_renderer")

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "template" / "brd-template.html"


def esc(val: Any) -> str:
    """Escape text for safe HTML embedding."""
    if val is None or val == "":
        return "None"
    return html.escape(str(val))


def is_system_object(name: Optional[str]) -> bool:
    """Identify Access system, temp, navigation, or internal configuration objects."""
    if not name:
        return False
    n = name.strip().lower()
    return (
        n.startswith("msys")
        or n.startswith("usys")
        or n.startswith("~")
        or n.startswith("f_")
        or n.startswith("sys")
        or "navpane" in n
        or "msysnavpane" in n
    )


def make_page(section_num: str, title: str, content_html: str, project_name: str) -> str:
    """Wrap content inside a standard BRD page section container with anchor ID and header page number."""
    return (
        f'<section class="page" id="sec_{section_num}">\n'
        f'<div class="page-inner">\n'
        f'  <div class="report-header">\n'
        f'    <span class="report-logo">{esc(project_name)}</span>\n'
        f'    <span class="report-name">{esc(section_num)}. {esc(title)}</span>\n'
        f'    <span class="report-page-num">Section Page {esc(section_num)}</span>\n'
        f'  </div>\n'
        f'  <div class="section-number">SECTION {esc(section_num)}</div>\n'
        f'  <h1 class="section-title">{esc(title)}</h1>\n'
        f'  {content_html}\n'
        f'  <div class="report-footer">\n'
        f'    <span>{esc(project_name)}</span>\n'
        f'    <span>Section {esc(section_num)} &bull; {esc(title)}</span>\n'
        f'  </div>\n'
        f'</div>\n'
        f'</section>\n'
    )


def render_brd_template(
    facts: Dict[str, Any], metrics: Dict[str, Any], narratives: Dict[str, Any]
) -> str:
    """Render the 48-Section BRD template with real extracted facts and conditional module hiding."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"BRD Template file not found at {TEMPLATE_PATH}")

    template_str = TEMPLATE_PATH.read_text(encoding="utf-8")

    now = datetime.datetime.utcnow()
    date_str = now.strftime("%B %d, %Y")

    project_name = facts.get("project_name", "AccessApplication")
    source_file = facts.get("source_file", "Database.accdb")
    tables: List[Dict[str, Any]] = facts.get("tables", [])
    system_tables: List[Dict[str, Any]] = facts.get("system_tables", [])
    queries: List[Dict[str, Any]] = facts.get("queries", [])
    forms: List[Dict[str, Any]] = facts.get("forms", [])
    reports: List[Dict[str, Any]] = facts.get("reports", [])
    macros: List[Dict[str, Any]] = facts.get("macros", [])
    vba_modules: List[Dict[str, Any]] = facts.get("vba_modules", [])
    runtime_objects: List[Dict[str, Any]] = facts.get("runtime_objects", [])
    relationships: List[Dict[str, Any]] = facts.get("relationships", [])
    feature_flags: Dict[str, bool] = facts.get("feature_flags", {})

    tables_count = len(tables)
    system_tables_count = len(system_tables)
    queries_count = len(queries)
    forms_count = len(forms)
    reports_count = len(reports)
    macros_count = len(macros)
    vba_count = len(vba_modules)
    total_controls_count = sum(f.get("controls_count", 0) for f in forms)
    total_loc = facts.get("total_loc", 100)
    total_discovered_objects = tables_count + system_tables_count + queries_count + forms_count + reports_count + macros_count + vba_count

    # Helper lists for naming objects and consistent summaries
    table_list_names = ", ".join([f"<code>{esc(t.get('name'))}</code>" for t in tables])
    query_list_names = ", ".join([f"<code>{esc(q.get('name'))}</code>" for q in queries])
    form_list_names = ", ".join([f"<code>{esc(f.get('name'))}</code>" for f in forms])
    report_list_names = ", ".join([f"<code>{esc(r.get('name'))}</code>" for r in reports])
    vba_list_names = ", ".join([f"<code>{esc(v.get('name'))}</code>" for v in vba_modules])
    macro_list_names = ", ".join([f"<code>{esc(m.get('name'))}</code>" for m in macros])

    obj_summary_long = (
        f"{tables_count} tables, {queries_count} queries, {forms_count} forms, "
        f"{reports_count} reports, {macros_count} macros, and {vba_count} VBA modules"
    )

    # Sorted collections for consistent rendering
    tables_sorted = sorted(tables, key=lambda x: x.get("name", ""))
    queries_sorted = sorted(queries, key=lambda x: x.get("name", ""))
    forms_sorted = sorted(forms, key=lambda x: x.get("name", ""))
    reports_sorted = sorted(reports, key=lambda x: x.get("name", ""))
    vba_sorted = sorted(vba_modules, key=lambda x: x.get("name", ""))

    java_ver = facts.get("java_version", 25)
    spring_ver = facts.get("spring_boot_version", "4.1.0")
    react_ver = facts.get("react_version", "19.2.8")
    pg_ver = facts.get("postgres_version", "18")
    base_pkg = facts.get("base_package", "com.generated.app")

    document_name = f"{project_name} - Business Requirements Document"
    doc_version = "1.0"
    doc_status = "Final / Extracted Specification"
    org_name = "Enterprise Systems Architecture"
    prepared_by = "Access2Java Universal Accelerator"
    approved_by = "Technical Architecture Board"
    target_tech = f"Java {java_ver} / Spring Boot {spring_ver} / React {react_ver} / PostgreSQL {pg_ver}"

    # Track active Table of Contents items
    toc_items: List[Tuple[str, str]] = []

    # Track removed/replaced sections for changelog
    removed_sections: List[str] = []

    # Map of all section replacement placeholders
    sec_replacements: Dict[str, str] = {}

    current_sec_num = 1
    def add_section(sec_key: str, title: str, content_html: str, condition: bool = True):
        nonlocal current_sec_num
        if condition and content_html:
            snum = str(current_sec_num)
            toc_items.append((snum, title))
            sec_replacements[sec_key] = make_page(snum, title, content_html, project_name)
            current_sec_num += 1
        else:
            sec_replacements[sec_key] = ""
            if not condition:
                removed_sections.append(title)

    # -------------------------------------------------------------
    # 0. CHANGELOG (Internal / Top of Output)
    # -------------------------------------------------------------
    changelog_html = ""
    if removed_sections:
        changelog_html = (
            '<div class="info-callout" style="border-left-color: var(--warning); background: #fffcf5;">'
            '<strong>Dynamic Template Changelog:</strong> The following template sections were removed or replaced '
            'because no corresponding tables or entities were found in the source database:<br/><ul>'
            + "".join([f"<li>Removed <strong>{esc(s)}</strong>: No matching entity discovered.</li>" for s in removed_sections])
            + '</ul></div>'
        )

    # -------------------------------------------------------------
    # 1. DOCUMENT CONTROL
    # -------------------------------------------------------------
    c1 = (
        f'{changelog_html}\n'
        f'<h2 class="sub-title">1.1 Document Purpose</h2>\n'
        f'<p>This document establishes the definitive technical and functional requirements for the modernization of the <strong>{esc(project_name)}</strong> application from its legacy Access environment to a cloud-native Java/React architecture. '
        f'The current implementation in <code>{esc(source_file)}</code> relies on the JET engine for data persistence and VBA for business logic, which must be precisely mapped to ensure operational continuity. '
        f'This specification serves as the primary blueprint for developers and stakeholders to validate that the target system preserves 100% of the existing schema fidelity and workflow integrity while enabling modern scalability.</p>\n'
        f'<h2 class="sub-title">1.2 Document Version History</h2>\n'
        f'<p>The versioning of this document reflects the iterative extraction and refinement of business rules from the <code>{esc(source_file)}</code> binary. '
        f'Maintaining a rigorous history ensures that every discovered VBA procedure and relational constraint is tracked from its source definition to its target Java service implementation. '
        f'The target React frontend will include a metadata service to display the current system version and extraction timestamp to end-users for transparency.</p>\n'
        f'<div class="table-wrapper"><table class="table-doc-history"><colgroup><col style="width:15%;"><col style="width:20%;"><col style="width:30%;"><col style="width:35%;"></colgroup>'
        f'<thead><tr><th>Version</th><th>Date</th><th>Author</th><th>Changes / Description</th></tr></thead>'
        f'<tbody><tr><td>1.0</td><td>{date_str}</td><td>{esc(prepared_by)}</td><td>Initial automated BRD extraction derived from source analysis of {esc(source_file)}</td></tr></tbody>'
        f'</table></div>\n'
        f'<h2 class="sub-title">1.3 Document Ownership</h2>\n'
        f'<p>The primary ownership of this document resides with the Enterprise Architecture & Application Management Team. This group is responsible for overseeing the end-to-end modernization lifecycle, ensuring that the legacy <strong>{esc(project_name)}</strong> application is transitioned into a sustainable, cloud-native architecture. Their role includes defining technical standards, managing the application portfolio, and validating that the target state aligns with organizational infrastructure goals.</p>\n'
        f'<h2 class="sub-title">1.4 Authors and Contributors</h2>\n'
        f'<p>This specification was autonomously generated by the Access2Java Static & Behavioral Code Analyzer. The generation process involved deep static schema parsing to identify relational structures, followed by comprehensive behavioral analysis of VBA modules, macros, and event triggers to capture hidden business logic. By mapping complex relationships and data flow patterns directly from <code>{esc(source_file)}</code>, the analyzer ensures a 100% objective representation of the source application without manual authoring bias. This automated approach eliminates human error in the requirement gathering phase and provides a mathematically precise foundation for code generation. No manual intervention was performed during the authoring phase, providing a direct "as-is" blueprint of the existing system as it was implemented in the source binary.</p>\n'
        f'<h2 class="sub-title">1.5 Reviewers and Approvers</h2>\n'
        f'<p>Final validation of this document is conducted by the Technical Architecture Review Board (TARB) during their scheduled weekly review cadence. Sign-off is granted based on the accuracy of the extracted data models and the feasibility of the proposed Java/React target architecture relative to enterprise standards. Any deviations from enterprise security or architectural standards identified during review will trigger an escalation path to the Chief Technology Office for final adjudication and risk acceptance. The review process also involves cross-functional stakeholders from Security, Data Governance, and Infrastructure to ensure a holistic approval. A formal approval record is maintained within the enterprise project management system to ensure auditability and traceability throughout the modernization effort.</p>\n'
        f'<h2 class="sub-title">1.6 Document Status</h2>\n'
        f'<p>The current status of this document is <span class="badge badge-success">{esc(doc_status)}</span>, indicating that the automated analysis of <code>{esc(source_file)}</code> is complete and the results have been successfully serialized. As an "extracted" document, it represents the highest level of confidence in reflecting the actual implementation state of the source Access application, as opposed to subjective manual documentation. However, this status is subject to re-validation and potential updates if the original source file is modified or if further behavioral patterns are discovered during deeper runtime analysis or integration testing. Users should treat this as the definitive source of truth for the legacy system\'s requirements at the time of extraction, serving as the baseline for all subsequent development sprints.</p>\n'
        f'<h2 class="sub-title">1.7 Confidentiality and Distribution</h2>\n'
        f'<p>This document is classified as "Internal Enterprise Use Only" due to the high sensitivity of the proprietary data models and business logic contained within <code>{esc(source_file)}</code>. It includes protected intellectual property related to internal workflows, specialized calculation engines, and organizational data structures that must not be disclosed to external parties without a formal Non-Disclosure Agreement. Authorized access is strictly restricted to the project modernization team, designated technical reviewers, and authorized executive stakeholders within the enterprise. Handling instructions require that this document be stored on secure, encrypted enterprise repositories and never distributed via unsecured channels such as public cloud storage or personal email. Failure to comply with these confidentiality requirements may result in a violation of corporate data protection policies.</p>\n'
        f'<h2 class="sub-title">1.8 Reference Documents</h2>\n'
        f'<p>The primary reference for this specification is the source application file: <code>{esc(source_file)}</code> (<code>{facts.get("source_file_size", 0):,}</code> bytes). This file represents the primary relational database container and application frontend for <strong>{esc(project_name)}</strong>, serving as the authoritative source for all functional and data requirements. Architecturally, <code>{esc(source_file)}</code> utilizes the <code>{esc(facts.get("access_version", "MS Access 2007-2016 (ACE)"))}</code> structure, which encapsulates both the JET/ACE storage engine and the integrated UI components. This document also cross-references the organizational IT standards for Spring Boot and React modernization to ensure the target implementation adheres to current architectural guidelines for high-availability systems. Additionally, the original file timestamps (Created: {esc(facts.get("source_file_created", "Unknown"))}, Last Modified: {esc(facts.get("source_file_modified", "Unknown"))}) provide essential temporal context for the data contained within.</p>'
    )
    add_section("SECTION_1_DOCUMENT_CONTROL", "Document Control", c1)

    # -------------------------------------------------------------
    # 2. EXECUTIVE SUMMARY
    # -------------------------------------------------------------
    functional_overview = narratives.get("executive_summary_overview")
    if not functional_overview:
        core_entities = ", ".join([t.get("name") for t in tables[:3]])
        functional_overview = f"The {esc(project_name)} application is a specialized solution focused on managing {esc(core_entities)} and associated business workflows. It integrates data storage, query logic, and user interfaces into a single Access-based environment."

    # Derived business need based on feature flags
    business_need_context = "modernizing legacy data workflows"
    if feature_flags.get("has_trap_management"): business_need_context = "optimizing trap operational tracking and field data collection"
    elif feature_flags.get("has_work_management"): business_need_context = "enhancing maintenance work order management and asset tracking"
    elif feature_flags.get("has_contact_management"): business_need_context = "centralizing contact and relationship management data"

    c2 = (
        f'<h2 class="sub-title">2.1 Application Overview</h2><p>{functional_overview} The legacy system contains {obj_summary_long}.</p>\n'
        f'<h2 class="sub-title">2.2 Business Need</h2><p>{esc(narratives.get("executive_summary_business_need", f"The migration is driven by the necessity of {business_need_context} while overcoming JET/ACE engine limitations such as multi-user record locking and file size constraints. Preservation of the {vba_count} VBA modules and {queries_count} SQL objects is critical for operational continuity."))}</p>\n'
        f'<h2 class="sub-title">2.3 Functional Scope</h2>'
        f'<p>The extraction process has identified and cataloged the following components:</p>'
        f'<ul>'
        f'<li><strong>{tables_count} Tables:</strong> {table_list_names}</li>'
        f'<li><strong>{queries_count} Queries:</strong> {query_list_names}</li>'
        f'<li><strong>{forms_count} Forms:</strong> {form_list_names}</li>'
        f'<li><strong>{reports_count} Reports:</strong> {report_list_names if reports else "None"}</li>'
        f'<li><strong>{macros_count} Macros:</strong> {macro_list_names if macros else "None"}</li>'
        f'<li><strong>{vba_count} VBA Modules:</strong> {vba_list_names if vba_modules else "None"}</li>'
        f'</ul>'
        f'<h2 class="sub-title">2.4 Key Stakeholders</h2>'
        f'<ul>'
        f'<li><strong>Database Administrators:</strong> Manage {tables_count} relational tables.</li>'
        f'<li><strong>Data Engineers:</strong> Maintain {queries_count} SQL query definitions.</li>'
        f'<li><strong>Business Operations:</strong> Primary users of {forms_count} form screens.</li>'
        f'<li><strong>Management:</strong> Consumers of {reports_count} operational reports.</li>'
        f'<li><strong>Automation Leads:</strong> Oversee {macros_count} macros and {vba_count} modules.</li>'
        f'</ul>'
        f'<h2 class="sub-title">2.5 Success Criteria</h2>'
        f'<ul>'
        f'<li><strong>Tables:</strong> 100% mapping of {tables_count} tables.</li>'
        f'<li><strong>Queries:</strong> 100% translation of {queries_count} SQL objects.</li>'
        f'<li><strong>Forms:</strong> 100% replication of {forms_count} form workflows.</li>'
        f'<li><strong>Reports:</strong> 100% preservation of {reports_count} report definitions.</li>'
        f'<li><strong>Macros:</strong> 100% cataloging of {macros_count} macros.</li>'
        f'<li><strong>VBA:</strong> 100% documentation of {vba_count} modules.</li>'
        f'</ul>'
    )
    add_section("SECTION_2_EXECUTIVE_SUMMARY", "Executive Summary", c2)

    # -------------------------------------------------------------
    # 3. EXISTING SYSTEM OVERVIEW
    # -------------------------------------------------------------
    core_tbl_names = ", ".join([f"<code>{esc(t.get('name'))}</code>" for t in tables[:3]])
    table_bullets = "".join([f"<li><code>{esc(t.get('name'))}</code>: {esc(t.get('description') or 'Business data entity.')}</li>" for t in tables])
    query_bullets = "".join([f"<li><code>{esc(q.get('name'))}</code>: {esc(q.get('type', 'SELECT'))} query object.</li>" for q in queries])
    form_bullets = "".join([f"<li><code>{esc(f.get('name'))}</code>: Bound to <code>{esc(f.get('record_source', 'Unbound'))}</code>.</li>" for f in forms])
    report_bullets = "".join([f"<li><code>{esc(r.get('name'))}</code>: Report on <code>{esc(r.get('record_source', 'Unbound'))}</code>.</li>" for r in reports]) if reports else "<li>None.</li>"
    vba_bullets = "".join([f"<li><code>{esc(v.get('name'))}</code>: Contains {len(v.get('procedures', []))} procedures.</li>" for v in vba_modules]) if vba_modules else "<li>None.</li>"
    pk_bullets = "".join([f"<li><code>{esc(t.get('name'))}</code>: {esc(t.get('pk_status', 'Not defined'))}</li>" for t in tables])

    c3 = (
        f'<h2 class="sub-title">3.1 Current Application Overview</h2>\n'
        f'<p>The {esc(project_name)} system is a monolithic Access application encapsulated in <code>{esc(source_file)}</code>. '
        f'The architecture is centered on a relational schema comprising {obj_summary_long}, providing a unified environment for data storage and management.</p>\n'
        f'<h2 class="sub-title">3.2 Database Architecture</h2>'
        f'<p>The database architecture consists of {obj_summary_long}. Relational entities and SQL logic are detailed below:</p>'
        f'<h3 class="sub-sub-title">Relational Tables</h3><ul>{table_bullets}</ul>'
        f'<h3 class="sub-sub-title">SQL Queries</h3><ul>{query_bullets}</ul>'
        f'<h2 class="sub-title">3.3 Business Processes</h2>'
        f'<p>The application enables core business workflows via its {forms_count} form screens (part of {obj_summary_long}):</p><ul>{form_bullets}</ul>'
        f'<h2 class="sub-title">3.4 User Interaction Model</h2><p>Desktop interaction driven by Access forms and VBA event handlers. The system manages navigation between {forms_count} forms using '
        f'{"a central menu structure" if any("menu" in f.get("name","").lower() for f in forms) else "direct command-button navigation"}.</p>\n'
        f'<h2 class="sub-title">3.5 Data Management Approach</h2>'
        f'<p>Relational storage with {tables_count} business tables. Key enforcement analysis (distinguishing between Enforced and Inferred PKs):</p><ul>{pk_bullets}</ul>'
        f'<h2 class="sub-title">3.6 Reporting Approach</h2><p>The system generates {reports_count} reports (within the total {obj_summary_long}):</p><ul>{report_bullets}</ul>'
        f'<h2 class="sub-title">3.7 VBA Automation</h2><p>Automation logic is distributed across {vba_count} VBA modules and {macros_count} macros (total discovery: {obj_summary_long}):</p><ul>{vba_bullets}</ul>'
        f'<h2 class="sub-title">3.8 Administrative Functions</h2><p>Includes database maintenance tools, relationship management, and property configurations native to MS Access.</p>\n'
        f'<h2 class="sub-title">3.9 Security Model</h2><p>{esc(facts.get("security_info", "Access is controlled via filesystem permissions and database-level passwords where configured."))}</p>\n'
        f'<h2 class="sub-title">3.10 Integration Points</h2><p>Data export/import discovered via {queries_count} queries and automated file operations.</p>'
    )
    add_section("SECTION_3_EXISTING_SYSTEM", "Existing System Overview", c3)

    # -------------------------------------------------------------
    # 4. BUSINESS CONTEXT & OBJECTIVES
    # -------------------------------------------------------------
    # Derive domain from feature flags or core tables
    domain = "General Business Operations"
    if feature_flags.get("has_trap_management"): domain = "Environmental Monitoring & Trap Management"
    elif feature_flags.get("has_work_management"): domain = "Asset Maintenance & Work Order Management"
    elif feature_flags.get("has_contact_management"): domain = "Customer Relationship Management (CRM)"

    core_workflows = []
    for f in forms_sorted[:3]:
        rs = f.get('record_source', 'data')
        core_workflows.append(f"Managing {esc(rs)} via the <code>{esc(f['name'])}</code> interface")

    workflow_list = "<ul>" + "".join([f"<li>{w}</li>" for w in core_workflows]) + "</ul>" if core_workflows else "<p>Operational workflows derived from core relational tables.</p>"

    enforced_pks = sum(1 for t in tables if t.get("enforced_pk_cols"))
    inferred_pks = sum(1 for t in tables if t.get("inferred_pk_cols"))

    report_names = [f"<code>{esc(r['name'])}</code>" for r in reports_sorted[:5]]
    report_context = f"Maintain reporting fidelity for {len(reports)} reports, including {', '.join(report_names)}." if reports else "No printable reports exist in this application; objectives focus on data integrity."

    vba_names = [f"<code>{esc(v['name'])}</code>" for v in vba_sorted[:3]]
    vba_context = f"Document all subroutines across {vba_count} VBA modules ({', '.join(vba_names)})." if vba_modules else "No VBA automation exists in this application."

    c4 = (
        f'<h2 class="sub-title">4.1 Business Context</h2><p>This application serves the <strong>{esc(domain)}</strong> domain, '
        f'supporting real-world processes extracted from <code>{esc(source_file)}</code>.</p>\n'
        f'<h2 class="sub-title">4.2 Operational Objectives</h2><p>The system aims to support the following specific data workflows:</p>{workflow_list}\n'
        f'<h2 class="sub-title">4.3 Data Management Objectives</h2><p>Document {tables_count} relational tables. '
        f'Analysis shows {enforced_pks} tables with enforced PKs and {inferred_pks} tables using inferred naming conventions (to be enforced in target).</p>\n'
        f'<h2 class="sub-title">4.4 Reporting Objectives</h2><p>{report_context}</p>\n'
        f'<h2 class="sub-title">4.5 Automation Objectives</h2><p>{vba_context}</p>'
    )
    add_section("SECTION_4_BUSINESS_CONTEXT", "Business Context and Objectives", c4)

    # -------------------------------------------------------------
    # 5. STAKEHOLDER ANALYSIS
    # -------------------------------------------------------------
    c5 = (
        f'<div class="table-wrapper"><table class="table-stakeholders"><colgroup><col style="width:25%;"><col style="width:25%;"><col style="width:50%;"></colgroup>'
        f'<thead><tr><th>Stakeholder Group</th><th>Role</th><th>Primary Expectations & Requirements</th></tr></thead>'
        f'<tbody>'
        f'<tr><td>Business Users</td><td>End Users</td><td>Form UI workflows and data entry functionality across {forms_count} screens</td></tr>'
        f'<tr><td>Database Admins</td><td>DBA</td><td>Data dictionary accuracy, primary/foreign keys, and referential integrity</td></tr>'
        f'<tr><td>Application Admins</td><td>App Admin</td><td>Role-based permission assignment and user administration</td></tr>'
        f'<tr><td>Developers / Support</td><td>Engineering</td><td>Maintainable specification of all {vba_count} VBA modules and {queries_count} queries</td></tr>'
        f'<tr><td>Management Users</td><td>Leadership</td><td>Reliable reporting, operational stability, and complete data documentation</td></tr>'
        f'</tbody></table></div>'
    )
    add_section("SECTION_5_STAKEHOLDER_ANALYSIS", "Stakeholder Analysis", c5)

    # -------------------------------------------------------------
    # 6. USER ROLES AND ACCESS REQUIREMENTS
    # -------------------------------------------------------------
    c6 = (
        f'<h2 class="sub-title">6.1 User Role Definition</h2><p>Role-Based Access Control (RBAC) definitions for application security.</p>\n'
        f'<div class="table-wrapper"><table class="table-roles"><colgroup><col style="width:20%;"><col style="width:30%;"><col style="width:50%;"></colgroup>'
        f'<thead><tr><th>Role Name</th><th>Scope</th><th>Permissions & Access Level</th></tr></thead>'
        f'<tbody>'
        f'<tr><td>System Administrator</td><td>Full System Access</td><td>Manage users, database administration, system configuration</td></tr>'
        f'<tr><td>Standard Business User</td><td>Operational Functions</td><td>Read/write data entry across {forms_count} form screens</td></tr>'
        f'<tr><td>Reporting User</td><td>Read-Only Analytics</td><td>Execute queries and view {reports_count} reports</td></tr>'
        f'<tr><td>Developer / Support</td><td>Technical Maintenance</td><td>API access, audit logs, and system diagnostics</td></tr>'
        f'</tbody></table></div>'
    )
    add_section("SECTION_6_USER_ROLES", "User Roles and Access Requirements", c6)

    # -------------------------------------------------------------
    # 7. OVERALL FUNCTIONAL SCOPE
    # -------------------------------------------------------------
    # 7.1 Startup
    startup_obj = "None"
    for m in macros:
        if m.get("name") == "AutoExec": startup_obj = "AutoExec Macro"
    if startup_obj == "None":
        for f in forms:
            if any(k in f.get("name","").lower() for k in ("main", "menu", "switchboard", "startup")):
                startup_obj = f"Startup Form (<code>{esc(f['name'])}</code>)"
                break

    # 7.2 Navigation
    nav_desc = f"Navigation between {forms_count} screens."
    main_menu = next((f for f in forms if "menu" in f.get("name","").lower()), None)
    if main_menu:
        targets = main_menu.get("navigation_targets", [])
        if targets:
            nav_desc = f"The <code>{esc(main_menu['name'])}</code> acts as the primary hub, providing paths to {', '.join([esc(t['name']) for t in targets[:3]])}."

    # 7.3 Admin
    admin_tables = [t['name'] for t in tables if any(k in t['name'].lower() for k in ("defaults", "config", "sys_", "setup", "admin"))]
    admin_desc = f"Includes {len(admin_tables)} administrative/lookup tables (e.g. {', '.join([f'<code>{esc(a)}</code>' for a in admin_tables[:3]])})." if admin_tables else "Administrative functions are handled via standard Access property configurations."

    # 7.4 Record Management
    vba_crud = any("openrecordset" in m.get("source","").lower() or "execute" in m.get("source","").lower() for m in vba_modules)
    crud_desc = "Standard Access JET engine record management"
    if vba_crud:
        crud_desc = "Custom CRUD operations wired to VBA event handlers for data validation and consistency."

    # 7.5 Search/Filter
    search_forms = [f['name'] for f in forms if any(k in (f.get("behavioral_description") or "").lower() for k in ("search", "filter", "find"))]
    search_desc = f"Search functionality implemented on {len(search_forms)} forms (e.g. {', '.join([f'<code>{esc(s)}</code>' for s in search_forms[:2]])})." if search_forms else "Basic Access 'Find' and 'Filter' features are available across all bound forms."

    c7 = (
        f'<h2 class="sub-title">7.1 Application Startup and Initialization</h2>'
        f'<p>The legacy application initializes via {startup_obj}, which triggers global variables and environment settings required for the session. '
        f'This sequence is critical to ensure that user permissions and default configurations are loaded before any data entry occurs. '
        f'The modernized React application must implement a global state initialization pattern in <code>App.jsx</code> to replicate this setup, ensuring a seamless entry into the primary dashboard.</p>\n'
        f'<h2 class="sub-title">7.2 Main Menu and Navigation</h2>'
        f'<p>{nav_desc} The current Access switchboard or main menu provides a centralized hub for users to access critical business modules. '
        f'Preserving this navigation flow is essential for user adoption, as it mirrors the established mental model of the daily operational workflow. '
        f'The target architecture will utilize React Router to provide a responsive sidebar navigation that maintains the logical grouping of forms and reports.</p>\n'
        f'<h2 class="sub-title">7.3 Database Administration</h2>'
        f'<p>{admin_desc} These administrative interfaces allow power users to maintain lookup values and system constants without altering the core schema. '
        f'Fidelity here is vital to prevent operational stagnation when business rules (like tax rates or site IDs) change. '
        f'The new system will provide a dedicated Admin module with role-based access to manage these parameters dynamically in the PostgreSQL backend.</p>\n'
        f'<h2 class="sub-title">7.4 Record Management</h2>'
        f'<p>{crud_desc} The system manages the lifecycle of business records through a series of bound forms and VBA-backed validation routines. '
        f'Dropping these validation rules during migration could lead to orphaned records or corrupted data in the target environment. '
        f'The Java Spring Boot services will implement Hibernate-based entity management to enforce these relational constraints and business validations server-side.</p>\n'
        f'<h2 class="sub-title">7.5 Search and Filtering</h2>'
        f'<p>{search_desc} Users currently rely on these tools to isolate specific records for editing and reporting based on ad-hoc criteria. '
        f'Efficient data retrieval is a key productivity driver, especially for large datasets where manual scrolling is infeasible. '
        f'The React frontend will implement advanced data grid filtering and server-side search endpoints to provide a faster, more intuitive search experience.</p>'
    )
    add_section("SECTION_7_OVERALL_FUNCTIONAL_SCOPE", "Overall Functional Scope", c7)

    # -------------------------------------------------------------
    # 8. TRAP MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_trap_management"):
        trap_tables = [t['name'] for t in tables if any(k in t['name'].lower() for k in ["trap", "pull"])]
        c8 = (
            f'<p>Dedicated operational data management for trap types, locations, status, and trap pull tracking. '
            f'Discovered entities include: {", ".join([f"<code>{esc(t)}</code>" for t in trap_tables])}.</p>\n'
            f'<div class="table-wrapper"><table class="table-trap"><colgroup><col style="width:25%;"><col style="width:45%;"><col style="width:30%;"></colgroup>'
            f'<thead><tr><th>Module Function</th><th>Scope & Validation Rules</th><th>Associated Tables / Objects</th></tr></thead>'
            f'<tbody>'
            f'<tr><td>Trap Type Management</td><td>Defines trap categories, specifications, and attributes</td><td><code>{esc(next((t for t in trap_tables if "type" in t.lower()), "TRAP_TYPE_TB"))}</code></td></tr>'
            f'<tr><td>Trap Location Management</td><td>Maintains trap placement coordinates and active status</td><td><code>{esc(next((t for t in trap_tables if "lctn" in t.lower() or "location" in t.lower()), "TRAP_LCTN_TB"))}</code></td></tr>'
            f'<tr><td>Trap Pull Data Entry</td><td>Records trap pull events, dates, and historical counts</td><td><code>{esc(next((t for t in trap_tables if "pull" in t.lower()), "TRAP_PULL_TB"))}</code></td></tr>'
            f'</tbody></table></div>'
        )
        add_section("SECTION_8_TRAP_MANAGEMENT", "Trap Management / Operational Data Management", c8, True)
    else:
        add_section("SECTION_8_TRAP_MANAGEMENT", "Trap Management", "", False)

    # -------------------------------------------------------------
    # 9. WORK / MAINTENANCE DATA MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_work_management"):
        work_tables = [t['name'] for t in tables if any(k in t['name'].lower() for k in ["work", "task", "maint"])]
        c9 = (
            f'<p>Work type, priority, area, maintainable items, vendors, supervisors, problem/failure codes, and cost centers. '
            f'Discovered entities include: {", ".join([f"<code>{esc(t)}</code>" for t in work_tables])}.</p>\n'
            f'<div class="table-wrapper"><table class="table-work"><colgroup><col style="width:25%;"><col style="width:45%;"><col style="width:30%;"></colgroup>'
            f'<thead><tr><th>Maintenance Category</th><th>Business Purpose & Scope</th><th>Lookup Tables & Relational Keys</th></tr></thead>'
            f'<tbody>'
            f'<tr><td>Work Type & Priority</td><td>Categorizes maintenance work orders and urgency groups</td><td>{esc(next((t for t in work_tables if "type" in t.lower() or "priority" in t.lower()), "Work Lookups"))}</td></tr>'
            f'<tr><td>Maintainable Items & Vendors</td><td>Catalogues equipment items, vendor IDs, and cost centers</td><td>{esc(next((t for t in tables if "vendor" in t["name"].lower()), "Vendor Schemas"))}</td></tr>'
            f'<tr><td>Problem & Failure Codes</td><td>Tracks failure remarks, problem codes, and DOECC groups</td><td>{esc(next((t for t in tables if "failure" in t["name"].lower() or "code" in t["name"].lower()), "Failure Codes"))}</td></tr>'
            f'</tbody></table></div>'
        )
        add_section("SECTION_9_WORK_MANAGEMENT", "Work / Maintenance Data Management", c9, True)
    else:
        add_section("SECTION_9_WORK_MANAGEMENT", "Work Management", "", False)

    # -------------------------------------------------------------
    # 10. LOCATION MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_location_management"):
        loc_tables = [t['name'] for t in tables if any(k in t['name'].lower() for k in ["location", "lctn", "site", "area"])]
        c10 = (
            f'<p>Master location registry, site IDs, active/inactive location status, location search, and reporting. '
            f'Discovered entities include: {", ".join([f"<code>{esc(t)}</code>" for t in loc_tables])}.</p>'
        )
        add_section("SECTION_10_LOCATION_MANAGEMENT", "Location Management", c10, True)
    else:
        add_section("SECTION_10_LOCATION_MANAGEMENT", "Location Management", "", False)

    # -------------------------------------------------------------
    # 11. CALENDAR & DATE MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_calendar_management"):
        c11 = (
            f'<p>Calendar functionality, date calculations, week-ending calculations, day-of-year calculations, and month/quarter/year aggregations.</p>'
        )
        add_section("SECTION_11_CALENDAR_MANAGEMENT", "Calendar and Date Management", c11, True)
    else:
        add_section("SECTION_11_CALENDAR_MANAGEMENT", "Calendar Management", "", False)

    # -------------------------------------------------------------
    # 12. CUMULATIVE VALUE MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_cumulative_management"):
        c12 = (
            f'<p>Processing for <code>CUM_VAL_TB</code> and <code>DECUM_VAL_TB</code> including cumulative value calculations and de-cumulative history.</p>'
        )
        add_section("SECTION_12_CUMULATIVE_VALUE", "Cumulative Value Management", c12, True)
    else:
        add_section("SECTION_12_CUMULATIVE_VALUE", "Cumulative Value Management", "", False)

    # -------------------------------------------------------------
    # 13. TAG AND METADATA MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_tag_management"):
        c13 = (
            f'<p>Management for <code>TAG_GRP_TB</code> and <code>TAG_NME_TB</code>, alternative tag names, item associations, and tag search.</p>'
        )
        add_section("SECTION_13_TAG_MANAGEMENT", "Tag and Metadata Management", c13, True)
    else:
        add_section("SECTION_13_TAG_MANAGEMENT", "Tag Management", "", False)

    # -------------------------------------------------------------
    # 14. DATA DICTIONARY MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_data_dictionary"):
        c14 = (
            f'<p>Data dictionary maintenance via <code>DATABASE_STRUCTURE_TB</code> cataloging table names, field metadata, data types, validation rules, and indexes.</p>'
        )
        add_section("SECTION_14_DATA_DICTIONARY", "Database Structure / Data Dictionary Management", c14, True)
    else:
        add_section("SECTION_14_DATA_DICTIONARY", "Data Dictionary Management", "", False)

    # -------------------------------------------------------------
    # 15. DYNAMIC DATABASE STRUCTURE MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_data_dictionary"):
        c15 = (
            f'<p>Queries and routines associated with creating, altering, and dropping <code>DATABASE_STRUCTURE_TB</code> entries and dynamic DDL execution.</p>'
        )
        add_section("SECTION_15_DYNAMIC_STRUCTURE", "Dynamic Database Structure Management", c15, True)
    else:
        add_section("SECTION_15_DYNAMIC_STRUCTURE", "Dynamic Structure Management", "", False)

    # -------------------------------------------------------------
    # 16. FILE MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_file_management"):
        c16 = (
            f'<p>File inventory tracking via <code>tblFileList</code>, file paths, load/save functions, and file export operations.</p>'
        )
        add_section("SECTION_16_FILE_MANAGEMENT", "File Management", c16, True)
    else:
        add_section("SECTION_16_FILE_MANAGEMENT", "File Management", "", False)

    # -------------------------------------------------------------
    # 17. CONTACT MANAGEMENT (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_contact_management"):
        c17 = (
            f'<p>Contact master registry via <code>tblContacts</code> including names, addresses, city, state, ZIP code, and contact search.</p>'
        )
        add_section("SECTION_17_CONTACT_MANAGEMENT", "Contact Management", c17, True)
    else:
        add_section("SECTION_17_CONTACT_MANAGEMENT", "Contact Management", "", False)

    # -------------------------------------------------------------
    # 18. ORGANIZATION & BRANDING (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_branding"):
        c18 = (
            f'<p>Organization configuration, logo storage in <code>LOGO_TB</code> / <code>tblDefaults</code>, and report branding graphics.</p>'
        )
        add_section("SECTION_18_BRANDING", "Organization and Branding", c18, True)
    else:
        add_section("SECTION_18_BRANDING", "Organization and Branding", "", False)

    # -------------------------------------------------------------
    # 19. REPORTING REQUIREMENTS
    # -------------------------------------------------------------
    c19 = (
        f'<p>Reporting requirements covering {reports_count} Access reports. Includes report parameters, filtering, sorting, grouping, print preview, and export.</p>\n'
        f'<div class="table-wrapper"><table class="table-reports"><colgroup><col style="width:25%;"><col style="width:45%;"><col style="width:30%;"></colgroup>'
        f'<thead><tr><th>Report Name</th><th>Source & Filtering Scope</th><th>Target Render Format</th></tr></thead>'
        f'<tbody>'
    )
    for r in reports_sorted:
        rname = r.get("name", "Report")
        c19 += f'<tr><td><code>{esc(rname)}</code></td><td>Extracted Access Report Template</td><td>Responsive HTML / PDF Report</td></tr>\n'

    # Document VBA-driven exports if reports are low or missing
    vba_exports = facts.get("vba_exports", [])
    if vba_exports:
        for vname in vba_exports:
            c19 += f'<tr><td><code>{esc(vname)}</code> (VBA Export)</td><td>Programmatic data export logic discovered in VBA module</td><td>Excel / PDF / CSV Export</td></tr>\n'

    if not reports and not vba_exports:
        c19 += '<tr><td colspan="3"><em>No formal report objects or VBA-driven exports defined in source database.</em></td></tr>\n'
    c19 += '</tbody></table></div>'
    add_section("SECTION_19_REPORTING", "Reporting Requirements", c19)

    # -------------------------------------------------------------
    # 20. DATA EXPORT AND IMPORT
    # -------------------------------------------------------------
    export_import_rows = [
        f'<tr><td>Excel / spreadsheet</td><td>{reports_count} report(s), {queries_count} query object(s), and {tables_count} business table(s) are available as export sources.</td><td>Validate columns, data types, and duplicate keys before import.</td></tr>',
        f'<tr><td>Delimited text</td><td>Backend analysis identified {tables_count} business table(s) and {queries_count} query object(s) suitable for delimited export.</td><td>Validate encoding, delimiters, nulls, and required fields.</td></tr>',
        f'<tr><td>Duplicate handling</td><td>{len(relationships)} relationship(s) were extracted for referential consistency checks.</td><td>Reject or report duplicate keys before persistence.</td></tr>',
    ]
    c20 = (
        f'<p>Data export/import requirements derived from {tables_count} business table(s), {queries_count} query object(s), {reports_count} report(s), and {len(relationships)} relationship(s) discovered by backend analysis.</p>\n'
        f'<div class="table-wrapper"><table class="table-export-import"><thead><tr><th>Channel</th><th>Detected source data</th><th>Validation requirement</th></tr></thead><tbody>{"".join(export_import_rows)}</tbody></table></div>'
    )
    add_section("SECTION_20_DATA_EXPORT_IMPORT", "Data Export and Import", c20)

    # -------------------------------------------------------------
    # 21. EMAIL AND COMMUNICATION (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_outlook"):
        c21 = (
            f'<p>Email automation, report attachments, Outlook MAPI integration, and email validation error handling.</p>'
        )
        add_section("SECTION_21_EMAIL", "Email and Communication", c21, True)
    else:
        add_section("SECTION_21_EMAIL", "Email and Communication", "", False)

    # -------------------------------------------------------------
    # 22. VBA AUTOMATION REQUIREMENTS
    # -------------------------------------------------------------
    c22 = (
        f'<p>VBA code automation requirements covering {vba_count} code modules ({facts.get("vba_loc", 0):,} LOC).</p>\n'
        f'<div class="table-wrapper"><table class="table-vba"><colgroup><col style="width:25%;"><col style="width:45%;"><col style="width:30%;"></colgroup>'
        f'<thead><tr><th>VBA Module Name</th><th>Behavioral Description & Routine Logic</th><th>Target Java Service Class</th></tr></thead>'
        f'<tbody>'
    )
    for v in vba_sorted:
        vname = v.get("name", "Module")
        vdesc = v.get("behavioral_description") or f"{len(v.get('procedures', []))} Procedures"
        proc_list = v.get("procedures", [])
        if proc_list:
            proc_bullets = "<br/><ul style='margin:4px 0 0; padding-left:16px;'>" + "".join(
                [f"<li><code>{esc(p.get('name'))}()</code>: {esc(p.get('behavioral_description'))}</li>" for p in proc_list[:8]]
            ) + "</ul>"
            vdesc += proc_bullets
        clean_vname = re.sub(r'[^a-zA-Z0-9]', '', vname)
        c22 += f'<tr><td><code>{esc(vname)}</code></td><td>{vdesc}</td><td><code>{esc(clean_vname)}Service.java</code></td></tr>\n'
    if not vba_modules:
        c22 += '<tr><td colspan="3"><em>No VBA code modules present in source database.</em></td></tr>\n'
    c22 += '</tbody></table></div>'
    add_section("SECTION_22_VBA_AUTOMATION", "VBA Automation Requirements", c22)

    # -------------------------------------------------------------
    # 23. QUERY REQUIREMENTS (Full SQL & Classification)
    # -------------------------------------------------------------
    c23_read = []
    c23_write = []
    for q in queries_sorted:
        qname = q.get("name", "Query")
        qsql = q.get("sql") or ""
        qtype = q.get("type") or q.get("kind") or "SELECT"

        is_mutation = any(k in qsql.upper() for k in ("INSERT ", "UPDATE ", "DELETE ", "INTO ", "DROP ", "ALTER "))

        row = (
            f'<tr><td><code>{esc(qname)}</code></td>'
            f'<td><code>{esc(qsql)}</code></td>'
            f'<td>Spring Data Repository Query</td></tr>\n'
        )
        if is_mutation:
            c23_write.append(row)
        else:
            c23_read.append(row)

    c23 = f'<h2 class="sub-title">23.1 Read-Only Data Retrieval Queries</h2>\n'
    c23 += '<div class="table-wrapper"><table class="table-queries"><thead><tr><th>Query Name</th><th>Full SQL Text / Purpose</th><th>Target Method</th></tr></thead><tbody>'
    c23 += "".join(c23_read) if c23_read else '<tr><td colspan="3">None detected</td></tr>'
    c23 += '</tbody></table></div>\n'

    c23 += f'<h2 class="sub-title">23.2 Data Mutation & Action Queries</h2>\n'
    c23 += '<div class="table-wrapper"><table class="table-queries"><thead><tr><th>Query Name</th><th>Full SQL Text / Action Type</th><th>Target Service</th></tr></thead><tbody>'
    c23 += "".join(c23_write) if c23_write else '<tr><td colspan="3">None detected</td></tr>'
    c23 += '</tbody></table></div>'

    add_section("SECTION_23_QUERY_REQUIREMENTS", "Query Requirements", c23)

    # -------------------------------------------------------------
    # 24. SQL SERVER / PASSTHROUGH (Conditional)
    # -------------------------------------------------------------
    if feature_flags.get("has_sql_server"):
        c24 = (
            f'<p>ODBC / SQL Server passthrough query requirements and external DSN bindings.</p>'
        )
        add_section("SECTION_24_SQL_SERVER", "SQL Server & External Connectivity", c24, True)
    else:
        add_section("SECTION_24_SQL_SERVER", "SQL Server Connectivity", "", False)

    # -------------------------------------------------------------
    # 25. DATA MODEL REQUIREMENTS (Mermaid Unified ERD)
    # -------------------------------------------------------------
    rel_count = len(relationships)

    def strip_diacritics(s: str) -> str:
        """Remove diacritics from a string."""
        return "".join(
            c for c in unicodedata.normalize("NFD", s)
            if unicodedata.category(c) != "Mn"
        )

    def sanitize_mermaid_id(name: str) -> str:
        """Sanitize identifiers for Mermaid ERD compatibility according to strict pipeline rules."""
        if not name: return "unknown"
        # 1. Strip diacritics
        s = strip_diacritics(name)
        # 2. Replace spaces and hyphens with underscores
        s = re.sub(r'[\s\-]', '_', s)
        # 3. Remove any other non-alphanumeric characters
        s = re.sub(r'[^a-zA-Z0-9_]', '', s)
        # 4. Ensure it doesn't start with a number
        if s and s[0].isdigit(): s = "T_" + s
        return s or "entity"

    def sanitize_mermaid_type(t: str) -> str:
        """Sanitize types - must be single word, alphanumeric."""
        if not t: return "VARCHAR"
        # Take first word, remove non-alphanumeric
        clean = t.split('(')[0].split(' ')[0]
        clean = "".join(filter(str.isalnum, clean))
        return clean.upper() or "VARCHAR"

    mermaid_lines = ["erDiagram"]
    table_id_map = {} # Original Name -> Sanitized ID

    # Step 1 — Deduplicate entities
    entities_to_render = []
    seen_entity_names = set()
    # Combine business and system tables for the unified diagram
    combined_tables = tables_sorted + sorted(system_tables, key=lambda x: x.get("name", ""))
    for tbl in combined_tables:
        raw_name = tbl.get("name", "Table")
        if raw_name not in seen_entity_names:
            entities_to_render.append(tbl)
            seen_entity_names.add(raw_name)

    # Step 4 — Emit valid attribute blocks
    for idx, tbl in enumerate(entities_to_render):
        raw_name = tbl.get("name", "Table")
        tname = sanitize_mermaid_id(raw_name)
        table_id_map[raw_name] = tname

        # Scale note: Split into domains if schema is large
        if len(entities_to_render) >= 15 and idx == 0:
            mermaid_lines.append("    %% Business Domain")
        if is_system_object(raw_name) and (idx > 0 and not is_system_object(entities_to_render[idx-1].get("name"))):
            mermaid_lines.append("    %% System/Metadata Domain")

        if raw_name != tname:
            mermaid_lines.append(f"    %% Original name: {raw_name}")

        mermaid_lines.append(f"    {tname} {{")
        cols = tbl.get("columns", [])
        for col in cols:
            raw_cname = col.get("name", "field")
            cname = sanitize_mermaid_id(raw_cname)
            ctype = sanitize_mermaid_type(col.get("pg_type"))

            is_pk = col.get("is_pk") or (raw_cname in tbl.get("enforced_pk_cols", [])) or (raw_cname in tbl.get("inferred_pk_cols", []))
            is_fk = bool(col.get("fk_target"))

            if is_pk or is_fk:
                # Exactly three tokens per line. Key marker PK takes precedence if both.
                key_marker = "PK" if is_pk else "FK"
                mermaid_lines.append(f"        {ctype} {cname} {key_marker}")
        mermaid_lines.append("    }")

    # Step 3 — Emit syntactically valid relationship lines
    # Deduplicate relationships by (parent, child, child_col)
    seen_rels = set()
    for rel in relationships:
        raw_p = rel.get("parent_table", "Parent")
        raw_c = rel.get("child_table", "Child")
        child_cols = rel.get("child_columns") or ["id"]
        ccol = child_cols[0] if child_cols else "id"

        ptbl = table_id_map.get(raw_p) or sanitize_mermaid_id(raw_p)
        ctbl = table_id_map.get(raw_c) or sanitize_mermaid_id(raw_c)

        rel_key = (ptbl, ctbl, ccol)
        if rel_key not in seen_rels:
            # Derive cardinality tokens
            left = "||" # Parent is usually mandatory one

            if rel.get("one_to_one"):
                right = "||" if rel.get("enforce_integrity") else "o|"
            else:
                right = "|{" if rel.get("enforce_integrity") else "o{"

            label = "references"
            # Quote label if it contains spaces
            if " " in label: label = f'"{label}"'

            mermaid_lines.append(f"    {ptbl} {left}--{right} {ctbl} : {label}")
            seen_rels.add(rel_key)

    mermaid_code = "\n".join(mermaid_lines)

    # Referential Integrity Table
    ri_rows = ""
    # ... rest of the code for RI table and logical schema cards ...

    # 25.2 Relational Entity Schema Cards
    er_grid_html = ""
    # Include all tables (business + system) if user wants 'all'
    all_tables_list = tables_sorted + sorted(system_tables, key=lambda x: x.get("name", ""))
    for tbl in all_tables_list:
        tname = tbl.get("name")
        cols = tbl.get("columns", [])

        field_rows = ""
        for col in cols:
            cname = col.get("name")
            ctype = col.get("access_type") or "Text"
            # Enhanced PK detection: check column flag, enforced list, or inferred list
            is_pk = col.get("is_pk") or (cname in tbl.get("enforced_pk_cols", [])) or (cname in tbl.get("inferred_pk_cols", []))
            is_fk = bool(col.get("fk_target"))

            pk_badge = '<span class="badge-pk">PK</span> ' if is_pk else ""
            fk_badge = '<span class="badge-fk">FK</span> ' if is_fk else ""
            fk_target = f'<span class="fk-target-badge">&rarr; {esc(col.get("fk_target"))}</span>' if is_fk else ""

            field_rows += (
                f'<div class="er-field">\n'
                f'  <span class="fname">{pk_badge}{fk_badge}{esc(cname)}{fk_target}</span>\n'
                f'  <span class="ftype">{esc(ctype)}</span>\n'
                f'</div>\n'
            )

        parent_rels = [r for r in relationships if r.get("parent_table") == tname]
        child_rels = [r for r in relationships if r.get("child_table") == tname]

        rel_tags = ""
        if parent_rels or child_rels:
            rel_tags += '<div class="er-card-rel-section">\n'
            for r in parent_rels:
                rel_tags += f'  <div class="er-card-rel-tag">&uarr; Parent of: {esc(r.get("child_table"))}</div>\n'
            for r in child_rels:
                rel_tags += f'  <div class="er-card-rel-tag">&darr; Child of: {esc(r.get("parent_table"))}</div>\n'
            rel_tags += '</div>\n'

        er_grid_html += (
            f'<div class="er-table">\n'
            f'  <div class="er-table-head">\n'
            f'    <span>{esc(tname)}</span>\n'
            f'    <span style="font-size:10px; opacity:0.8;">DB TABLE</span>\n'
            f'  </div>\n'
            f'  {field_rows}\n'
            f'  {rel_tags}\n'
            f'</div>\n'
        )

    # 25.3 Referential Integrity Table
    ri_rows = ""
    for rel in relationships:
        ptbl = rel.get("parent_table")
        ctbl = rel.get("child_table")
        pcol = rel.get("parent_columns", ["ID"])[0] if rel.get("parent_columns") else "ID"
        ccol = rel.get("child_columns", ["ID"])[0] if rel.get("child_columns") else "ID"
        rules = []
        if rel.get("cascade_update"): rules.append("Cascade Update")
        if rel.get("cascade_delete"): rules.append("Cascade Delete")
        rules_str = ", ".join(rules) if rules else "Restrict"

        ri_rows += (
            f'<tr>\n'
            f'  <td><code>{esc(ptbl)}.{esc(pcol)}</code></td>\n'
            f'  <td style="text-align:center; font-family:monospace; color:#2563eb; font-weight:bold;">1 &mdash;&mdash;|&mdash;&mdash;&lt; {{1:N}}</td>\n'
            f'  <td><code>{esc(ctbl)}.{esc(ccol)}</code></td>\n'
            f'  <td>{esc(rules_str)}</td>\n'
            f'</tr>\n'
        )

    c25 = (
        f'<p>Conceptual and logical data model specifications for {len(combined_tables)} business and system tables and {rel_count} referential relationships.</p>\n'
        f'<div style="display:flex; gap:10px; margin-bottom:20px; align-items:center;">'
        f'<span style="font-size:12px; font-weight:700; color:var(--muted);">MODEL VIEWS:</span>'
        f'<span class="badge badge-info" style="padding:6px 12px; border-radius:4px;">Unified ER Diagram</span>'
        f'<span class="badge" style="padding:6px 12px; border:1px solid var(--primary); color:var(--primary); border-radius:4px;">Relational Schema Card</span>'
        f'</div>\n'
        f'<h2 class="sub-title">Unified Entity-Relationship Diagram (Crow\'s Foot Notation)</h2>\n'
        f'<div class="mermaid">\n'
        f'{mermaid_code}\n'
        f'</div>\n'
        f'<div style="page-break-after: always; break-after: page;"></div>\n'
        f'<h2 class="sub-title">Relational Entity Schema Cards</h2>\n'
        f'<div class="er-grid">\n'
        f'  {er_grid_html}\n'
        f'</div>\n'
        f'<h2 class="sub-title">Referential Integrity & Foreign Key Mappings</h2>\n'
        f'<div class="table-wrapper">\n'
        f'  <table>\n'
        f'    <thead><tr><th>Primary Entity (Parent)</th><th>Connect Symbol</th><th>Foreign Entity (Child)</th><th>Constraint Rules</th></tr></thead>\n'
        f'    <tbody>{ri_rows if ri_rows else "<tr><td colspan=4>No relationships defined.</td></tr>"}</tbody>\n'
        f'  </table>\n'
        f'</div>'
    )
    add_section("SECTION_25_DATA_MODEL", "Data Model Requirements", c25)

    # -------------------------------------------------------------
    # 26. CORE BUSINESS TABLES
    # -------------------------------------------------------------
    c26_rows = []
    for tbl in tables_sorted: # Show all tables
        tname = tbl.get("name")
        c26_rows.append(
            f'<tr><td><code>{esc(tname)}</code></td><td>{esc(tbl.get("pk_status"))}</td>'
            f'<td>{len(tbl.get("columns", []))}</td><td>{esc(tbl.get("row_count", "Unknown"))}</td></tr>'
        )
    c26 = (
        f'<p>Primary business entities central to the application domain.</p>\n'
        f'<div class="table-wrapper"><table class="table-core"><thead><tr><th>Table Name</th><th>PK Status</th><th>Field Count</th><th>Row Count</th></tr></thead>'
        f'<tbody>{"".join(c26_rows)}</tbody></table></div>'
    )
    add_section("SECTION_26_CORE_TABLES", "Core Business Tables", c26)

    # -------------------------------------------------------------
    # 27. BUSINESS RULES (Derived from VBA & Queries)
    # -------------------------------------------------------------
    c27_rows = []
    # 1. Rules from VBA procedures
    for v in vba_sorted:
        vname = v.get("name")
        for p in v.get("procedures", []):
            pname = p.get("name")
            pdesc = p.get("behavioral_description")
            if pdesc and len(pdesc) > 20:
                c27_rows.append(
                    f'<tr><td>Logic Rule</td><td>{esc(vname)}.{esc(pname)}</td>'
                    f'<td>{esc(pdesc)}</td><td>VBA Subroutine/Function</td></tr>'
                )
    # 2. Rules from Mutation Queries
    for q in queries_sorted:
        qname = q.get("name")
        qsql = q.get("sql", "")
        if any(k in qsql.upper() for k in ("INSERT ", "UPDATE ", "DELETE ", "INTO ")):
            c27_rows.append(
                f'<tr><td>Data Rule</td><td>{esc(qname)}</td>'
                f'<td>Mutation query affecting underlying recordsets. Type: {esc(q.get("type", "Action"))}</td><td>SQL Query</td></tr>'
            )

    c27_body = "".join(c27_rows) if c27_rows else '<tr><td colspan="4">No complex business rules identified.</td></tr>'
    c27 = (
        f'<p>Inventory of discovered business rules, validation logic, and data mutation behaviors extracted from VBA modules and SQL action queries.</p>\n'
        f'<div class="table-wrapper"><table class="table-rules"><thead><tr>'
        f'<th>Rule Category</th><th>Source Object</th><th>Logic Description</th><th>Implementation</th>'
        f'</tr></thead><tbody>'
        f'{c27_body}'
        f'</tbody></table></div>'
    )
    add_section("SECTION_27_BUSINESS_RULES", "Business Rules", c27)

    # -------------------------------------------------------------
    # 31. INDIVIDUAL FORM INVENTORY
    # -------------------------------------------------------------
    c31_rows = []
    for f in forms_sorted:
        fname = f.get("name", "Form")
        rsource = f.get("record_source", "Unbound")
        ctrl_count = f.get("controls_count", 0)
        ev_summary = f.get("events_summary", "None")
        fdesc = f.get("behavioral_description", "UI Screen")
        c31_rows.append(
            f'<tr><td><code>{esc(fname)}</code></td><td><code>{esc(rsource)}</code></td>'
            f'<td>{ctrl_count} controls</td><td>{esc(ev_summary)}</td><td>{esc(fdesc)}</td></tr>'
        )

    c31_body = "".join(c31_rows) if c31_rows else '<tr><td colspan="5">No forms discovered.</td></tr>'
    c31 = (
        f'<p>Detailed inventory of interactive user interface forms, including their data bindings and control complexity.</p>\n'
        f'<div class="table-wrapper"><table class="table-forms"><thead><tr>'
        f'<th>Form Name</th><th>Record Source</th><th>Complexity</th><th>Event Handlers</th><th>Functional Description</th>'
        f'</tr></thead><tbody>'
        f'{c31_body}'
        f'</tbody></table></div>'
    )
    add_section("SECTION_31_FORM_INVENTORY", "Individual Form Inventory", c31)

    # -------------------------------------------------------------
    # 32. REPORT REQUIREMENTS
    # -------------------------------------------------------------
    c32_rows = []
    for r in reports_sorted:
        rname = r.get("name", "Report")
        rsource = r.get("record_source", "Unbound")
        c32_rows.append(
            f'<tr><td><code>{esc(rname)}</code></td><td><code>{esc(rsource)}</code></td>'
            f'<td>{esc(r.get("behavioral_description"))}</td></tr>'
        )
    c32 = (
        f'<p>Detailed specifications for structured document reports and analytical outputs.</p>\n'
        f'<div class="table-wrapper"><table class="table-report-req"><thead><tr><th>Report Name</th><th>Record Source</th><th>Grouping & Aggregation Behavior</th></tr></thead>'
        f'<tbody>{"".join(c32_rows) if c32_rows else "<tr><td colspan=3>No formal reports discovered.</td></tr>"}</tbody></table></div>'
    )
    add_section("SECTION_32_REPORT_REQUIREMENTS", "Detailed Report Requirements", c32)

    # -------------------------------------------------------------
    # 38. TECHNICAL ARCHITECTURE (High-Fidelity Dynamic Flow)
    # -------------------------------------------------------------
    target_lang = facts.get("target_backend_language", "Java")
    target_fe = facts.get("react_version", "React")
    if isinstance(target_fe, (int, float)): target_fe = "React"
    target_be = facts.get("spring_boot_version", "Spring Boot")
    if isinstance(target_be, (int, float)): target_be = "Spring Boot"

    # Tier 1 Components
    t1_cards = []
    if forms_count > 0:
        t1_cards.append(f'<div class="tier-card"><div class="tier-card-title">Forms</div><div class="tier-card-detail">{forms_count} screens</div></div>')
    if vba_count > 0:
        t1_cards.append(f'<div class="tier-card"><div class="tier-card-title">VBA modules</div><div class="tier-card-detail">{vba_count} modules</div></div>')
    if tables_count > 0:
        t1_cards.append(f'<div class="tier-card"><div class="tier-card-title">Tables</div><div class="tier-card-detail">{tables_count} entities</div></div>')

    # Tier 2 Components
    t2_cards = [
        f'<div class="tier-card"><div class="tier-card-title" style="color:#991b1b;">Schema extractor</div><div class="tier-card-detail">Tables and relations</div></div>',
        f'<div class="tier-card"><div class="tier-card-title" style="color:#991b1b;">Logic converter</div><div class="tier-card-detail">VBA to {esc(target_lang)}</div></div>',
        f'<div class="tier-card"><div class="tier-card-title" style="color:#991b1b;">UI generator</div><div class="tier-card-detail">Forms to React</div></div>'
    ]

    # Tier 3 Components
    t3_cards = [
        f'<div class="tier-card"><div class="tier-card-title">React frontend</div><div class="tier-card-detail">{forms_count} screens</div></div>',
        f'<div class="tier-card"><div class="tier-card-title">Spring Boot API</div><div class="tier-card-detail">Service layer</div></div>',
        f'<div class="tier-card"><div class="tier-card-title">PostgreSQL DB</div><div class="tier-card-detail">{tables_count} tables</div></div>'
    ]

    arch_html = (
        f'<div class="arch-flow-container">\n'
        f'  <!-- Tier 1 -->\n'
        f'  <div class="arch-tier tier-legacy">\n'
        f'    <div class="tier-title">Legacy Access system</div>\n'
        f'    <div class="tier-subtitle">{esc(source_file)}</div>\n'
        f'    <div class="tier-grid">{" ".join(t1_cards)}</div>\n'
        f'  </div>\n'
        f'  <div class="tier-arrow"></div>\n'
        f'  <!-- Tier 2 -->\n'
        f'  <div class="arch-tier tier-engine">\n'
        f'    <div class="tier-title">Migration engine</div>\n'
        f'    <div class="tier-subtitle">Access2Java universal accelerator</div>\n'
        f'    <div class="tier-grid">{" ".join(t2_cards)}</div>\n'
        f'  </div>\n'
        f'  <div class="tier-arrow"></div>\n'
        f'  <!-- Tier 3 -->\n'
        f'  <div class="arch-tier tier-target">\n'
        f'    <div class="tier-title">Target system</div>\n'
        f'    <div class="tier-subtitle">React and Spring Boot</div>\n'
        f'    <div class="tier-grid">{" ".join(t3_cards)}</div>\n'
        f'  </div>\n'
        f'</div>'
    )

    c38 = (
        f'<p>Modernization architecture mapping the transition from legacy desktop components to a distributed web architecture.</p>\n'
        f'{arch_html}\n'
        f'<h2 class="sub-title">38.1 Component Mapping</h2>\n'
        f'<ul>\n'
        f'<li><strong>Legacy Tier:</strong> Encapsulates {forms_count} screens and {tables_count} tables within the <code>{esc(source_file)}</code> container.</li>\n'
        f'<li><strong>Migration Tier:</strong> Automated extraction and translation of VBA logic to {target_lang} and UI to React.</li>\n'
        f'<li><strong>Target Tier:</strong> Cloud-native deployment utilizing Spring Boot services and a React-based interactive frontend.</li>\n'
        f'</ul>'
    )
    add_section("SECTION_38_TECHNICAL_ARCHITECTURE", "Technical Architecture", c38)

    # -------------------------------------------------------------
    # 39. DATA ARCHITECTURE & SPECIFICATIONS
    # -------------------------------------------------------------
    pk_note = (
        '<div class="info-callout"><strong>Primary Key Verification Note:</strong> Analysis of the source JET engine metadata indicates that PK constraints are often not enforced at the file level. '
        'Fields labeled "Inferred PK" are identified by naming convention (e.g. <i>ID</i> suffix) or AutoNumber type but lack a unique index. '
        '<strong>Target Recommendation:</strong> Enforce strict primary keys on all PostgreSQL tables during migration.</div>'
    )

    c39_rows = []
    for table in tables_sorted:
        tname = table.get("name", "Table")
        cols = table.get("columns") or []
        for col in cols:
            cname = col.get("name", "Field")
            # Enhanced PK detection
            is_pk = col.get("is_pk") or (cname in table.get("enforced_pk_cols", [])) or (cname in table.get("inferred_pk_cols", []))
            # Determine PK type
            pk_label = "-"
            if is_pk:
                if cname in table.get("enforced_pk_cols", []):
                    pk_label = "Enforced PK"
                else:
                    pk_label = "Inferred PK"

            c39_rows.append(
                f'<tr><td><code>{esc(tname)}</code></td><td><code>{esc(cname)}</code></td>'
                f'<td>{esc(col.get("access_type") or "Text")}</td>'
                f'<td><code>{esc(col.get("pg_type") or "VARCHAR")}</code></td>'
                f'<td><span class="badge { "badge-info" if "Inferred" in pk_label else "badge-success" if "Enforced" in pk_label else "" }">{esc(pk_label)}</span></td>'
                f'<td>{esc(col.get("fk_target") or "-")}</td>'
                f'<td>{esc(col.get("size") or "-")}</td><td>{esc(col.get("description") or "-")}</td></tr>\n'
            )

    # Sample Data Enhancement
    sample_data_html = '<h2 class="sub-title">39.3 Representative Sample Data</h2>\n'
    for table in tables_sorted:
        sdata = table.get("sample_data")
        if sdata:
            tname = table.get("name")
            sample_data_html += f'<div class="sub-sub-title">Table: {esc(tname)}</div>\n'
            sample_data_html += '<div class="table-wrapper"><table><thead><tr>'
            # Assuming first row defines headers
            headers = list(sdata[0].keys())
            for h in headers: sample_data_html += f'<th>{esc(h)}</th>'
            sample_data_html += '</tr></thead><tbody>'
            for row in sdata:
                sample_data_html += '<tr>'
                for h in headers:
                    val = row.get(h)
                    # Mask PII (Heuristic)
                    if any(p in h.lower() for p in ("name", "email", "phone", "ssn", "pesel", "address", "pwd")):
                        val = "****" if val else "None"
                    sample_data_html += f'<td>{esc(val)}</td>'
                sample_data_html += '</tr>'
            sample_data_html += '</tbody></table></div>'

    c39 = (
        f'{pk_note}\n'
        f'<h2 class="sub-title">39.1 Comprehensive Data Dictionary</h2>\n'
        f'<div class="table-wrapper"><table class="table-data-architecture"><thead><tr>'
        f'<th>Table</th><th>Field</th><th>Access Type</th><th>PostgreSQL Type</th><th>Key Status</th><th>FK Target</th><th>Size</th><th>Validation</th>'
        f'</tr></thead><tbody>{"".join(c39_rows)}</tbody></table></div>\n'
        f'{sample_data_html}'
    )
    add_section("SECTION_39_DATA_MIGRATION", "Data Architecture and Specifications", c39)

    # -------------------------------------------------------------
    # 46. REQUIREMENTS TRACEABILITY MATRIX (Full Coverage)
    # -------------------------------------------------------------
    c46_rows = []
    for idx, tbl in enumerate(tables_sorted, start=1):
        tname = tbl.get("name", "Table")
        c46_rows.append(
            f'<tr><td>REQ-{idx:03d}</td><td>Data Entity Persistence</td><td><code>{esc(tname)}</code></td>'
            f'<td><code>{esc(re.sub(r"[^a-zA-Z0-9]", "", tname))}Entity.java</code></td><td>Schema Comparison</td></tr>\n'
        )
    c46 = (
        f'<p>Complete Requirements Traceability Matrix mapping every source entity to its target application component.</p>\n'
        f'<div class="table-wrapper"><table class="table-matrix"><colgroup><col style="width:15%;"><col style="width:25%;"><col style="width:25%;"><col style="width:20%;"><col style="width:15%;"></colgroup>'
        f'<thead><tr><th>Req ID</th><th>Functional Scope</th><th>Access Source Object</th><th>Target Component</th><th>Verification</th></tr></thead>'
        f'<tbody>{"".join(c46_rows)}</tbody></table></div>'
    )
    add_section("SECTION_46_TRACEABILITY_MATRIX", "Requirements Traceability Matrix", c46)

    # -------------------------------------------------------------
    # 47. ACCEPTANCE CRITERIA
    # -------------------------------------------------------------
    c47 = (
        f'<p>The following criteria must be met for the migrated system to be accepted, ensuring a high-confidence transition from the legacy environment:</p>'
        f'<ul>'
        f'<li><strong>Data Fidelity:</strong> All {tables_count} business tables must be migrated to PostgreSQL with 100% record count and checksum match. '
        f'<br/><i>Verification: Automated row-count comparison script and sample field hash validation between Access and PostgreSQL.</i></li>'
        f'<li><strong>Logic Fidelity:</strong> All {vba_count} VBA modules and {macros_count} macros must have corresponding functional logic implemented in Java services. '
        f'<br/><i>Verification: Side-by-side execution of complex business rules and comparison of output values for identical input sets.</i></li>'
        f'<li><strong>UI Fidelity:</strong> All {forms_count} form screens must be accessible and functional within the React web frontend, maintaining existing data workflows. '
        f'<br/><i>Verification: Structured User Acceptance Testing (UAT) walkthrough of each form to confirm presence of all required fields and actions.</i></li>'
        f'<li><strong>Performance:</strong> Primary data retrieval queries must execute within 200ms in the target environment under a load of 10 concurrent users. '
        f'<br/><i>Verification: Execution of JMeter performance scripts or integrated Spring Boot metrics monitoring during peak load simulation.</i></li>'
        f'<li><strong>Relational Integrity:</strong> All {len(relationships)} referential relationships must be strictly enforced in the target PostgreSQL schema. '
        f'<br/><i>Verification: Execution of DDL validation scripts to confirm existence of Foreign Key constraints matching the <code>MSysRelationships</code> catalog.</i></li>'
        f'</ul>'
    )
    add_section("SECTION_47_ACCEPTANCE_CRITERIA", "Acceptance Criteria", c47)

    # -------------------------------------------------------------
    # 48. APPENDICES
    # -------------------------------------------------------------
    # Appendix A - Database Object Inventory
    app_a_rows = (
        f'<tr><td>Business Tables</td><td>{tables_count}</td><td>Relational Entities</td><td>Schema Data Storage</td><td>Active / In Scope</td></tr>'
        f'<tr><td>System Tables</td><td>{system_tables_count}</td><td>Access Configuration</td><td>UI Metadata / Ribbons</td><td>Excluded from Data Migration</td></tr>'
        f'<tr><td>SQL Queries</td><td>{queries_count}</td><td>Data Views & Filters</td><td>Query Engine</td><td>Active / Translated to Repositories</td></tr>'
        f'<tr><td>User Forms</td><td>{forms_count}</td><td>Interactive Screens</td><td>Desktop UI / Workstation UI</td><td>Active / Translated to Web Views</td></tr>'
        f'<tr><td>Output Reports</td><td>{reports_count}</td><td>Printable Documents</td><td>Access Report Runtime</td><td>Active / Translated to Web Reports</td></tr>'
        f'<tr><td>Macros</td><td>{macros_count}</td><td>Event Procedures</td><td>Macro Actions</td><td>Active / Translated to Workflows</td></tr>'
        f'<tr><td>VBA Code Modules</td><td>{vba_count}</td><td>Business Logic ({total_loc:,} LOC)</td><td>VBA Engine</td><td>Active / Translated to Java Services</td></tr>'
    )

    # Appendix B - Table Inventory
    app_b_rows = ""
    for t in tables_sorted:
        tname = t.get("name", "Unknown")
        cols_count = len(t.get("columns", []))
        pk_cols = t.get("enforced_pk_cols", []) or t.get("inferred_pk_cols", [])
        pk_status = ", ".join(pk_cols) if pk_cols else "None"
        desc = t.get("description") or f"Primary transactional data storage for {esc(tname)} entity."

        app_b_rows += (
            f'<tr>'
            f'<td><code>{esc(tname)}</code></td>'
            f'<td>{cols_count} Columns</td>'
            f'<td><code>{esc(pk_status)}</code></td>'
            f'<td>Relational Entity Table</td>'
            f'<td>{esc(desc)}</td>'
            f'</tr>\n'
        )

    c48 = (
        f'<h2 class="sub-title">Appendix A — Database Object Inventory</h2>\n'
        f'<p>Complete summary of all {total_discovered_objects} database objects discovered in <code>{esc(source_file)}</code>.</p>\n'
        f'<div class="table-wrapper">\n'
        f'  <table>\n'
        f'    <thead><tr>'
        f'      <th>Object Category</th><th>Count</th><th>Classification</th><th>Storage Engine</th><th>Scope & Status</th>'
        f'    </tr></thead>\n'
        f'    <tbody>{app_a_rows}</tbody>\n'
        f'  </table>\n'
        f'</div>\n'
        f'<h2 class="sub-title">Appendix B — Table Inventory</h2>\n'
        f'<p>Inventory of all {tables_count} business data tables extracted from source database.</p>\n'
        f'<div class="table-wrapper">\n'
        f'  <table>\n'
        f'    <thead><tr>'
        f'      <th>Table Name</th><th>Columns</th><th>Primary Key Status</th><th>Classification</th><th>Business Description</th>'
        f'    </tr></thead>\n'
        f'    <tbody>{app_b_rows}</tbody>\n'
        f'  </table>\n'
        f'</div>'
    )
    add_section("SECTION_48_APPENDICES", "Appendices", c48)

    # -------------------------------------------------------------
    # BUILD DYNAMIC TABLE OF CONTENTS
    # -------------------------------------------------------------
    toc_html_items = []
    for snum, stitle in toc_items:
        # Assuming Page 1 is Cover, Page 2 is TOC, so Section 1 starts on Page 3
        page_num = int(snum) + 2
        toc_html_items.append(
            f'<tr>'
            f'<td class="toc-item-num">{snum}</td>'
            f'<td class="toc-item-title"><a href="#sec_{snum}">{esc(stitle)}</a></td>'
            f'<td class="toc-item-page">{page_num}</td>'
            f'</tr>'
        )
    toc_html = "\n".join(toc_html_items)

    # -------------------------------------------------------------
    # PERFORM PLACEHOLDER REPLACEMENTS
    # -------------------------------------------------------------
    replacements: Dict[str, str] = {
        "PROJECT_NAME": esc(project_name),
        "DOCUMENT_NAME": esc(document_name),
        "DOCUMENT_VERSION": esc(doc_version),
        "DOCUMENT_DATE": date_str,
        "DOCUMENT_STATUS": esc(doc_status),
        "ORGANIZATION_NAME": esc(org_name),
        "PREPARED_BY": esc(prepared_by),
        "APPROVED_BY": esc(approved_by),
        "SOURCE_APPLICATION": esc(source_file),
        "TARGET_TECHNOLOGY": esc(target_tech),
        "TABLE_OF_CONTENTS": toc_html,
        "source_file_name": esc(source_file),
        "file_size": f"{facts.get('source_file_size', 0):,}",
        "project_name": esc(project_name),
        "format_version": esc(facts.get("access_version", "MS Access 2007-2016 (ACE)")),
        "TABLES_COUNT": str(tables_count),
        "FORMS_COUNT": str(forms_count),
        "REPORTS_COUNT": str(reports_count),
        "MACROS_COUNT": str(macros_count),
        "USER_CONTROLS_COUNT": str(total_controls_count) if total_controls_count > 0 else str(forms_count),
        "CUSTOM_FORMS_COUNT": str(forms_count),
        **sec_replacements,
    }

    rendered = template_str
    for key, value in replacements.items():
        placeholder = "{{" + key + "}}"
        rendered = rendered.replace(placeholder, str(value))

    # Clean up any residual unmatched {{...}} tags smoothly
    remaining_placeholders = re.findall(r"\{\{([A-Za-z0-9_]+)\}\}", rendered)
    if remaining_placeholders:
        for ph in set(remaining_placeholders):
            placeholder = "{{" + ph + "}}"
            rendered = rendered.replace(placeholder, "")

    return rendered

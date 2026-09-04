import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, r"c:\Users\Admin.ST-SHANKAR\Downloads\MS-Access-Java-React-Accelerator-base-working (2)\MS-Access-Java-React-Accelerator-base-working")

from BRD.services.static_analyzer import compute_static_metrics
from BRD.services.template_renderer import render_brd_template

def test_dynamic_brd_rendering():
    print("--- Testing Dynamic BRD Generation ---")
    
    # Test Job 1: Northwind Sales Database
    facts_job1 = {
        "job_id": "job_northwind_101",
        "project_name": "NorthwindSalesApp",
        "source_file": "Northwind.accdb",
        "source_file_size": 2048000,
        "tables_count": 3,
        "queries_count": 2,
        "forms_count": 2,
        "reports_count": 1,
        "macros_count": 0,
        "vba_modules_count": 1,
        "tables": [
            {
                "name": "Customers",
                "columns": [
                    {"name": "CustomerID", "type": "VARCHAR(5)", "pk": True},
                    {"name": "CompanyName", "type": "VARCHAR(40)"},
                    {"name": "ContactName", "type": "VARCHAR(30)"}
                ]
            },
            {
                "name": "Orders",
                "columns": [
                    {"name": "OrderID", "type": "INTEGER", "pk": True},
                    {"name": "CustomerID", "type": "VARCHAR(5)", "fk": True},
                    {"name": "OrderDate", "type": "TIMESTAMP"}
                ]
            },
            {
                "name": "Products",
                "columns": [
                    {"name": "ProductID", "type": "INTEGER", "pk": True},
                    {"name": "ProductName", "type": "VARCHAR(40)"},
                    {"name": "UnitPrice", "type": "NUMERIC(10,2)"}
                ]
            }
        ],
        "queries": [{"name": "InvoicesQuery"}, {"name": "SalesByQuarter"}],
        "forms": [{"name": "CustomerEntryForm"}, {"name": "OrderDetailsForm"}],
        "reports": [{"name": "MonthlySalesReport"}],
        "macros": [],
        "vba_modules": [{"name": "SalesCalcModule", "code": "Sub CalcSales()\nEnd Sub\n"}],
        "sql_loc": 25,
        "vba_loc": 40,
        "total_loc": 350,
        "orphans": []
    }

    metrics_job1 = compute_static_metrics(facts_job1)
    html_job1 = render_brd_template(facts_job1, metrics_job1, narratives={})

    assert "NorthwindSalesApp" in html_job1, "Project name missing in Job 1 HTML!"
    assert "Customers" in html_job1, "Table 'Customers' missing in Job 1 HTML!"
    assert "Orders" in html_job1, "Table 'Orders' missing in Job 1 HTML!"
    assert "Products" in html_job1, "Table 'Products' missing in Job 1 HTML!"
    assert "/api/v1/customers" in html_job1, "API endpoint '/api/v1/customers' missing in Job 1 HTML!"
    assert "InvoicesQuery" in html_job1, "Query 'InvoicesQuery' missing in Job 1 HTML!"
    assert "CustomerEntryForm" in html_job1, "Form 'CustomerEntryForm' missing in Job 1 HTML!"
    print("[OK] Job 1 (NorthwindSalesApp) dynamically rendered successfully!")

    # Test Job 2: Healthcare Patient Database
    facts_job2 = {
        "job_id": "job_healthcare_202",
        "project_name": "PatientCareSystem",
        "source_file": "HospitalDb.accdb",
        "source_file_size": 5120000,
        "tables_count": 2,
        "queries_count": 1,
        "forms_count": 1,
        "reports_count": 0,
        "macros_count": 0,
        "vba_modules_count": 0,
        "tables": [
            {
                "name": "Patients",
                "columns": [
                    {"name": "PatientID", "type": "BIGINT", "pk": True},
                    {"name": "FullName", "type": "VARCHAR(100)"},
                    {"name": "DOB", "type": "DATE"}
                ]
            },
            {
                "name": "Appointments",
                "columns": [
                    {"name": "AppointmentID", "type": "BIGINT", "pk": True},
                    {"name": "PatientID", "type": "BIGINT", "fk": True},
                    {"name": "DoctorName", "type": "VARCHAR(100)"}
                ]
            }
        ],
        "queries": [{"name": "ActiveAppointmentsQuery"}],
        "forms": [{"name": "PatientCheckInForm"}],
        "reports": [],
        "macros": [],
        "vba_modules": [],
        "sql_loc": 15,
        "vba_loc": 0,
        "total_loc": 180,
        "orphans": []
    }

    metrics_job2 = compute_static_metrics(facts_job2)
    html_job2 = render_brd_template(facts_job2, metrics_job2, narratives={})

    assert "PatientCareSystem" in html_job2, "Project name missing in Job 2 HTML!"
    assert "Patients" in html_job2, "Table 'Patients' missing in Job 2 HTML!"
    assert "Appointments" in html_job2, "Table 'Appointments' missing in Job 2 HTML!"
    assert "/api/v1/patients" in html_job2, "API endpoint '/api/v1/patients' missing in Job 2 HTML!"
    assert "NorthwindSalesApp" not in html_job2, "Job 1 data leaked into Job 2 HTML!"
    assert "Customers" not in html_job2, "Job 1 table leaked into Job 2 HTML!"
    print("[OK] Job 2 (PatientCareSystem) dynamically rendered successfully!")
    print("[OK] Verification PASSED: BRD generation is 100% dynamic without false assumptions or cross-job cache leaks!")

if __name__ == "__main__":
    test_dynamic_brd_rendering()

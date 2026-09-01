# MS Access → Spring Boot + React + Database Converter

## 1. Product Objective

Build a production-oriented migration/conversion application that accepts real-world Microsoft Access applications and converts supported portions into a modern:

* Spring Boot backend
* React frontend
* PostgreSQL database

The target is NOT 100% automatic conversion of every possible Microsoft Access application.

The target is:

> Support approximately 60–70% of real-world MS Access application patterns, with very high conversion correctness inside the supported scope.

For a project that falls within the supported scope, the converter should generate a complete, buildable, runnable, testable Spring Boot + React + PostgreSQL project without requiring the developer to manually correct generated source code.

Unsupported or ambiguous functionality must be identified explicitly before generation or during validation. Do not silently generate incorrect code.

The converter should behave more like a compiler and migration platform than like a simple LLM code generator.

---

# 2. Core Product Principle

Do NOT build:

.accdb → LLM → Spring Boot + React

Build:

.accdb/.mdb → deterministic extraction → Access Intermediate Representation → dependency analysis → semantic analysis → controlled code generation → dependency resolution → build → automated tests → repair → final validated project

The LLM must be a reasoning and semantic interpretation component inside the pipeline, not the entire conversion engine.

Use deterministic logic whenever the source information is factual and machine-readable.

Use the LLM only where semantic interpretation is required.

---

# 3. Real-World Access Application Model

An Access application is not necessarily only one isolated `.accdb`.

Microsoft documents Access database objects such as tables, queries, forms, and reports, and also notes that one Access database can contain links to tables stored in another database.

Therefore, the converter must support:

## 3.1 Single-file application

Example:

EmployeeManagement.accdb

Contains:

* Tables
* Relationships
* Queries
* Forms
* Reports
* Macros
* VBA modules
* Startup configuration

## 3.2 Split Access application

Example:

EmployeeManagement_FE.accdb
EmployeeManagement_BE.accdb

Frontend:

* Forms
* Reports
* Queries
* VBA
* Macros
* linked table definitions

Backend:

* Tables
* Relationships
* data

The frontend may be the file the user launches, while the backend contains the data.

## 3.3 Access + external database

Example:

EmployeeManagement.accdb
↓
SQL Server linked tables

or:

EmployeeManagement.accdb
↓
MySQL/PostgreSQL/ODBC

## 3.4 Access + external files

Examples:

* Excel
* CSV
* text files
* PDFs/documents
* images
* external configuration files

## 3.5 Access + external automation/integration

Examples:

* Outlook
* Office automation
* COM libraries
* ActiveX
* DLLs
* Windows APIs
* external executables
* ODBC
* third-party components

The converter must discover these dependencies rather than assuming that everything is physically contained inside `.accdb`.

---

# 4. Primary Input Formats

The converter's primary input should be:

* `.accdb`
* `.mdb`

Also support an optional project/package mode containing:

* frontend `.accdb`
* backend `.accdb`
* source-control-exported Access source
* external files

Input modes:

1. Single Access file
2. Access frontend + backend
3. Access project package
4. Access source export package

The system must normalize all input modes into the same internal model.

---

# 5. Access Extraction Strategy

Do not try to read the entire Access application using only ODBC.


ODBC/ACE connectivity is useful for database schema and data access, but UI and code objects require Access-specific APIs/automation.

The preferred Windows extraction path is:

MS Access application / ACE / DAO
↓
Object extraction
↓
normalized JSON + source artifacts

The extractor should be able to use Microsoft Access automation where available.

Recommended extraction capabilities include:

* Access Application COM automation
* DAO
* ACE/Jet provider where required
* Access `SaveAsText` for object source export
* DAO TableDefs
* DAO QueryDefs
* DAO Relations
* linked TableDef metadata
* Access project properties
* Access startup configuration

Do not depend only on the ODBC driver because forms, reports, VBA modules, macros, and other Access application objects cannot be fully represented through ordinary table access.

---

# 6. Extraction Pipeline

Input:

project.accdb

Step 1:
Verify extension.

Step 2:
Verify file accessibility.

Step 3:
Determine Access/ACE compatibility.

Step 4:
Detect whether the file is:

* standalone
* frontend
* backend
* linked frontend
* encrypted/password protected
* corrupt/unreadable
* legacy `.mdb`

Step 5:
Extract metadata.

Step 6:
Extract all Access objects.

Step 7:
Extract source/code representations.

Step 8:
Discover external dependencies.

Step 9:
Construct dependency graph.

Step 10:
Construct Access Intermediate Representation.

Step 11:
Run supportability analysis.

Step 12:
Only then start conversion.

---

# 7. Access Objects That Must Be Extracted

## Database

Extract:

* database name
* Access version
* file format
* encryption status
* startup settings
* application title
* custom properties
* references
* linked data sources

## Tables

Extract:

* table name
* columns
* data types
* field size
* precision
* scale
* required
* default value
* validation rule
* validation text
* primary key
* unique indexes
* indexes
* relationships
* lookup properties
* calculated fields
* attachment fields
* multi-value fields
* hyperlink fields
* OLE fields
* replication IDs where applicable

## Relationships

Extract:

* parent table
* child table
* parent key
* child key
* one-to-one
* one-to-many
* cascade update
* cascade delete
* relationship attributes

## Queries

Extract:

* query name
* SQL
* query type
* parameters
* referenced tables
* referenced queries
* joins
* filters
* group by
* order by
* aggregate functions
* crosstab definitions
* action queries
* make-table queries
* pass-through queries
* DDL queries
* union queries

Classify each query.

## Forms

Extract:

* form name
* record source
* form properties
* controls
* control type
* control name
* bound field
* row source
* events
* event handlers
* VBA module
* subforms
* parent-child links
* validation rules
* conditional formatting
* navigation behavior

## Reports

Extract:

* report name
* record source
* sections
* report header
* page header
* detail
* page footer
* report footer
* groups
* sorting
* calculated controls
* subreports
* event VBA
* formatting
* page setup
* parameters

## Macros

Extract:

* macro name
* macro actions
* action arguments
* conditions
* nested macro structures
* RunCode
* RunMacro
* OpenForm
* OpenReport
* RunQuery
* SetValue
* SendObject
* TransferSpreadsheet
* TransferText
* TransferDatabase
* OutputTo
* DoMenuItem
* other actions

## VBA

Extract:

* standard modules
* form modules
* report modules
* class modules
* functions
* subs
* event procedures
* declarations
* constants
* references
* API declarations
* DAO
* ADODB
* CurrentDb
* DoCmd
* Forms!
* Reports!
* Me
* Recordset usage
* error handling
* external automation

## Startup/Application configuration

Extract:

* startup form
* startup macro
* AutoExec
* hidden navigation pane settings
* custom menus
* custom ribbon where accessible
* application title
* startup options
* trusted location assumptions
* security settings

---

# 8. External Dependency Discovery

For every linked table, inspect:

* TableDef.Name
* TableDef.Connect
* TableDef.SourceTableName

Detect:

* Access backend
* SQL Server
* MySQL
* PostgreSQL
* ODBC
* Excel
* CSV
* text
* other databases
* external files

Build:

ExternalDependency

with:

* dependency type
* connection information
* location
* database/server
* source table
* credentials presence without exposing secrets
* migration strategy
* support status
* risk level

Never expose credentials in generated reports or logs.

---

# 9. Source Control and Reference Corpus

The product must use a large reference corpus of public Access applications and Access development repositories to identify patterns and edge cases.

Do not claim "all GitHub Access repositories." Instead build a broad representative corpus.

Reference project patterns should include:

* basic CRUD
* employee management
* HR
* leave management
* attendance
* inventory
* purchasing
* sales
* orders
* CRM
* accounting
* reporting
* dashboards
* login systems
* barcode workflows
* low-stock alerts
* Excel integration
* SQL Server integration
* split frontends/backends
* VBA-heavy projects
* macro-heavy projects
* reports
* subforms
* subreports
* parameter queries
* crosstab queries
* action queries
* pass-through queries
* AutoExec
* email automation
* linked tables
* lookup fields
* calculated fields
* external file integration
* large object-count Access applications

Public Access version-control projects demonstrate that Access applications can contain large numbers of forms, reports, queries, modules and table definitions, and they also show that exporting Access objects into source-controlled representations is practical. Use such repositories as reference material and test-corpus sources.

---

# 10. Access Intermediate Representation

Build a canonical intermediate model.

Do not generate Java/React directly from Access objects.

Recommended model:

ApplicationIR

```
application
database
tables
relationships
indexes
queries
forms
controls
reports
macros
vbaModules
businessRules
externalDependencies
startupConfiguration
references
supportability
warnings
conversionPlan
```

Example:

{
"application": {
"name": "EmployeeLeave"
},
"database": {
"engine": "ACCESS"
},
"tables": [],
"relationships": [],
"queries": [],
"forms": [],
"reports": [],
"macros": [],
"vbaModules": [],
"externalDependencies": []
}

All downstream processing must use this representation instead of directly depending on Access APIs.

---

# 11. Dependency Graph

Every Access object must become a graph node.

Examples:

frmLeaveApplication
↓
btnSubmit_Click
↓
CalculateLeaveDays
↓
DetermineLeaveStatus
↓
qryInsertLeave
↓
Leaves

Another:

frmEmployee
↓
cmbDepartment
↓
qryDepartmentLookup
↓
Departments

Another:

rptLeaveSummary
↓
qryEmployeeLeaveReport
↓
Employees
Leaves
Departments

The dependency graph must support:

* upstream dependency
* downstream dependency
* direct dependency
* indirect dependency
* circular references
* orphan objects
* unused objects

This graph is critical for LLM context selection and correct generation ordering.

---

# 12. Supportability Engine

Before generation, classify every object into:

SUPPORTED
SUPPORTED_WITH_TRANSFORMATION
SUPPORTED_WITH_REVIEW
UNSUPPORTED
FAILED_EXTRACTION

Each object receives:

* support status
* complexity
* risk
* conversion strategy
* dependency count
* confidence
* reason

Example:

{
"object": "modLeave.DetermineStatus",
"category": "VBA_FUNCTION",
"status": "SUPPORTED",
"complexity": "LOW",
"conversion": "SPRING_SERVICE_RULE"
}

Example:

{
"object": "modOutlook.SendInvoice",
"category": "VBA",
"status": "SUPPORTED_WITH_REVIEW",
"risk": "HIGH",
"reason": "External Outlook automation"
}

---

# 13. Coverage Scoring

Do NOT measure conversion quality simply by line count.

Measure:

* project archetype coverage
* object coverage
* behavior coverage
* generated-code build success
* test success

Provide:

Overall supportability score

Example:

Database coverage: 96%
Query coverage: 89%
Form coverage: 84%
VBA coverage: 67%
Report coverage: 78%
External dependency coverage: 52%

Overall estimated conversion coverage: 78%

Also produce:

Fully supported:
72%

Supported with review:
17%

Unsupported:
11%

This allows the user to know the expected result BEFORE generation.

---

# 14. Target 60–70% Strategy

The main strategy is not to support every Access feature poorly.

Instead:

1. Define a supported scope.
2. Make that scope extremely reliable.
3. Expand scope based on real reference projects.
4. Never silently convert unsupported behavior.
5. Never declare success just because source files were generated.

The target should be:

"approximately 60–70% of real-world Access application patterns can be completely converted into a buildable and behaviorally validated application."

For supported patterns, source-code correction should not normally be necessary.

---

# 15. Access Data Type Conversion

Use a deterministic mapping matrix.

Examples:

Access Short Text
→ VARCHAR

Access Long Text
→ TEXT

Access Integer
→ INTEGER

Access Long Integer
→ BIGINT

Access Double
→ DOUBLE PRECISION

Access Currency
→ NUMERIC

Access Date/Time
→ TIMESTAMP

Access Yes/No
→ BOOLEAN

Access AutoNumber
→ identity/bigint

Access Hyperlink
→ TEXT

Access Attachment
→ external file storage or BYTEA based on configuration

Access OLE Object
→ external storage or BYTEA with review

Special fields such as:

* Lookup
* Multi-value
* Attachment
* Calculated
* Replication ID

must have explicit handlers.

Do not ask the LLM to decide primitive database type conversions.

---

# 16. Query Conversion Engine

Every query must first be classified.

Types:

* SELECT
* INSERT
* UPDATE
* DELETE
* PARAMETER
* CROSSTAB
* UNION
* PASS-THROUGH
* MAKE-TABLE
* DDL
* ACTION

Detect Access-specific functions:

* Nz
* IIf
* DateDiff
* DatePart
* Format
* DLookup
* DCount
* DSum
* DMax
* DMin
* Switch
* Choose
* domain aggregate functions

Do not perform naive string replacement.

Build a query AST or structured query representation.

Example:

Access:

Nz(Salary, 0)

should become an appropriate PostgreSQL/JPA expression rather than remain as Access syntax.

Simple queries should be converted deterministically.

Complex or ambiguous queries may invoke the LLM.

---

# 17. VBA Conversion Engine

Never do:

VBA source → LLM → Java

Use:

VBA
→ tokenizer
→ AST
→ control-flow analysis
→ symbol analysis
→ dependency analysis
→ business-rule extraction
→ known-pattern transformation
→ LLM semantic analysis only when necessary
→ target Java representation
→ Java generation

The engine must recognize:

* If
* Else
* Select Case
* For
* For Each
* Do While
* Do Until
* functions
* subs
* ByVal
* ByRef
* error handlers
* Recordset
* DAO
* ADODB
* CurrentDb
* DoCmd
* Forms!
* Reports!
* Me
* MsgBox
* InputBox
* DLookup
* DCount
* SQL execution
* external automation

Known CRUD patterns should be handled deterministically.

Complex business rules should use the LLM.

---

# 18. Business Rule Extraction

A major goal is to transform implicit VBA behavior into explicit business-rule objects.

Example VBA:

If leaveDays > 3 Then
status = "Manager Approval"
Else
status = "Pending"
End If

Intermediate representation:

{
"type": "BUSINESS_RULE",
"name": "LongLeaveRequiresManagerApproval",
"inputs": ["leaveDays"],
"condition": "leaveDays > 3",
"trueResult": "MANAGER_APPROVAL",
"falseResult": "PENDING"
}

The Java generator then creates the implementation.

Do not rely on the LLM to write arbitrary architecture every time.

---

# 19. Forms → React

Access forms should be converted into:

* pages
* components
* forms
* tables
* dialogs
* navigation
* lookup controls
* validation
* API calls

Form mapping:

TextBox
→ Input

ComboBox
→ Select/Autocomplete

CheckBox
→ Checkbox/Switch

OptionGroup
→ Radio/segmented control

CommandButton
→ Button/action

Subform
→ child component/table

Tab control
→ Tabs

Image
→ image component

Date picker
→ date input/date picker

Access form event
→ React UI event and/or Spring service

Important:

Do not put business rules only in React.

Business rules must live in the Spring Boot service layer.

React performs presentation and client validation.

---

# 20. Reports → Modern Reporting

V1 report scope:

* basic tabular reports
* grouping
* sorting
* totals
* filters
* parameters
* PDF output
* CSV output

Do not promise perfect pixel-level Access report reproduction.

Represent the report semantically:

* data source
* fields
* grouping
* aggregation
* sorting
* display rules

Then generate a modern report implementation.

Complex subreports or unusual VBA report behavior should receive review/unsupported classification.

---

# 21. Macros

Convert common macros:

OpenForm
→ React Router navigation

OpenReport
→ report page/report API

RunQuery
→ API call/repository operation

RunCode
→ backend service

SetValue
→ React state or backend operation depending on semantics

SendObject
→ email service

TransferSpreadsheet
→ import/export service

AutoExec
→ application startup workflow

Unknown macro actions must be classified instead of silently ignored.

---

# 22. Authentication and Security

If the Access application contains users/security:

Access users/roles
→ Spring Security

Do not store plaintext passwords in the generated application.

If source Access data contains plaintext demo passwords, classify them as source security debt.

Generated authentication should use:

* hashed passwords
* session or JWT based on configuration
* role/authority mapping
* protected API endpoints
* protected frontend routes

Do not reproduce insecure Access authentication patterns literally.

---

# 23. Target Application Architecture

Generate:

generated-project/

```
backend/
    pom.xml
    src/main/java/...
    src/main/resources/...
    src/test/...

frontend/
    package.json
    package-lock.json
    vite.config.js
    src/...

database/
    schema.sql
    data.sql
    migrations/

tests/
    migration/
    behavioral/

migration-report/
    inventory.json
    coverage.json
    warnings.json
    dependency-report.json
    build-report.json

README.md
```

---

# 24. Default Target Technology Profile

As of August 18, 2026, the current verified baseline should be:

Backend:
Spring Boot 4.1.0

Java:
Java 25 LTS preferred

Frontend:
React 19.2.x

Bundler:
Vite 8.1.x

Node:
Node 24 LTS

Database:
PostgreSQL 18.x

Maven:
current compatible Maven 3.x, minimum based on Spring Boot support

Spring Boot 4.1.0 requires at least Java 17 and supports Java up to Java 26. Maven 3.6.3 or newer is supported.

Java 25 is an LTS release and should be the preferred generated Java target for newly generated applications, while the converter may provide other supported Java versions through a compatibility profile.

React 19.2 is the current documented React version.

Vite 8.1 is the current verified Vite release baseline.

Node.js 24 is LTS and should be preferred over Current releases for generated production projects.

PostgreSQL 18 is the current major PostgreSQL release and PostgreSQL 18.4 is a current 2026 patch release.

Important:

Do not hardcode "latest" dependency versions.

Create a version compatibility matrix.

---

# 25. Version Compatibility Matrix

Create:

technology-versions.json

It should contain:

Java versions
Spring Boot versions
Spring Framework versions
Maven versions
Node versions
React versions
Vite versions
PostgreSQL versions
JDBC versions
Flyway versions
Hibernate versions
Jackson versions
Spring Security versions
frontend library versions

Example:

{
"springBoot": {
"4.1.0": {
"javaMin": 17,
"javaRecommended": 25
}
},
"react": {
"19.2": {
"nodeRecommended": 24
}
}
}

The exact matrix must be validated by the converter itself before generation.

---

# 26. Generated Project Dependency Policy

Never use:

"latest"

Never allow unbounded:

^version

or

~version

for generated application dependencies where deterministic builds are required.

Pin exact versions for generated applications.

Maintain:

pom.xml
package.json
package-lock.json

All generated builds should be reproducible.

Use compatible dependency management and BOMs wherever possible.

Maven supports dependency management and BOM import, and Maven explicitly exposes dependency convergence problems when multiple versions of an artifact appear in the dependency graph.

---

# 27. Maven Dependency Rules

Generated Spring Boot project must:

1. Prefer Spring Boot starters.
2. Use Spring's managed dependency versions.
3. Avoid explicitly overriding managed dependency versions unless required.
4. Record every explicit override.
5. Detect duplicate transitive versions.
6. Run dependency tree analysis.
7. Run dependency convergence analysis.
8. Reject unsafe convergence failures.
9. Avoid SNAPSHOT dependencies unless explicitly configured.
10. Generate a dependency report.

Use:

mvn dependency:tree

and dependency convergence checking.

Maven documents dependency convergence as the condition where one artifact should resolve consistently rather than through conflicting versions.

If conflicts occur:

1. Determine which dependency introduces each version.
2. Prefer a compatible version managed by Spring Boot.
3. Use dependencyManagement/BOM.
4. Add exclusions only when justified.
5. Never blindly choose the newest version.
6. Rebuild.
7. Test.

---

# 28. React/NPM Dependency Rules

Generate:

package.json
package-lock.json

Use exact versions.

Use:

npm ci

for generated-project verification.

npm documents that npm ci performs a clean install and fails when package.json and package-lock.json are inconsistent.

Peer-dependency conflicts must be detected.

Do not automatically solve every peer-dependency problem with:

--legacy-peer-deps

unless the converter explicitly records that compatibility decision.

npm documents that strict peer dependency conflicts can cause installation failure.

Preferred remediation order:

1. Select compatible package version.
2. Replace incompatible library with supported equivalent.
3. Remove unnecessary dependency.
4. Override dependency only with verified compatibility.
5. Use legacy peer resolution only as an explicit last-resort compatibility mode.

---

# 29. Example Frontend Dependency Policy

Prefer a minimal stable dependency set.

Base:

* react
* react-dom
* react-router-dom
* axios or fetch
* Vite

Add libraries only when Access application requirements demand them.

Do not generate a giant package.json.

Every generated dependency should have an originating Access requirement.

Example:

Access date picker
→ generated date-picker dependency

Access chart/report
→ generated chart/report dependency

No requirement
→ do not add library

---

# 30. Java Version Mismatch Handling

The converter must detect:

source Java version
target Java version
library bytecode compatibility
Maven compiler version
Spring Boot supported range

Never generate:

Java 24 source
with
Java 21 target

unless explicitly supported and tested.

Validate with:

mvn -version
java -version

and the generated pom compiler configuration.

If the environment Java version is incompatible:

Do not silently modify code.

Show:

ENVIRONMENT_MISMATCH

and explain:

Required Java: 25
Detected Java: 21

Provide environment setup guidance.

---

# 31. Node Version Handling

Before building frontend:

node --version
npm --version

Compare with generated project's:

engines

and configured compatibility profile.

Use Node 24 LTS as the preferred baseline for the generated project.

Do not use Node 26 Current by default even though it is a current release. Production output should prefer LTS.

---

# 32. Database Version Handling

The generated project should use PostgreSQL 18.x as the default target.

However, generated SQL should avoid unnecessary version-specific features.

Prefer portable PostgreSQL SQL where possible.

Migration should generate:

schema.sql
data.sql

or Flyway/Liquibase migrations if configured.

DB validation must verify:

* tables
* columns
* PK
* FK
* indexes
* constraints
* seed data
* query execution

---

# 33. Build Validation Pipeline

After code generation:

## Backend

mvn clean test

mvn package

mvn dependency:tree

dependency convergence check

## Frontend

npm ci

npm run build

## Database

create database
run migrations
validate schema
run smoke queries

## Integration

start backend
start database
start frontend
run API tests
run UI tests

The conversion is NOT considered successful merely because files were generated.

---

# 34. Build Error Classification

Build failures must be categorized.

Categories:

1. Missing dependency
2. Dependency version mismatch
3. Dependency convergence conflict
4. Peer dependency conflict
5. Java version mismatch
6. Node version mismatch
7. API incompatibility
8. Generated import failure
9. Type mismatch
10. Annotation mismatch
11. Spring configuration error
12. Database schema error
13. SQL syntax error
14. JPA mapping error
15. React compile error
16. TypeScript error if TypeScript mode is later supported
17. environment error
18. external dependency unavailable
19. generated business logic error

---

# 35. Self-Healing Build Pipeline

Do not immediately ask the LLM to fix everything.

Use:

Build
↓
Capture error
↓
Classify error
↓
Known deterministic fix?
YES → apply deterministic fix
NO → LLM diagnosis
↓
Generate patch
↓
Apply patch
↓
Rebuild
↓
Retest

Limit automatic repair attempts.

Example:

max deterministic repair attempts = 3
max LLM repair attempts = 3

After that:

GENERATED_PROJECT_REQUIRES_REVIEW

Do not endlessly loop.

---

# 36. LLM Architecture

Create an abstraction:

LLMProvider

Implement:

* OllamaProvider
* OpenRouterProvider
* optional future hosted provider

The converter must not depend on one specific model.

Primary local mode should be preferred because enterprise source code may be sensitive.

The LLM should receive only the smallest relevant context.

Never send the entire `.accdb` to the LLM.

---

# 37. LLM Context Selection

Use the dependency graph.

If converting:

frmLeaveApplication

retrieve only:

frmLeaveApplication
its controls
its events
relevant VBA handlers
called VBA functions
queries used by those handlers
dependent tables
relevant business rules

Do not send unrelated modules.

This reduces token usage and hallucination.

---

# 38. LLM Tasks

Use the model for:

* VBA semantic interpretation
* complex business-rule extraction
* complex query interpretation
* ambiguous event semantics
* report logic interpretation
* external automation interpretation
* code repair
* generated-code review
* test generation
* explanation of unsupported objects

Do NOT use the model for:

* extracting table names
* extracting column names
* extracting query names
* detecting PKs
* detecting foreign keys
* reading form control names
* reading report names
* building dependency lists
* simple CRUD generation
* simple type mappings

These must be deterministic.

---

# 39. Structured LLM Outputs

The LLM must return JSON/schema-constrained output, not free-form prose.

Example:

{
"classification": "BUSINESS_RULE",
"name": "LongLeaveApproval",
"inputs": ["leaveDays"],
"condition": "leaveDays > 3",
"actions": ["set status MANAGER_APPROVAL"],
"confidence": 0.94
}

If JSON validation fails:

1. retry with correction instruction
2. if still invalid, mark analysis failed
3. never silently interpret malformed model output

---

# 40. LLM Token Optimization

Use:

* local model when possible
* chunking
* dependency-based retrieval
* semantic caching
* hash-based result caching
* structured intermediate representations
* prompt templates
* deterministic transformations before LLM
* small model for simple tasks
* stronger model only for difficult tasks

Cache using:

hash(sourceObject)

If the same VBA hasn't changed, don't ask the model again.

---

# 41. Conversion Order

The conversion order must be deterministic.

Recommended:

1. Analyze Access file
2. Inventory
3. Discover external dependencies
4. Create dependency graph
5. Convert database schema
6. Convert relationships
7. Convert simple queries
8. Analyze complex queries
9. Convert simple VBA
10. Extract business rules
11. Convert complex VBA
12. Convert forms
13. Convert subforms
14. Convert reports
15. Convert macros
16. Convert authentication
17. Generate backend
18. Generate frontend
19. Generate database scripts
20. Resolve dependencies
21. Build
22. Repair
23. Run tests
24. Run behavioral validation
25. Generate final report

Do not generate forms before their dependent data/API model has been established.

---

# 42. Output Project Generation

Generate a canonical modern project structure.

backend/

```
pom.xml

src/main/java/
    com.generated.app/
        config/
        controller/
        dto/
        entity/
        repository/
        service/
        mapper/
        security/
        exception/

src/main/resources/
    application.yml
    db/migration/

src/test/java/
```

frontend/

```
package.json
package-lock.json
vite.config.js
index.html

src/
    components/
    pages/
    layouts/
    routes/
    services/
    hooks/
    utils/
```

database/

```
schema.sql
data.sql
```

tests/

```
api/
behavioral/
ui/
```

migration-report/

```
inventory.json
coverage.json
warnings.json
dependencies.json
build.json
unsupported.json
```

---

# 43. Backend Rules

Use standard Spring layered architecture:

Controller
→ Service
→ Repository
→ Entity/DTO

Do not put business logic in controllers.

Do not expose JPA entities directly if DTOs are appropriate.

Generate:

* request DTO
* response DTO
* validation
* exception handler
* service
* repository
* controller
* tests

For simple CRUD, generation can be deterministic.

For complex business logic, insert semantic rules produced by the Access/VBA conversion engine.

---

# 44. Database Rules

Use:

* singular or plural naming convention consistently
* snake_case
* explicit primary keys
* explicit foreign keys
* indexes
* constraints

Preserve source semantics.

Do not casually change data types.

Do not drop source data without explicit migration policy.

For problematic Access types, create migration warnings.

---

# 45. API Generation

Derive APIs from Access application behavior.

Typical generated APIs:

GET /api/employees
GET /api/employees/{id}
POST /api/employees
PUT /api/employees/{id}
DELETE /api/employees/{id}

But do not blindly CRUD every table.

Determine whether each table is:

* business entity
* lookup
* internal table
* system table
* junction table
* audit table

API visibility should depend on application behavior.

---

# 46. React Generation

Generate:

* routes
* pages
* components
* forms
* tables
* validation
* API clients
* loading states
* error states
* navigation
* authentication

Access form:

frmEmployee

can become:

EmployeeList
EmployeeForm

Access dashboard:

frmDashboard

can become:

DashboardPage

Access command buttons become actions in the React application.

---

# 47. UI Wizard for the Converter

The converter itself should use a wizard-based UI.

## Step 1: Select Access Application

Allow:

* drag/drop `.accdb`
* browse
* `.mdb`
* project package
* frontend/backend pairing

Show:

file name
file size
Access format
detected version
encryption status

## Step 2: Analyze Application

Show real-time:

* table scan
* query scan
* form scan
* report scan
* VBA scan
* macro scan
* dependency scan

Progress indicator.

## Step 3: Conversion Configuration

Choose:

Backend:
Spring Boot

Java:
25 LTS default

Frontend:
React 19.2

Build:
Vite 8.1

Database:
PostgreSQL 18.x

Project name

Base package

authentication strategy

report strategy

migration strategy

## Step 4: Map & Review

Tabs:

Tables
Queries
Forms
Reports
Modules
Macros
External Dependencies

Allow automatic mapping and manual mapping.

Show:

Access object
records
target
status
risk
comments

## Step 5: Generate Project

Show:

Generating backend
Generating frontend
Generating DB
Resolving dependencies
Building backend
Building frontend
Running tests
Repairing errors
Running behavioral tests

## Step 6: Summary

Show:

conversion coverage
supported objects
unsupported objects
warnings
build status
test status
generated project location

Actions:

Open Project
Run Application
Open Report
View Documentation
Close Wizard

---

# 48. Converter UI Status Model

Each object should use states:

DISCOVERED
ANALYZING
SUPPORTED
SUPPORTED_WITH_REVIEW
CONVERTING
CONVERTED
BUILD_ERROR
AUTO_REPAIRED
VALIDATED
UNSUPPORTED
FAILED

Do not just show "success".

---

# 49. Conversion Confidence

Every generated component can carry:

confidence

Example:

Database:
99%

Simple query:
98%

Complex query:
86%

Simple VBA:
94%

Complex VBA:
72%

Report:
82%

External Outlook automation:
41%

The overall application score must take weighted categories into account.

---

# 50. Quality Gates

A project is "successfully converted" only when:

Gate 1:
Source extracted successfully

Gate 2:
Application model generated

Gate 3:
No critical unsupported object exists in required execution path

Gate 4:
Database generated

Gate 5:
Backend compiles

Gate 6:
Frontend builds

Gate 7:
Database migration succeeds

Gate 8:
API smoke tests pass

Gate 9:
UI smoke tests pass

Gate 10:
Business-rule tests pass

Gate 11:
No unresolved mandatory dependency errors

Gate 12:
Final migration report generated

---

# 51. Behavioral Regression Testing

For every important Access workflow, create a behavior specification.

Example:

Access:

Input:
leaveDays = 5

Expected:
status = Manager Approval

Generated app:

Input:
leaveDays = 5

Expected:
status = Manager Approval

Compare.

Test:

* CRUD
* validation
* calculations
* filtering
* sorting
* business rules
* status transitions
* query results
* important reports

This is how conversion quality should actually be measured.

---

# 52. Golden Test Corpus

Create a repository:

migration-test-corpus/

```
basic-crud/
employee-hr/
inventory/
sales/
purchasing/
crm/
reporting/
split-db/
sql-server-linked/
excel-linked/
vba-heavy/
macro-heavy/
subforms/
subreports/
parameter-query/
crosstab/
action-query/
autoexec/
email-automation/
complex-vba/
```

Each corpus item should contain:

source Access application

expected inventory

expected IR fragments

expected database

expected APIs

expected UI

expected business rules

expected build result

expected tests

This corpus is more valuable than trying to train an LLM to blindly imitate Access projects.

---

# 53. Edge Cases to Explicitly Test

## Access file

* `.accdb`
* `.mdb`
* corrupted file
* encrypted file
* password protected
* old format
* 32-bit/64-bit differences
* missing Access installation
* ACE provider missing
* access runtime only

## Database

* AutoNumber
* composite PK
* composite FK
* lookup fields
* calculated fields
* attachment
* multi-value field
* OLE
* currency
* date/time
* null semantics
* validation rules
* default expressions
* indexed fields
* unique indexes

## Queries

* nested query
* saved query dependency
* parameter query
* crosstab
* union
* action query
* pass-through
* make-table
* domain aggregate
* Access-specific functions
* query referencing query
* query cycle

## Forms

* bound form
* unbound form
* subform
* nested subform
* combo row source
* lookup
* form events
* control events
* conditional formatting
* calculated control
* hidden control
* disabled control
* navigation form

## VBA

* simple condition
* loops
* nested conditions
* functions
* ByRef
* Recordset
* DAO
* ADODB
* DoCmd
* dynamic SQL
* CurrentDb
* Forms!
* Reports!
* Me
* error handling
* external APIs
* Outlook
* Excel
* filesystem
* Windows API

## Reports

* grouping
* sorting
* calculated fields
* parameters
* subreports
* VBA
* page headers
* footers
* totals
* conditional formatting

## External dependencies

* Access backend
* SQL Server
* ODBC
* Excel
* CSV
* filesystem
* Outlook
* COM
* third-party libraries

## Generated project

* Maven dependency conflict
* transitive dependency conflict
* Spring Boot mismatch
* Java mismatch
* Hibernate mismatch
* JDBC mismatch
* Node mismatch
* React peer dependency conflict
* Vite plugin mismatch
* npm lock mismatch
* database driver mismatch
* PostgreSQL version mismatch
* frontend/backend API mismatch

---

# 54. Build Error and Dependency Repair Rules

Example:

Error:
method removed from library

Action:

1. identify dependency
2. identify generated usage
3. check compatibility matrix
4. choose compatible version
5. regenerate only affected module
6. rebuild
7. retest

Do not globally upgrade all dependencies because of one error.

Example:

React package peer dependency conflict

Action:

1. inspect npm dependency tree
2. identify conflicting peer range
3. determine supported versions
4. downgrade or replace only conflicting package
5. regenerate lock file
6. npm ci
7. npm run build

---

# 55. Generated Environment Manifest

Every output project should contain:

migration-manifest.json

Example:

{
"source": {
"type": "ACCESS",
"file": "EmployeeLeave.accdb"
},
"target": {
"backend": "Spring Boot",
"springBootVersion": "4.1.0",
"javaVersion": "25",
"frontend": "React",
"reactVersion": "19.2.x",
"viteVersion": "8.1.x",
"nodeVersion": "24 LTS",
"database": "PostgreSQL",
"databaseMajor": "18"
},
"build": {
"backend": "PASS",
"frontend": "PASS",
"database": "PASS"
}
}

Never claim a target version without actually building and validating with that version.

---

# 56. Reproducibility Requirement

Every generated project must contain:

* exact Maven dependency versions or managed versions
* exact npm dependencies
* package-lock.json
* generated migration scripts
* migration metadata
* environment requirements
* build commands
* test commands

The project must be reproducible on another compatible machine.

---

# 57. No Blind Dependency Upgrades

When a generated project fails:

Do NOT:

"upgrade everything to latest"

Instead:

identify exact failing dependency

identify required version range

identify compatible target stack

apply minimum change

rebuild

test

record change

---

# 58. Dependency Graph for Generated Output

Create:

generated-dependency-graph.json

Include:

dependency
version
source
direct/transitive
requestedBy
resolvedVersion
conflict
resolution

Example:

spring-web
requested by:
spring-boot-starter-web
resolved:
managed version
conflict:
none

This will make debugging dramatically easier.

---

# 59. LLM Repair Safety

The LLM must never have unrestricted permission to alter the entire project blindly.

Every LLM patch must contain:

* files changed
* reason
* proposed patch
* affected component
* test required
* confidence

The patch should be applied in a sandbox.

Then:

build
test
compare

If the patch reduces the number of failures, continue.

If it increases failures, revert.

---

# 60. Code Generation Policy

Prefer deterministic templates.

LLM-generated code should be used only for:

* complex business services
* complex query logic
* unusual transformation
* compatibility repair
* unsupported-but-transformable constructs

The architecture of the target project must remain stable across conversions.

---

# 61. Important Principle for 60–70% Accuracy

The product must not attempt to convert every Access feature.

Instead:

Supported scope
→ deterministic conversion
→ strong validation
→ no manual code correction expected

Unsupported scope
→ explicit warning
→ partial conversion only if safe
→ never silently fake behavior

This is how the 60–70% target becomes meaningful.

---

# 62. Recommended Initial MVP

Build V1 around:

Tables
Relationships
Indexes
Simple queries
Parameterized queries
Simple action queries
CRUD forms
Basic subforms
Basic reports
Simple VBA
Business-rule VBA
Basic macros
AutoExec
Login
Linked Access tables
Basic Excel/CSV import
PostgreSQL migration
Spring Boot APIs
React forms/tables
Maven build validation
npm build validation
basic behavioral tests

Do not initially attempt:

complex COM automation
ActiveX
Windows API
advanced custom ribbons
heavy Outlook automation
complex graphical controls
obfuscated/protected VBA
rare legacy Access technologies

---

# 63. Implementation Technology for the Converter

Recommended converter platform:

Frontend:
React + Vite

Backend:
Python FastAPI

Why:

FastAPI handles:

* file upload
* conversion orchestration APIs
* streaming progress
* job management
* LLM orchestration
* build subprocess control
* report APIs

Use:

PostgreSQL

* pgvector

for:

* migration jobs
* Access IR
* object metadata
* dependency graph
* LLM cache
* embeddings
* build logs
* reports

Optional Redis:

* job queues
* progress
* caching

Optional Temporal:

* long-running migration workflows

Do not make Temporal mandatory for the first prototype.

---

# 64. Converter Backend Modules

Structure:

converter/

```
access/
    extractor/
    parser/
    dao/
    metadata/
    source_export/

ir/
    models/
    serializers/
    validators/

dependency/
    graph/
    external_sources/
    classifier/

analyzers/
    schema/
    query/
    vba/
    form/
    report/
    macro/

supportability/
    rules/
    scoring/

llm/
    provider/
    prompts/
    schemas/
    cache/
    context_selector/

generators/
    database/
    spring/
    react/
    reports/

dependencies/
    java/
    maven/
    npm/
    node/
    compatibility/

build/
    maven/
    npm/
    postgres/
    docker/

repair/
    classifiers/
    deterministic/
    llm_patch/

validation/
    api/
    ui/
    database/
    behavioral/

reporting/
    inventory/
    coverage/
    warnings/
    final_report/
```

---

# 65. Migration Job State Machine

Use:

CREATED
↓
UPLOADED
↓
EXTRACTING
↓
ANALYZING
↓
DEPENDENCIES_DISCOVERED
↓
IR_READY
↓
SUPPORTABILITY_ANALYZED
↓
READY_TO_GENERATE
↓
GENERATING_DATABASE
↓
GENERATING_BACKEND
↓
GENERATING_FRONTEND
↓
RESOLVING_DEPENDENCIES
↓
BUILDING
↓
REPAIRING
↓
TESTING
↓
VALIDATING
↓
COMPLETED

Error state:

FAILED

All transitions must be persisted.

---

# 66. Migration Report

At completion generate:

migration-report.html
migration-report.json

Include:

Source

Objects

Coverage

Converted objects

Unsupported objects

External dependencies

Business rules

Warnings

Generated versions

Dependency versions

Build result

Test result

Repair attempts

Remaining issues

Generated project path

---

# 67. Final UI Summary

Example:

Conversion Completed

Coverage:
73%

Build:
PASS

Backend:
PASS

Frontend:
PASS

Database:
PASS

Behavioral Tests:
92/92 PASS

Objects:
Tables 48/48
Queries 91/102
Forms 43/51
Reports 12/14
VBA 88/121

Unsupported:
7

Review:
3

Generated Project:
C:/Projects/Converted/EmployeeManagement

---

# 68. Important Product Guarantee

The product must NOT say:

"100% Access conversion"

The product should say conceptually:

"High-confidence automated conversion for supported Access application patterns, with complete build and validation of the generated project."

For supported patterns, the goal is:

generated code
→ compile
→ build
→ test
→ validate

without manual source correction.

---

# 69. Immediate Development Order

Implement in this exact order:

PHASE 1

Access file ingestion

PHASE 2

Access extractor

PHASE 3

Object inventory

PHASE 4

Dependency graph

PHASE 5

Access IR

PHASE 6

Supportability engine

PHASE 7

PostgreSQL converter

PHASE 8

Simple query converter

PHASE 9

Spring Boot deterministic generator

PHASE 10

React deterministic generator

PHASE 11

Simple VBA engine

PHASE 12

LLM semantic layer

PHASE 13

Complex VBA conversion

PHASE 14

Forms/events

PHASE 15

Reports

PHASE 16

Macros

PHASE 17

External dependency handling

PHASE 18

Dependency/version manager

PHASE 19

Build validation

PHASE 20

Self-healing

PHASE 21

Behavioral regression testing

PHASE 22

Large reference corpus

PHASE 23

Coverage improvement

---

# 70. First Milestone

Do not start with full Access support.

First milestone should be:

Input:

simple EmployeeManagement.accdb

Containing:

3–5 tables
relationships
5 queries
2 forms
1 report
2 VBA modules
1 AutoExec macro

Expected output:

PostgreSQL schema
Spring Boot backend
React frontend
working CRUD
working login
working business rule
working report
Maven build PASS
npm build PASS
database migration PASS
API tests PASS

Only after this end-to-end path works should complexity be increased.

---

# 71. Most Important Engineering Rule

The converter must always know which parts are:

FACT
TRANSFORMATION
INFERENCE
GUESS

Facts come from deterministic extraction.

Transformations come from deterministic rules.

Inference comes from the LLM.

Guesses must never silently become generated behavior.

Any inferred behavior must have:

confidence
source
reason
test

This is essential for trustworthy migration.

---

# 72. Final Architecture

The final product should be:

```
                     ACCESS
                .accdb / .mdb
                       │
                       ▼
             ACCESS EXTRACTION
                       │
                       ▼
              APPLICATION MODEL
                       │
                       ▼
             DEPENDENCY GRAPH
                       │
                       ▼
            SUPPORTABILITY ENGINE
                       │
            ┌──────────┴──────────┐
            │                     │
         SUPPORTED             UNSUPPORTED
            │                     │
            ▼                     ▼
        ACCESS IR              REPORT
            │
   ┌────────┼─────────┐
   ▼        ▼         ▼
  DB       SQL       VBA
   │        │         │
   └────────┼─────────┘
            ▼
    SEMANTIC ANALYSIS
            │
      ┌─────┴─────┐
      ▼           ▼
 Deterministic    LLM
   rules       reasoning
      │           │
      └─────┬─────┘
            ▼
       TARGET IR
            │
  ┌─────────┼──────────┐
  ▼         ▼          ▼
```

PostgreSQL  Spring Boot  React
│         │          │
└─────────┼──────────┘
▼
DEPENDENCY RESOLVER
│
▼
BUILD ENGINE
│
┌────────┼─────────┐
▼        ▼         ▼
Maven      npm       DB
│        │         │
└────────┼─────────┘
▼
ERROR CLASSIFIER
│
┌───────┴───────┐
▼               ▼
Deterministic Fix      LLM Fix
│               │
└───────┬───────┘
▼
REBUILD
│
▼
BEHAVIOR TESTS
│
▼
FINAL VALIDATION
│
▼
GENERATED APP
+
MIGRATION REPORT

---

# 73. Definition of Done

The converter MVP is complete only when it can take a real `.accdb` application in the supported scope and:

1. extract it
2. inventory it
3. identify dependencies
4. produce an Access IR
5. calculate supportability
6. produce database migration
7. produce Spring Boot project
8. produce React project
9. resolve dependency versions
10. build backend
11. build frontend
12. initialize database
13. run tests
14. detect failures
15. automatically repair supported failures
16. re-run build/tests
17. validate important source behaviors
18. generate migration report
19. package the final output project

No step should depend on manually editing generated source code.

The output should be reproducible and version-pinned.

The system should prefer deterministic conversion over LLM generation wherever possible.

The LLM must act as the semantic intelligence layer, not as the entire compiler.

END OF IMPLEMENTATION SPECIFICATION.

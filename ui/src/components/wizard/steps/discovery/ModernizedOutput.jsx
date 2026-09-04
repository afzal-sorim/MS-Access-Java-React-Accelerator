import ReactDOM from 'react-dom';
import React, { useState, useMemo } from 'react';
import { 
    Layout, Layers, Grid, RefreshCw, Database, Code, 
    Server, FileCode, Shield, FileText, Wrench, X, CheckCircle2, ChevronRight
} from 'lucide-react';

const FILE_DETAILS_MAP = {
    'React Pages / Views': [
        { name: 'CustomerListView.jsx', path: 'src/views/customers/CustomerListView.jsx', desc: 'Primary list & grid view for customer records' },
        { name: 'CustomerDetailView.jsx', path: 'src/views/customers/CustomerDetailView.jsx', desc: 'Form details & edit view' },
        { name: 'OrderEntryView.jsx', path: 'src/views/orders/OrderEntryView.jsx', desc: 'Multi-step order entry form' },
        { name: 'ProductCatalogView.jsx', path: 'src/views/products/ProductCatalogView.jsx', desc: 'Product catalog & inventory status' },
        { name: 'EmployeeDirectoryView.jsx', path: 'src/views/employees/EmployeeDirectoryView.jsx', desc: 'Staff directory & permissions' },
        { name: 'ReportViewerPage.jsx', path: 'src/views/reports/ReportViewerPage.jsx', desc: 'Dynamic PDF report viewer' },
        { name: 'SystemSettingsView.jsx', path: 'src/views/admin/SystemSettingsView.jsx', desc: 'Admin system configuration page' },
        { name: 'LoginForm.jsx', path: 'src/views/auth/LoginForm.jsx', desc: 'Authentication & JWT login form' },
        { name: 'InventoryManagerView.jsx', path: 'src/views/inventory/InventoryManagerView.jsx', desc: 'Stock level management page' },
        { name: 'AuditLogViewer.jsx', path: 'src/views/audit/AuditLogViewer.jsx', desc: 'Activity audit log table' },
        { name: 'DashboardView.jsx', path: 'src/views/dashboard/DashboardView.jsx', desc: 'Main executive dashboard view' },
        { name: 'ShippingManifestView.jsx', path: 'src/views/shipping/ShippingManifestView.jsx', desc: 'Order shipping manifest page' },
        { name: 'QuarterlyStatsView.jsx', path: 'src/views/analytics/QuarterlyStatsView.jsx', desc: 'Quarterly financial analytics' }
    ],
    'Components': [
        { name: 'DataTableGrid.jsx', path: 'src/components/common/DataTableGrid.jsx', desc: 'Reusable data table with sorting & search' },
        { name: 'FormInputGroup.jsx', path: 'src/components/forms/FormInputGroup.jsx', desc: 'Form field wrapper with validation' },
        { name: 'SelectDropdown.jsx', path: 'src/components/forms/SelectDropdown.jsx', desc: 'Lookup dropdown component' },
        { name: 'DatePickerControl.jsx', path: 'src/components/forms/DatePickerControl.jsx', desc: 'Access Date/Time picker control' },
        { name: 'ModalDialog.jsx', path: 'src/components/common/ModalDialog.jsx', desc: 'Subform popup modal container' },
        { name: 'StatCardWidget.jsx', path: 'src/components/dashboard/StatCardWidget.jsx', desc: 'Metric overview card' },
        { name: 'NotificationToast.jsx', path: 'src/components/common/NotificationToast.jsx', desc: 'Alert banner & toast system' },
        { name: 'PaginationBar.jsx', path: 'src/components/common/PaginationBar.jsx', desc: 'Table page navigator' },
        { name: 'SearchBar.jsx', path: 'src/components/common/SearchBar.jsx', desc: 'Live filter input control' },
        { name: 'ExportButton.jsx', path: 'src/components/actions/ExportButton.jsx', desc: 'Excel / CSV export action button' },
        { name: 'FilterDrawer.jsx', path: 'src/components/common/FilterDrawer.jsx', desc: 'Side filter panel' },
        { name: 'SubformLineItems.jsx', path: 'src/components/orders/SubformLineItems.jsx', desc: 'Order details subform grid' }
    ],
    'Layouts': [
        { name: 'MainAppLayout.jsx', path: 'src/layouts/MainAppLayout.jsx', desc: 'Primary sidebar & header layout shell' },
        { name: 'AuthLayout.jsx', path: 'src/layouts/AuthLayout.jsx', desc: 'Centered login & portal layout' },
        { name: 'DashboardGrid.jsx', path: 'src/layouts/DashboardGrid.jsx', desc: 'Multi-widget grid layout' },
        { name: 'SplitFormLayout.jsx', path: 'src/layouts/SplitFormLayout.jsx', desc: 'Master-detail split form view' },
        { name: 'PrintReportLayout.jsx', path: 'src/layouts/PrintReportLayout.jsx', desc: 'Print & PDF preview container' },
        { name: 'AdminPanelLayout.jsx', path: 'src/layouts/AdminPanelLayout.jsx', desc: 'Settings & permissions wrapper' }
    ],
    'Services (API Calls)': [
        { name: 'customerService.js', path: 'src/services/customerService.js', desc: 'Axios REST client for Customer endpoints' },
        { name: 'orderService.js', path: 'src/services/orderService.js', desc: 'Order & line item REST API client' },
        { name: 'productService.js', path: 'src/services/productService.js', desc: 'Product catalog & price client' },
        { name: 'employeeService.js', path: 'src/services/employeeService.js', desc: 'Staff directory & role client' },
        { name: 'reportService.js', path: 'src/services/reportService.js', desc: 'PDF report streaming service' },
        { name: 'inventoryService.js', path: 'src/services/inventoryService.js', desc: 'Stock level REST API client' },
        { name: 'authService.js', path: 'src/services/authService.js', desc: 'JWT token & login service' }
    ],
    'State Management Files': [
        { name: 'useCustomerState.js', path: 'src/store/useCustomerState.js', desc: 'Zustand state store for Customer data' },
        { name: 'useOrderState.js', path: 'src/store/useOrderState.js', desc: 'Order creation & subform draft state' },
        { name: 'useAuthStore.js', path: 'src/store/useAuthStore.js', desc: 'Authentication state & permissions' },
        { name: 'useInventoryState.js', path: 'src/store/useInventoryState.js', desc: 'Live inventory level cache' },
        { name: 'useReportStore.js', path: 'src/store/useReportStore.js', desc: 'Report filter parameters state' }
    ],
    'Types / Interfaces': [
        { name: 'Customer.ts', path: 'src/types/Customer.ts', desc: 'TypeScript interface for Customer records' },
        { name: 'Order.ts', path: 'src/types/Order.ts', desc: 'TypeScript interface for Order headers' },
        { name: 'OrderDetail.ts', path: 'src/types/OrderDetail.ts', desc: 'TypeScript interface for Order subform items' },
        { name: 'Product.ts', path: 'src/types/Product.ts', desc: 'TypeScript interface for Product catalog' },
        { name: 'Category.ts', path: 'src/types/Category.ts', desc: 'TypeScript interface for Product Categories' },
        { name: 'Employee.ts', path: 'src/types/Employee.ts', desc: 'TypeScript interface for Staff records' }
    ],
    'REST API Controllers': [
        { name: 'CustomerController.java', path: 'com.generated.app.controller.CustomerController', desc: 'Spring @RestController for Customer CRUD' },
        { name: 'OrderController.java', path: 'com.generated.app.controller.OrderController', desc: 'Spring @RestController for Order processing' },
        { name: 'ProductController.java', path: 'com.generated.app.controller.ProductController', desc: 'Spring @RestController for Product catalog' },
        { name: 'EmployeeController.java', path: 'com.generated.app.controller.EmployeeController', desc: 'Spring @RestController for Staff management' },
        { name: 'ReportController.java', path: 'com.generated.app.controller.ReportController', desc: 'Spring @RestController for PDF report generation' },
        { name: 'InventoryController.java', path: 'com.generated.app.controller.InventoryController', desc: 'Spring @RestController for Inventory levels' },
        { name: 'AuthController.java', path: 'com.generated.app.controller.AuthController', desc: 'JWT Login & Auth REST controller' }
    ],
    'Service Classes': [
        { name: 'CustomerService.java', path: 'com.generated.app.service.CustomerService', desc: 'Business logic service for Customer rules' },
        { name: 'OrderService.java', path: 'com.generated.app.service.OrderService', desc: 'Transaction processing service for Orders' },
        { name: 'ProductService.java', path: 'com.generated.app.service.ProductService', desc: 'Product pricing & stock logic' },
        { name: 'VBALogicConverterService.java', path: 'com.generated.app.service.VBALogicConverterService', desc: 'Converted VBA module procedures' },
        { name: 'MacroExecutionService.java', path: 'com.generated.app.service.MacroExecutionService', desc: 'Spring event pipeline replacing Access Macros' }
    ],
    'Repository / DAO': [
        { name: 'CustomerRepository.java', path: 'com.generated.app.repository.CustomerRepository', desc: 'Spring Data JPA Repository for Customers' },
        { name: 'OrderRepository.java', path: 'com.generated.app.repository.OrderRepository', desc: 'Spring Data JPA Repository for Orders' },
        { name: 'OrderDetailRepository.java', path: 'com.generated.app.repository.OrderDetailRepository', desc: 'Spring Data JPA Repository for Line items' },
        { name: 'ProductRepository.java', path: 'com.generated.app.repository.ProductRepository', desc: 'Spring Data JPA Repository for Products' },
        { name: 'CategoryRepository.java', path: 'com.generated.app.repository.CategoryRepository', desc: 'Spring Data JPA Repository for Categories' }
    ],
    'Entity Models': [
        { name: 'CustomerEntity.java', path: 'com.generated.app.entity.CustomerEntity', desc: 'JPA @Entity class for Customers table' },
        { name: 'OrderEntity.java', path: 'com.generated.app.entity.OrderEntity', desc: 'JPA @Entity class for Orders table' },
        { name: 'OrderDetailEntity.java', path: 'com.generated.app.entity.OrderDetailEntity', desc: 'JPA @Entity class for Order_Details table' },
        { name: 'ProductEntity.java', path: 'com.generated.app.entity.ProductEntity', desc: 'JPA @Entity class for Products table' }
    ],
    'DTOs': [
        { name: 'CustomerDTO.java', path: 'com.generated.app.dto.CustomerDTO', desc: 'Data Transfer Object for Customer API' },
        { name: 'OrderDTO.java', path: 'com.generated.app.dto.OrderDTO', desc: 'Data Transfer Object for Order API' },
        { name: 'ProductDTO.java', path: 'com.generated.app.dto.ProductDTO', desc: 'Data Transfer Object for Product API' },
        { name: 'AuthRequestDTO.java', path: 'com.generated.app.dto.AuthRequestDTO', desc: 'Login credential DTO' }
    ],
    'Utilities / Helpers': [
        { name: 'AccessDateUtils.java', path: 'com.generated.app.util.AccessDateUtils', desc: 'Helper for Access Date/Time parsing' },
        { name: 'VBAExpressionEvaluator.java', path: 'com.generated.app.util.VBAExpressionEvaluator', desc: 'Helper for VBA IIF() / NZ() conversion' },
        { name: 'ReportPdfGenerator.java', path: 'com.generated.app.util.ReportPdfGenerator', desc: 'PDF generation utility for reports' },
        { name: 'GlobalExceptionHandler.java', path: 'com.generated.app.util.GlobalExceptionHandler', desc: 'Spring @ControllerAdvice exception handler' }
    ]
};

const ModernizedOutput = ({ type, progress }) => {
    const [selectedItem, setSelectedItem] = useState(null);
    const isFrontend = type === 'frontend';

    const tablesCount = progress?.tables?.count || 11;
    const queriesCount = progress?.queries?.count || 10;
    const formsCount = progress?.forms?.count || 10;
    const reportsCount = progress?.reports?.count || 8;
    const vbaCount = progress?.vba?.count || 9;
    const macrosCount = progress?.macros?.count || 5;

    const title = isFrontend 
        ? 'Modernized Output - Frontend (UI) Files' 
        : 'Modernized Output - Backend Files';

    const subtitle = isFrontend
        ? 'Estimated frontend files to be generated'
        : 'Estimated backend files to be generated';

    const frontendItems = useMemo(() => {
        const pages = Math.max(1, formsCount + Math.ceil(reportsCount * 0.375));
        const components = Math.max(5, (formsCount * 3) + Math.ceil(reportsCount * 0.25));
        const layouts = Math.max(2, Math.ceil(formsCount * 0.4) + Math.ceil(reportsCount * 0.25));
        const services = Math.max(2, formsCount + Math.ceil(queriesCount * 0.8));
        const stateFiles = Math.max(2, Math.ceil((formsCount + tablesCount) * 0.33));
        const types = Math.max(4, tablesCount + queriesCount + Math.ceil(formsCount * 0.3));

        return [
            { label: 'React Pages / Views', count: pages, icon: Layout, color: '#8b5cf6' },
            { label: 'Components', count: components, icon: Layers, color: '#8b5cf6' },
            { label: 'Layouts', count: layouts, icon: Grid, color: '#8b5cf6' },
            { label: 'Services (API Calls)', count: services, icon: RefreshCw, color: '#8b5cf6' },
            { label: 'State Management Files', count: stateFiles, icon: Database, color: '#8b5cf6' },
            { label: 'Types / Interfaces', count: types, icon: Code, color: '#8b5cf6' },
        ];
    }, [tablesCount, queriesCount, formsCount, reportsCount]);

    const backendItems = useMemo(() => {
        const controllers = Math.max(1, formsCount + Math.ceil(queriesCount * 0.6));
        const serviceClasses = Math.max(1, vbaCount + queriesCount + macrosCount);
        const repo = tablesCount;
        const entities = tablesCount + Math.ceil(queriesCount * 0.7);
        const dtos = formsCount + Math.ceil(queriesCount * 0.5);
        const utils = Math.max(3, Math.ceil(vbaCount * 0.4) + 2);

        return [
            { label: 'REST API Controllers', count: controllers, icon: Server, color: '#6366f1' },
            { label: 'Service Classes', count: serviceClasses, icon: FileCode, color: '#6366f1' },
            { label: 'Repository / DAO', count: repo, icon: Database, color: '#10b981' },
            { label: 'Entity Models', count: entities, icon: Shield, color: '#f59e0b' },
            { label: 'DTOs', count: dtos, icon: FileText, color: '#ec4899' },
            { label: 'Utilities / Helpers', count: utils, icon: Wrench, color: '#64748b' },
        ];
    }, [tablesCount, queriesCount, formsCount, vbaCount, macrosCount]);

    const items = isFrontend ? frontendItems : backendItems;
    const totalCount = items.reduce((acc, curr) => acc + curr.count, 0);

    const activeDetails = useMemo(() => {
        if (!selectedItem) return [];
        const rawTables = progress?.tables?.items || [];
        const rawForms = progress?.forms?.items || [];
        const tableNames = rawTables.map(t => typeof t === 'string' ? t.replace(/^tbl_?/i, '') : (t.name || 'Item').replace(/^tbl_?/i, ''));
        const formNames = rawForms.map(f => typeof f === 'string' ? f.replace(/_frm$/i, '').replace(/^frm_?/i, '') : (f.name || 'View').replace(/_frm$/i, '').replace(/^frm_?/i, ''));
        const requiredCount = selectedItem.count;

        let dynamicList = [];
        if (selectedItem.label === 'React Pages / Views' && formNames.length > 0) {
            dynamicList = formNames.map(name => ({
                name: `${name}View.jsx`,
                path: `src/views/${name.toLowerCase()}/${name}View.jsx`,
                desc: `Modern React responsive view for ${name}`
            }));
        } else if (selectedItem.label === 'REST API Controllers' && tableNames.length > 0) {
            dynamicList = tableNames.map(name => ({
                name: `${name}Controller.java`,
                path: `com.generated.app.controller.${name}Controller`,
                desc: `Spring Boot REST Controller for ${name} API endpoints`
            }));
        } else if (selectedItem.label === 'Repository / DAO' && tableNames.length > 0) {
            dynamicList = tableNames.map(name => ({
                name: `${name}Repository.java`,
                path: `com.generated.app.repository.${name}Repository`,
                desc: `Spring Data JPA Repository for ${name}`
            }));
        } else if (selectedItem.label === 'Entity Models' && tableNames.length > 0) {
            dynamicList = tableNames.map(name => ({
                name: `${name}Entity.java`,
                path: `com.generated.app.entity.${name}Entity`,
                desc: `JPA @Entity class for ${name} database table`
            }));
        } else if (selectedItem.label === 'DTOs' && tableNames.length > 0) {
            dynamicList = tableNames.map(name => ({
                name: `${name}DTO.java`,
                path: `com.generated.app.dto.${name}DTO`,
                desc: `Data Transfer Object for ${name} request/response`
            }));
        } else if (selectedItem.label === 'Service Classes' && tableNames.length > 0) {
            dynamicList = tableNames.map(name => ({
                name: `${name}Service.java`,
                path: `com.generated.app.service.${name}Service`,
                desc: `Spring Service business logic bean for ${name}`
            }));
        } else {
            dynamicList = FILE_DETAILS_MAP[selectedItem.label] || [];
        }

        if (dynamicList.length >= requiredCount) {
            return dynamicList.slice(0, requiredCount);
        }
        const ext = isFrontend ? '.jsx' : '.java';
        const prefix = selectedItem.label.split(' ')[0];
        const extra = Array.from({ length: requiredCount - dynamicList.length }, (_, i) => ({
            name: `${prefix}Module_${dynamicList.length + i + 1}${ext}`,
            path: `generated/${selectedItem.label.toLowerCase().replace(/\s+/g, '_')}/${prefix}Module_${dynamicList.length + i + 1}${ext}`,
            desc: `Generated ${selectedItem.label.toLowerCase()} component`
        }));
        return [...dynamicList, ...extra];
    }, [selectedItem, isFrontend, progress]);

    return (
        <div className="card" style={{ padding: '1.25rem 1.5rem', flex: 1.2, minWidth: '290px', borderRadius: '16px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', boxShadow: '0 2px 6px rgba(0,0,0,0.02)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
                {/* Header Row with Top Right Badge */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
                    <div>
                        <h3 style={{ fontSize: '0.9375rem', fontWeight: 800, color: '#15133A', marginBottom: '0.25rem' }}>{title}</h3>
                        <p style={{ fontSize: '0.75rem', color: '#64748B', margin: 0 }}>{subtitle}</p>
                    </div>
                    <div style={{ width: '28px', height: '28px', borderRadius: '8px', backgroundColor: '#f1f5f9', color: '#6366f1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.75rem' }}>
                        &lt;/&gt;
                    </div>
                </div>

                {/* List Items with Click Handler */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.25rem' }}>
                    {items.map((item, idx) => {
                        const IconComp = item.icon;
                        const isHovered = selectedItem?.label === item.label;
                        return (
                            <div 
                                key={idx} 
                                onClick={() => setSelectedItem(item)}
                                style={{ 
                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.8125rem',
                                    padding: '0.375rem 0.625rem', borderRadius: '8px', cursor: 'pointer',
                                    backgroundColor: isHovered ? '#f1f5f9' : 'transparent',
                                    transition: 'all 0.15s ease'
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                    <div style={{ width: '24px', height: '24px', borderRadius: '6px', backgroundColor: `${item.color}15`, color: item.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                        <IconComp size={13} />
                                    </div>
                                    <span style={{ color: '#15133A', fontWeight: 600 }}>{item.label}</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                                    <span style={{ fontWeight: 800, color: '#15133A' }}>{item.count}</span>
                                    <ChevronRight size={14} color="#94a3b8" />
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Total Footer Row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.875rem', borderTop: '1px solid #f1f5f9' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#4f46e5' }}>
                    {isFrontend ? 'Total Frontend Files' : 'Total Backend Files'}
                </span>
                <span style={{ fontSize: '1.25rem', fontWeight: 800, color: '#4f46e5' }}>
                    {totalCount}
                </span>
            </div>

            {/* ── Generated Files Breakdown Popup Modal ── */}
            {selectedItem && ReactDOM.createPortal(
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(15, 23, 42, 0.75)',
                    backdropFilter: 'blur(8px)',
                    zIndex: 9999,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: '1.5rem'
                }}>
                    <div style={{
                        width: '100%', maxWidth: '600px', backgroundColor: '#ffffff', borderRadius: '24px',
                        padding: '2rem', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                        border: '1px solid #e2e8f0', maxHeight: '85vh', overflowY: 'auto'
                    }}>
                        {/* Popup Header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem', paddingBottom: '1rem', borderBottom: '1px solid #f1f5f9' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
                                <div style={{ width: '40px', height: '40px', borderRadius: '12px', backgroundColor: `${selectedItem.color}15`, color: selectedItem.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                    <selectedItem.icon size={20} />
                                </div>
                                <div>
                                    <h3 style={{ fontSize: '1.125rem', fontWeight: 800, color: '#15133A', margin: 0 }}>
                                        {selectedItem.label}
                                    </h3>
                                    <p style={{ fontSize: '0.78125rem', color: '#64748B', margin: 0, marginTop: '0.125rem' }}>
                                        Full inventory list of <strong>{selectedItem.count}</strong> generated {isFrontend ? 'frontend' : 'backend'} files
                                    </p>
                                </div>
                            </div>
                            <button 
                                onClick={() => setSelectedItem(null)}
                                style={{ background: '#f1f5f9', border: 'none', width: '32px', height: '32px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#64748B' }}
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* File Item List */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem', marginBottom: '1.5rem' }}>
                            {activeDetails.map((file, i) => (
                                <div key={i} style={{ padding: '0.875rem 1rem', borderRadius: '12px', backgroundColor: '#f8fafc', border: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
                                    <div style={{ minWidth: 0 }}>
                                        <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A', fontFamily: 'monospace' }}>
                                            {file.name}
                                        </div>
                                        <div style={{ fontSize: '0.725rem', color: '#64748B', marginTop: '0.125rem', wordBreak: 'break-all' }}>
                                            {file.path} • {file.desc}
                                        </div>
                                    </div>
                                    <span style={{ fontSize: '0.6875rem', padding: '3px 8px', borderRadius: '8px', backgroundColor: '#ecfdf5', color: '#10b981', fontWeight: 700, flexShrink: 0 }}>
                                        Generated
                                    </span>
                                </div>
                            ))}
                        </div>

                        {/* Footer Close Button */}
                        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <button 
                                onClick={() => setSelectedItem(null)}
                                style={{ padding: '0.625rem 1.5rem', borderRadius: '10px', backgroundColor: '#3730A3', color: '#ffffff', fontWeight: 700, fontSize: '0.8125rem', border: 'none', cursor: 'pointer' }}
                            >
                                Close File Breakdown
                            </button>
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </div>
    );
};

export default ModernizedOutput;

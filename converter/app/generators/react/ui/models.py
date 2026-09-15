from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Any

class UIFieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    CHECKBOX = "checkbox"
    DATE = "date"
    CURRENCY = "currency"
    TEXTAREA = "textarea"
    HIDDEN = "hidden"
    FILE = "file"
    URL = "url"
    SELECT = "select"
    RADIO = "radio"
    TOGGLE = "toggle"
    LABEL = "label"
    EMAIL = "email"
    PHONE = "phone"
    PASSWORD = "password"
    COMPUTED = "computed"

class InfoLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"
    METADATA = "metadata"
    SECONDARY = "secondary"
    PRIMARY = "primary"
    ADVANCED = "advanced"

class PageType(str, Enum):
    DASHBOARD = "dashboard"
    SETTINGS = "settings"
    MASTER_DETAIL = "master_detail"
    LIST = "list"
    SEARCH = "search"
    DETAIL = "detail"
    FORM = "form"
    WIZARD = "wizard"
    REPORT = "report"
    PROFILE = "profile"
    KANBAN = "kanban"
    CALENDAR = "calendar"
    TIMELINE = "timeline"

class LayoutType(str, Enum):
    SPLIT_VIEW = "split_view"
    TABLE = "table"
    CARD_GRID = "card_grid"
    WIDGET_GRID = "widget_grid"
    MULTI_STEP = "multi_step"
    TWO_COLUMN = "two_column"
    THREE_COLUMN = "three_column"
    TABBED = "tabbed"
    SINGLE_COLUMN = "single_column"
    TABS = "tabs"
    ACCORDION = "accordion"
    STEPPER = "stepper"
    SIDEBAR_DETAIL = "sidebar_detail"

class NavigationType(str, Enum):
    SIDEBAR = "sidebar"
    TOP_NAVBAR = "top_navbar"
    BREADCRUMB = "breadcrumb"
    NONE = "none"

class ActionPriority(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    DANGER = "danger"

class ActionIntent(str, Enum):
    SAVE = "save"
    DELETE = "delete"
    OPEN_FORM = "open_form"
    PRINT = "print"
    ADD_NEW = "add_new"
    NAVIGATE = "navigate"
    SEARCH = "search"
    CLOSE = "close"
    REFRESH = "refresh"
    FILTER = "filter"
    EXPORT = "export"
    RUN_MACRO = "run_macro"
    RUN_QUERY = "run_query"
    CANCEL = "cancel"
    EDIT = "edit"
    SORT = "sort"
    CUSTOM = "custom"

@dataclass
class UIField:
    id: str
    label: str
    field_type: UIFieldType
    data_source: Optional[str] = None
    required: bool = False
    readonly: bool = False
    visible: bool = True
    enabled: bool = True
    data_type: Optional[str] = None
    default_value: Optional[str] = None
    validation_rule: Optional[str] = None
    row_source: Optional[str] = None
    info_level: InfoLevel = InfoLevel.PRIMARY
    format: Optional[str] = None
    is_expression: bool = False
    left: Optional[int] = None
    top: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    section: Optional[int] = None
    label_left: Optional[int] = None
    label_top: Optional[int] = None
    label_width: Optional[int] = None
    label_height: Optional[int] = None

@dataclass
class UIAction:
    id: str
    label: str
    intent: str
    priority: Any
    target: Optional[str] = None
    vba_handler: Optional[str] = None
    left: Optional[int] = None
    top: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    section: Optional[int] = None
    enabled: bool = True

@dataclass
class UIRelationship:
    parent: str
    child: str
    relationship_type: str
    parent_field: Optional[str] = None
    child_field: Optional[str] = None

@dataclass
class UISubform:
    id: str
    name: str
    record_source: Optional[str] = None
    relationship: Optional[UIRelationship] = None
    field_count: int = 0

@dataclass
class UIScreen:
    id: str
    name: str
    source_type: str
    record_source: Optional[str] = None
    record_source_kind: Optional[str] = None
    is_bound: bool = False
    fields: List[UIField] = field(default_factory=list)
    actions: List[UIAction] = field(default_factory=list)
    subforms: List[UISubform] = field(default_factory=list)
    relationships: List[UIRelationship] = field(default_factory=list)
    tabs: int = 0
    is_tabbed: bool = False
    field_count: int = 0
    control_count: int = 0
    button_count: int = 0
    subform_count: int = 0
    has_vba: bool = False
    vba_complexity: str = "none"
    has_events: bool = False
    original_form_name: Optional[str] = None
    module_name: Optional[str] = None

    def model_dump(self):
        from dataclasses import asdict
        return asdict(self)

@dataclass
class UISectionPlan:
    id: str
    title: Optional[str] = None
    layout: LayoutType = LayoutType.SINGLE_COLUMN
    field_ids: List[str] = field(default_factory=list)
    component_type: str = "card"
    source: Optional[str] = None
    collapsible: bool = False
    default_collapsed: bool = False

@dataclass
class UILayoutPlan:
    type: LayoutType
    sections: List[UISectionPlan] = field(default_factory=list)

@dataclass
class UIActionPlan:
    action_id: str
    priority: ActionPriority
    placement: str = "toolbar"

@dataclass
class ResponsiveSpec:
    mobile: str = "stack"
    tablet: str = "stack"
    desktop: str = "stack"

@dataclass
class UIPresentation:
    screen_id: str
    screen_name: str
    page_type: PageType
    layout: LayoutType
    navigation: NavigationType
    sections: List[UISectionPlan] = field(default_factory=list)
    actions: List[Any] = field(default_factory=list)
    action_plans: List[UIActionPlan] = field(default_factory=list)
    fields: List[UIField] = field(default_factory=list)
    relationships: List[UIRelationship] = field(default_factory=list)
    subforms: List[UISubform] = field(default_factory=list)
    responsive: ResponsiveSpec = field(default_factory=ResponsiveSpec)
    information_hierarchy: Any = None
    record_source: Optional[str] = None
    is_bound: bool = False
    confidence: float = 1.0
    decision_mode: str = "deterministic"

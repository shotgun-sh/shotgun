"""Widget utilities and coordinators for TUI."""

from shotgun.tui.widgets.autopilot_startup_widget import AutopilotStartupWidget
from shotgun.tui.widgets.plan_panel import PlanPanelWidget
from shotgun.tui.widgets.stage_approval_widget import StageApprovalWidget
from shotgun.tui.widgets.widget_coordinator import WidgetCoordinator

__all__ = [
    "AutopilotStartupWidget",
    "PlanPanelWidget",
    "StageApprovalWidget",
    "WidgetCoordinator",
]

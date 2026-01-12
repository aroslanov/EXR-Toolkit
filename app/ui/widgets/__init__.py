"""UI widgets module."""
from .attribute_editor import AttributeEditor, AddAttributeDialog
from .processing_widget import ProcessingWidget
from .filter_browser import FilterBrowser
from .pipeline_list import PipelineList
from .parameter_editor import ParameterEditor

__all__ = [
    "AttributeEditor",
    "AddAttributeDialog",
    "ProcessingWidget",
    "FilterBrowser",
    "PipelineList",
    "ParameterEditor",
]

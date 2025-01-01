# workflows package

import pathlib
import importlib

# Module constants
DEFAULT_WORKFLOW_NAME = "sd_1_5"  # Default workflow

# Module memory
_workflows = {}  # Dictionary to store all workflow modules
_available_workflows = ""  # Description of available workflows

# Load all workflows on module import
def _load_workflows():
    global _workflows, _available_workflows
    print("Loading workflows")
    package_name = __package__ or pathlib.Path(__file__).parent.name
    for f in pathlib.Path(__file__).parent.glob("*.py"):
        if f.name != "__init__.py" and f.name != "templates":
            module_name = f.stem
            try:
                print(f"Importing workflow {module_name} from {package_name}")
                module = importlib.import_module(f".{module_name}", package=package_name)
                _workflows[module_name] = module
            except ImportError as e:
                print(f"WARNING: Failed to import {module_name}: {str(e)}")
    _available_workflows = ", ".join(_workflows.keys())

# Load workflows when this module is imported
_load_workflows()

# Get a workflow by name
def get_workflow(workflow_name):
    global _workflows, _available_workflows
    if workflow_name not in _workflows:
        raise ValueError(f"ERROR: Workflow '{workflow_name}' not found. Available workflows: {_available_workflows}")
    return _workflows[workflow_name]

# Get the default workflow
def get_default_workflow():
    return get_workflow(DEFAULT_WORKFLOW_NAME)

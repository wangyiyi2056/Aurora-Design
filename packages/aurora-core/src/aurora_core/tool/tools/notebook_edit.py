"""NotebookEditTool — edit Jupyter notebook cells."""
from typing import Any, Dict, Optional

from aurora_core.tool.base import (
    ToolResult,
    ToolUseContext,
    ValidationResult,
    build_tool,
)

TOOL_NAME = "NotebookEdit"
TOOL_DESCRIPTION = """Edit a Jupyter notebook (.ipynb) file.
Supports replacing, inserting, or deleting cells by cell index.
Also allows changing cell types (code/markdown)."""

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "notebook_path": {
            "type": "string",
            "description": "Path to the .ipynb file.",
        },
        "cell_id": {
            "type": "string",
            "description": "ID of the cell to edit/replace.",
        },
        "new_source": {
            "type": "string",
            "description": "New source content for the cell.",
        },
        "cell_type": {
            "type": "string",
            "enum": ["code", "markdown"],
            "description": "Cell type (required when inserting).",
        },
        "edit_mode": {
            "type": "string",
            "enum": ["replace", "insert", "delete"],
            "description": "Edit operation (default: replace).",
        },
    },
    "required": ["notebook_path", "new_source"],
}


async def notebook_edit_call(
    args: Dict[str, Any],
    context: ToolUseContext,
    on_progress=None,
) -> ToolResult[str]:
    """Edit a Jupyter notebook."""
    import json
    from pathlib import Path

    notebook_path = args.get("notebook_path", "")
    cell_id = args.get("cell_id")
    new_source = args.get("new_source", "")
    cell_type = args.get("cell_type")
    edit_mode = args.get("edit_mode", "replace")

    path = Path(notebook_path)
    if not path.exists():
        return ToolResult(data=f"Error: Notebook not found: {path}")

    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return ToolResult(data=f"Error: Invalid notebook: {e}")

    cells = notebook.get("cells", [])
    target_idx = None

    if cell_id:
        for i, cell in enumerate(cells):
            if cell.get("id") == cell_id:
                target_idx = i
                break

    if target_idx is None:
        # Default to last cell for insert, first cell for edit
        if edit_mode == "insert":
            target_idx = 0
        else:
            target_idx = 0 if not cells else 0

    if edit_mode == "delete":
        if not cells:
            return ToolResult(data="Error: No cells to delete")
        removed = cells.pop(target_idx)
        notebook["cells"] = cells
        path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
        return ToolResult(data=f"Deleted cell {target_idx} (type: {removed.get('cell_type', 'unknown')})")

    if edit_mode == "insert":
        new_cell = {
            "cell_type": cell_type or "code",
            "metadata": {},
            "source": new_source.split("\n"),
        }
        cells.insert(target_idx, new_cell)
    else:
        if target_idx >= len(cells):
            return ToolResult(data=f"Error: Cell index {target_idx} out of range")
        cells[target_idx]["source"] = new_source.split("\n")
        if cell_type:
            cells[target_idx]["cell_type"] = cell_type
        if target_idx == 0:
            cells[0] = cells[target_idx]
        else:
            cells[target_idx] = cells[target_idx]

    notebook["cells"] = cells
    path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
    return ToolResult(data=f"Notebook cell {edit_mode}d at index {target_idx}")


async def notebook_edit_validate(
    args: Dict[str, Any],
    context: ToolUseContext,
) -> ValidationResult:
    if not args.get("notebook_path"):
        return ValidationResult.fail("notebook_path is required")
    if not args.get("new_source"):
        return ValidationResult.fail("new_source is required")
    return ValidationResult.ok()


NotebookEditTool = build_tool(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_schema=INPUT_SCHEMA,
    call_fn=notebook_edit_call,
    validate_input_fn=notebook_edit_validate,
    is_concurrency_safe_fn=lambda _: False,
    is_read_only_fn=lambda _: False,
    is_destructive_fn=lambda _: True,
    get_path_fn=lambda args: args.get("notebook_path"),
)

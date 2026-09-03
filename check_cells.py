import json

with open("notebooks/03_feature_engineering.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

for i, cell in enumerate(nb["cells"]):
    source = "".join(cell["source"])
    if cell["cell_type"] == "code":
        try:
            compile(source, f"cell_{i}", "exec")
        except SyntaxError as e:
            print(f"Syntax error in code cell index {i} (1-based cell {i+1}):")
            print(f"  Line {e.lineno}: {e.msg}")
            print(f"  Text: {e.text}")
    print(f"Cell {i} (type: {cell['cell_type']}) has {len(cell['source'])} lines. Starts with: {source[:60]!r}")

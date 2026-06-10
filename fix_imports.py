import os
import glob
import re

base_dir = "/Users/wyl/Desktop/Aurora-Design/frontend/src/features/construct/knowledge"

def replace_in_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Generic replacements for graph components
    content = re.sub(r"@/components/graph/", r"@/features/construct/knowledge/components/graph/", content)
    content = re.sub(r"@/stores/", r"@/features/construct/knowledge/stores/", content)
    content = re.sub(r"@/hooks/useLightragGraph", r"@/features/construct/knowledge/hooks/useLightragGraph", content)
    content = re.sub(r"@/hooks/useRandomGraph", r"@/features/construct/knowledge/hooks/useRandomGraph", content)
    content = re.sub(r"@/lib/constants", r"@/features/construct/knowledge/lib/constants", content)
    content = re.sub(r"@/utils/graphColor", r"@/features/construct/knowledge/utils/graphColor", content)
    
    # Fix UI component capitalization (LightRAG uses Button, Checkbox. Aurora uses button, checkbox)
    content = re.sub(r"@/components/ui/Button", r"@/components/ui/button", content)
    content = re.sub(r"@/components/ui/Checkbox", r"@/components/ui/checkbox", content)
    content = re.sub(r"@/components/ui/Input", r"@/components/ui/input", content)
    content = re.sub(r"@/components/ui/Separator", r"@/components/ui/separator", content)
    content = re.sub(r"@/components/ui/Popover", r"@/components/ui/popover", content)
    content = re.sub(r"@/components/ui/Dialog", r"@/components/ui/dialog", content)
    content = re.sub(r"@/components/ui/ScrollArea", r"@/components/ui/scroll-area", content)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

files = []
files.extend(glob.glob(f"{base_dir}/**/*.ts", recursive=True))
files.extend(glob.glob(f"{base_dir}/**/*.tsx", recursive=True))

for file in files:
    if "fix_imports" not in file:
        replace_in_file(file)

print("Imports fixed.")

import json
import re

def update_file(path, new_keys):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # find the last key of graphPanel.nodeTypes
    match = re.search(r"(\s+)'graphPanel\.nodeTypes\.unknown':.*?,?\n", content)
    if not match:
        print("Could not find unknown key in", path)
        return
        
    indent = match.group(1)
    insert_pos = match.end()
    
    insert_str = ""
    for k, v in new_keys.items():
        if f"'graphPanel.nodeTypes.{k}'" not in content:
            insert_str += f"{indent}'graphPanel.nodeTypes.{k}': '{v}',\n"
        
    new_content = content[:insert_pos] + insert_str + content[insert_pos:]
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Updated", path)

zh_keys = {
    'creature': '生物',
    'method': '方法',
    'content': '内容',
    'data': '数据',
    'artifact': '人造物',
    'naturalobject': '自然物'
}

en_keys = {
    'creature': 'Creature',
    'method': 'Method',
    'content': 'Content',
    'data': 'Data',
    'artifact': 'Artifact',
    'naturalobject': 'Natural Object'
}

update_file('/Users/wyl/Desktop/Aurora-Design/frontend/src/i18n/locales/zh-CN.ts', zh_keys)
update_file('/Users/wyl/Desktop/Aurora-Design/frontend/src/i18n/locales/en.ts', en_keys)

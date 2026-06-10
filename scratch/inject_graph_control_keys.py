import os
import re

graph_keys = {
    # 悬浮按钮 tooltips
    'graphPanel.sideBar.zoomControl.rotateCw': {
        'zh-CN': '顺时针旋转',
        'zh-TW': '顺时針旋轉',
        'en': 'Rotate Clockwise'
    },
    'graphPanel.sideBar.zoomControl.rotateCcw': {
        'zh-CN': '逆时针旋转',
        'zh-TW': '逆時針旋轉',
        'en': 'Rotate Counter-Clockwise'
    },
    'graphPanel.sideBar.zoomControl.resetZoom': {
        'zh-CN': '重置视图',
        'zh-TW': '重置檢視',
        'en': 'Reset View'
    },
    'graphPanel.sideBar.zoomControl.zoomIn': {
        'zh-CN': '放大',
        'zh-TW': '放大',
        'en': 'Zoom In'
    },
    'graphPanel.sideBar.zoomControl.zoomOut': {
        'zh-CN': '缩小',
        'zh-TW': '縮小',
        'en': 'Zoom Out'
    },
    'graphPanel.sideBar.fullScreenControl.toggle': {
        'zh-CN': '切换全屏',
        'zh-TW': '切換全螢幕',
        'en': 'Toggle Fullscreen'
    },
    'graphPanel.sideBar.layoutsControl.select': {
        'zh-CN': '选择布局',
        'zh-TW': '選擇佈局',
        'en': 'Select Layout'
    },
    'graphPanel.sideBar.layoutsControl.toggleAnimation': {
        'zh-CN': '运行布局动画',
        'zh-TW': '運行佈局動畫',
        'en': 'Run Layout Animation'
    },
    # 布局名称翻译
    'graphPanel.sideBar.layoutsControl.layouts.Circular': {
        'zh-CN': '环形布局',
        'zh-TW': '環形佈局',
        'en': 'Circular'
    },
    'graphPanel.sideBar.layoutsControl.layouts.Circlepack': {
        'zh-CN': '圆包布局',
        'zh-TW': '圓包佈局',
        'en': 'Circlepack'
    },
    'graphPanel.sideBar.layoutsControl.layouts.Random': {
        'zh-CN': '随机布局',
        'zh-TW': '隨機佈局',
        'en': 'Random'
    },
    'graphPanel.sideBar.layoutsControl.layouts.Noverlaps': {
        'zh-CN': '防重叠布局',
        'zh-TW': '防重疊佈局',
        'en': 'Noverlaps'
    },
    'graphPanel.sideBar.layoutsControl.layouts.Force Directed': {
        'zh-CN': '力导向布局',
        'zh-TW': '力導向佈局',
        'en': 'Force Directed'
    },
    'graphPanel.sideBar.layoutsControl.layouts.Force Atlas': {
        'zh-CN': '力导向 Atlas 布局',
        'zh-TW': '力導向 Atlas 佈局',
        'en': 'Force Atlas'
    }
}

i18n_dir = '/Users/wyl/Desktop/Aurora-Design/frontend/src/i18n'
types_path = os.path.join(i18n_dir, 'types.ts')
locales_dir = os.path.join(i18n_dir, 'locales')

# 1. Update types.ts
print(f"Reading {types_path}...")
with open(types_path, 'r', encoding='utf-8') as f:
    types_content = f.read()

dict_start_match = re.search(r'export\s+interface\s+Dict\s*\{', types_content)
if not dict_start_match:
    raise ValueError("Could not find 'export interface Dict' in types.ts")

insert_pos = dict_start_match.end()
new_types_declarations = "\n"
for key in sorted(graph_keys.keys()):
    if f"'{key}'" not in types_content:
        new_types_declarations += f"  '{key}': string;\n"

if new_types_declarations.strip():
    types_content = types_content[:insert_pos] + new_types_declarations + types_content[insert_pos:]
    print("Writing updated types.ts...")
    with open(types_path, 'w', encoding='utf-8') as f:
        f.write(types_content)
else:
    print("All keys already present in types.ts.")

# 2. Update locales
for filename in os.listdir(locales_dir):
    if not filename.endswith('.ts'):
        continue
    
    locale_name = filename[:-3]
    file_path = os.path.join(locales_dir, filename)
    print(f"Processing: {filename}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    last_brace_match = list(re.finditer(r'\};?\s*$', content))
    if not last_brace_match:
        continue
        
    last_brace = last_brace_match[-1]
    brace_start = last_brace.start()
    
    new_translations = ""
    for key, translations in sorted(graph_keys.items()):
        if f"'{key}':" in content:
            continue
        val = translations.get(locale_name, translations.get('en'))
        val_escaped = val.replace("'", "\\'")
        new_translations += f"  '{key}': '{val_escaped}',\n"
        
    if new_translations:
        content = content[:brace_start] + new_translations + content[brace_start:]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Injected new keys into {filename}.")

print("Completed incremental inject!")

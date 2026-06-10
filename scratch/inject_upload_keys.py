import os
import re

upload_keys = {
    'knowledge.v2.doc.uploadDesc': {
        'zh-CN': '拖拽文件或点击选择，上传后台自动处理，无需等待。',
        'zh-TW': '拖拽檔案或點擊選擇，上傳後台自動處理，無需等待。',
        'en': 'Drag & drop files or click to choose. The backend processes automatically.'
    },
    'knowledge.v2.doc.releaseToUpload': {
        'zh-CN': '松开以上传文件',
        'zh-TW': '鬆開以上傳檔案',
        'en': 'Release to upload files'
    },
    'knowledge.v2.doc.dragFilesHere': {
        'zh-CN': '拖拽文件到此处',
        'zh-TW': '拖拽檔案至此處',
        'en': 'Drag files here'
    },
    'knowledge.v2.doc.clickOrDragHint': {
        'zh-CN': '或点击选择文件 · 支持多文件 · 上传即处理',
        'zh-TW': '或點擊選擇檔案 · 支援多檔案 · 上傳即處理',
        'en': 'or click to select files · multiple files supported · upload and process'
    },
    'knowledge.v2.doc.continueAdd': {
        'zh-CN': '点击或拖拽继续添加文件',
        'zh-TW': '點擊或拖拽繼續新增檔案',
        'en': 'Click or drag to continue adding files'
    },
    'knowledge.v2.doc.uploadSuccessClose': {
        'zh-CN': '个文件上传完成，后台正在分析处理，窗口即将关闭…',
        'zh-TW': '個檔案上傳完成，後台正在分析處理，視窗即將關閉…',
        'en': 'files uploaded successfully. Processing in background, window closing...'
    },
    'knowledge.v2.doc.uploadFailedRetry': {
        'zh-CN': '个上传失败，请重试或移除后关闭。',
        'zh-TW': '個上傳失敗，請重試或移除後關閉。',
        'en': 'failed to upload, please retry or remove and close.'
    },
    'knowledge.v2.doc.submittedProcessing': {
        'zh-CN': '已提交，后台处理中',
        'zh-TW': '已提交，後台處理中',
        'en': 'Submitted, processing in background'
    },
    'knowledge.v2.doc.uploadSuccessText': {
        'zh-CN': '个成功。',
        'zh-TW': '個成功。',
        'en': 'succeeded.'
    },
    'knowledge.v2.doc.retry': {
        'zh-CN': '重试',
        'zh-TW': '重試',
        'en': 'Retry'
    },
    'knowledge.v2.doc.remove': {
        'zh-CN': '移除',
        'zh-TW': '移除',
        'en': 'Remove'
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
for key in sorted(upload_keys.keys()):
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
    for key, translations in sorted(upload_keys.items()):
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

import os
import re

# Defined new translation keys with their specific translations
# Other locales not explicitly defined here will fallback to the 'en' translation.
keys_to_add = {
    # 通用
    'common.saving': {
        'zh-CN': '保存中…',
        'zh-TW': '保存中…',
        'en': 'Saving...'
    },
    # 知识库文档
    'knowledge.v2.doc.all': {
        'zh-CN': '全部',
        'zh-TW': '全部',
        'en': 'All'
    },
    'knowledge.v2.doc.upload': {
        'zh-CN': '上传文件',
        'zh-TW': '上傳檔案',
        'en': 'Upload'
    },
    'knowledge.v2.doc.insertText': {
        'zh-CN': '插入文本',
        'zh-TW': '插入文字',
        'en': 'Insert Text'
    },
    'knowledge.v2.doc.dropFiles': {
        'zh-CN': '松开鼠标以上传文件',
        'zh-TW': '松開滑鼠以上傳檔案',
        'en': 'Drop files to upload'
    },
    'knowledge.v2.doc.noDocs': {
        'zh-CN': '暂无文档',
        'zh-TW': '暫無文件',
        'en': 'No documents found'
    },
    'knowledge.v2.doc.page': {
        'zh-CN': '页',
        'zh-TW': '頁',
        'en': 'Page'
    },
    'knowledge.v2.doc.perPage': {
        'zh-CN': '条/页',
        'zh-TW': '條/頁',
        'en': '/ page'
    },
    'knowledge.v2.doc.insertTextTitle': {
        'zh-CN': '插入文本文件',
        'zh-TW': '插入文字文件',
        'en': 'Insert Text Document'
    },
    'knowledge.v2.doc.insertTextDesc': {
        'zh-CN': '粘贴或输入文本内容以添加到当前知识库。',
        'zh-TW': '貼上或輸入文字內容以新增到目前知識庫。',
        'en': 'Paste or type text content to add to this knowledge base.'
    },
    'knowledge.v2.doc.insertTextPlaceholder': {
        'zh-CN': '请输入文本内容…',
        'zh-TW': '請輸入文字內容…',
        'en': 'Enter text content...'
    },
    'knowledge.v2.doc.docDetails': {
        'zh-CN': '文档详情',
        'zh-TW': '文件詳情',
        'en': 'Document Details'
    },
    'knowledge.v2.doc.docDetailsDesc': {
        'zh-CN': '关于该文档及其处理状态的详细信息。',
        'zh-TW': '關於該文件及其處理狀態的詳細資訊。',
        'en': 'Detailed information about this document and its processing status.'
    },
    'knowledge.v2.doc.processingError': {
        'zh-CN': '处理错误',
        'zh-TW': '處理錯誤',
        'en': 'Processing Error'
    },
    'knowledge.v2.doc.noErrorMsg': {
        'zh-CN': '未记录任何错误信息。',
        'zh-TW': '未記錄任何錯誤資訊。',
        'en': 'No error message was recorded.'
    },
    'knowledge.v2.doc.errorStage': {
        'zh-CN': '错误发生阶段：',
        'zh-TW': '錯誤發生階段：',
        'en': 'Error occurred during '
    },
    'knowledge.v2.doc.reprocess': {
        'zh-CN': '重新处理',
        'zh-TW': '重新處理',
        'en': 'Reprocess'
    },
    # 知识库设置
    'knowledge.v2.settings.kbInfo': {
        'zh-CN': '知识库信息',
        'zh-TW': '知識庫資訊',
        'en': 'Knowledge Base Info'
    },
    'knowledge.v2.settings.name': {
        'zh-CN': '名称',
        'zh-TW': '名稱',
        'en': 'Name'
    },
    'knowledge.v2.settings.documents': {
        'zh-CN': '文档数',
        'zh-TW': '文件數',
        'en': 'Documents'
    },
    'knowledge.v2.settings.chunks': {
        'zh-CN': '分块数',
        'zh-TW': '分塊數',
        'en': 'Chunks'
    },
    'knowledge.v2.settings.strategy': {
        'zh-CN': '分块策略',
        'zh-TW': '分塊策略',
        'en': 'Chunk Strategy'
    },
    'knowledge.v2.settings.collection': {
        'zh-CN': '集合名称',
        'zh-TW': '集合名稱',
        'en': 'Collection'
    },
    'knowledge.v2.settings.chunkSize': {
        'zh-CN': '分块大小',
        'zh-TW': '分塊大小',
        'en': 'Chunk Size'
    },
    'knowledge.v2.settings.saveConfig': {
        'zh-CN': '保存配置',
        'zh-TW': '儲存配置',
        'en': 'Save Configuration'
    },
    'knowledge.v2.settings.cacheManagement': {
        'zh-CN': '缓存管理',
        'zh-TW': '快取管理',
        'en': 'Cache Management'
    },
    'knowledge.v2.settings.llmCache': {
        'zh-CN': 'LLM 响应缓存',
        'zh-TW': 'LLM 回應快取',
        'en': 'LLM Response Cache'
    },
    'knowledge.v2.settings.llmCacheDesc': {
        'zh-CN': '清除缓存的 LLM 响应以强制重新生成。',
        'zh-TW': '清除快取的 LLM 回應以強制重新產生。',
        'en': 'Clear cached LLM responses to force regeneration'
    },
    'knowledge.v2.settings.clearLlmCache': {
        'zh-CN': '清除 LLM 缓存',
        'zh-TW': '清除 LLM 快取',
        'en': 'Clear LLM Cache'
    },
    'knowledge.v2.settings.queryCache': {
        'zh-CN': '查询缓存',
        'zh-TW': '查詢快取',
        'en': 'Query Cache'
    },
    'knowledge.v2.settings.queryCacheDesc': {
        'zh-CN': '清除缓存的查询结果。',
        'zh-TW': '清除快取的查詢結果。',
        'en': 'Clear cached query results'
    },
    'knowledge.v2.settings.clearQueryCache': {
        'zh-CN': '清除查询缓存',
        'zh-TW': '清除查詢快取',
        'en': 'Clear Query Cache'
    },
    'knowledge.v2.settings.dangerZone': {
        'zh-CN': '危险区域',
        'zh-TW': '危險區域',
        'en': 'Danger Zone'
    },
    'knowledge.v2.settings.deleteAll': {
        'zh-CN': '删除全部文档',
        'zh-TW': '刪除全部文件',
        'en': 'Delete All Documents'
    },
    'knowledge.v2.settings.deleteAllDesc': {
        'zh-CN': '删除当前知识库中的所有文档。',
        'zh-TW': '刪除目前知識庫中的所有文件。',
        'en': 'Remove all documents from this knowledge base'
    },
    'knowledge.v2.settings.deleteKb': {
        'zh-CN': '删除知识库',
        'zh-TW': '刪除知識庫',
        'en': 'Delete Knowledge Base'
    },
    'knowledge.v2.settings.deleteKbDesc': {
        'zh-CN': '永久删除此知识库及其所有数据。',
        'zh-TW': '永久刪除此知識庫及其所有資料。',
        'en': 'Permanently delete this knowledge base and all its data'
    },
    'knowledge.v2.settings.clearLlmCacheTitle': {
        'zh-CN': '清除 LLM 缓存',
        'zh-TW': '清除 LLM 快取',
        'en': 'Clear LLM Cache'
    },
    'knowledge.v2.settings.clearLlmCacheConfirm': {
        'zh-CN': '这将清除所有缓存的 LLM 响应。未来的查询将重新生成响应。此操作无法撤销。',
        'zh-TW': '這將清除所有快取的 LLM 回應。未來的查詢將重新產生回應。此動作無法撤銷。',
        'en': 'This will clear all cached LLM responses. Future queries will regenerate responses. This action cannot be undone.'
    },
    # 属性面板字段名映射
    'graphPanel.propertiesView.node.propertyNames.description': {
        'zh-CN': '描述',
        'zh-TW': '描述',
        'en': 'Description'
    },
    'graphPanel.propertiesView.node.propertyNames.entity_id': {
        'zh-CN': '实体 ID',
        'zh-TW': '實體 ID',
        'en': 'Entity ID'
    },
    'graphPanel.propertiesView.node.propertyNames.entity_type': {
        'zh-CN': '实体类型',
        'zh-TW': '實體類型',
        'en': 'Entity Type'
    },
    'graphPanel.propertiesView.node.propertyNames.keywords': {
        'zh-CN': '关键词',
        'zh-TW': '關鍵詞',
        'en': 'Keywords'
    },
    'graphPanel.propertiesView.node.propertyNames.source_id': {
        'zh-CN': '源 ID',
        'zh-TW': '源 ID',
        'en': 'Source ID'
    },
    'graphPanel.propertiesView.node.propertyNames.Neighbour': {
        'zh-CN': '邻居',
        'zh-TW': '鄰居',
        'en': 'Neighbour'
    },
    # 图例节点类型翻译
    'graphPanel.nodeTypes.person': {
        'zh-CN': '人物',
        'zh-TW': '人物',
        'en': 'Person'
    },
    'graphPanel.nodeTypes.organization': {
        'zh-CN': '组织',
        'zh-TW': '組織',
        'en': 'Organization'
    },
    'graphPanel.nodeTypes.event': {
        'zh-CN': '事件',
        'zh-TW': '事件',
        'en': 'Event'
    },
    'graphPanel.nodeTypes.location': {
        'zh-CN': '地点',
        'zh-TW': '地點',
        'en': 'Location'
    },
    'graphPanel.nodeTypes.concept': {
        'zh-CN': '概念',
        'zh-TW': '概念',
        'en': 'Concept'
    },
    'graphPanel.nodeTypes.document': {
        'zh-CN': '文档',
        'zh-TW': '文件',
        'en': 'Document'
    },
    'graphPanel.nodeTypes.chunk': {
        'zh-CN': '文本块',
        'zh-TW': '文字塊',
        'en': 'Chunk'
    },
    'graphPanel.nodeTypes.unknown': {
        'zh-CN': '未知',
        'zh-TW': '未知',
        'en': 'Unknown'
    }
}

i18n_dir = '/Users/wyl/Desktop/Aurora-Design/frontend/src/i18n'
types_path = os.path.join(i18n_dir, 'types.ts')
locales_dir = os.path.join(i18n_dir, 'locales')

# 1. Update types.ts
print(f"Reading {types_path}...")
with open(types_path, 'r', encoding='utf-8') as f:
    types_content = f.read()

# Find the end of export interface Dict
# We will inject right after export interface Dict {
dict_start_match = re.search(r'export\s+interface\s+Dict\s*\{', types_content)
if not dict_start_match:
    raise ValueError("Could not find 'export interface Dict' in types.ts")

insert_pos = dict_start_match.end()
new_types_declarations = "\n"
for key in sorted(keys_to_add.keys()):
    # Only add if not already present
    if f"'{key}'" not in types_content:
        new_types_declarations += f"  '{key}': string;\n"

if new_types_declarations.strip():
    types_content = types_content[:insert_pos] + new_types_declarations + types_content[insert_pos:]
    print("Writing updated types.ts...")
    with open(types_path, 'w', encoding='utf-8') as f:
        f.write(types_content)
else:
    print("All keys already present in types.ts.")

# 2. Update each of the 16 locales files
for filename in os.listdir(locales_dir):
    if not filename.endswith('.ts'):
        continue
    
    locale_name = filename[:-3] # e.g., 'en', 'zh-CN', 'zh-TW', 'fa' ...
    file_path = os.path.join(locales_dir, filename)
    print(f"Processing locale file: {filename} (locale: {locale_name})...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We will find the ending }; of the export const xx: Dict = { ... };
    # To be extremely safe, we look for the last }; in the file
    last_brace_match = list(re.finditer(r'\};?\s*$', content))
    if not last_brace_match:
        print(f"Warning: Could not find closing brace }}; in {filename}, skipping.")
        continue
    
    last_brace = last_brace_match[-1]
    brace_start = last_brace.start()
    
    new_translations = ""
    for key, translations in sorted(keys_to_add.items()):
        if f"'{key}':" in content:
            print(f"  Key '{key}' already exists in {filename}, skipping.")
            continue
            
        val = translations.get(locale_name, translations.get('en'))
        # Escape single quotes in value
        val_escaped = val.replace("'", "\\'")
        new_translations += f"  '{key}': '{val_escaped}',\n"
        
    if new_translations:
        content = content[:brace_start] + new_translations + content[brace_start:]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Successfully injected {len(keys_to_add)} keys into {filename}.")
    else:
        print(f"  No new keys needed to be added to {filename}.")

print("Completed successfully!")

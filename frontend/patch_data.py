import re
with open('/Users/wyl/Desktop/Aurora-Design/frontend/src/features/construct/knowledge/hooks/useLightragGraph.tsx', 'r') as f:
    content = f.read()

mapping_code = """
  if (rawData) {
    if (!rawData.nodes) rawData.nodes = [];
    if (!rawData.edges) rawData.edges = [];
    rawData.nodes = rawData.nodes.map((n: any) => ({
      ...n,
      id: n.id || n.entity_name || n.name,
      labels: n.labels || (n.entity_type ? [n.entity_type] : ['Entity']),
      properties: n.properties || n
    }));
    rawData.edges = rawData.edges.map((e: any, idx: number) => ({
      ...e,
      id: e.id || `edge-${idx}`,
      source: e.source_id || e.source,
      target: e.target_id || e.target,
      label: e.label || e.description || e.keywords || 'RELATED',
      properties: e.properties || e
    }));
"""

content = content.replace("  if (rawData) {", mapping_code)
with open('/Users/wyl/Desktop/Aurora-Design/frontend/src/features/construct/knowledge/hooks/useLightragGraph.tsx', 'w') as f:
    f.write(content)


import { useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Wrench, Code, CheckCircle, Palette, EyeOff, Clock, Search } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Tag } from "@/components/ui/tag"
import { Descriptions, DescriptionItem } from "@/components/ui/descriptions"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import { useSkills } from "@/features/construct/skills/hooks/use-skills"
import {
  listDesignSkills,
  updateDesignSkillManagement,
  type DesignSkillSummary,
} from "@/services/design-skills"

interface SkillInfo {
  name: string
  description: string
  description_cn: string
  parameters: Record<string, unknown>
  is_builtin: boolean
}

type SkillTab = "tools" | "design-ready" | "design-pending" | "design-hidden" | "design-all"

export default function SkillsPage() {
  const { t } = useTranslation("construct")
  const queryClient = useQueryClient()
  const { data, isLoading } = useSkills()
  const designSkillsQuery = useQuery({
    queryKey: ["design-skills", "management"],
    queryFn: () => listDesignSkills({ includeHidden: true }),
  })
  const skills = data?.skills || []
  const designSkills = designSkillsQuery.data || []
  const [selectedSkill, setSelectedSkill] = useState<SkillInfo | null>(null)
  const [selectedDesignSkill, setSelectedDesignSkill] = useState<DesignSkillSummary | null>(null)
  const [activeTab, setActiveTab] = useState<SkillTab>("tools")
  const [query, setQuery] = useState("")
  const managementMutation = useMutation({
    mutationFn: ({ id, hidden }: { id: string; hidden: boolean }) =>
      updateDesignSkillManagement(id, { hidden }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["design-skills"] })
    },
  })

  // 按类别分组技能（避免重复，每个技能只属于一个类别）
  const categorizedSkills = (() => {
    const data: SkillInfo[] = []
    const sql: SkillInfo[] = []
    const analysis: SkillInfo[] = []
    const other: SkillInfo[] = []

    for (const s of skills) {
      if (['sql_execute', 'sql_chart', 'sql_dashboard'].includes(s.name) || s.name.startsWith('sql_')) {
        sql.push(s)
      } else if (['python_analysis', 'anomaly_detection', 'volatility_analysis', 'metric_info'].includes(s.name)) {
        analysis.push(s)
      } else if (['csv_analysis', 'excel2table', 'database_schema', 'database_summary'].includes(s.name)) {
        data.push(s)
      } else if (['data_analysis'].includes(s.name)) {
        analysis.push(s)
      } else if (['web_search', 'indicator', 'report_generation'].includes(s.name)) {
        other.push(s)
      } else {
        other.push(s)
      }
    }

    return { data, sql, analysis, other }
  })()

  const categoryLabels = {
    data: t("skill.category.data") || "数据处理",
    sql: t("skill.category.sql") || "SQL查询",
    analysis: t("skill.category.analysis") || "数据分析",
    other: t("skill.category.other") || "其他工具",
  }

  const visibleDesignSkills = designSkills.filter((skill) => !skill.hidden && skill.status !== "adapter-pending")
  const pendingDesignSkills = designSkills.filter((skill) => skill.status === "adapter-pending")
  const hiddenDesignSkills = designSkills.filter((skill) => skill.hidden)
  const filteredDesignSkills = useMemo(() => {
    const source =
      activeTab === "design-ready"
        ? visibleDesignSkills
        : activeTab === "design-pending"
          ? pendingDesignSkills
          : activeTab === "design-hidden"
            ? hiddenDesignSkills
            : activeTab === "design-all"
              ? designSkills
              : []
    const q = query.trim().toLowerCase()
    if (!q) return source
    return source.filter((skill) =>
      [skill.id, skill.name, skill.description, skill.mode, skill.surface, skill.scenario, skill.adapterKind]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(q)),
    )
  }, [activeTab, designSkills, hiddenDesignSkills, pendingDesignSkills, query, visibleDesignSkills])

  const tabs: Array<{ key: SkillTab; label: string; count: number }> = [
    { key: "tools", label: "工具技能", count: skills.length },
    { key: "design-ready", label: "可用设计", count: visibleDesignSkills.length },
    { key: "design-pending", label: "待适配", count: pendingDesignSkills.length },
    { key: "design-hidden", label: "已隐藏", count: hiddenDesignSkills.length },
    { key: "design-all", label: "全部设计", count: designSkills.length },
  ]

  const renderSkillCard = (skill: SkillInfo) => (
    <div
      key={skill.name}
      className="bg-card rounded-lg border border-border p-4 hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => setSelectedSkill(skill)}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Wrench className="h-4 w-4 text-primary" />
          <span className="font-semibold text-foreground">
            {skill.name}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {skill.is_builtin && (
            <Tag variant="default">{t("skill.builtin") || "内置"}</Tag>
          )}
          <Tag variant="success" className="flex items-center gap-1">
            <CheckCircle className="h-3 w-3" /> {t("skill.available") || "可用"}
          </Tag>
        </div>
      </div>

      <div className="text-muted-foreground text-sm mb-2">
        {skill.description_cn || skill.description}
      </div>

      <div className="text-muted-foreground/70 text-xs line-clamp-2">
        {skill.description}
      </div>

      <div className="mt-3 flex items-center gap-1 text-xs text-muted-foreground">
        <Code className="h-3 w-3" />
        <span>
          {(() => {
            const params = skill.parameters as { properties?: Record<string, unknown> }
            return params?.properties ? Object.keys(params.properties).length : 0
          })()} 个参数
        </span>
      </div>
    </div>
  )

  const renderDesignSkillCard = (skill: DesignSkillSummary) => {
    const pending = skill.status === "adapter-pending"
    return (
      <div
        key={skill.id}
        className="bg-card rounded-lg border border-border p-4 hover:shadow-md transition-shadow cursor-pointer"
        onClick={() => setSelectedDesignSkill(skill)}
      >
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="min-w-0 flex items-center gap-2">
            {pending ? (
              <Clock className="h-4 w-4 text-yellow-400 shrink-0" />
            ) : skill.hidden ? (
              <EyeOff className="h-4 w-4 text-muted-foreground shrink-0" />
            ) : (
              <Palette className="h-4 w-4 text-primary shrink-0" />
            )}
            <span className="font-semibold text-foreground truncate">{skill.name}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {skill.hidden && <Tag variant="secondary">隐藏</Tag>}
            {pending ? (
              <Tag variant="warning">待适配</Tag>
            ) : (
              <Tag variant="success">可用</Tag>
            )}
          </div>
        </div>
        <div className="text-muted-foreground text-sm mb-3 line-clamp-2">
          {skill.description || "暂无描述"}
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Tag variant="outline">{skill.source}</Tag>
          {skill.mode && <Tag variant="info">{skill.mode}</Tag>}
          {skill.surface && <Tag variant="outline">{skill.surface}</Tag>}
          {skill.adapterKind && <Tag variant="warning">{skill.adapterKind}</Tag>}
          {skill.hasAssets && <Tag variant="secondary">assets</Tag>}
          {skill.hasReferences && <Tag variant="secondary">references</Tag>}
        </div>
      </div>
    )
  }

  const toggleSelectedDesignVisibility = async () => {
    if (!selectedDesignSkill) return
    const updated = await managementMutation.mutateAsync({
      id: selectedDesignSkill.id,
      hidden: !selectedDesignSkill.hidden,
    })
    setSelectedDesignSkill(updated)
  }

  return (
    <ConstructShell>
      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">
            {t("skill.title") || "技能管理"}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t("skill.description") || `平台已集成 ${skills.length} 个工具技能和 ${designSkills.length} 个设计技能`}
          </p>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/20">
            <div className="text-blue-400 text-sm">数据处理</div>
            <div className="text-2xl font-bold text-blue-300">
              {categorizedSkills.data.length}
            </div>
          </div>
          <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
            <div className="text-green-400 text-sm">SQL查询</div>
            <div className="text-2xl font-bold text-green-300">
              {categorizedSkills.sql.length}
            </div>
          </div>
          <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
            <div className="text-purple-400 text-sm">数据分析</div>
            <div className="text-2xl font-bold text-purple-300">
              {categorizedSkills.analysis.length}
            </div>
          </div>
          <div className="bg-orange-500/10 rounded-lg p-4 border border-orange-500/20">
            <div className="text-orange-400 text-sm">设计技能</div>
            <div className="text-2xl font-bold text-orange-300">
              {designSkills.length}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 mb-4">
          {tabs.map((tab) => (
            <Button
              key={tab.key}
              type="button"
              variant={activeTab === tab.key ? "default" : "outline"}
              size="sm"
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
              <span className="text-xs opacity-80">{tab.count}</span>
            </Button>
          ))}
        </div>

        {activeTab !== "tools" ? (
          <div className="relative mb-4 max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={query}
              onChange={(event) => setQuery(event.currentTarget.value)}
              placeholder="搜索设计技能、类型、场景..."
            />
          </div>
        ) : null}

        {(isLoading || designSkillsQuery.isLoading) && (
          <div className="text-muted-foreground text-center py-8">
            {t("common.loading") || "加载中..."}
          </div>
        )}

        {activeTab === "tools" ? (
          (Object.entries(categorizedSkills) as [string, SkillInfo[]][]).map(([category, categorySkills]) => (
            categorySkills.length > 0 && (
              <div key={category} className="mb-6">
                <h2 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
                  <Tag variant="outline">{categoryLabels[category as keyof typeof categoryLabels]}</Tag>
                  <span className="text-sm text-muted-foreground">{categorySkills.length} 个技能</span>
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {categorySkills.map(renderSkillCard)}
                </div>
              </div>
            )
          ))
        ) : (
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
              <Tag variant="outline">{tabs.find((tab) => tab.key === activeTab)?.label}</Tag>
              <span className="text-sm text-muted-foreground">{filteredDesignSkills.length} 个技能</span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredDesignSkills.map(renderDesignSkillCard)}
            </div>
          </div>
        )}

        {activeTab === "tools" && skills.length === 0 && !isLoading && (
          <div className="text-muted-foreground text-center py-8">
            {t("skill.empty") || "暂无技能"}
          </div>
        )}
        {activeTab !== "tools" && filteredDesignSkills.length === 0 && !designSkillsQuery.isLoading && (
          <div className="text-muted-foreground text-center py-8">
            暂无匹配的设计技能
          </div>
        )}

        <Dialog open={selectedSkill !== null} onOpenChange={(open) => !open && setSelectedSkill(null)}>
          <DialogContent className="max-w-[600px]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Wrench className="h-4 w-4 text-primary" />
                <span>{selectedSkill?.name}</span>
                {selectedSkill?.is_builtin && <Tag variant="default">内置</Tag>}
              </DialogTitle>
            </DialogHeader>
            {selectedSkill && (
              <Descriptions bordered>
                <DescriptionItem label={t("skill.description_cn") || "中文描述"}>
                  {selectedSkill.description_cn || selectedSkill.description}
                </DescriptionItem>
                <DescriptionItem label={t("skill.description") || "英文描述"}>
                  {selectedSkill.description}
                </DescriptionItem>
                <DescriptionItem label={t("skill.status") || "状态"}>
                  <Tag variant="success" className="flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" /> {t("skill.available") || "可用"}
                  </Tag>
                </DescriptionItem>
                <DescriptionItem label={t("skill.type") || "类型"}>
                  {selectedSkill.is_builtin ? (
                    <Tag variant="default">{t("skill.builtin") || "内置"}</Tag>
                  ) : (
                    <Tag variant="secondary">{t("skill.custom") || "自定义"}</Tag>
                  )}
                </DescriptionItem>
                <DescriptionItem label={t("skill.parameters") || "参数定义"}>
                  <pre className="bg-muted p-3 rounded text-xs overflow-auto max-h-[200px]">
                    {JSON.stringify(selectedSkill.parameters, null, 2)}
                  </pre>
                </DescriptionItem>
              </Descriptions>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setSelectedSkill(null)}>
                {t("common.close") || "关闭"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={selectedDesignSkill !== null} onOpenChange={(open) => !open && setSelectedDesignSkill(null)}>
          <DialogContent className="max-w-[720px]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Palette className="h-4 w-4 text-primary" />
                <span>{selectedDesignSkill?.name}</span>
                {selectedDesignSkill?.hidden && <Tag variant="secondary">隐藏</Tag>}
                {selectedDesignSkill?.status === "adapter-pending" ? (
                  <Tag variant="warning">待适配</Tag>
                ) : (
                  <Tag variant="success">可用</Tag>
                )}
              </DialogTitle>
            </DialogHeader>
            {selectedDesignSkill && (
              <Descriptions bordered>
                <DescriptionItem label="描述">
                  {selectedDesignSkill.description || "暂无描述"}
                </DescriptionItem>
                <DescriptionItem label="来源">
                  <Tag variant="outline">{selectedDesignSkill.source}</Tag>
                </DescriptionItem>
                <DescriptionItem label="分类">
                  <div className="flex flex-wrap gap-2">
                    {selectedDesignSkill.mode && <Tag variant="info">{selectedDesignSkill.mode}</Tag>}
                    {selectedDesignSkill.surface && <Tag variant="outline">{selectedDesignSkill.surface}</Tag>}
                    {selectedDesignSkill.scenario && <Tag variant="outline">{selectedDesignSkill.scenario}</Tag>}
                    {selectedDesignSkill.previewType && <Tag variant="secondary">{selectedDesignSkill.previewType}</Tag>}
                  </div>
                </DescriptionItem>
                <DescriptionItem label="资源">
                  <div className="flex flex-wrap gap-2">
                    <Tag variant={selectedDesignSkill.hasAssets ? "success" : "outline"}>assets</Tag>
                    <Tag variant={selectedDesignSkill.hasReferences ? "success" : "outline"}>references</Tag>
                  </div>
                </DescriptionItem>
                <DescriptionItem label="适配状态">
                  <div className="flex flex-wrap gap-2">
                    <Tag variant={selectedDesignSkill.status === "adapter-pending" ? "warning" : "success"}>
                      {selectedDesignSkill.status}
                    </Tag>
                    {selectedDesignSkill.adapterKind && <Tag variant="warning">{selectedDesignSkill.adapterKind}</Tag>}
                    {selectedDesignSkill.dependencyType && <Tag variant="outline">{selectedDesignSkill.dependencyType}</Tag>}
                  </div>
                </DescriptionItem>
                <DescriptionItem label="示例 Prompt">
                  {selectedDesignSkill.examplePrompt || "暂无"}
                </DescriptionItem>
                <DescriptionItem label="触发词">
                  {selectedDesignSkill.triggers.length ? selectedDesignSkill.triggers.join(", ") : "暂无"}
                </DescriptionItem>
              </Descriptions>
            )}
            <DialogFooter>
              <Button
                variant="outline"
                onClick={toggleSelectedDesignVisibility}
                disabled={!selectedDesignSkill || managementMutation.isPending}
              >
                {selectedDesignSkill?.hidden ? "显示到聊天导入" : "从聊天导入隐藏"}
              </Button>
              <Button variant="outline" onClick={() => setSelectedDesignSkill(null)}>
                {t("common.close") || "关闭"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </ConstructShell>
  )
}

import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Wrench, Code, CheckCircle } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Tag } from "@/components/ui/tag"
import { Descriptions, DescriptionItem } from "@/components/ui/descriptions"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import { useSkills } from "@/features/construct/skills/hooks/use-skills"

interface SkillInfo {
  name: string
  description: string
  description_cn: string
  parameters: Record<string, unknown>
  is_builtin: boolean
}

export default function SkillsPage() {
  const { t } = useTranslation("construct")
  const { data, isLoading } = useSkills()
  const skills = data?.skills || []
  const [selectedSkill, setSelectedSkill] = useState<SkillInfo | null>(null)

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

  return (
    <ConstructShell>
      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">
            {t("skill.title") || "技能管理"}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t("skill.description") || `平台已集成 ${skills.length} 个内置技能，支持数据分析、SQL查询、可视化等功能`}
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
            <div className="text-orange-400 text-sm">其他工具</div>
            <div className="text-2xl font-bold text-orange-300">
              {categorizedSkills.other.length}
            </div>
          </div>
        </div>

        {isLoading && (
          <div className="text-muted-foreground text-center py-8">
            {t("common.loading") || "加载中..."}
          </div>
        )}

        {(Object.entries(categorizedSkills) as [string, SkillInfo[]][]).map(([category, categorySkills]) => (
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
        ))}

        {skills.length === 0 && !isLoading && (
          <div className="text-muted-foreground text-center py-8">
            {t("skill.empty") || "暂无技能"}
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
      </div>
    </ConstructShell>
  )
}
import { useTranslation } from "react-i18next"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import { useSkills } from "@/features/construct/skills/hooks/use-skills"

export default function SkillsPage() {
  const { t } = useTranslation("construct")
  const { data: skills = {}, isLoading } = useSkills()

  return (
    <ConstructShell>
      {isLoading && <div className="text-text-secondary">Loading...</div>}
      <div className="flex flex-col gap-3">
        {Object.entries(skills).map(([name, desc]) => (
          <div
            key={name}
            className="bg-surface px-4 py-4 rounded-lg"
          >
            <div className="font-semibold">{name}</div>
            <div className="text-text-secondary text-sm mt-1">{desc}</div>
          </div>
        ))}
        {Object.keys(skills).length === 0 && !isLoading && (
          <div className="text-text-secondary">{t("agent.empty")}</div>
        )}
      </div>
    </ConstructShell>
  )
}

import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  useOperators,
  useRunAwel,
} from "@/features/construct/flow/hooks/use-flow"

const nodeTypes = [
  { key: "start", color: "#52c41a" },
  { key: "llm", color: "#1677ff" },
  { key: "condition", color: "#faad14" },
  { key: "end", color: "#ff4d4f" },
]

const mockNodes = [
  { id: "1", type: "start", x: 80, y: 120 },
  { id: "2", type: "llm", x: 280, y: 120 },
  { id: "3", type: "condition", x: 480, y: 120 },
  { id: "4", type: "end", x: 680, y: 120 },
]

const mockEdges = [
  { from: "1", to: "2" },
  { from: "2", to: "3" },
  { from: "3", to: "4" },
]

export default function FlowPage() {
  const { t } = useTranslation("construct")
  const [input, setInput] = useState("hello chatbi")
  const [result, setResult] = useState<unknown>(null)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)

  const { data: operators = [], isLoading } = useOperators()
  const runner = useRunAwel()

  const run = async () => {
    const data = await runner.mutateAsync(input)
    setResult(data)
  }

  const opList = operators as Array<{ name: string; type: string }>

  return (
    <ConstructShell>
      <Tabs defaultValue="canvas" className="mb-4">
        <TabsList>
          <TabsTrigger value="canvas">{t("awel.canvas")}</TabsTrigger>
          <TabsTrigger value="operators">{t("awel.operators")}</TabsTrigger>
          <TabsTrigger value="run">{t("awel.runFlow")}</TabsTrigger>
        </TabsList>

        <TabsContent value="canvas">
          <div className="flex gap-4 h-[480px]">
            {/* Node Palette */}
            <Card className="w-48 flex-shrink-0 p-3">
              <h4 className="font-semibold mb-3 text-sm">{t("awel.nodePalette")}</h4>
              <div className="flex flex-col gap-2">
                {nodeTypes.map((n) => (
                  <div
                    key={n.key}
                    className="px-3 py-2 rounded-lg text-sm text-white cursor-pointer hover:opacity-90"
                    style={{ backgroundColor: n.color }}
                  >
                    {t(`awel.nodes.${n.key}`)}
                  </div>
                ))}
              </div>
            </Card>

            {/* Canvas */}
            <div className="flex-1 bg-card rounded-xl border border-border relative overflow-hidden"
            >
              <div className="absolute top-3 left-3 text-xs text-muted-foreground">
                {t("awel.placeholder")}
              </div>
              <svg className="w-full h-full">
                {mockEdges.map((e) => {
                  const fromNode = mockNodes.find((n) => n.id === e.from)
                  const toNode = mockNodes.find((n) => n.id === e.to)
                  if (!fromNode || !toNode) return null
                  return (
                    <line
                      key={`${e.from}-${e.to}`}
                      x1={fromNode.x + 60}
                      y1={fromNode.y + 20}
                      x2={toNode.x}
                      y2={toNode.y + 20}
                      stroke="currentColor"
                      strokeOpacity={0.4}
                      strokeWidth={2}
                    />
                  )
                })}
                {mockNodes.map((n) => {
                  const color = nodeTypes.find((t) => t.key === n.type)?.color || "#999"
                  const isSelected = selectedNode === n.id
                  return (
                    <g
                      key={n.id}
                      transform={`translate(${n.x}, ${n.y})`}
                      className="cursor-pointer"
                      onClick={() => setSelectedNode(n.id)}
                    >
                      <rect
                        width={120}
                        height={40}
                        rx={8}
                        fill={color}
                        stroke={isSelected ? "currentColor" : "none"}
                        strokeWidth={isSelected ? 3 : 0}
                      />
                      <text
                        x={60}
                        y={25}
                        textAnchor="middle"
                        fill="#fff"
                        fontSize={12}
                      >
                        {t(`awel.nodes.${n.type}`)}
                      </text>
                    </g>
                  )
                })}
              </svg>
            </div>

            {/* Properties */}
            <Card className="w-56 flex-shrink-0 p-3">
              <h4 className="font-semibold mb-3 text-sm">{t("awel.properties")}</h4>
              {selectedNode ? (
                <div className="text-sm">
                  <p className="m-0 mb-2">
                    <span className="text-muted-foreground">ID: </span>
                    {selectedNode}
                  </p>
                  <p className="m-0 text-muted-foreground">
                    Click a node to view its configuration.
                  </p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground m-0">
                  Select a node to edit properties.
                </p>
              )}
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="operators">
          {isLoading && <div className="text-muted-foreground text-sm mb-4">Loading...</div>}
          <div className="flex flex-wrap gap-2 mb-8">
            {opList.map((op) => (
              <div
                key={op.name}
                className="bg-card px-3 py-2 rounded-lg text-xs border border-border"
              >
                {op.name}{" "}
                <span className="text-muted-foreground">({op.type})</span>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="run">
          <div className="flex gap-3 mb-3">
            <Input
              className="flex-1"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <Button onClick={run} disabled={runner.isPending}>
              {runner.isPending ? "Running..." : t("awel.run")}
            </Button>
          </div>
          {result !== null && (
            <pre className="bg-card p-3 rounded-lg text-xs overflow-auto max-h-96 border border-border">
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </TabsContent>
      </Tabs>
    </ConstructShell>
  )
}

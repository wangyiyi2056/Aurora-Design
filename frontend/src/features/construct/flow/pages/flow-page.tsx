import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Tag } from "@/components/ui/tag"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  createFlow,
  deleteFlow,
  listFlowRuns,
  listFlows,
  runFlow,
  updateFlow,
  type FlowPayload,
} from "@/services/flow"

const defaultNodes = JSON.stringify([{ id: "upper", type: "uppercase" }], null, 2)

export default function FlowPage() {
  const qc = useQueryClient()
  const flowsQuery = useQuery({ queryKey: ["flows", "list"], queryFn: listFlows })
  const [form, setForm] = useState({ name: "", description: "", nodes: defaultNodes, input: "hello" })
  const [selectedFlowId, setSelectedFlowId] = useState("")
  const [lastOutput, setLastOutput] = useState("")
  const flows = flowsQuery.data?.items || []
  const runsQuery = useQuery({
    queryKey: ["flows", selectedFlowId, "runs"],
    queryFn: () => listFlowRuns(selectedFlowId),
    enabled: Boolean(selectedFlowId),
  })

  const createMutation = useMutation({
    mutationFn: createFlow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["flows", "list"] })
      setForm({ name: "", description: "", nodes: defaultNodes, input: "hello" })
    },
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<FlowPayload> }) => updateFlow(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["flows", "list"] }),
  })
  const deleteMutation = useMutation({
    mutationFn: deleteFlow,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["flows", "list"] }),
  })
  const runMutation = useMutation({
    mutationFn: ({ id, input }: { id: string; input: string }) => runFlow(id, input),
    onSuccess: (run) => {
      setLastOutput(JSON.stringify(run.output, null, 2))
      qc.invalidateQueries({ queryKey: ["flows", run.flow_id, "runs"] })
    },
  })

  const parseNodes = () => JSON.parse(form.nodes || "[]") as Record<string, unknown>[]

  const save = () => {
    if (!form.name.trim()) return
    createMutation.mutate({
      name: form.name,
      description: form.description,
      nodes: parseNodes(),
      edges: [],
      variables: {},
      enabled: true,
    })
  }

  return (
    <ConstructShell>
      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <Card className="space-y-3 p-4">
          <h3 className="m-0 text-base font-semibold">Flows</h3>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name" />
          <Textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Description"
            rows={2}
          />
          <Textarea value={form.nodes} onChange={(e) => setForm({ ...form, nodes: e.target.value })} rows={8} />
          <Button onClick={save} disabled={createMutation.isPending}>Add Flow</Button>
        </Card>

        <div className="space-y-3">
          {flows.map((flow) => (
            <Card key={flow.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="m-0 font-semibold">{flow.name}</h4>
                    <Tag variant={flow.enabled ? "success" : "secondary"}>{flow.enabled ? "Enabled" : "Disabled"}</Tag>
                    <Tag variant="outline">{flow.nodes.length} nodes</Tag>
                  </div>
                  <p className="m-0 mt-2 text-sm text-muted-foreground">{flow.description || "-"}</p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSelectedFlowId(flow.id)
                      runMutation.mutate({ id: flow.id, input: form.input })
                    }}
                  >
                    Run
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => updateMutation.mutate({ id: flow.id, payload: { enabled: !flow.enabled } })}
                  >
                    Toggle
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => deleteMutation.mutate(flow.id)}>
                    Delete
                  </Button>
                </div>
              </div>
            </Card>
          ))}
          {lastOutput && (
            <Card className="p-4">
              <h4 className="m-0 mb-2 font-semibold">Last Output</h4>
              <pre className="max-h-40 overflow-auto rounded-md border bg-muted/40 p-3 text-xs">{lastOutput}</pre>
            </Card>
          )}
          {selectedFlowId && (
            <Card className="p-4">
              <h4 className="m-0 mb-2 font-semibold">Run History</h4>
              <div className="space-y-2 text-sm">
                {(runsQuery.data?.items || []).map((run) => (
                  <div key={run.id} className="flex items-center justify-between rounded-md border px-3 py-2">
                    <span>{run.status}</span>
                    <span className="text-muted-foreground">{String(run.output ?? run.error ?? "")}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </ConstructShell>
  )
}

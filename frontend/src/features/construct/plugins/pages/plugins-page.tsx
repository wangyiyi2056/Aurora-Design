import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Tag } from "@/components/ui/tag"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  createPlugin,
  deletePlugin,
  disablePlugin,
  listPlugins,
  setPluginEnabled,
  updatePlugin,
  type PluginPayload,
} from "@/services/plugins"

export default function PluginsPage() {
  const qc = useQueryClient()
  const pluginsQuery = useQuery({ queryKey: ["plugins", "list"], queryFn: listPlugins })
  const [form, setForm] = useState<PluginPayload>({
    name: "",
    description: "",
    entrypoint: "",
    enabled: false,
    config: {},
  })
  const plugins = pluginsQuery.data?.items || []

  const refresh = () => qc.invalidateQueries({ queryKey: ["plugins", "list"] })
  const createMutation = useMutation({
    mutationFn: createPlugin,
    onSuccess: () => {
      refresh()
      setForm({ name: "", description: "", entrypoint: "", enabled: false, config: {} })
    },
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<PluginPayload> }) => updatePlugin(id, payload),
    onSuccess: refresh,
  })
  const enableMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => setPluginEnabled(id, enabled),
    onSuccess: refresh,
  })
  const disableMutation = useMutation({ mutationFn: disablePlugin, onSuccess: refresh })
  const deleteMutation = useMutation({ mutationFn: deletePlugin, onSuccess: refresh })

  const save = () => {
    if (!form.name?.trim()) return
    createMutation.mutate(form)
  }

  return (
    <ConstructShell>
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card className="space-y-3 p-4">
          <h3 className="m-0 text-base font-semibold">Local Plugins</h3>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name" />
          <Input
            value={form.entrypoint}
            onChange={(e) => setForm({ ...form, entrypoint: e.target.value })}
            placeholder="Entrypoint"
          />
          <Textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Description"
            rows={3}
          />
          <Button onClick={save} disabled={createMutation.isPending}>Add Plugin</Button>
        </Card>

        <div className="space-y-3">
          {plugins.map((plugin) => (
            <Card key={plugin.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="m-0 font-semibold">{plugin.name}</h4>
                    <Tag variant={plugin.enabled ? "success" : "secondary"}>
                      {plugin.enabled ? "Enabled" : "Disabled"}
                    </Tag>
                  </div>
                  <p className="m-0 mt-2 text-sm text-muted-foreground">{plugin.description || "-"}</p>
                  <p className="m-0 mt-2 font-mono text-xs text-muted-foreground">{plugin.entrypoint || "-"}</p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      plugin.enabled
                        ? disableMutation.mutate(plugin.id)
                        : enableMutation.mutate({ id: plugin.id, enabled: true })
                    }
                  >
                    {plugin.enabled ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => updateMutation.mutate({ id: plugin.id, payload: { description: plugin.description } })}
                  >
                    Save
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => deleteMutation.mutate(plugin.id)}>
                    Delete
                  </Button>
                </div>
              </div>
            </Card>
          ))}
          {plugins.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">No plugins yet</div>
          )}
        </div>
      </div>
    </ConstructShell>
  )
}

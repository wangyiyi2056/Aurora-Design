import { describe, expect, it } from "vitest"

import {
  artifactsFromAgentEvents,
  artifactsFromAssistantText,
  canonicalArtifactsForAssistant,
} from "./generated-artifacts"

describe("canonicalArtifactsForAssistant", () => {
  it("keeps the richer HTML candidate when Write and final artifact both exist", () => {
    const textArtifacts = artifactsFromAssistantText(`
<artifact identifier="pitch" type="text/html" title="Pitch Deck">
<!doctype html><html><body>summary</body></html>
</artifact>
`)
    const eventArtifacts = artifactsFromAgentEvents([
      {
        kind: "tool_use",
        id: "tool-1",
        name: "Write",
        input: {
          file_path: "pitch-deck.html",
          content: "<!doctype html><html><body><section>slide 1</section><section>slide 2</section></body></html>",
        },
      },
    ])

    expect(canonicalArtifactsForAssistant(textArtifacts, eventArtifacts).map((artifact) => artifact.name)).toEqual([
      "pitch-deck.html",
    ])
  })

  it("uses Write tool files when the assistant did not emit a final artifact", () => {
    const eventArtifacts = artifactsFromAgentEvents([
      {
        kind: "tool_use",
        id: "tool-1",
        name: "Write",
        input: {
          file_path: "login.html",
          content: "<!doctype html><html><body>login</body></html>",
        },
      },
    ])

    expect(canonicalArtifactsForAssistant([], eventArtifacts).map((artifact) => artifact.name)).toEqual([
      "login.html",
    ])
  })
})

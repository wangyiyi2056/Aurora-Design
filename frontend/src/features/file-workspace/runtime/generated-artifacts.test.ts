import { describe, expect, it } from "vitest"

import {
  artifactFromStreamEvent,
  artifactFromToolCallStartEvent,
  artifactsFromAgentEvents,
  artifactsFromAssistantText,
  artifactsFromPartialAssistantText,
  safeFileStem,
} from "./generated-artifacts"

describe("generated workspace artifacts", () => {
  it("extracts html step chunks as generated files", () => {
    const artifact = artifactFromStreamEvent({
      type: "step.chunk",
      id: "render",
      output_type: "html",
      content: { title: "Report/May", html: "<html><body>ok</body></html>" },
    })

    expect(artifact).toMatchObject({
      name: "generated/Report-May.html",
      content: "<html><body>ok</body></html>",
      shouldOpen: true,
    })
  })

  it("sanitizes unsafe file stems", () => {
    expect(safeFileStem("../bad:name?.html")).toBe("bad-name")
  })

  it("extracts generated files from normal assistant text code fences", () => {
    const artifacts = artifactsFromAssistantText(`
这里是登录页面：

\`\`\`html
<!doctype html><html><body><form>Login</form></body></html>
\`\`\`

\`\`\`md
# 使用说明
\`\`\`
`)

    expect(artifacts).toHaveLength(2)
    expect(artifacts[0]).toMatchObject({
      name: "generated/HTML.html",
      content: "<!doctype html><html><body><form>Login</form></body></html>",
      shouldOpen: true,
      encoding: "utf8",
    })
    expect(artifacts[1]).toMatchObject({
      name: "generated/Markdown.md",
      content: "# 使用说明",
      shouldOpen: false,
      encoding: "utf8",
    })
  })

  it("extracts Open Design artifact tags before falling back to code fences", () => {
    const artifacts = artifactsFromAssistantText(`
Here is the page:
<artifact identifier="login" type="text/html" title="Login Page">
<!doctype html><html><body>Login</body></html>
</artifact>
`)

    expect(artifacts).toHaveLength(1)
    expect(artifacts[0]).toMatchObject({
      name: "generated/Login Page.html",
      content: "<!doctype html><html><body>Login</body></html>",
      shouldOpen: true,
      encoding: "utf8",
    })
  })

  it("extracts markdown data images as workspace image files", () => {
    const artifacts = artifactsFromAssistantText(
      "![preview](data:image/png;base64,iVBORw0KGgo=)",
    )

    expect(artifacts).toHaveLength(1)
    expect(artifacts[0]).toMatchObject({
      name: "generated/preview.png",
      content: "iVBORw0KGgo=",
      encoding: "base64",
      shouldOpen: true,
    })
  })

  it("extracts previewable files from Write tool inputs", () => {
    const artifacts = artifactsFromAgentEvents([
      {
        kind: "tool_use",
        id: "tool-1",
        name: "Write",
        input: {
          file_path: "login.html",
          content: "<!doctype html><html><body>Login</body></html>",
        },
      },
    ])

    expect(artifacts).toHaveLength(1)
    expect(artifacts[0]).toMatchObject({
      name: "login.html",
      content: "<!doctype html><html><body>Login</body></html>",
      shouldOpen: true,
      encoding: "utf8",
    })
  })

  it("extracts previewable files from streaming Write tool starts", () => {
    const artifact = artifactFromToolCallStartEvent({
      type: "tool_call_start",
      id: "tool-1",
      tool_name: "Write",
      arguments: JSON.stringify({
        file_path: "pitch-deck.html",
        content: "<!doctype html><html><body>deck</body></html>",
      }),
    })

    expect(artifact).toMatchObject({
      name: "pitch-deck.html",
      shouldOpen: true,
    })
  })

  it("extracts a live partial Open Design artifact before the closing tag arrives", () => {
    const artifacts = artifactsFromPartialAssistantText(`
<artifact identifier="login" type="text/html" title="Login Page">
<!doctype html><html><body><form>Log
`)

    expect(artifacts).toHaveLength(1)
    expect(artifacts[0]).toMatchObject({
      name: "generated/Login Page.html",
      content: "<!doctype html><html><body><form>Log",
      shouldOpen: true,
      encoding: "utf8",
    })
  })
})

import { theme } from "antd"
import type { ThemeConfig } from "antd"

const lightTokens = {
  colorPrimary: "#0069fe",
  colorSuccess: "#52c41a",
  colorError: "#ff4d4f",
  colorWarning: "#faad14",
  borderRadius: 4,
  colorBgContainer: "#ffffff",
  colorBgElevated: "#f3f4f6",
  colorText: "#111827",
  colorTextSecondary: "#6b7280",
  colorBorder: "#e5e7eb",
  colorBorderSecondary: "#f3f4f6",
  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.05)",
  boxShadowSecondary: "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.05)",
  controlOutline: "#3b82f6",
}

const darkTokens = {
  colorPrimary: "#0069fe",
  colorSuccess: "#52c41a",
  colorError: "#ff4d4f",
  colorWarning: "#faad14",
  borderRadius: 4,
  colorBgContainer: "#161b22",
  colorBgElevated: "#1f2937",
  colorText: "#e6edf3",
  colorTextSecondary: "#8b949e",
  colorBorder: "#30363d",
  colorBorderSecondary: "#21262d",
  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.35), 0 2px 4px -2px rgb(0 0 0 / 0.25)",
  boxShadowSecondary: "0 10px 15px -3px rgb(0 0 0 / 0.45), 0 4px 6px -4px rgb(0 0 0 / 0.35)",
  controlOutline: "#3b82f6",
}

export function getAntdTheme(mode: "light" | "dark"): ThemeConfig {
  return {
    token: mode === "dark" ? darkTokens : lightTokens,
    algorithm: mode === "dark" ? theme.darkAlgorithm : theme.defaultAlgorithm,
  }
}

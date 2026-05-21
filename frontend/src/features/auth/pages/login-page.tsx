import { useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { BrandLogo } from "@/components/brand/brand-logo"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useTheme } from "@/hooks/use-theme"

export default function LoginPage() {
  useTheme()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [focusedField, setFocusedField] = useState<string | null>(null)

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      setLoading(true)
      // TODO: integrate with auth API
      setTimeout(() => {
        setLoading(false)
        navigate("/")
      }, 800)
    },
    [navigate]
  )

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-[#08090d]">
      {/* Left brand panel — desktop only */}
      <div className="relative hidden w-1/2 items-center justify-center lg:flex">
        {/* Aurora orbs */}
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          <div
            className="absolute left-1/2 top-1/3 h-[500px] w-[700px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-40 blur-[120px]"
            style={{
              background:
                "radial-gradient(ellipse at center, #0069fe 0%, #3b82f6 40%, transparent 70%)",
              animation: "aurora-pulse 8s ease-in-out infinite",
            }}
          />
          <div
            className="absolute bottom-1/3 right-1/4 h-[350px] w-[500px] rounded-full opacity-25 blur-[100px]"
            style={{
              background:
                "radial-gradient(ellipse at center, #6366f1 0%, #00c6ff 50%, transparent 70%)",
              animation: "aurora-pulse 12s ease-in-out infinite 3s",
            }}
          />
        </div>

        {/* Grid texture */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.04]"
          aria-hidden="true"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />

        {/* Brand content */}
        <div className="relative z-10 flex flex-col items-center gap-8 px-12">
          <div className="relative">
            <BrandLogo className="h-20 w-20" />
            <div className="absolute -inset-6 -z-10 rounded-full bg-[#0069fe]/15 blur-xl" />
          </div>
          <div className="text-center">
            <h1 className="text-4xl font-bold tracking-tight text-white">
              Aurora Design
            </h1>
            <p className="mt-3 text-base text-white/45">
              Intelligent design workspace for modern teams
            </p>
          </div>

          {/* Feature highlights */}
          <div className="mt-4 flex flex-col gap-4 text-sm text-white/35">
            <div className="flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0069fe]/15 text-[#0069fe]">
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </span>
              AI-powered design generation
            </div>
            <div className="flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0069fe]/15 text-[#0069fe]">
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </span>
              Real-time collaboration
            </div>
            <div className="flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0069fe]/15 text-[#0069fe]">
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </span>
              Component library & exports
            </div>
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex flex-1 items-center justify-center px-6 py-12 lg:w-1/2">
        {/* Mobile aurora background */}
        <div className="pointer-events-none absolute inset-0 lg:hidden" aria-hidden="true">
          <div
            className="absolute left-1/2 top-1/4 h-[400px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-25 blur-[100px]"
            style={{
              background:
                "radial-gradient(ellipse at center, #0069fe 0%, #3b82f6 40%, transparent 70%)",
              animation: "aurora-pulse 8s ease-in-out infinite",
            }}
          />
        </div>

        <div className="relative z-10 w-full max-w-[400px]">
          {/* Mobile brand */}
          <div className="mb-10 flex flex-col items-center gap-4 lg:hidden">
            <div className="relative">
              <BrandLogo className="h-12 w-12" />
              <div className="absolute -inset-3 -z-10 rounded-full bg-[#0069fe]/10 blur-md" />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              Aurora Design
            </h1>
          </div>

          {/* Welcome text */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-white">
              Welcome back
            </h2>
            <p className="mt-1.5 text-sm text-white/40">
              Sign in to continue to your workspace
            </p>
          </div>

          {/* Form card */}
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.025] p-7 shadow-2xl backdrop-blur-xl">
            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              {/* Email field */}
              <div className="flex flex-col gap-2">
                <label
                  htmlFor="login-email"
                  className="text-sm font-medium text-white/60"
                >
                  Email address
                </label>
                <div className="relative">
                  <Input
                    id="login-email"
                    type="email"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onFocus={() => setFocusedField("email")}
                    onBlur={() => setFocusedField(null)}
                    required
                    autoComplete="email"
                    className="h-11 border-white/[0.08] bg-white/[0.04] text-white placeholder:text-white/20 focus-visible:border-[#0069fe]/50 focus-visible:ring-[#0069fe]/20"
                  />
                  {focusedField === "email" && (
                    <div className="pointer-events-none absolute inset-0 rounded-md border border-[#0069fe]/30" />
                  )}
                </div>
              </div>

              {/* Password field */}
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="login-password"
                    className="text-sm font-medium text-white/60"
                  >
                    Password
                  </label>
                  <button
                    type="button"
                    className="text-xs font-medium text-[#0069fe] transition-colors hover:text-[#3b82f6]"
                    onClick={(e) => e.preventDefault()}
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <Input
                    id="login-password"
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onFocus={() => setFocusedField("password")}
                    onBlur={() => setFocusedField(null)}
                    required
                    autoComplete="current-password"
                    className="h-11 border-white/[0.08] bg-white/[0.04] text-white placeholder:text-white/20 focus-visible:border-[#0069fe]/50 focus-visible:ring-[#0069fe]/20"
                  />
                  {focusedField === "password" && (
                    <div className="pointer-events-none absolute inset-0 rounded-md border border-[#0069fe]/30" />
                  )}
                </div>
              </div>

              {/* Remember me */}
              <label className="flex items-center gap-2 text-sm text-white/50 select-none">
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 rounded border-white/20 bg-white/[0.04] text-[#0069fe] focus:ring-[#0069fe]/30"
                />
                Remember me for 30 days
              </label>

              {/* Submit button */}
              <Button
                type="submit"
                className="h-11 w-full rounded-lg bg-[#0069fe] text-sm font-semibold text-white shadow-lg shadow-[#0069fe]/20 transition-all hover:bg-[#0058d4] hover:shadow-xl hover:shadow-[#0069fe]/30 active:scale-[0.98]"
                disabled={loading}
              >
                {loading ? (
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                ) : (
                  "Sign in"
                )}
              </Button>
            </form>

            {/* Divider */}
            <div className="my-6 flex items-center gap-3">
              <div className="h-px flex-1 bg-white/[0.06]" />
              <span className="text-xs text-white/25">or continue with</span>
              <div className="h-px flex-1 bg-white/[0.06]" />
            </div>

            {/* Social login */}
            <div className="flex gap-3">
              <button
                type="button"
                className="flex h-11 flex-1 items-center justify-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.03] text-sm font-medium text-white/70 transition-all hover:bg-white/[0.06] hover:text-white active:scale-[0.98]"
                onClick={(e) => e.preventDefault()}
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                GitHub
              </button>
              <button
                type="button"
                className="flex h-11 flex-1 items-center justify-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.03] text-sm font-medium text-white/70 transition-all hover:bg-white/[0.06] hover:text-white active:scale-[0.98]"
                onClick={(e) => e.preventDefault()}
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                </svg>
                Google
              </button>
            </div>
          </div>

          {/* Footer */}
          <p className="mt-8 text-center text-sm text-white/30">
            Don&apos;t have an account?{" "}
            <button
              type="button"
              className="font-medium text-[#0069fe] transition-colors hover:text-[#3b82f6]"
              onClick={(e) => e.preventDefault()}
            >
              Create one
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}

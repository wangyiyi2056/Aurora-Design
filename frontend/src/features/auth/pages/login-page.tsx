import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { BrandLogo } from "@/components/brand/brand-logo"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useTheme } from "@/hooks/use-theme"

export default function LoginPage() {
  useTheme()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    // TODO: integrate with auth API
    setTimeout(() => {
      setLoading(false)
      navigate("/")
    }, 800)
  }

  return (
    <div className="login-page">
      <div className="login-aurora" aria-hidden="true" />

      <div className="login-container">
        <Card className="login-card">
          <CardHeader className="login-header">
            <div className="login-brand">
              <BrandLogo className="h-10 w-10" />
              <span className="login-brand-name">Aurora Design</span>
            </div>
            <CardTitle className="login-title">Welcome back</CardTitle>
            <CardDescription className="login-desc">
              Sign in to continue to your workspace
            </CardDescription>
          </CardHeader>

          <form onSubmit={handleSubmit}>
            <CardContent className="login-content">
              <div className="login-field">
                <label htmlFor="login-email" className="login-label">
                  Email
                </label>
                <Input
                  id="login-email"
                  type="email"
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  className="login-input"
                />
              </div>

              <div className="login-field">
                <div className="login-label-row">
                  <label htmlFor="login-password" className="login-label">
                    Password
                  </label>
                  <a
                    href="#"
                    className="login-forgot"
                    onClick={(e) => e.preventDefault()}
                  >
                    Forgot password?
                  </a>
                </div>
                <Input
                  id="login-password"
                  type="password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="login-input"
                />
              </div>
            </CardContent>

            <CardFooter className="login-footer">
              <Button
                type="submit"
                className="login-submit"
                disabled={loading}
                size="lg"
              >
                {loading ? (
                  <span className="login-spinner" />
                ) : (
                  "Sign in"
                )}
              </Button>

              <p className="login-signup">
                Don&apos;t have an account?{" "}
                <a href="#" className="login-signup-link" onClick={(e) => e.preventDefault()}>
                  Create one
                </a>
              </p>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  )
}

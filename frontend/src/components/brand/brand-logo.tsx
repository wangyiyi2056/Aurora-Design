import logoUrl from "@/assets/logo.png"

interface BrandLogoProps {
  className?: string
}

export function BrandLogo({ className = "h-8 w-8" }: BrandLogoProps) {
  return (
    <img
      src={logoUrl}
      alt=""
      aria-hidden="true"
      className={`${className} shrink-0 object-contain`}
      draggable={false}
    />
  )
}

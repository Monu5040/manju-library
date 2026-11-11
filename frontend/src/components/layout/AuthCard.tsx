import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function AuthCard({
  title,
  description,
  children,
}: {
  title: string
  description: ReactNode
  children: ReactNode
}) {
  return (
    <div className="flex justify-center px-4 py-12 sm:py-20">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>
            <span className="text-2xl">{title}</span>
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </div>
  )
}

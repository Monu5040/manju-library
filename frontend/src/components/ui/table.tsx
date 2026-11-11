import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export function Table({ className, ...props }: ComponentProps<'table'>) {
  return (
    <div className="w-full overflow-x-auto rounded-xl border bg-card">
      <table className={cn('w-full caption-bottom text-sm', className)} {...props} />
    </div>
  )
}

export function THead(props: ComponentProps<'thead'>) {
  return <thead className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground" {...props} />
}

export function TBody(props: ComponentProps<'tbody'>) {
  return <tbody className="divide-y" {...props} />
}

export function TR({ className, ...props }: ComponentProps<'tr'>) {
  return <tr className={cn('transition-colors', className)} {...props} />
}

export function TH({ className, ...props }: ComponentProps<'th'>) {
  return <th scope="col" className={cn('px-4 py-2.5 font-medium whitespace-nowrap', className)} {...props} />
}

export function TD({ className, ...props }: ComponentProps<'td'>) {
  return <td className={cn('px-4 py-3 align-middle', className)} {...props} />
}

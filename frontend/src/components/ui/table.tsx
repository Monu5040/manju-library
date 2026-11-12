import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export function Table({ className, ...props }: ComponentProps<'table'>) {
  return (
    <div className="w-full overflow-x-auto rounded-2xl border bg-card shadow-card">
      <table className={cn('w-full caption-bottom text-sm', className)} {...props} />
    </div>
  )
}

export function THead(props: ComponentProps<'thead'>) {
  return (
    <thead
      className="border-b bg-muted/55 text-left text-[11px] font-semibold tracking-[0.06em] text-muted-foreground uppercase"
      {...props}
    />
  )
}

export function TBody(props: ComponentProps<'tbody'>) {
  return <tbody className="divide-y divide-border/70 [&>tr]:transition-colors [&>tr:hover]:bg-muted/35" {...props} />
}

export function TR({ className, ...props }: ComponentProps<'tr'>) {
  return <tr className={cn(className)} {...props} />
}

export function TH({ className, ...props }: ComponentProps<'th'>) {
  return <th scope="col" className={cn('px-4 py-3 font-semibold whitespace-nowrap first:pl-5 last:pr-5', className)} {...props} />
}

export function TD({ className, ...props }: ComponentProps<'td'>) {
  return <td className={cn('px-4 py-3.5 align-middle first:pl-5 last:pr-5', className)} {...props} />
}

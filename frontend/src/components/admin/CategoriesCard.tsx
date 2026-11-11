import { useState } from 'react'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { api, errorMessage } from '@/lib/api'
import { fieldErrors } from '@/lib/errors'
import { useLedgerCategories } from '@/lib/ledger'
import { useAdminMutation } from '@/lib/queries'
import type { LedgerCategory, LedgerKind } from '@/lib/types'

const KINDS: { kind: LedgerKind; title: string }[] = [
  { kind: 'EXPENSE', title: 'Expenses' },
  { kind: 'INCOME', title: 'Other income' },
]

/** Settings: the categories offered when entering expenses and other income. */
export function CategoriesCard({ canEdit }: { canEdit: boolean }) {
  const categories = useLedgerCategories()
  const [editing, setEditing] = useState<Partial<LedgerCategory> | null>(null)
  const toggle = useAdminMutation((c: LedgerCategory) =>
    api(`/admin/ledger/categories/${c.id}/`, { method: 'PATCH', body: { is_active: !c.is_active } }),
  )
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div className="space-y-1.5">
          <CardTitle>Expense and income categories</CardTitle>
          <CardDescription>Offered when entering expenses. A category in use can be turned off but not deleted.</CardDescription>
        </div>
        {canEdit && (
          <Button size="sm" variant="outline" onClick={() => setEditing({ kind: 'EXPENSE' })}>
            Add category
          </Button>
        )}
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-2">
        {toggle.error && <Alert variant="destructive" className="md:col-span-2">{errorMessage(toggle.error)}</Alert>}
        {KINDS.map(({ kind, title }) => (
          <div key={kind}>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">{title}</h3>
            <ul className="divide-y rounded-lg border">
              {categories.data
                ?.filter((c) => c.kind === kind)
                .map((c) => (
                  <li key={c.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                    <span className={c.is_active ? undefined : 'text-muted-foreground line-through'}>
                      {c.name}
                      <span className="ml-2 text-xs text-muted-foreground">{c.entry_count} entries</span>
                    </span>
                    <span className="flex items-center gap-1">
                      {!c.is_active && <Badge>off</Badge>}
                      {canEdit && !c.code && (
                        <Button size="sm" variant="ghost" onClick={() => setEditing(c)}>
                          Rename
                        </Button>
                      )}
                      {canEdit && c.code !== 'past-fees' && (
                        <Button size="sm" variant="ghost" disabled={toggle.isPending} onClick={() => toggle.mutate(c)}>
                          {c.is_active ? 'Turn off' : 'Turn on'}
                        </Button>
                      )}
                    </span>
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </CardContent>
      {editing && <CategoryDialog category={editing} onClose={() => setEditing(null)} />}
    </Card>
  )
}

function CategoryDialog({ category, onClose }: { category: Partial<LedgerCategory>; onClose: () => void }) {
  const [name, setName] = useState(category.name ?? '')
  const [kind, setKind] = useState<LedgerKind>(category.kind ?? 'EXPENSE')
  const save = useAdminMutation(() =>
    api(category.id ? `/admin/ledger/categories/${category.id}/` : '/admin/ledger/categories/', {
      method: category.id ? 'PATCH' : 'POST',
      body: category.id ? { name } : { name, kind },
    }),
  )
  const errors = fieldErrors(save.error)
  return (
    <Dialog open onClose={onClose} title={category.id ? 'Rename category' : 'Add a category'}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && !Object.keys(errors).length && <Alert variant="destructive">{errorMessage(save.error)}</Alert>}
        <Field label="Name" id="cat-name" error={errors.name}>
          <Input id="cat-name" required maxLength={60} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        {!category.id && (
          <Field label="Used for" id="cat-kind" error={errors.kind}>
            <Select id="cat-kind" value={kind} onChange={(e) => setKind(e.target.value as LedgerKind)}>
              <option value="EXPENSE">Expenses</option>
              <option value="INCOME">Other income</option>
            </Select>
          </Field>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

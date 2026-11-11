import { Link } from 'react-router'
import { Button } from '@/components/ui/button'

export default function HomePage() {
  return (
    <section className="mx-auto flex max-w-3xl flex-col items-center gap-6 px-4 py-20 text-center sm:py-28">
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
        A quiet place to study, every day
      </h1>
      <p className="max-w-xl text-lg text-muted-foreground">
        Reserved seats, flexible shifts from early morning to late night, and plans from one month
        to a year.
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        <Button asChild size="lg">
          <Link to="/login">Student login</Link>
        </Button>
        <Button asChild size="lg" variant="outline">
          <Link to="/staff/login">Staff login</Link>
        </Button>
      </div>
    </section>
  )
}

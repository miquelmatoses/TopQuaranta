/**
 * AdminDashboardPage — staff landing. Stub until Sprint 2 when we
 * port the Django /staff/dashboard view to React.
 */
export default function AdminDashboardPage() {
  return (
    <section className="py-8">
      <h1 className="text-3xl font-bold text-white mb-4">Staff</h1>
      <div className="bg-white text-tq-ink rounded-lg p-6">
        <p className="text-sm">
          El panell staff en React es porta al Sprint 2. Mentrestant les
          operacions de staff segueixen disponibles a través de la API
          (i seran accessibles aquí un cop acabem la migració).
        </p>
      </div>
    </section>
  )
}

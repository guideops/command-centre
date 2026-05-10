import { Outlet } from '@tanstack/react-router'
import { AppShell } from '../components/layout/AppShell'

export function RootComponent() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  )
}

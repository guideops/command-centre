import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'
import { RootComponent } from './routes/__root'
import { CommandPage } from './routes/index'
import { ActivityPage } from './routes/activity'
import { SkillsPage } from './routes/skills'

const rootRoute = createRootRoute({ component: RootComponent })
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: CommandPage })
const activityRoute = createRoute({ getParentRoute: () => rootRoute, path: '/activity', component: ActivityPage })
const skillsRoute = createRoute({ getParentRoute: () => rootRoute, path: '/skills', component: SkillsPage })

export const routeTree = rootRoute.addChildren([indexRoute, activityRoute, skillsRoute])

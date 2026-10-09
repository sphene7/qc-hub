import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", name: "home" },
  { path: "/admin", name: "admin" },
  { path: "/preview", name: "preview" },
  {
    path: "/project/:wid",
    redirect: (to) => ({
      name: "project-view",
      params: { wid: to.params.wid, tab: "dashboard" },
    }),
  },
  {
    path: "/project/:wid/settings",
    name: "project-settings",
    props: true,
  },
  {
    path: "/project/:wid/:tab/:layout",
    name: "project-layout",
    props: true,
  },
  {
    path: "/project/:wid/:tab",
    name: "project-view",
    props: true,
  },
  {
    path: "/m/:key",
    name: "module",
    props: true,
  },
  {
    path: "/monitor",
    name: "monitor",
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/",
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;

/** Build a project URL segment (layout only applies to dashboard tab). */
export function projectPath(wid, tab = "dashboard", layout = "workbench") {
  if (tab === "settings") return `/project/${wid}/settings`;
  if (tab === "dashboard" && layout) {
    return `/project/${wid}/dashboard/${layout}`;
  }
  return `/project/${wid}/${tab}`;
}

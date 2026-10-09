/** Resolve a configured product module to an accessible project. */

export function resolveModuleProject(mod, projectList) {
  if (!mod) return null;

  const byId = projectList.find((p) => p.id === mod.project_id);
  if (byId) {
    return { project: byId, matchType: "id" };
  }

  const label = (mod.label || "").trim();
  const desc = (mod.description || "").trim();
  const byName = projectList.find((p) => {
    const name = (p.name || "").trim();
    if (!name) return false;
    if (label && (name.includes(label) || label.includes(name))) return true;
    if (desc && (name.includes(desc) || desc.includes(name))) return true;
    return false;
  });
  if (byName) {
    return { project: byName, matchType: "name" };
  }

  return null;
}

export function findModuleByKey(modules, key) {
  return (modules || []).find((m) => m.key === key) || null;
}

# Scene Config: KB & Skill Select

2026-05-09

Replace free-text Input fields for adding knowledge bases and skills in SceneDetail with shadcn `<Select>` dropdowns, allowing users to pick from existing items.

## Motivation

Currently, adding a KB or skill to a scene requires manual text entry. Users must know the exact name/ID. Replace with a dropdown that lists available items.

## Design

### Data Sources

| Field | API | Key | Display |
|-------|-----|-----|---------|
| Knowledge bases | `knowledgeApi.list()` | `kbs[].id` | `id` |
| Skills | `skillsApi.list()` | combined `public[] + private[]` | `title` (fallback `name`) |

### Filtering

Items already in the scene (`mounted_kbs` / `env_skills`) are excluded from the dropdown.

### Interaction

1. Page load: fetch KB and skill lists via React Query
2. Select shows placeholder "Add KB..." / "Add skill..."
3. On select (`onValueChange`): append to scene, call update API, reset select
4. Existing display unchanged (KB list items, skill Badges)

### Scope

- File: `web-ui/src/pages/SceneDetail.tsx` only
- Uses existing `@/components/ui/select` and existing API functions

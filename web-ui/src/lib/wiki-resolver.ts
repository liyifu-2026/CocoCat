export interface WikiPageInfo {
  name: string
  title: string
  path: string
}

export function resolveWikiPage(
  slug: string,
  pages: WikiPageInfo[],
): WikiPageInfo | undefined {
  const slugLower = slug.toLowerCase()
  return pages.find(
    p =>
      p.name.toLowerCase() === slugLower ||
      p.title.toLowerCase() === slugLower,
  )
}

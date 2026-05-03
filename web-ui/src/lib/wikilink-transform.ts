export function transformWikilinks(body: string): string {
  if (!body.includes("[[")) return body
  const parts = body.split(/(```[\s\S]*?```)/g)
  return parts
    .map((part, idx) => (idx % 2 === 1 ? part : transformOutsideCode(part)))
    .join("")
}

const WIKILINK_RE = /\[\[([^\]|\n]+)(?:\|([^\]\n]*))?\]\]/g

function transformOutsideCode(text: string): string {
  if (!text.includes("[[")) return text
  const parts = text.split(/(`[^`\n]+`)/g)
  return parts
    .map((part, idx) => (idx % 2 === 1 ? part : replaceWikilinks(part)))
    .join("")
}

function replaceWikilinks(text: string): string {
  return text.replace(WIKILINK_RE, (_match, rawTarget: string, rawAlias?: string) => {
    const target = rawTarget.trim()
    const alias = rawAlias?.trim() ?? ""
    const label = alias.length > 0 ? alias : target
    const href = `#${encodeURIComponent(target)}`
    const escapedLabel = label.replace(/\[/g, "\\[").replace(/\]/g, "\\]")
    return `[${escapedLabel}](${href})`
  })
}

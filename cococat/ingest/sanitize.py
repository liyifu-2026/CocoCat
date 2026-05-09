"""KB sanitizer — fixes common LLM output corruption in wiki pages."""

import re

_FRONTMATTER_WRAPPER = re.compile(
    r"^```(?:yaml|yml)?\s*\n(---\s*\n.*?\n---)\s*\n```", re.DOTALL
)
_FRONTMATTER_PREFIX = re.compile(r"^frontmatter:\s*\n", re.MULTILINE)
_WIKILINK_LIST = re.compile(r"\[\[([^\]]+)\]\]")


def sanitize_frontmatter(content: str) -> str:
    """Fix common LLM output issues in wiki page frontmatter.

    1. Strip code-fence wrapping (```yaml ... --  ... ```)
    2. Fix `frontmatter:` key prefix
    3. Convert [[a]], [[b]] wikilink lists to [a, b] for YAML compatibility
    """
    # 1. Strip code fence wrapper
    m = _FRONTMATTER_WRAPPER.match(content)
    if m:
        fm = m.group(1)
        body = content[m.end():]
        content = fm + "\n" + body

    # 2. Fix frontmatter: prefix
    if content.startswith("frontmatter:"):
        content = content[len("frontmatter:"):]
        if content.startswith("\n"):
            content = content[1:]
        if not content.startswith("---"):
            content = "---\n" + content.strip()

    # 3. Fix wikilink lists in YAML (related: [[a]], [[b]] → related: [a, b])
    def _fix_related(line: str) -> str:
        if not line.strip().startswith("related:"):
            return line
        items = re.findall(r'\[\[([^\]]+)\]\]', line)
        if items:
            prefix = line.split(":")[0] + ":"
            return f"{prefix} [{', '.join(items)}]"
        return line

    lines = content.split("\n")
    lines = [_fix_related(l) for l in lines]
    content = "\n".join(lines)

    return content

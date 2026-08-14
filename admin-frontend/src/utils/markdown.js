export function splitCanonicalMarkdown(canonicalMarkdown) {
  const match = canonicalMarkdown.match(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n){1,2}/);
  return match
    ? { frontmatter: match[0], body: canonicalMarkdown.slice(match[0].length) }
    : { frontmatter: "", body: canonicalMarkdown };
}

export function replaceMarkdownBody(canonicalMarkdown, body) {
  const { frontmatter } = splitCanonicalMarkdown(canonicalMarkdown);
  return `${frontmatter}${body}`;
}

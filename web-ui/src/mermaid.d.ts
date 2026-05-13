declare module "mermaid" {
  interface MermaidConfig {
    startOnLoad?: boolean
    theme?: string
    [key: string]: unknown
  }
  interface MermaidAPI {
    run: (opts: { nodes: HTMLElement[] }) => Promise<void>
    initialize: (config: MermaidConfig) => void
  }
  const mermaid: MermaidAPI & { default?: MermaidAPI }
  export default mermaid
}

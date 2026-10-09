import React, { useMemo } from 'react'
import { parseMarkdown } from '../../chat/markdown'

// Agent replies with light Markdown (**bold**, *italic*, `code`, bullet / numbered lines).
// The pure parser lives in src/chat/markdown.js (unit-tested there).
// Built from React elements only — never dangerouslySetInnerHTML — so any HTML in the
// text is shown as text.
function renderInline(nodes) {
  return nodes.map((node, i) => {
    switch (node.type) {
      case 'strong':
        return <strong key={i}>{renderInline(node.children)}</strong>
      case 'em':
        return <em key={i}>{renderInline(node.children)}</em>
      case 'code':
        return <code key={i} className="md-code">{node.value}</code>
      case 'br':
        return <br key={i} />
      default:
        return <React.Fragment key={i}>{node.value}</React.Fragment>
    }
  })
}

export default function MarkdownText({ text, className = '' }) {
  const blocks = useMemo(() => parseMarkdown(text), [text])

  return (
    <div className={`md-text ${className}`.trim()}>
      {blocks.map((block, i) => {
        if (block.type === 'list') {
          const ListTag = block.ordered ? 'ol' : 'ul'
          return (
            <ListTag key={i} className="md-list" start={block.ordered && block.start !== 1 ? block.start : undefined}>
              {block.items.map((item, j) => <li key={j}>{renderInline(item)}</li>)}
            </ListTag>
          )
        }
        return <p key={i} className="md-p">{renderInline(block.children)}</p>
      })}
    </div>
  )
}

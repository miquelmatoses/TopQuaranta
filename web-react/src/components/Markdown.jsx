import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/** Renders user-supplied markdown. react-markdown never emits raw HTML,
 *  so this is XSS-safe without extra sanitization. */
export default function Markdown({ children, className = '' }) {
  return (
    <div
      className={
        'leading-relaxed ' +
        '[&_h1]:text-2xl [&_h1]:font-display [&_h1]:font-bold [&_h1]:mt-4 [&_h1]:mb-2 ' +
        '[&_h2]:text-xl [&_h2]:font-display [&_h2]:font-bold [&_h2]:mt-4 [&_h2]:mb-2 ' +
        '[&_h3]:text-lg [&_h3]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1 ' +
        '[&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:mb-3 ' +
        '[&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:mb-3 ' +
        '[&_li]:mb-1 ' +
        '[&_code]:bg-black/10 [&_code]:px-1 [&_code]:rounded [&_code]:text-[0.9em] ' +
        '[&_pre]:bg-black/10 [&_pre]:p-3 [&_pre]:rounded [&_pre]:overflow-x-auto [&_pre]:mb-3 ' +
        '[&_pre_code]:bg-transparent [&_pre_code]:p-0 ' +
        '[&_blockquote]:border-l-4 [&_blockquote]:border-tq-yellow [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:opacity-80 [&_blockquote]:my-3 ' +
        '[&_strong]:font-bold [&_em]:italic ' +
        '[&_hr]:my-4 [&_hr]:border-black/20 ' +
        '[&_table]:border-collapse [&_table]:my-3 ' +
        '[&_th]:border [&_th]:border-black/20 [&_th]:px-2 [&_th]:py-1 [&_th]:bg-black/5 ' +
        '[&_td]:border [&_td]:border-black/20 [&_td]:px-2 [&_td]:py-1 ' +
        className
      }
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer" className="underline" />
          ),
        }}
      >
        {children || ''}
      </ReactMarkdown>
    </div>
  )
}

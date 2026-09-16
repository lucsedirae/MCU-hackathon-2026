import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Render model output as text/React elements, never executable HTML. Images stay
// as labels so a response cannot initiate unsolicited remote image requests.
const components = {
  a: ({ href, children }) => href
    ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
    : <span>{children}</span>,
  img: ({ alt }) => <span>{alt || '[Image]'}</span>,
  table: ({ children }) => <div className="agent-table" tabIndex={0} role="region" aria-label="Response table"><table>{children}</table></div>,
};

export default function AgentMessage({ children }) {
  return <div className="agent-markdown"><Markdown remarkPlugins={[remarkGfm]} components={components}>{children}</Markdown></div>;
}

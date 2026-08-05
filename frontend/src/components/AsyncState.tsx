export function LoadingState({ label = 'Loading data…' }: { label?: string }) {
  return <p className="state-message" role="status">{label}</p>;
}

export function ErrorState({ message }: { message: string }) {
  return <p className="state-message state-error" role="alert">{message}</p>;
}

export function EmptyState({ message }: { message: string }) {
  return <p className="state-message">{message}</p>;
}
